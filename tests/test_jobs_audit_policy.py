from __future__ import annotations

import asyncio
import json
import unittest

from core.errors import ARTIFACT_FORBIDDEN, GatewayError
from core.policy import CallerIdentity
from tests.helpers import fresh_gateway


class JobsAuditPolicyTests(unittest.TestCase):
    def test_job_status_visibility_and_terminal_state(self) -> None:
        services, _, dispatcher = fresh_gateway()
        job = services.jobs.create(
            request_id="req_test",
            caller_id="role_default",
            tool_name="test_tool",
            input_summary={"text": {"length": 4, "prefix": "test"}},
        )
        services.jobs.mark_running(job.id)
        running = asyncio.run(
            dispatcher.dispatch(
                "job_status",
                {"job_id": job.id},
                authorization="Bearer test-role-token",
            )
        )
        services.jobs.mark_succeeded(job.id, {"done": True}, [])
        terminal = asyncio.run(
            dispatcher.dispatch(
                "job_status",
                {"job_id": job.id},
                authorization="Bearer test-role-token",
            )
        )
        visible = services.jobs.get(job.id, CallerIdentity("role_default", "role_play"))
        self.assertEqual(visible.status, "succeeded")
        self.assertFalse(running["polling"]["terminal"])
        self.assertEqual(running["polling"]["next_poll_after_seconds"], 2)
        self.assertTrue(terminal["polling"]["terminal"])
        with self.assertRaises(GatewayError) as denied:
            services.jobs.get(job.id, CallerIdentity("other", "role_play"))
        self.assertEqual(denied.exception.code, ARTIFACT_FORBIDDEN)

    def test_audit_summarizes_and_redacts_inputs(self) -> None:
        services, _, _ = fresh_gateway()
        audit_id = services.audit.start(
            request_id="req_test",
            job_id=None,
            caller_id="role_default",
            tool_name="image_generate",
            risk_level="medium",
            arguments={"prompt": "x" * 250, "api_key": "secret-value"},
        )
        services.audit.finish(audit_id=audit_id, policy_decision="allow", status="succeeded")
        row = services.audit.conn.execute("SELECT input_summary_json FROM audit_events WHERE id = ?", (audit_id,)).fetchone()
        summary = json.loads(row["input_summary_json"])
        self.assertEqual(summary["api_key"], "[redacted]")
        self.assertEqual(summary["prompt"]["length"], 250)
        self.assertEqual(len(summary["prompt"]["prefix"]), 200)

    def test_anonymous_policy_only_allows_health_check(self) -> None:
        services, _, _ = fresh_gateway()
        caller = services.policy.resolve_caller(None)
        self.assertTrue(services.policy.evaluate(caller=caller, tool_name="health_check", risk_level="low", arguments={}).allowed)
        self.assertFalse(services.policy.evaluate(caller=caller, tool_name="artifact_get", risk_level="low", arguments={}).allowed)


if __name__ == "__main__":
    unittest.main()
