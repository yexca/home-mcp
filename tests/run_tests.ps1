$ErrorActionPreference = "Stop"
$env:CONFIG_PATH = "tests/config/test.config.yaml"
$env:IMAGE_MODULE_ENABLED = ""
$env:LOCAL_IMAGE_MODULE_ENABLED = ""
$env:TTS_MODULE_ENABLED = ""
$env:MATRIX_MODULE_ENABLED = ""
$env:PRINTER_MODULE_ENABLED = ""
python -m unittest discover -s tests
