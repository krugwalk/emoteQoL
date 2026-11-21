import hashlib
import json
import os
import shutil
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = "tarngaina/LtMAO"
BRANCH = "hai"
BIN = "res/wiwawe/WwiseApp/Authoring/x64/Release/bin/"
DATA = "res/wiwawe/WwiseApp/Authoring/Data/"
PROJ = "res/wiwawe/WwiseLeagueProjects/"
VGM = "res/tools/vgmstream/"
BIN_SKIP = {n.lower() for n in (
    "AudioFilesManagementUI.dll", "Ionic.Zip.dll", "Plugin_Common_PropertyCurve.dll", "SignalMgr.dll", "SoundBanksManagementUI.dll", "ffi-7.dll", "glib-2.0-0.dll", "gobject-2.0-0.dll",
    "iconv.dll", "intl.dll", "intl3_tsvn.dll", "libapr_tsvn.dll", "libaprutil_tsvn.dll", "libcrypto-3-x64.dll", "libsasl.dll", "libssl-3-x64.dll", "libsvn_tsvn.dll")}
VGM_SKIP = {"swresample-vgmstream-4.dll"}
SCHEMA_FILES = {"ExternalSources.xsd", "ObjectDataSchema.123.xsd"}
SCHEMA_DIRS = {"WAAPI", "Definitions"}

def wanted(path):
    if path == "LICENSE" or path.startswith(PROJ):
        return True
    if path.startswith(VGM):
        return path[len(VGM):].lower() not in VGM_SKIP
    if path.startswith(BIN):
        return path[len(BIN):].lower() not in BIN_SKIP
    if path.startswith(DATA):
        rest = path[len(DATA):]
        if rest.startswith("WObjects/"):
            return True
        if rest.startswith("Schemas/"):
            sub = rest[len("Schemas/"):]
            return sub.split("/")[0] in SCHEMA_DIRS if "/" in sub else sub in SCHEMA_FILES
    return False

def _read(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "EmoteQoL"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def listing():
    data = json.loads(_read("https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (REPO, BRANCH)).decode("utf-8"))
    if data.get("truncated"):
        raise RuntimeError("GitHub returned an incomplete file list")
    items = [(e["path"], int(e["size"]), e["sha"]) for e in data["tree"] if e["type"] == "blob" and wanted(e["path"])]
    if not any(p.endswith("WwiseConsole.exe") for p, s, h in items) or not any(p.endswith("vgmstream-cli.exe") for p, s, h in items):
        raise RuntimeError("the LtMAO files were not found where expected")
    return items

def is_complete(folder):
    return bool(folder) and os.path.exists(os.path.join(folder, *(BIN + "WwiseConsole.exe").split("/"))) and os.path.isdir(os.path.join(folder, *PROJ.strip("/").split("/")))

def download(dest, progress=None):
    if os.path.exists(os.path.join(dest, "start.bat")):
        raise RuntimeError("%s is a full LtMAO install and was left alone" % dest)
    items = listing()
    total = sum(s for p, s, h in items)
    part = dest.rstrip("\\/") + ".part"
    shutil.rmtree(part, ignore_errors=True)
    lock = threading.Lock()
    done = [0]
    failed = []

    def fetch(item):
        path, size, sha = item
        url = "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, BRANCH, urllib.request.quote(path))
        last = None
        for attempt in range(4):
            if failed:
                return
            try:
                data = _read(url)
                if len(data) != size or hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() != sha:
                    raise RuntimeError("%s did not download correctly" % path)
                target = os.path.join(part, *path.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as f:
                    f.write(data)
                with lock:
                    done[0] += len(data)
                    if progress:
                        progress(done[0], total)
                return
            except Exception as e:
                last = e
        failed.append(last)

    try:
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(fetch, items))
        if failed:
            raise failed[0]
        if not is_complete(part):
            raise RuntimeError("the download is missing files")
        shutil.rmtree(dest, ignore_errors=True)
        os.replace(part, dest)
    finally:
        shutil.rmtree(part, ignore_errors=True)
    return dest
