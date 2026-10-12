from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from app.config import Settings
from app.main import build_services
from core.db import connect_database
from core.errors import GatewayError, RATE_LIMITED
from core.jobs import JobManager
from core.limits import InMemoryRateLimiter
from modules.image.service import prepare_image_generate, _validate_download_url, _ImageRedirectHandler
from tests.helpers import fresh_image_gateway
from tests.test_image_generate import make_context
from transport.admin_routes import _save_management_config, _management_status, _restart_required


class RuntimeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.services, self.registry, self.dispatcher = fresh_image_gateway()
        self.addCleanup(self.services.close)

    def save(self, **fields):
        with self.services.management.lock:
            return _save_management_config(self.services, {"owned_fields": fields})

    def test_save_updates_quota_window_and_schemas_without_restart(self):
        before = self.services.snapshot()
        self.save(IMAGE_JOBS_PER_CALLER_PER_DAY="60", IMAGE_RATE_WINDOW_SECONDS="90", IMAGE_MAX_PROMPT_CHARS="12",
                  IMAGE_ALLOWED_OUTPUT_FORMATS="webp", IMAGE_DEFAULT_OUTPUT_FORMAT="webp", IMAGE_MAX_EDIT_INPUT_IMAGES="2")
        self.assertEqual(self.services.config.limits["image_jobs_per_caller_per_day"], 60)
        self.assertEqual(self.services.config.limits["image_rate_window_seconds"], 90)
        self.assertEqual(before.config.limits["image_jobs_per_caller_per_day"], 20)
        self.assertEqual(before.registry.get("image_generate").input_schema["properties"]["prompt"]["maxLength"], 100)
        props = self.registry.get("image_generate").input_schema["properties"]
        self.assertEqual(props["prompt"]["maxLength"], 12)
        self.assertEqual(props["output_format"]["enum"], ["webp"])
        self.assertEqual(props["output_format"]["default"], "webp")
        self.assertEqual(self.registry.get("image_edit").input_schema["properties"]["image_artifact_ids"]["maxItems"], 2)
        self.assertFalse(_restart_required(self.services, _management_status(self.services)))
        with patch.object(self.services.limits, "check") as check:
            prepared = prepare_image_generate({"prompt": "hello"}, make_context(self.services))
            self.assertEqual(prepared.output_format, "webp")
            self.assertEqual(check.call_args.kwargs, {"limit": 60, "window_seconds": 90})
        failed = asyncio.run(self.dispatcher.dispatch("image_generate", {"prompt": "x" * 13}, authorization="Bearer test-host-token"))
        self.assertEqual(failed["error"]["code"], "INVALID_ARGUMENT")
        restarted, _, _ = build_services(Settings(self.services.management.load()))
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.config.limits["image_jobs_per_caller_per_day"], 60)

    def test_policy_artifact_and_audit_controls_apply_immediately(self):
        old = self.services.snapshot()
        self.save(POLICY_UNAUTHENTICATED_CALLER="host_assistant", ARTIFACT_MAX_BYTES="8", AUDIT_PROMPT_SUMMARY_CHARS="3",
                  CALLER_HOST_ASSISTANT_TOKEN="new-test-host-token")
        self.assertEqual(self.services.policy.resolve_caller(None).caller_id, "host_assistant")
        self.assertEqual(self.services.policy.resolve_caller("Bearer new-test-host-token").caller_id, "host_assistant")
        self.assertEqual(self.services.policy.resolve_caller("Bearer test-host-token").caller_id, "anonymous")
        self.assertEqual(old.policy.resolve_caller(None).caller_id, "anonymous")
        self.assertEqual(old.artifacts.settings.artifacts["max_artifact_bytes"], 1048576)
        with self.assertRaises(GatewayError):
            self.services.artifacts.create_from_bytes(kind="image", mime_type="image/png", extension="png", data=b"123456789",
                owner=self.services.policy.resolve_caller(None), source_tool="test")
        self.assertEqual(self.services.audit.settings.audit["prompt_summary_chars"], 3)
        response, _ = self.save(CALLER_HOST_ASSISTANT_TOKEN="", ARTIFACT_SIGNED_URL_SECRET="")
        self.assertEqual(self.services.config.callers["host_assistant"]["token"], "new-test-host-token")
        self.assertNotIn("new-test-host-token", json.dumps(response))

    def test_invalid_configuration_leaves_database_and_runtime_unchanged(self):
        baseline = deepcopy(self.services.management.load())
        settings = self.services.config
        for fields in (
            {"IMAGE_JOBS_PER_CALLER_PER_DAY": "-1"}, {"IMAGE_RATE_WINDOW_SECONDS": "nan"},
            {"MAX_IMAGE_JOBS_GLOBAL": "1.5"}, {"IMAGE_TOTAL_TIMEOUT_SECONDS": "inf"},
            {"TTS_MIN_SPEED": "2"}, {"LOCAL_IMAGE_QUALITY_PRESETS": "[]"},
            {"LOCAL_IMAGE_STYLE_PRESETS": '{"anime": {"inputs": [1]}}'},
            {"LOCAL_IMAGE_COMFYUI_NODE_MAPPINGS": '{"sampler": {}}'},
            {"IMAGE_MAX_EDIT_TOTAL_IMAGE_BYTES": "1"}, {"POLICY_UNAUTHENTICATED_CALLER": "unknown"},
            {"IMAGE_ALLOWED_OUTPUT_FORMATS": "bad"},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.save(**fields)
            self.assertEqual(self.services.management.load(), baseline)
            self.assertIs(self.services.config, settings)

    def test_module_switch_still_reports_restart_with_immediate_limits(self):
        self.save(IMAGE_MODULE_ENABLED="false", IMAGE_JOBS_PER_CALLER_PER_DAY="61")
        self.assertTrue(self.services.config.modules["image"]["enabled"])
        self.assertEqual(self.services.config.limits["image_jobs_per_caller_per_day"], 61)
        self.assertTrue(_restart_required(self.services, _management_status(self.services)))
        self.assertIn("image_generate", {tool["name"] for tool in self.registry.list_tools()})

    def test_schema_changes_notify_connected_clients(self):
        notifications = []
        self.services.on_tools_changed = lambda: notifications.append("changed")
        self.save(IMAGE_JOBS_PER_CALLER_PER_DAY="60")
        self.assertEqual(notifications, [])
        self.save(IMAGE_MAX_PROMPT_CHARS="50")
        self.assertEqual(notifications, ["changed"])

    def test_concurrency_admission_is_atomic_across_connections_and_releases_terminal_jobs(self):
        limits = {"max_image_jobs_global": 1, "max_image_jobs_per_caller": 1}
        conns = [connect_database(self.services.config.database["path"]) for _ in range(2)]
        for conn in conns:
            self.addCleanup(conn.close)
        managers = [JobManager(conn) for conn in conns]
        def attempt(index):
            try:
                return managers[index].create(request_id=f"req-{index}", caller_id=f"caller-{index}",
                    tool_name=("image_generate", "local_image_generate")[index], input_summary={}, limits=limits)
            except GatewayError as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        jobs = [result for result in results if not isinstance(result, GatewayError)]
        errors = [result for result in results if isinstance(result, GatewayError)]
        self.assertEqual(len(jobs), 1)
        self.assertEqual([exc.code for exc in errors], [RATE_LIMITED])
        self.services.jobs.mark_failed(jobs[0].id, "TEST", "finished")
        self.services.jobs.create(request_id="new", caller_id="c", tool_name="image_edit", input_summary={}, limits=limits)
        self.save(MAX_IMAGE_JOBS_GLOBAL="0", MAX_IMAGE_JOBS_PER_CALLER="0")
        self.services.jobs.create(request_id="unlimited", caller_id="c", tool_name="image_generate", input_summary={}, limits=self.services.config.limits)


class RateWindowTests(unittest.TestCase):
    def test_limit_updates_retain_count_and_window_changes_apply_immediately(self):
        limiter = InMemoryRateLimiter()
        with patch("core.limits.monotonic", return_value=100):
            limiter.check("image", limit=1, window_seconds=86400)
            with self.assertRaises(GatewayError):
                limiter.check("image", limit=1, window_seconds=86400)
            limiter.check("image", limit=2, window_seconds=86400)
        with patch("core.limits.monotonic", return_value=111):
            limiter.check("image", limit=1, window_seconds=10)
            limiter.check("image", limit=0, window_seconds=10)

    def test_cdn_whitelist_and_redirect_checks(self):
        config = {"openai_compatible": {"base_url": "https://api.example.test", "allowed_image_url_hosts": ["cdn.example.test"]}}
        _validate_download_url("https://cdn.example.test/image.png", config)
        _validate_download_url("https://api.example.test/image.png", config)
        for url in ("https://evil.example/image.png", "http://cdn.example.test/image.png"):
            with self.subTest(url=url), self.assertRaises(GatewayError):
                _validate_download_url(url, config)
        with self.assertRaises(GatewayError):
            _ImageRedirectHandler(config).redirect_request(None, None, 302, "Found", {}, "https://evil.example/image.png")

    def test_unrestricted_download_hosts_still_validate_scheme_and_host(self):
        config = {"openai_compatible": {"allowed_image_url_hosts": ["*"]}}
        _validate_download_url("https://any-cdn.example/image.png", config)
        from urllib.request import Request
        redirected = _ImageRedirectHandler(config).redirect_request(
            Request("https://first.example/image.png"), None, 302, "Found", {}, "https://second.example/image.png")
        self.assertEqual(redirected.full_url, "https://second.example/image.png")
        for url in ("http://any-cdn.example/image.png", "file:///image.png", "https:///image.png"):
            with self.subTest(url=url), self.assertRaises(GatewayError):
                _validate_download_url(url, config)
        config["allow_http_image_urls"] = True
        _validate_download_url("http://any-cdn.example/image.png", config)
