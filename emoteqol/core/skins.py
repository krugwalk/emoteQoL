import os, glob, struct, threading
from PIL import Image, ImageDraw
import numpy as np
from emoteqol.formats import wad as wadtool; from emoteqol.core import emotes as C

LOAD_SIZE = (308, 560); CIRCLE_SIZE = 128
NAMES = {"MonkeyKing": "Wukong", "FiddleSticks": "Fiddlesticks", "Chogath": "Cho'Gath", "Khazix": "Kha'Zix", "Kogmaw": "Kog'Maw", "Reksai": "Rek'Sai", "Velkoz": "Vel'Koz",
         "Kaisa": "Kai'Sa", "Belveth": "Bel'Veth", "KSante": "K'Sante", "Leblanc": "LeBlanc", "JarvanIV": "Jarvan IV", "Nunu": "Nunu & Willump", "TwistedFate": "Twisted Fate",
         "MasterYi": "Master Yi", "MissFortune": "Miss Fortune", "DrMundo": "Dr. Mundo", "AurelionSol": "Aurelion Sol", "LeeSin": "Lee Sin", "XinZhao": "Xin Zhao", "TahmKench": "Tahm Kench", "RenataGlasc": "Renata Glasc"}

def champions(final):
    out = []
    for p in sorted(glob.glob(os.path.join(final, "Champions", "*.wad.client"))):
        n = os.path.basename(p)[:-len(".wad.client")]
        if "." in n: continue
        out.append((NAMES.get(n, n), n))
    return sorted(out, key=lambda x: x[0].lower())

_wads = {}; _lock = threading.Lock()
def open_wad(final, champ):
    with _lock:
        k = (final, champ)
        if k not in _wads: _wads[k] = wadtool.Wad(os.path.join(final, "Champions", champ + ".wad.client"))
        return _wads[k]

def read(wad, path):
    with _lock: return wad.read(path)

def art_paths(c, n):
    c = c.lower()
    load = ["assets/characters/%s/skins/base/%sloadscreen.tex" % (c, c)] if n == 0 else ["assets/characters/%s/skins/skin%02d/%sloadscreen_%d.tex" % (c, n, c, n), "assets/characters/%s/skins/skin%d/%sloadscreen_%d.tex" % (c, n, c, n)]
    circle = ["assets/characters/%s/hud/%s_circle_%d.tex" % (c, c, n)] + (["assets/characters/%s/hud/%s_circle.tex" % (c, c)] if n == 0 else [])
    square = ["assets/characters/%s/hud/%s_square_%d.tex" % (c, c, n)] + (["assets/characters/%s/hud/%s_square.tex" % (c, c)] if n == 0 else [])
    return load, circle, square

def skins(final, champ, max_n=200):
    W = open_wad(final, champ); out = []
    for n in range(max_n):
        l, ci, sq = art_paths(champ, n); f = lambda ps: next((p for p in ps if wadtool.h(p) in W.entries), None)
        d = dict(n=n, load=f(l), circle=f(ci), square=f(sq))
        if d["load"] or d["circle"] or d["square"]: out.append(d)
    return out

def tex_info(d):
    w, h, _, fmt, _, mips = struct.unpack("<HHBBBB", d[4:12]); return w, h, fmt, mips

def place_rect(img, w, h, rect, bg=(0, 0, 0, 0)):
    x0, y0, x1, y1 = rect; nw, nh = max(1, round((x1 - x0) * w)), max(1, round((y1 - y0) * h)); out = Image.new("RGBA", (w, h), bg)
    out.paste(C._resize_rgba(img.convert("RGBA"), nw, nh), (round(x0 * w), round(y0 * h))); return out

def default_rect(iw, ih, fw, fh, mode="cover"):
    k = (max if mode == "cover" else min)(fw / iw, fh / ih); rw, rh = iw * k / fw, ih * k / fh
    return ((1 - rw) / 2, (1 - rh) / 2, (1 + rw) / 2, (1 + rh) / 2)

def to_tex(img, w, h, fmt):
    return C.encode_tex(img.resize((w, h), Image.LANCZOS) if img.size != (w, h) else img, "DXT1" if fmt == 10 else "DXT5", mips=False)

def circle_mask(img):
    S = 4; n = img.width; m = Image.new("L", (n * S, n * S), 0); ImageDraw.Draw(m).ellipse((0, 0, n * S - 1, n * S - 1), fill=255)
    out = img.convert("RGBA"); out.putalpha(m.resize((n, n), Image.LANCZOS)); return out

def build(final, champ, skin, load_img=None, load_rect=None, hud_img=None, hud_rect=None):
    W = open_wad(final, champ); info = next((s for s in skins(final, champ, skin + 1) if s["n"] == skin), None) or dict(n=skin, load=None, circle=None, square=None)
    lpaths, cpaths, spaths = art_paths(champ, skin); files = {}; notes = []; root = "WAD/%s.wad.client/" % champ
    if load_img is not None:
        path = info["load"] or lpaths[0]; w, h, fmt = LOAD_SIZE[0], LOAD_SIZE[1], 10
        if info["load"]: w, h, fmt, _ = tex_info(read(W, path))
        files[root + path] = to_tex(place_rect(load_img, w, h, load_rect, (0, 0, 0, 255)).convert("RGB"), w, h, fmt if fmt in (10, 12) else 10); notes.append("loading screen")
    if hud_img is not None:
        cpath = info["circle"] or cpaths[0]; w = h = CIRCLE_SIZE; fmt = 12
        if info["circle"]: w, h, fmt, _ = tex_info(read(W, cpath))
        sq = place_rect(hud_img, w, h, hud_rect, (0, 0, 0, 255)); circ = circle_mask(sq)
        files[root + cpath] = to_tex(circ, w, h, 12); notes.append("HUD / minimap portrait")
        if info["square"]:
            spath = info["square"]; sw, sh, sfmt, _ = tex_info(read(W, spath)); s = place_rect(hud_img, sw, sh, hud_rect, (0, 0, 0, 255)).convert("RGB")
            ImageDraw.Draw(s).rectangle((0, 0, sw - 1, sh - 1), outline=(8, 8, 8), width=max(1, sw // 32)); files[root + spath] = to_tex(s, sw, sh, sfmt if sfmt in (10, 12) else 10); notes.append("square portrait")
    return files, notes
