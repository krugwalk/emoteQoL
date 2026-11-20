import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.request

VERSION = "1.14.1"
REPO = "krugwalk/emoteQoL"
ASSET_NAME = "EmoteQoL.exe"

def api_url():
    return os.environ.get("EMOTEQOL_UPDATE_API") or "https://api.github.com/repos/%s/releases/latest" % REPO

def parse(tag):
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums[:4]) if nums else ()

def newer(latest, current=VERSION):
    a, b = parse(latest), parse(current)
    return bool(a) and a > b

def _release_info(data, current):
    tag = data.get("tag_name", "")
    if not newer(tag, current):
        return None
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    return dict(
        tag=tag,
        url=data.get("html_url") or "https://github.com/%s/releases/latest" % REPO,
        asset_url=asset.get("browser_download_url") if asset else None,
        size=asset.get("size") if asset else None,
        digest=asset.get("digest") if asset else None,
    )

def _fetch(timeout):
    req = urllib.request.Request(api_url(), headers={"User-Agent": "EmoteQoL-update-check", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def check(current=VERSION, timeout=6):
    try:
        return _release_info(_fetch(timeout), current)
    except Exception:
        return None

def check_status(current=VERSION, timeout=10):
    try:
        data = _fetch(timeout)
    except Exception:
        return "error", None
    info = _release_info(data, current)
    return ("update", info) if info else ("current", None)

def check_async(callback, current=VERSION):
    def run():
        callback(check(current))
    threading.Thread(target=run, daemon=True).start()

def download(url, dest, size=None, digest=None, progress=None):
    req = urllib.request.Request(url, headers={"User-Agent": "EmoteQoL-update"})
    sha = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or size or 0)
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if size and done != size:
        raise RuntimeError("the download is incomplete (%d of %d bytes)" % (done, size))
    if digest and digest.startswith("sha256:") and sha.hexdigest() != digest.split(":", 1)[1].lower():
        raise RuntimeError("the downloaded file does not match its checksum")
    with open(dest, "rb") as f:
        if f.read(2) != b"MZ":
            raise RuntimeError("the downloaded file is not a Windows program")
    return dest

def apply_and_restart(new_exe, target_exe):
    bat = os.path.join(tempfile.gettempdir(), "emoteqol_apply_update.bat")
    lines = [
        "@echo off",
        "set PYINSTALLER_RESET_ENVIRONMENT=1",
        "set _MEIPASS2=",
        "set n=0",
        ":wait",
        "set /a n+=1",
        "ping -n 2 127.0.0.1 >nul",
        'copy /y "%s" "%s" >nul 2>&1' % (new_exe, target_exe),
        "if errorlevel 1 (",
        "  if %n% lss 40 goto wait",
        ")",
        'start "" "%s"' % target_exe,
        'del "%s" >nul 2>&1' % new_exe,
    ]
    with open(bat, "w") as f:
        f.write("\r\n".join(lines) + "\r\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000008, close_fds=True, env=env)
