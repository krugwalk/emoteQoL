import struct, hashlib, json, os, re
from emoteqol.formats import binparse as BP
from emoteqol.core import emotes as C

FLAGS = C.FLAGS
_spans = C._spans
_fields = C._fields

SYSTEM = 0x45cd899f
CONST = 0xb4b427aa
DYN = 0xbc037de7
TIMES = 0x5d68eeb5
VALUES = 0x34474c3b
_F = BP.fnv
H = dict(name=FLAGS["name"], life=FLAGS["life"], delay=FLAGS["delay"], blend=FLAGS["blend"], tex=FLAGS["tex"], birth=FLAGS["birthscale"], texdiv=FLAGS["texdiv"], count=FLAGS["count"],
         scale=_F("scale0"), vel=_F("velocity"), rot=_F("rotation0"), color=_F("color"), pos=_F("emitterposition"), rotflag=_F("isrotationenabled"), uni=_F("isuniformscale"))
MOTION = ("name", "life", "delay", "blend", "scale", "vel", "rot", "color", "pos", "rotflag", "uni")
VFX_PAT = re.compile(rb"assets/loadouts/summoneremotes/[a-z0-9_/\- .]*?_vfx\.tex")
MIN_TEMPLATE = 100
_mem = {}

def _plain(v):
    if isinstance(v, tuple) and len(v) == 3 and v[0] == "obj":
        return tuple((a, _plain(c)) for a, b, c in v[2])
    if isinstance(v, list):
        return tuple(_plain(x) for x in v)
    if isinstance(v, tuple):
        return tuple(round(x, 3) if isinstance(x, float) else _plain(x) for x in v)
    return round(v, 3) if isinstance(v, float) else v

def _curve(v):
    if not isinstance(v, tuple) or len(v) != 3 or v[0] != "obj":
        return None
    const, times, vals = None, None, None
    for fh, ft, val in v[2]:
        if fh == CONST:
            const = val
        elif fh == DYN and isinstance(val, tuple) and len(val) == 3 and val[0] == "obj":
            for f2, t2, v2 in val[2]:
                if f2 == TIMES and isinstance(v2, tuple):
                    times = list(v2[2])
                elif f2 == VALUES and isinstance(v2, tuple):
                    vals = list(v2[2])
    return dict(const=const, times=times, values=vals)

def _emitters(b):
    BP.RANGES.clear()
    ents = BP.parse(b)
    out = []
    for entry in ents:
        if ents[entry][0] != SYSTEM:
            continue
        BP.RANGES.clear()
        BP.parse(b)
        ln_off, lst = _spans(b, entry)
        if not lst:
            continue
        items = []
        for it in lst["items"]:
            F = _fields(b, it["start"])
            tex = None
            if H["tex"] in F:
                ft, vs = F[H["tex"]]
                n = struct.unpack_from("<H", b, vs)[0]
                tex = bytes(b[vs + 2:vs + 2 + n]).decode("latin1").lower()
            items.append((F, it, tex))
        out.append((entry, ln_off, lst, items))
    return out

def _val(b, F, key):
    if H[key] not in F:
        return None
    ft, vs = F[H[key]]
    try:
        return BP.value(BP.R(b, vs), ft)
    except Exception:
        return None

def layers(binbytes, vfx_path):
    b = bytes(binbytes)
    target = vfx_path.lower()
    out = []
    for entry, ln_off, lst, items in _emitters(b):
        if not any(t == target for F, it, t in items):
            continue
        for F, it, tex in items:
            if tex != target:
                continue
            life = _curve(_val(b, F, "life"))
            birth = _curve(_val(b, F, "birth"))
            d = _val(b, F, "delay")
            out.append(dict(
                name=_val(b, F, "name") or "", blend=_val(b, F, "blend"), life=(life or {}).get("const") or 1.0, delay=d if isinstance(d, float) else 0.0,
                birth=(birth or {}).get("const") or (1.0, 1.0, 1.0), uniform=bool(_val(b, F, "uni")), rotation=bool(_val(b, F, "rotflag")), flip="texdiv" if (H["texdiv"] in F or H["count"] in F) else None,
                scale=_curve(_val(b, F, "scale")), vel=_curve(_val(b, F, "vel")), rot=_curve(_val(b, F, "rot")), color=_curve(_val(b, F, "color")), pos=_curve(_val(b, F, "pos"))))
    return out

def signature(binbytes, vfx_path):
    b = bytes(binbytes)
    target = vfx_path.lower()
    rows = []
    for entry, ln_off, lst, items in _emitters(b):
        if not any(t == target for F, it, t in items):
            continue
        for F, it, tex in items:
            if tex != target:
                continue
            row = tuple((k, repr(_plain(_val(b, F, k)))) for k in MOTION)
            rows.append(row)
    if not rows:
        return None
    return hashlib.sha1(repr(tuple(sorted(rows))).encode()).hexdigest()[:12]

def is_flipbook(binbytes, vfx_path):
    return any(l["flip"] for l in layers(binbytes, vfx_path))

def _interp(times, values, a):
    if a <= times[0]:
        return values[0]
    for i in range(1, len(times)):
        if a <= times[i]:
            u = (a - times[i - 1]) / max(1e-9, times[i] - times[i - 1])
            p, q = values[i - 1], values[i]
            if isinstance(p, tuple):
                return tuple(x + (y - x) * u for x, y in zip(p, q))
            return p + (q - p) * u
    return values[-1]

def sample(curve, a, default):
    if not curve:
        return default
    t, v = curve.get("times"), curve.get("values")
    if t and v and len(t) == len(v):
        return _interp(t, v, a)
    return curve["const"] if curve.get("const") is not None else default

def _integral(curve, life, upto, comp):
    if not curve or upto <= 0:
        return 0.0
    steps = 24
    total = 0.0
    prev = sample(curve, 0.0, (0.0, 0.0, 0.0))[comp]
    for i in range(1, steps + 1):
        a = upto * i / steps
        cur = sample(curve, a, (0.0, 0.0, 0.0))[comp]
        total += (prev + cur) / 2.0 * (upto / steps) * life
        prev = cur
    return total

def pose(layer, t):
    life, delay = layer["life"], layer["delay"]
    if t < delay or t >= delay + life:
        return None
    age = (t - delay) / life
    sc = sample(layer["scale"], age, (1.0, 1.0, 1.0))
    bx, by = layer["birth"][0], layer["birth"][1]
    sx = bx * sc[0]
    sy = sx if layer["uniform"] else by * sc[1]
    col = sample(layer["color"], age, (1.0, 1.0, 1.0, 1.0))
    alpha = max(0.0, min(1.0, col[3] if len(col) > 3 else 1.0))
    pos = layer["pos"]["const"] if layer["pos"] and layer["pos"].get("const") else (0.0, 0.0, 0.0)
    dx = pos[0] + _integral(layer["vel"], life, age, 0)
    dy = pos[1] + _integral(layer["vel"], life, age, 1)
    rot = _integral(layer["rot"], life, age, 0) if layer["rotation"] else 0.0
    return dict(sx=sx, sy=sy, dx=dx, dy=-dy, rot=rot, alpha=alpha, name=layer["name"])

def visible_layers(lay):
    return [l for l in lay if l["blend"] != 4 and not l["name"].lower().endswith("glow")]

def reference_size(lay):
    for name in ("introalpha", "intro"):
        for l in lay:
            if l["name"].lower() == name and l["birth"][0] > 0:
                return l["birth"][0]
    for l in lay:
        if l["blend"] != 4 and l["birth"][0] > 0:
            return l["birth"][0]
    return 70.0

def length(lay):
    return max((l["delay"] + l["life"] for l in visible_layers(lay)), default=2.3)

def classify(lay):
    intro = [l for l in visible_layers(lay) if l["delay"] == 0.0] or visible_layers(lay)
    if not intro:
        return "Other"
    main = intro[0]
    vel = max((abs(v[1]) for l in intro if l["vel"] and l["vel"]["values"] for v in l["vel"]["values"]), default=0.0)
    rot = max((abs(v[0]) for l in intro if l["rotation"] and l["rot"] and l["rot"]["values"] for v in l["rot"]["values"]), default=0.0)
    vals = main["scale"]["values"] if main["scale"] and main["scale"]["values"] else None
    first = vals[0][0] if vals else 1.0
    peak = max((max(v[0], v[1]) for v in vals), default=1.0) if vals else 1.0
    steps = len(vals) if vals else 0
    if vel >= 300:
        return "Jump in"
    if rot >= 30:
        return "Squiggle in"
    if first >= 0.9:
        return "Fade in"
    if steps >= 8 and peak >= 1.3:
        return "Squish in"
    if first < 0.3 and peak >= 1.3:
        return "Bounce in"
    if first < 0.3 and peak >= 1.1:
        return "Pop in"
    if first < 0.3:
        return "Grow in"
    return "Other"

def _cache_path():
    return os.path.join(C.APPDATA, "popup_styles.json")

def harvest(game, progress=None):
    if "data" in _mem:
        return _mem["data"]
    path = _cache_path()
    if os.path.exists(path):
        try:
            data = json.load(open(path, encoding="utf-8"))
            if data.get("v") == 1:
                _mem["data"] = data
                return data
        except Exception:
            pass
    bins = C.emote_bins(game)
    sigs = {}
    by_vfx = {}
    for n, bh in enumerate(bins):
        if progress and n % 200 == 0:
            progress(n / max(1, len(bins)))
        d = game.read(bh)
        if not d:
            continue
        b = bytes(d)
        for v in set(m.decode() for m in VFX_PAT.findall(b.lower())):
            try:
                lay = layers(b, v)
                if not lay or any(l["flip"] for l in lay):
                    continue
                s = signature(b, v)
            except Exception:
                continue
            if not s:
                continue
            by_vfx[v] = [s, bh]
            if s not in sigs:
                sigs[s] = dict(sig=s, count=0, label="", samples=[], rep=v, rep_bin=bh, layers=lay)
            c = sigs[s]
            c["count"] += 1
            if len(c["samples"]) < 4:
                c["samples"].append(v)
    ordered = sorted(sigs.values(), key=lambda c: -c["count"])
    used = {}
    clusters = []
    for c in ordered:
        label = classify(c.pop("layers"))
        if c["count"] >= MIN_TEMPLATE:
            used[label] = used.get(label, 0) + 1
            if used[label] > 1:
                label = "%s %d" % (label, used[label])
        c["label"] = label
        clusters.append(c)
    index = {c["sig"]: i for i, c in enumerate(clusters)}
    data = dict(v=1, clusters=clusters, by_vfx={k: [index[s], bh] for k, (s, bh) in by_vfx.items()})
    try:
        json.dump(data, open(path, "w", encoding="utf-8"))
    except Exception:
        pass
    _mem["data"] = data
    return data

def templates(game):
    data = harvest(game)
    return [dict(label=c["label"], count=c["count"], vfx=c["rep"], bin=c["rep_bin"], samples=c["samples"]) for c in data["clusters"] if c["count"] >= MIN_TEMPLATE]

def label_of(game, vfx_path):
    data = harvest(game)
    e = data["by_vfx"].get(vfx_path.lower())
    return data["clusters"][e[0]]["label"] if e else None

def source_for(game, vfx_path):
    data = harvest(game)
    e = data["by_vfx"].get(vfx_path.lower())
    if not e:
        return None
    d = game.read(e[1])
    return (bytes(d), vfx_path) if d else None

def own_layers(game, vfx_path):
    data = harvest(game)
    e = data["by_vfx"].get(vfx_path.lower())
    bh = e[1] if e else None
    if bh is None:
        for h in C.emote_bins(game):
            d = game.read(h)
            if d and vfx_path.lower().encode() in d.lower():
                bh = h
                break
    d = game.read(bh) if bh is not None else None
    return layers(d, vfx_path) if d else []

def detect(game, em, files, other):
    key = em["vfx"].lower().encode()
    mine = None
    for name, data in list(files.items()) + list(other.items()):
        if name.lower().endswith(".bin") and isinstance(data, (bytes, bytearray)) and key in bytes(data).lower():
            try:
                mine = signature(data, em["vfx"])
            except Exception:
                mine = None
            if mine:
                break
    if not mine:
        return None
    d = harvest(game)
    own = d["by_vfx"].get(em["vfx"].lower())
    if own and d["clusters"][own[0]]["sig"] == mine:
        return None
    for c in d["clusters"]:
        if c["sig"] == mine:
            return dict(label=c["label"], vfx=c["rep"])
    return None

def _find(b, vfx_path):
    target = vfx_path.lower()
    for entry, ln_off, lst, items in _emitters(b):
        if any(t == target for F, it, t in items):
            return ln_off, lst, items
    return None

def apply_style(binbytes, vfx_path, src_bytes, src_vfx, extra_map=None):
    d = bytearray(binbytes)
    sb = bytes(src_bytes)
    own_lay = layers(bytes(d), vfx_path)
    t = _find(bytes(d), vfx_path)
    s = _find(sb, src_vfx)
    if not t or not s:
        return bytes(binbytes), 0
    smap = {src_vfx.lower(): vfx_path}
    for k, v in (extra_map or {}).items():
        smap[k.lower()] = v
    pieces = []
    for F, it, tex in s[2]:
        item = bytearray(sb[it["start"]:it["end"]])
        if tex in smap:
            ft, vs = F[H["tex"]]
            rel = vs - it["start"]
            n = struct.unpack_from("<H", item, rel)[0]
            new = smap[tex].encode("latin1")
            item[rel + 2:rel + 2 + n] = new
            struct.pack_into("<H", item, rel, len(new))
            so = it["size_off"] - it["start"]
            struct.pack_into("<I", item, so, struct.unpack_from("<I", item, so)[0] + len(new) - n)
        pieces.append(bytes(item))
    ln_off, lst, items = t
    start, end = items[0][1]["start"], items[-1][1]["end"]
    data = b"".join(pieces)
    delta = len(data) - (end - start)
    d[start:end] = data
    struct.pack_into("<I", d, lst["size_off"], struct.unpack_from("<I", d, lst["size_off"])[0] + delta)
    struct.pack_into("<I", d, lst["size_off"] + 4, len(pieces))
    struct.pack_into("<I", d, ln_off, struct.unpack_from("<I", d, ln_off)[0] + delta)
    out = bytes(d)
    BP.RANGES.clear()
    BP.parse(out)
    new_lay = layers(out, vfx_path)
    a, b2 = reference_size(own_lay), reference_size(new_lay)
    if a > 0 and b2 > 0 and abs(a / b2 - 1.0) > 0.001:
        out, _ = C.scale_popup(out, vfx_path, a / b2)
    return out, len(pieces)
