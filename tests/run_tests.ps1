$ErrorActionPreference = "Stop"
$env:CONFIG_PATH = "tests/config/test.config.yaml"
$env:GATEWAY_TOKEN_HOST = "test-host-token"
$env:GATEWAY_TOKEN_ROLE_DEFAULT = "test-role-token"
$env:ARTIFACT_SIGNING_SECRET = "test-artifact-signing-secret"
python -m unittest discover -s tests
