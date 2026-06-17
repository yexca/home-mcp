@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\apply_agent.ps1" %*
