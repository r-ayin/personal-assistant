@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m personal_assistant.cli perception %*
