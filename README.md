# EmoteQoL

Change League of Legends emotes, loading screens and HUD portraits with your own pictures, GIFs, videos and sounds. It saves a `.fantome` file that you import into a skin changer like [LTK Manager](https://github.com/LeagueToolkit/ltk-manager/releases/latest) (download it from its releases page) and turn on like any other mod.

Not affiliated with Riot Games. Personal use only.

## Download

Get `EmoteQoL.exe` from the [latest release](https://github.com/krugwalk/emoteQoL/releases/latest), run it and click Install. It finds your League folder and lets you pick where to install it.

Windows might warn about an unknown app because the exe isn't signed. Click "More info", then "Run anyway".

## What it does

- Swap any emote for a picture, a GIF or a video
- Make an emote bigger or smaller in game with the size slider
- Remove the stock flash and green glow around the picture and make it solid, with a brightness slider, so it isn't washed out
- Change just the sound of an emote
- Change the loading screen and HUD portrait of any champion and skin
- Open a `.fantome` you already have, look at the pictures, GIFs and sounds inside it, edit them and save, the rest of the file stays as it is

Everything you add shows up in the list at the bottom. Press Save to make the `.fantome`.

## Custom sounds

To use your own sound file the app needs [LtMAO](https://github.com/tarngaina/LtMAO). Download it and unzip it anywhere, you don't have to run it. EmoteQoL finds it by itself, or you can point to it with the "Find LtMAO" button.

Without LtMAO you can still copy the sound of another emote.

## Run it from source

```
pip install -r requirements.txt
python -m emoteqol
```

Needs Python 3.14 or newer. To build the exe, run `build.bat`.

## Credits

LtMAO by tarngaina for the sound conversion. PyAV, Pillow, NumPy and xxhash for the rest.

MIT license.
