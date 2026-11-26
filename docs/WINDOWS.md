# Windows

## Supported way to run
1. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
2. Unzip the project, open the folder, double-click `Start_NPCGA.bat`.
3. The first launch creates `.venv`, installs the packages and opens http://localhost:8501.
   Keep the black window open while you work; close it to stop the app.

## Command line
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,gis,web]"
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m npcga.cli_folder --folder "path\to\csv_folder" --name my_area
```

## Standalone installer
Not provided yet. A packaged installer (PyInstaller + Inno Setup) must be built and tested on a
clean Windows machine before it is announced; until then `Start_NPCGA.bat` is the supported way.

## Troubleshooting
- "py is not recognized": Python is missing or not on PATH; reinstall and tick "Add to PATH".
- PowerShell says scripts are disabled: use `Start_NPCGA.bat` or call `.venv\Scripts\python.exe`
  directly (no activation needed).
- `pip` fails building a package: use Python 3.12 (very new Python versions may lack ready-made
  wheels for some libraries).
