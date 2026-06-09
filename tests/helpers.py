from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.config import load_settings
from app.main import build_services


def fresh_gateway():
    os.environ["CONFIG_PATH"] = "env/test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_image_gateway():
    os.environ["CONFIG_PATH"] = "env/image.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["IMAGE_API_BASE_URL"] = "http://127.0.0.1:1"
    os.environ["IMAGE_API_MODEL"] = "test-image-model"
    os.environ["IMAGE_API_KEY"] = "test-image-api-key"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-image-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_phase4_gateway():
    os.environ["CONFIG_PATH"] = "env/phase4.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["MATRIX_ACCESS_TOKEN"] = "test-matrix-token"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-phase4-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)


def fresh_phase5_gateway():
    os.environ["CONFIG_PATH"] = "env/phase5.test.config.yaml"
    os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
    os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
    os.environ["PRINTER_BRIDGE_API_KEY"] = "test-printer-token"
    settings = load_settings()
    Path("tmp").mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="gateway-phase5-test-", dir="tmp"))
    settings.raw["artifacts"]["root"] = str(root)
    settings.raw["database"]["path"] = str(root / "metadata.sqlite3")
    return build_services(settings)
