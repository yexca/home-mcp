@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\apply_webUI_config.ps1" %*
