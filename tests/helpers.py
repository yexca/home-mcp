from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.config import load_settings
from app.main import build_services


def _isolate_module_switch_env() -> None:
    for env_name in (
        "IMAGE_MODULE_ENABLED",
        "LOCAL_IMAGE_MODULE_ENABLED",
        "TTS_MODULE_ENABLED",
        "MATRIX_MODULE_ENABLED",
        "PRINTER_MODULE_ENABLED",
    ):
        os.environ[env_name] = ""


def fresh_gateway():
    _isolate_module_switch_env()
    os.environ["CONFIG_PATH"] = "tests/config/test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["ARTIFACT_SIGNING_SECRET"] = "test-artifact-signing-secret"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_image_gateway():
    _isolate_module_switch_env()
    os.environ["CONFIG_PATH"] = "tests/config/image.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["ARTIFACT_SIGNING_SECRET"] = "test-artifact-signing-secret"
    os.environ["IMAGE_API_BASE_URL"] = "http://127.0.0.1:1"
    os.environ["IMAGE_API_MODEL"] = "test-image-model"
    os.environ["IMAGE_API_KEY"] = "test-image-api-key"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-image-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_localimage_gateway():
    _isolate_module_switch_env()
    os.environ["CONFIG_PATH"] = "tests/config/localimage.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["ARTIFACT_SIGNING_SECRET"] = "test-artifact-signing-secret"
    os.environ["LOCAL_IMAGE_COMFYUI_BASE_URL"] = "http://127.0.0.1:1"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-localimage-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_phase4_gateway():
    _isolate_module_switch_env()
    os.environ["CONFIG_PATH"] = "tests/config/phase4.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["ARTIFACT_SIGNING_SECRET"] = "test-artifact-signing-secret"
    os.environ["MATRIX_ACCESS_TOKEN"] = "test-matrix-token"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-phase4-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_phase5_gateway():
    _isolate_module_switch_env()
    os.environ["CONFIG_PATH"] = "tests/config/phase5.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["ARTIFACT_SIGNING_SECRET"] = "test-artifact-signing-secret"
    os.environ["PRINTER_BRIDGE_API_KEY"] = "test-printer-token"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-phase5-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)
