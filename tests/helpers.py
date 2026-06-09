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
