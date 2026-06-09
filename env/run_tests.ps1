$ErrorActionPreference = "Stop"
$env:CONFIG_PATH = "env/test.config.yaml"
$env:GATEWAY_TOKEN_HOST = "test-host-token"
$env:GATEWAY_TOKEN_ROLE_DEFAULT = "test-role-token"
python -m unittest discover -s tests
