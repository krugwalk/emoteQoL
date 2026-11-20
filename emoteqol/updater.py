import json, re, threading, urllib.request

VERSION = "1.12.0"
REPO = "krugwalk/emoteQoL"
API = "https://api.github.com/repos/%s/releases/latest" % REPO

def parse(tag):
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums[:4]) if nums else ()

def newer(latest, current=VERSION):
    a, b = parse(latest), parse(current)
    return bool(a) and a > b

def check(current=VERSION, timeout=6):
    try:
        req = urllib.request.Request(API, headers={"User-Agent": "EmoteQoL-update-check", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        if newer(tag, current):
            url = data.get("html_url") or "https://github.com/%s/releases/latest" % REPO
            return tag, url
    except Exception:
        return None
    return None

def check_async(callback, current=VERSION):
    def run():
        callback(check(current))
    threading.Thread(target=run, daemon=True).start()
