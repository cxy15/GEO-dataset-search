@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo 错误：未找到 "%VENV_PY%"，请先创建 .venv 并 pip install -r requirements.txt
  exit /b 1
)
echo 请将研究意图作为参数传入，可选参数见：
"%VENV_PY%" -m geo_reporter --help
echo.
set /p INTENT=研究意图: 
if "!INTENT!"=="" (
  echo 错误：研究意图不能为空。
  exit /b 1
)
set /p RETMAX=retmax [默认40]: 
if "!RETMAX!"=="" set RETMAX=40
set /p OUT=输出报告 [默认 geo_report.txt]: 
if "!OUT!"=="" set OUT=geo_report.txt
"%VENV_PY%" -u -m geo_reporter "!INTENT!" -n !RETMAX! -o "!OUT!"
exit /b %ERRORLEVEL%
