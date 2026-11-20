# EmoteQoL

A Windows app that lets you change League of Legends emotes, loading screens and HUD portraits with your own pictures, GIFs, videos and sounds, and packs everything into a `.fantome` mod you can import into LTK Manager (or any other cslol-based mod manager).

You can start from nothing, or open a `.fantome` you already have and change just the parts you want. Everything else in that file is kept.

> Personal use only. This project is not affiliated with or endorsed by Riot Games. League of Legends is a trademark of Riot Games, Inc.

## Download

1. Go to the [Releases page](https://github.com/krugwalk/emoteQoL/releases/latest).
2. Download `EmoteQoL.exe`. You do not need Python.
3. Run it. The first time, it installs itself: it finds your League of Legends folder (or asks you to pick it), lets you choose where to install the app (the default is a folder in your user profile), and can add a desktop shortcut.

If Windows SmartScreen warns about an unknown app, choose "More info" then "Run anyway". The exe is not code-signed.

The app checks GitHub when it starts and shows a banner if a newer version is available. Download the new `EmoteQoL.exe`, close the app, run the new file once and click Install.

## What it does

### Emotes tab

- Search all emotes, with their icons, and pick the one you want to change.
- Replace the emote with a picture, a GIF or a video (mp4, webm, mov, mkv, avi).
- Move and stretch the picture by dragging it on the preview. Drag the edges to stretch one side, drag a corner to resize while keeping proportions (hold Shift to stretch freely), and use the mouse wheel to zoom. The bright square is what goes in the emote.
- GIFs and videos play as an animation in game. A speed setting (100% is the clip's own speed) controls how much of the clip fits in the popup.
- Change only the sound of an emote, without changing its picture.
- Silence the generic "pop" sound that every emote plays (on by default, you can turn it off).
- Stack extra layers of the picture ("Solidity") if the popup looks see-through in game.

### Sounds

- Use any sound file (mp3, wav, ogg, mp4 and more), or use the sound of a video you picked as the emote.
- Choose how long the sound is with the length slider, and set the in-game volume in dB.
- Or reuse the sound of any other emote in the game.
- Your own sounds are converted to the game's audio format with the Wwise converter that ships with [LtMAO](https://github.com/tarngaina/LtMAO). Download LtMAO and unzip it anywhere (you do not need to run it). The app finds it on its own, or you can point it at the folder with the "Find LtMAO..." button. Without LtMAO you can still use another emote's sound or a ready-made `.wem` file.

### Loading screen / HUD tab

- Pick any champion and skin. The list shows the current loading screen of each skin.
- Replace the loading screen and the round HUD / minimap portrait (and the square portrait where the skin has one) with your own pictures, using the same drag-to-stretch editor.
- Works on a `.fantome` you already have: open it first, and the tab shows the art that fantome already contains. Add your picture and save, and only that art is replaced.

### Packs

- Everything you add shows up in the pack list at the bottom.
- Save writes a `.fantome`. Open loads an existing one so you can edit it.
- Set the name, author and license of the pack before saving.

## Requirements

- Windows 10 or 11
- League of Legends installed
- For your own sounds: LtMAO (see above)

## Project layout

```
emoteqol/
  __main__.py        entry point (python -m emoteqol)
  installer.py       first-run install, League detection, desktop shortcut
  updater.py         checks GitHub for a newer release
  assets/            app icon
  ui/
    app.py           main window and the Emotes tab
    skin_tab.py      Loading screen / HUD tab
  core/
    emotes.py        emote catalogue, textures, flipbooks, .fantome import and export
    audio.py         sound conversion, bank and audio package editing
    skins.py         loading screen and HUD portrait textures
  formats/
    wad.py           .wad.client reader
    bank.py          Wwise sound bank reader
    wpk.py           audio package reader
    binparse.py      particle / data file reader
```

## Run from source

```
pip install -r requirements.txt
python -m emoteqol
```

Python 3.14 or newer is required, because textures are decompressed with the standard library's `compression.zstd`.

## Build the exe

```
build.bat
```

The exe is written to `dist\EmoteQoL.exe`.

## How it works, briefly

- Game files are read from the `.wad.client` archives in `Game\DATA\FINAL`. Nothing in your game folder is modified; the output is a separate `.fantome` file.
- Emote pictures replace the emote's textures. Animations are turned into a flipbook sprite sheet, and the emote's particle file is patched so the animation plays straight through the popup.
- Sounds replace the audio inside the emote sound package, and the bank's volume setting is edited when you change the game volume.
- Loading screens and HUD portraits replace the champion's own texture files.

## Credits

- [LtMAO](https://github.com/tarngaina/LtMAO) by tarngaina: the Wwise-based sound conversion method.
- [PyAV](https://github.com/PyAV-Org/PyAV) (FFmpeg) for reading videos and audio.
- [Pillow](https://python-pillow.org/), [NumPy](https://numpy.org/), [xxhash](https://github.com/ifduyue/python-xxhash).

## License

MIT. See `LICENSE`.
