@echo off
cd /d "%~dp0"
if exist ".venv312\Scripts\activate.bat" (
    call ".venv312\Scripts\activate.bat"
) else (
    if exist ".venv\Scripts\activate.bat" (
        call ".venv\Scripts\activate.bat"
    )
)
python yotudrive_gui.py
pause
