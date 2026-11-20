@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name EmoteQoL --icon emoteqol\assets\icon.ico --add-data "emoteqol\assets\icon.ico;." --paths . --hidden-import compression.zstd --collect-all av --distpath dist emoteqol\__main__.py
echo.
echo Built: dist\EmoteQoL.exe
