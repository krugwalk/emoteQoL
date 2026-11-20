@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name EmoteQoL --icon emoteqol\assets\icon.ico --add-data "emoteqol\assets\icon.ico;." --add-data "emoteqol\assets\scene.png;." --add-data "emoteqol;source\emoteqol" --add-data "README.md;source" --add-data "LICENSE;source" --add-data "requirements.txt;source" --add-data "build.bat;source" --add-data ".gitignore;source" --paths . --hidden-import compression.zstd --collect-all av --distpath dist emoteqol\__main__.py
echo.
echo Built: dist\EmoteQoL.exe
