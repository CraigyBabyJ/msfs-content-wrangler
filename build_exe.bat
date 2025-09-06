@echo off
setlocal
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm ^
  --onefile ^
  --windowed ^
  --name "MSFS-Content-Wrangler" ^
  --add-data "rules.json;." ^
  --add-data "resources.qss;." ^
  main.py
echo Built to .\dist\MSFS-Content-Wrangler.exe
endlocal
