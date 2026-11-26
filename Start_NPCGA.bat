@echo off
cd /d "%~dp0"
title NASA POWER Climate and GIS Analyzer
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Install Python 3.12 from python.org and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating the Python environment...
  py -3.12 -m venv .venv
  if errorlevel 1 goto error
)
echo Installing or checking required packages...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[web,gis]"
if errorlevel 1 goto error
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  mkdir "%USERPROFILE%\.streamlit" >nul 2>nul
  (echo [general]& echo email = "") > "%USERPROFILE%\.streamlit\credentials.toml"
)
echo Starting NPCGA in your browser...
.venv\Scripts\python.exe -m streamlit run app.py --browser.gatherUsageStats false
pause
exit /b 0
:error
echo.
echo Setup failed. Check your internet connection and Python 3.12 installation.
pause
exit /b 1
