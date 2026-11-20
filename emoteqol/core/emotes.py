import io, os, re, json, struct, zipfile, math, time, threading, sys, string, glob, shutil
import numpy as np
from PIL import Image, ImageSequence
from emoteqol.formats import wad as wadtool; from emoteqol.formats import binparse as BP

DEFAULT_GAME = r"C:\Riot Games\League of Legends\Game\DATA\FINAL"
_BASE = os.environ.get("APPDATA", os.path.expanduser("~")); APPDATA = os.path.join(_BASE, "EmoteQoL"); _OLD = os.path.join(_BASE, "EmoteMaker")
if os.path.isdir(_OLD) and not os.path.exists(APPDATA):
    try: shutil.copytree(_OLD, APPDATA)
    except Exception: pass
os.makedirs(APPDATA, exist_ok=True)
EMOTE_BIN = 0xf8ed8b424917d8f6
FLAGS = dict(birthscale=0xf0eb7084, startframe=0x76f8ad24, delay=0x22e763bc, blend=0xfa784eab, texdiv=0x86a84509, count=0x1e67b0f1, rate=0x9b111ae4, tex=0x3c6468f4, life=0x2a552694, emlist=0x868eb76a, name=0x3d25b8ce)

def decode_tex(d):
    assert d[:4] == b"TEX\0", "not a TEX file"
    w, h, _, fmt, _, mips = struct.unpack("<HHBBBB", d[4:12]); data = d[12:]
    if fmt == 20:
        return Image.frombuffer("RGBA", (w, h), bytes(data[-w * h * 4:]), "raw", "BGRA", 0, 1)
    fourcc = {10: b"DXT1", 12: b"DXT5"}[fmt]; bs = 8 if fmt == 10 else 16; big = data[-(((w + 3) // 4) * ((h + 3) // 4) * bs):]
    hdr = bytearray(128); hdr[0:4] = b"DDS "; struct.pack_into("<7I", hdr, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(big), 0, 0)
    struct.pack_into("<I", hdr, 76, 32); struct.pack_into("<I", hdr, 80, 4); hdr[84:88] = fourcc; struct.pack_into("<I", hdr, 108, 0x1000)
    return Image.open(io.BytesIO(bytes(hdr) + big)).convert("RGBA")

def _bc(img, fmt):
    b = io.BytesIO(); img.save(b, format="DDS", pixel_format=fmt); return b.getvalue()[128:]
def encode_tex(img, fmt="DXT5", mips=True):
    img = img.convert("RGBA"); w, h = img.size; levels = []; cur = img
    if fmt == "BGRA8":
        return b"TEX\0" + struct.pack("<HHBBBB", w, h, 1, 20, 0, 0) + img.tobytes("raw", "BGRA")
    while True:
        lw, lh = cur.size; src = cur if (lw >= 4 and lh >= 4) else cur.resize((max(4, lw), max(4, lh)), Image.BOX); levels.append(_bc(src, fmt))
        if not mips or (lw == 1 and lh == 1): break
        cur = cur.resize((max(1, lw // 2), max(1, lh // 2)), Image.BOX)
    return b"TEX\0" + struct.pack("<HHBBBB", w, h, 1, 12 if fmt == "DXT5" else 10, 0, 1 if mips else 0) + b"".join(reversed(levels))

def _resize_rgba(im, w, h):
    if im.size == (w, h): return im
    a = im.getchannel("A")
    if a.getextrema()[0] == 255: return im.resize((w, h), Image.LANCZOS)
    x = np.asarray(im, dtype=np.float32); al = x[..., 3:4] / 255.0; pm = x.copy(); pm[..., :3] *= al
    big = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA") if False else None
    chans = [Image.fromarray(pm[..., i]).resize((w, h), Image.LANCZOS) for i in range(4)]
    r = np.stack([np.asarray(c, dtype=np.float32) for c in chans], axis=-1); al2 = r[..., 3:4] / 255.0
    r[..., :3] = np.where(al2 > 1e-4, r[..., :3] / np.maximum(al2, 1e-4), 0.0)
    return Image.fromarray(np.clip(r + 0.5, 0, 255).astype(np.uint8), "RGBA")

def preset_rect(w, h, mode):
    if mode == "stretch": return (0.0, 0.0, 1.0, 1.0)
    k = (min if mode == "contain" else max)(1.0 / w, 1.0 / h); rw, rh = w * k, h * k
    return ((1 - rw) / 2, (1 - rh) / 2, (1 + rw) / 2, (1 + rh) / 2)

def fit_frame(frame, size, mode, adj=(100, 0, 0)):
    frame = frame.convert("RGBA")
    if len(adj) == 4:
        x0, y0, x1, y1 = adj; px0, py0 = round(x0 * size), round(y0 * size); nw, nh = max(1, round((x1 - x0) * size)), max(1, round((y1 - y0) * size))
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0)); out.paste(_resize_rgba(frame, nw, nh), (px0, py0)); return out
    scale, dx, dy = adj; w, h = frame.size
    if mode == "stretch": sx, sy = size / w, size / h
    else: sx = sy = (min if mode == "contain" else max)(size / w, size / h)
    k = max(1, scale) / 100.0; nw, nh = max(1, round(w * sx * k)), max(1, round(h * sy * k)); r = frame.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0)); out.paste(r, (round((size - nw) / 2 + dx / 100.0 * size), round((size - nh) / 2 + dy / 100.0 * size))); return out

VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v")
def is_video(path): return os.path.splitext(path)[1].lower() in VIDEO_EXT

def load_video_frames(path, fps=24.0, max_seconds=8.0, max_side=384):
    import av
    c = av.open(path); vs = c.streams.video[0]; frames = []; step = 1.0 / fps; nxt = 0.0
    try:
        for fr in c.decode(vs):
            t = float(fr.pts * vs.time_base) if fr.pts is not None else nxt
            if t > max_seconds: break
            if t + 1e-6 >= nxt:
                im = fr.to_image().convert("RGBA"); im.thumbnail((max_side, max_side), Image.LANCZOS); frames.append(im); nxt = max(nxt + step, t + step * 0.5)
    finally: c.close()
    if not frames: raise RuntimeError("could not read any video frames from that file")
    return frames, [step] * len(frames)

def load_frames(path):
    if is_video(path): return load_video_frames(path)
    im = Image.open(path); frames = []; durs = []
    for fr in ImageSequence.Iterator(im): frames.append(fr.convert("RGBA").copy()); durs.append(max(0.01, fr.info.get("duration", 40) / 1000.0))
    if not frames: frames = [im.convert("RGBA")]; durs = [0.04]
    return frames, durs

class Game:
    def __init__(self, final_dir):
        self.dir = final_dir; self.wad = wadtool.Wad(os.path.join(final_dir, "Global.wad.client")); self.lock = threading.Lock()
    def read(self, path):
        with self.lock: d = self.wad.read(path)
        return d if isinstance(d, (bytes, bytearray)) else None
    def has(self, path): return wadtool.h(path) in self.wad.entries

def pretty(name):
    name = re.sub(r"^\d+_", "", name); name = re.sub(r"(?i)^(em|emote)_", "", name); return re.sub(r"\s+", " ", name.replace("_", " ")).strip()

def build_catalogue(game, progress=None):
    cache = os.path.join(APPDATA, "catalogue.json")
    if os.path.exists(cache):
        try: return json.load(open(cache, encoding="utf-8"))
        except Exception: pass
    d = game.read(EMOTE_BIN); assert d, "emote data not found in Global.wad.client"
    paths = sorted(set(m.group().decode("latin1") for m in re.finditer(rb"ASSETS/Loadouts/SummonerEmotes/[ -~]*?_Inventory\.tex", d, re.I)))
    cat = []
    for i, p in enumerate(paths):
        base = p[:-len("_Inventory.tex")]; p_ = p.lower()
        if not game.has(p_): continue
        parts = base.split("/"); cat.append(dict(key=base, name=pretty(parts[-1]), group="/".join(parts[3:-1]) or "(general)", inv=p, sel=base + "_Selector.tex", vfx=base + "_VFX.tex", glow=base + "_Glow.tex"))
        if progress and i % 200 == 0: progress(i / len(paths))
    json.dump(cat, open(cache, "w", encoding="utf-8")); return cat

def emote_bins(game, progress=None):
    cache = os.path.join(APPDATA, "emote_bins.json")
    if os.path.exists(cache):
        try: return [int(x) for x in json.load(open(cache))]
        except Exception: pass
    out = []; items = list(game.wad.entries.items())
    for n, (ph, (off, csz, usz, typ)) in enumerate(items):
        if progress and n % 500 == 0: progress(n / len(items))
        if usz > 8_000_000 or usz < 64: continue
        try: d = game.read(ph)
        except Exception: continue
        if isinstance(d, (bytes, bytearray)) and d[:4] == b"PROP" and b"summoneremotes" in d.lower() and b"_vfx.tex" in d.lower(): out.append(ph)
    json.dump([str(x) for x in out], open(cache, "w")); return out

def _fields(d, vs):
    r = BP.R(bytes(d), vs + 8); c = r.u16(); out = {}
    for _ in range(c): fh = r.u32(); ft = r.u8(); out[fh] = (ft, r.p); BP.value(r, ft)
    return out
def _spans(d, entry):
    BP.RANGES.clear(); ents = BP.parse(bytes(d)); start, end = BP.RANGES[entry]; r = BP.R(bytes(d), start); ln_off = r.p; r.u32(); r.u32(); fc = r.u16(); lst = None
    for _ in range(fc):
        fh = r.u32(); ft = r.u8()
        if fh == FLAGS["emlist"]:
            r.u8(); size_off = r.p; r.u32(); r.u32(); items = []
            cnt = struct.unpack_from("<I", d, size_off + 4)[0]; items = []
            for _i in range(cnt):
                nh = r.u32(); sz_off = r.p; sz = r.u32(); ct_off = r.p; c = r.u16()
                for _f in range(c): a = r.u32(); b = r.u8(); BP.value(r, b)
                items.append(dict(start=sz_off - 4, size_off=sz_off, count_off=ct_off, end=sz_off + 4 + sz)); r.p = sz_off + 4 + sz
            lst = dict(size_off=size_off, items=items)
        else: BP.value(r, ft)
    return ln_off, lst

def patch_flipbook(binbytes, vfx_path, cols, rows, fps):
    d = bytearray(binbytes); BP.RANGES.clear(); ents = BP.parse(bytes(d)); n_ch = 0; notes = []; target = vfx_path.lower()
    for entry in sorted(ents, key=lambda e: -BP.RANGES[e][0]):
        if ents[entry][0] != 0x45cd899f: continue
        BP.RANGES.clear(); BP.parse(bytes(d)); ln_off, lst = _spans(d, entry)
        if not lst: continue
        total = 0
        for it in reversed(lst["items"]):
            F = _fields(d, it["start"])
            if FLAGS["tex"] not in F or FLAGS["life"] not in F: continue
            ft, vs = F[FLAGS["tex"]]; n = struct.unpack_from("<H", d, vs)[0]; tp = bytes(d[vs + 2:vs + 2 + n]).decode("latin1").lower()
            if tp != target: continue
            if FLAGS["texdiv"] in F or FLAGS["count"] in F: notes.append("an emitter already used a flipbook and was left as it is"); continue
            ft2, vs2 = _fields(d, F[FLAGS["life"]][1])[0xb4b427aa]; life = struct.unpack_from("<f", d, vs2)[0]
            if not (0.05 < life < 30): notes.append("an emitter has an animated lifetime and was left as it is"); continue
            cnt = cols * rows; rate = float(fps)
            delay = struct.unpack_from("<f", d, F[FLAGS["delay"]][1])[0] if FLAGS["delay"] in F else 0.0
            add = (struct.pack("<IB", FLAGS["texdiv"], 11) + struct.pack("<2f", float(cols), float(rows)) + struct.pack("<IB", FLAGS["count"], 5) + struct.pack("<H", cnt)
                   + struct.pack("<IB", FLAGS["rate"], 10) + struct.pack("<f", rate)); nf = 3
            start = int(round(delay * rate)) % cnt
            if start: add += struct.pack("<IB", FLAGS["startframe"], 5) + struct.pack("<H", start); nf = 4
            d[it["end"]:it["end"]] = add
            struct.pack_into("<I", d, it["size_off"], struct.unpack_from("<I", d, it["size_off"])[0] + len(add)); struct.pack_into("<H", d, it["count_off"], struct.unpack_from("<H", d, it["count_off"])[0] + nf); total += len(add); n_ch += 1
        if total:
            struct.pack_into("<I", d, lst["size_off"], struct.unpack_from("<I", d, lst["size_off"])[0] + total); struct.pack_into("<I", d, ln_off, struct.unpack_from("<I", d, ln_off)[0] + total)
    BP.RANGES.clear(); BP.parse(bytes(d))
    return bytes(d), n_ch, sorted(set(notes))

def scale_popup(binbytes, vfx_path, factor):
    d = bytearray(binbytes); BP.RANGES.clear(); ents = BP.parse(bytes(d)); changed = 0; target = vfx_path.lower()
    for entry in ents:
        if ents[entry][0] != 0x45cd899f: continue
        BP.RANGES.clear(); BP.parse(bytes(d)); ln_off, lst = _spans(d, entry)
        if not lst: continue
        uses = False
        for it in lst["items"]:
            F = _fields(d, it["start"])
            if FLAGS["tex"] in F:
                ft, vs = F[FLAGS["tex"]]; n = struct.unpack_from("<H", d, vs)[0]
                if bytes(d[vs + 2:vs + 2 + n]).decode("latin1").lower() == target: uses = True
        if not uses: continue
        for it in lst["items"]:
            F = _fields(d, it["start"])
            if FLAGS["birthscale"] not in F: continue
            try: ft, vs = _fields(d, F[FLAGS["birthscale"]][1])[0xb4b427aa]
            except KeyError: continue
            if ft != 12: continue
            x, y, z = struct.unpack_from("<3f", d, vs); struct.pack_into("<3f", d, vs, x * factor, y * factor, z * factor); changed += 1
    BP.RANGES.clear(); BP.parse(bytes(d))
    return bytes(d), changed

def build_size_only(game, em, size):
    files = {}; notes = []; hits = 0
    for bh in emote_bins(game):
        d = game.read(bh)
        if d and em["vfx"].lower().encode() in d.lower():
            nb, n = scale_popup(d, em["vfx"], max(1.0, float(size)) / 100.0)
            if n: files["%016x.bin" % bh] = nb; hits += n
    notes.append("in-game size %d%%: %d popup layer(s) resized" % (size, hits) if hits else "in-game size: this popup has no size setting that can be changed")
    return files, notes

def flipbook_info(binbytes, vfx_path):
    d = bytearray(binbytes); BP.RANGES.clear(); ents = BP.parse(bytes(d)); target = vfx_path.lower()
    for entry in ents:
        if ents[entry][0] != 0x45cd899f: continue
        BP.RANGES.clear(); BP.parse(bytes(d)); ln_off, lst = _spans(d, entry)
        if not lst: continue
        for it in lst["items"]:
            F = _fields(d, it["start"])
            if FLAGS["tex"] not in F or FLAGS["texdiv"] not in F or FLAGS["count"] not in F: continue
            ft, vs = F[FLAGS["tex"]]; n = struct.unpack_from("<H", d, vs)[0]
            if bytes(d[vs + 2:vs + 2 + n]).decode("latin1").lower() != target: continue
            div = BP.value(BP.R(bytes(d), F[FLAGS["texdiv"]][1]), F[FLAGS["texdiv"]][0]); count = BP.value(BP.R(bytes(d), F[FLAGS["count"]][1]), F[FLAGS["count"]][0])
            fps = BP.value(BP.R(bytes(d), F[FLAGS["rate"]][1]), F[FLAGS["rate"]][0]) if FLAGS["rate"] in F else None
            cols, rows = int(round(div[0])), int(round(div[1]))
            if cols >= 1 and rows >= 1 and count >= 1: return cols, rows, int(count), (float(fps) if fps else None)
    return None

def extract_frames(em, files, other):
    key = em["vfx"].lower()
    tex = files.get(key)
    if tex is None:
        tex = next((v for k, v in files.items() if k.lower().endswith(".tex") and ("vfx" in k.lower() or "vf2" in k.lower())), None)
    if tex is None: return None
    sheet = decode_tex(tex); info = None
    sources = list(files.items()) + [(n, d) for n, d in other.items()]
    for name, data in sources:
        if name.lower().endswith(".bin") and isinstance(data, (bytes, bytearray)) and key.encode() in bytes(data).lower():
            try: info = flipbook_info(data, em["vfx"])
            except Exception: info = None
            if info: break
    if not info: return [sheet], [0.1], None
    cols, rows, count, fps = info; cw, ch = sheet.width // cols, sheet.height // rows
    frames = [sheet.crop(((i % cols) * cw, (i // cols) * ch, (i % cols) * cw + cw, (i // cols) * ch + ch)) for i in range(min(count, cols * rows))]
    step = 1.0 / fps if fps else 1.0 / 12.0
    return frames, [step] * len(frames), fps

def popup_length(binbytes, vfx_path):
    d = bytearray(binbytes); BP.RANGES.clear(); ents = BP.parse(bytes(d)); best = 0.0; target = vfx_path.lower()
    for entry in ents:
        if ents[entry][0] != 0x45cd899f: continue
        BP.RANGES.clear(); BP.parse(bytes(d)); ln_off, lst = _spans(d, entry)
        if not lst: continue
        for it in lst["items"]:
            F = _fields(d, it["start"])
            if FLAGS["tex"] not in F or FLAGS["life"] not in F: continue
            ft, vs = F[FLAGS["tex"]]; n = struct.unpack_from("<H", d, vs)[0]
            if bytes(d[vs + 2:vs + 2 + n]).decode("latin1").lower() != target: continue
            try: life = struct.unpack_from("<f", d, _fields(d, F[FLAGS["life"]][1])[0xb4b427aa][1])[0]
            except Exception: continue
            delay = struct.unpack_from("<f", d, F[FLAGS["delay"]][1])[0] if FLAGS["delay"] in F else 0.0
            if 0.05 < life < 30: best = max(best, delay + life)
    return best

def boost_opacity(binbytes, vfx_path, copies=1):
    d = bytearray(binbytes); BP.RANGES.clear(); ents = BP.parse(bytes(d)); n_dup = 0; target = vfx_path.lower()
    for entry in sorted(ents, key=lambda e: -BP.RANGES[e][0]):
        if ents[entry][0] != 0x45cd899f: continue
        BP.RANGES.clear(); BP.parse(bytes(d)); ln_off, lst = _spans(d, entry)
        if not lst: continue
        total = 0; added = 0
        for it in reversed(lst["items"]):
            F = _fields(d, it["start"])
            if FLAGS["tex"] not in F: continue
            ft, vs = F[FLAGS["tex"]]; n = struct.unpack_from("<H", d, vs)[0]
            if bytes(d[vs + 2:vs + 2 + n]).decode("latin1").lower() != target: continue
            if FLAGS["blend"] in F and BP.value(BP.R(bytes(d), F[FLAGS["blend"]][1]), F[FLAGS["blend"]][0]) != 1: continue
            blob = bytes(d[it["start"]:it["end"]]); d[it["end"]:it["end"]] = blob * copies; total += len(blob) * copies; added += copies; n_dup += 1
        if total:
            struct.pack_into("<I", d, lst["size_off"], struct.unpack_from("<I", d, lst["size_off"])[0] + total)
            struct.pack_into("<I", d, lst["size_off"] + 4, struct.unpack_from("<I", d, lst["size_off"] + 4)[0] + added)
            struct.pack_into("<I", d, ln_off, struct.unpack_from("<I", d, ln_off)[0] + total)
    BP.RANGES.clear(); BP.parse(bytes(d))
    return bytes(d), n_dup

def make_sheet(frames, durs, cell=None, fit="contain", max_frames=64, adj=(100, 0, 0), max_width=2048, t_end=None):
    ends = np.cumsum(durs); tot = float(ends[-1])
    if t_end: tot = min(tot, float(t_end)); frames = frames[:int(np.searchsorted(ends, tot, side="left")) + 1]
    n = 1
    while n < min(len(frames), max_frames): n *= 2
    n = min(n, max_frames) if len(frames) > 1 else 1
    cols = {1: 1, 2: 2, 4: 2, 8: 4, 16: 4, 32: 8, 64: 8}[n]; rows = n // cols
    if not cell: cell = max(64, min(512, max_width // cols))
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (0, 0, 0, 0))
    for k in range(n):
        t = (k + 0.5) / n * tot; i = min(int(np.searchsorted(ends, t, side="right")), len(frames) - 1)
        sheet.paste(fit_frame(frames[i], cell, fit, adj), ((k % cols) * cell, (k // cols) * cell))
    return sheet, cols, rows

def build_replacement(game, em, image_path, animated=True, fit="contain", speed=100.0, progress=None, adj=(100, 0, 0), opacity=0, quality="compact", popup_size=100, preloaded=None):
    notes = []; frames, durs = preloaded if preloaded else load_frames(image_path); files = {}; best = quality == "best"; fmt = "BGRA8" if best else "DXT5"
    still = frames[0] if len(frames) == 1 else frames[len(frames) // 2]
    files[em["inv"].lower()] = encode_tex(fit_frame(still, 256, fit, adj), "DXT5", mips=False)
    if game.has(em["sel"].lower()): files[em["sel"].lower()] = encode_tex(fit_frame(still, 128, fit, adj), "DXT5", mips=False)
    if not game.has(em["vfx"].lower()): notes.append("this emote has no in-game popup texture; only its icons were replaced"); return files, notes
    hits = []
    if (animated and len(frames) > 1) or opacity or popup_size != 100:
        for bh in emote_bins(game, progress):
            d = game.read(bh)
            if d and em["vfx"].lower().encode() in d.lower(): hits.append((bh, d))
    bins = {}
    if animated and len(frames) > 1:
        if not hits: notes.append("couldn't find this emote's popup effect, so the popup shows a still image"); animated = False
        else:
            T = max((popup_length(d, em["vfx"]) for bh, d in hits), default=0.0) or 2.3
            sp = max(1.0, float(speed)) / 100.0; window = min(float(sum(durs)), T * sp)
            sheet, cols, rows = make_sheet(frames, durs, None, fit, 64, adj, 1024 if best else 2048, window); changed = 0
            fps = cols * rows / max(0.05, window) * sp
            for bh, d in hits:
                nb, n, nn = patch_flipbook(d, em["vfx"], cols, rows, fps); notes += nn
                if n: bins[bh] = nb; changed += n
            if changed: files[em["vfx"].lower()] = encode_tex(sheet, fmt, mips=not best); notes.append("animated: %d frames of %d px covering the first %.1f s of the clip, %d popup emitter(s)" % (cols * rows, sheet.width // cols, window, changed))
            else: notes.append("popup effect has no usable emitter, so the popup shows a still image"); animated = False
    if not animated or len(frames) == 1:
        if em["vfx"].lower() not in files:
            size = 256 if best else 512
            files[em["vfx"].lower()] = encode_tex(fit_frame(still, size, fit, adj), fmt, mips=not best)
    if opacity:
        done = 0
        for bh, d in hits:
            nb, n = boost_opacity(bins.get(bh, d), em["vfx"], int(opacity))
            if n: bins[bh] = nb; done += n
        notes.append("opacity: %d popup layer(s) stacked %dx so the picture is more solid" % (done, int(opacity) + 1) if done else "opacity: no stackable popup layer found")
    if popup_size != 100:
        done = 0
        for bh, d in hits:
            nb, n = scale_popup(bins.get(bh, d), em["vfx"], max(1.0, float(popup_size)) / 100.0)
            if n: bins[bh] = nb; done += n
        notes.append("in-game size %d%%: %d popup layer(s) resized" % (popup_size, done) if done else "in-game size: this popup has no size setting that can be changed")
    for bh, nb in bins.items(): files["%016x.bin" % bh] = nb
    return files, notes

GLOBAL_DIR = "WAD/Global.wad.client/"
class Pack:
    def __init__(self):
        self.info = {"Name": "My Emotes", "Author": "", "License": "", "Version": "1.0.0", "Description": "Emote replacements made with EmoteQoL"}
        self.emotes = {}
        self.sounds = {}
        self.silence_pop = True
        self.art = {}
        self.other = {}
    def add(self, em, files, source, notes=""): self.emotes[em["key"]] = dict(name=em["name"], inv=em["inv"], files=files, source=source, note=notes)
    def remove(self, key): self.emotes.pop(key, None); self.sounds.pop(key, None); self.art.pop(key, None)

def _same_game_file(zip_name, target):
    a = zip_name.replace("\\", "/").split("/"); b = target.split("/")
    if len(a) < 3 or a[0].upper() != "WAD" or a[1].lower() != b[1].lower(): return False
    rest = "/".join(a[2:]).lower(); path = "/".join(b[2:]).lower()
    if rest == path: return True
    stem = rest.split(".")[0]
    if "/" not in rest and len(stem) == 16:
        try: return int(stem, 16) == wadtool.h(path)
        except ValueError: return False
    return False

def import_fantome(path, catalogue):
    p = Pack(); z = zipfile.ZipFile(path); by_inv = {e["inv"].lower(): e for e in catalogue}; by_base = {e["key"].lower(): e for e in catalogue}
    try: p.info.update(json.loads(z.read("META/info.json")))
    except Exception: pass
    meta = {}
    try: meta = json.loads(z.read("META/emotemaker.json"))
    except Exception: pass
    p.silence_pop = bool(meta.get("_options", {}).get("silence_pop", False)); groups = {}; art_meta = meta.get("_art", {})
    for n in z.namelist():
        if n.endswith("/"): continue
        low = n.lower()
        if low.startswith(GLOBAL_DIR.lower()) and "loadouts/summoneremotes/" in low:
            wp = n[len(GLOBAL_DIR):].lower(); base = re.sub(r"_(inventory|selector|vfx|glow)\.tex$", "", wp)
            if base in {k.lower()[len("assets/"):] if False else k.lower() for k in by_base}: groups.setdefault(base, {})[wp] = z.read(n)
            else: p.other[n] = z.read(n)
        elif n == "META/info.json" or n == "META/emotemaker.json": continue
        else: p.other[n] = z.read(n)
    for base, files in groups.items():
        e = by_base[base]; p.emotes[e["key"]] = dict(name=e["name"], inv=e["inv"], files=files, source=meta.get(e["key"], {}).get("source", "(from imported file)"), note=meta.get(e["key"], {}).get("note", ""))
    for key, m in art_meta.items():
        names = [n for n in m.get("files", []) if n in p.other]
        if names: p.art[key] = dict(name=m.get("name", key), files={n: p.other.pop(n) for n in names}, source=m.get("source", ""), note=m.get("note", ""))
    by_key = {e["key"]: e for e in catalogue}
    for key, m in meta.items():
        if key.startswith("_") or key in p.emotes or "sound" not in m or key not in by_key: continue
        e = by_key[key]; p.emotes[key] = dict(name=e["name"], inv=e["inv"], files={}, source=m.get("source", "(sound only)"), note=m.get("note", "sound only (from imported file)"))
    return p

def export_fantome(pack, path, image_bytes=None, game=None):
    extra = {}; pop = bool(pack.silence_pop and (pack.emotes or pack.sounds))
    if pack.sounds or pop:
        from emoteqol.core import audio as A
        if game is None: raise RuntimeError("the game is needed to build custom sounds")
        names = {"wpk": "WAD/Common.wad.client/%016x.wpk" % A.PK_HASH, "bnk": "WAD/Common.wad.client/%016x.bnk" % A.BNK_HASH}
        bw, bb = pack.other.get(names["wpk"]), pack.other.get(names["bnk"])
        wpk_b, bnk_b, notes = A.apply_sounds(game, {s["event"]: (s["wem"], s["pcm"]) for s in pack.sounds.values() if s.get("wem")}, bw, bb, {s["event"]: s["retarget"] for s in pack.sounds.values() if s.get("retarget")}, {s["event"]: s.get("level") for s in pack.sounds.values() if s.get("wem")}, [A.POP_EVENT] if pop else None)
        if bw is not None or pop or any(s.get("wem") for s in pack.sounds.values()): extra[names["wpk"]] = wpk_b
        if bb is not None or bnk_b != A.common_wad(game).read(A.SFX_BNK): extra[names["bnk"]] = bnk_b
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        taken = {GLOBAL_DIR + wp for e in pack.emotes.values() for wp in e["files"]} | set(extra)
        art_files = {n: d for a in pack.art.values() for n, d in a["files"].items()}
        for n, d in pack.other.items():
            if n in taken or any(_same_game_file(n, t) for t in art_files): continue
            z.writestr(n, d)
        for n, d in art_files.items(): z.writestr(n, d)
        for n, d in extra.items(): z.writestr(n, d)
        meta = {}
        for key, e in pack.emotes.items():
            for wp, d in e["files"].items(): z.writestr(GLOBAL_DIR + wp, d)
            meta[key] = dict(source=e["source"], note=e["note"])
            if key in pack.sounds: meta[key]["sound"] = dict(source=pack.sounds[key]["source"], event=pack.sounds[key]["event"])
        meta["_options"] = dict(silence_pop=pop); meta["_art"] = {k: dict(name=a["name"], files=list(a["files"]), source=a.get("source", ""), note=a.get("note", "")) for k, a in pack.art.items()}
        z.writestr("META/info.json", json.dumps(pack.info, indent=2)); z.writestr("META/emotemaker.json", json.dumps(meta, indent=2))
        if image_bytes: z.writestr("META/image.png", image_bytes)

def resolve_final(path):
    if not path: return None
    for sub in ("", "Game", os.path.join("Game", "DATA", "FINAL"), os.path.join("DATA", "FINAL"), "FINAL", os.path.join("League of Legends", "Game", "DATA", "FINAL")):
        p = os.path.normpath(os.path.join(path, sub))
        if os.path.exists(os.path.join(p, "Global.wad.client")): return p
    return None

def detect_league():
    cands = []
    try:
        j = json.load(open(os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Riot Games", "RiotClientInstalls.json")))
        for v in list(j.values()) + [x for x in j.get("associated_client", {})]:
            if isinstance(v, str): cands.append(v)
            elif isinstance(v, dict): cands += [x for x in v.values() if isinstance(x, str)]
    except Exception: pass
    for k in list(cands):
        d = os.path.dirname(k.strip('"'))
        cands += [d, os.path.dirname(d), os.path.join(os.path.dirname(d), "League of Legends")]
    for drv in [x + ":\\" for x in string.ascii_uppercase if os.path.exists(x + ":\\")]:
        for sub in (r"Riot Games\League of Legends", r"Games\Riot Games\League of Legends", r"Program Files\Riot Games\League of Legends", r"Program Files (x86)\Riot Games\League of Legends", "League of Legends"):
            cands.append(os.path.join(drv, sub))
    cands.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(DEFAULT_GAME)))))
    for p in cands:
        r = resolve_final(p)
        if r: return r
    return None
