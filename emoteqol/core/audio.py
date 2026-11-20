import io, os, re, struct, wave, array, shutil, subprocess, tempfile, sys
from emoteqol.formats import wad as wadtool; from emoteqol.formats import binparse as BP; from emoteqol.formats import bank; from emoteqol.formats import wpk

SFX_WPK = "assets/sounds/wwise2016/sfx/shared/misc_emotes_sfx_audio.wpk"; SFX_BNK = "assets/sounds/wwise2016/sfx/shared/misc_emotes_sfx_events.bnk"
COMMON = ("Maps", "Shipping", "Common.wad.client")
RATE = 44100
PK_HASH = wadtool.h(SFX_WPK); BNK_HASH = wadtool.h(SFX_BNK)

def fnv32(s):
    h = 2166136261
    for ch in s.lower().encode(): h = (h * 16777619) & 0xFFFFFFFF; h ^= ch
    return h

def common_wad(game): return wadtool.Wad(os.path.join(game.dir, *COMMON))

def event_for_emote(game, em, emote_bin_list):
    target = em["vfx"].lower().encode()
    for bh in emote_bin_list:
        d = game.read(bh)
        if not d or target not in d.lower(): continue
        BP.RANGES.clear()
        try: ents = BP.parse(bytes(d))
        except Exception: continue
        for h, (t, f) in ents.items():
            raw = d[BP.RANGES[h][0]:BP.RANGES[h][1]]
            if target in raw.lower():
                for fh, ft, v in f:
                    if fh == 0xe0c375ae and isinstance(v, str) and v: return str(v)
    return None

def event_sounds(bnk, event_name):
    secs, objs = bank.parse_bank(bnk); eid = fnv32(event_name)
    if eid not in objs or objs[eid][0] != 4: return None
    t, q, ln = objs[eid]; b = bnk[q + 5:q + ln]; out = []
    for i in range(b[4]):
        a = struct.unpack_from("<I", b, 5 + 4 * i)[0]
        if a not in objs: continue
        ta, qa, la = objs[a]; tgt, = struct.unpack_from("<I", bnk, qa + 5 + 6)
        if tgt in objs and objs[tgt][0] == 2: q2 = objs[tgt][1]; out.append((tgt, struct.unpack_from("<I", bnk, q2 + 5 + 9)[0]))
    return out

def _ffmpeg():
    p = shutil.which("ffmpeg")
    if p: return p
    for c in (os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "ffmpeg.exe"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")):
        if os.path.exists(c): return c
    return None

def _read_wav(path):
    w = wave.open(path); ch, sw, rate = w.getnchannels(), w.getsampwidth(), w.getframerate(); a = array.array("h"); raw = w.readframes(w.getnframes())
    if sw != 2: raise RuntimeError("Only 16-bit .wav is supported without ffmpeg (this file is %d-bit)." % (sw * 8))
    a.frombytes(raw)
    if ch > 1: a = array.array("h", [int(sum(a[i:i + ch]) / ch) for i in range(0, len(a) - ch + 1, ch)])
    if rate != RATE:
        n = int(len(a) * RATE / rate); a = array.array("h", [a[min(len(a) - 1, int(i * rate / RATE))] for i in range(n)])
    return a

def _av_pcm(path):
    import av, numpy as np
    c = av.open(path)
    try:
        if not c.streams.audio: raise RuntimeError("this file has no sound")
        rs = av.AudioResampler(format="s16", layout="mono", rate=RATE); chunks = []
        for fr in c.decode(audio=0):
            for o in rs.resample(fr): chunks.append(o.to_ndarray().reshape(-1))
        for o in rs.resample(None): chunks.append(o.to_ndarray().reshape(-1))
    finally: c.close()
    a = array.array("h"); a.frombytes(np.concatenate(chunks).astype(np.int16).tobytes() if chunks else b""); return a

def audio_duration(path):
    if path.lower().endswith(".wem"): return None
    try:
        import av
        c = av.open(path)
        try:
            if not c.streams.audio: return None
            st = c.streams.audio[0]; d = float(st.duration * st.time_base) if st.duration else (c.duration / 1e6 if c.duration else None)
        finally: c.close()
        if d: return d
    except Exception: pass
    try: return len(load_pcm(path)) / RATE
    except Exception: return None

def load_pcm(path):
    ext = os.path.splitext(path)[1].lower()
    try: return _av_pcm(path)
    except Exception: pass
    ff = _ffmpeg()
    if ff:
        tmp = tempfile.mktemp(suffix=".wav")
        try:
            subprocess.run([ff, "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", tmp], check=True, capture_output=True, creationflags=0x08000000)
            return _read_wav(tmp)
        finally:
            if os.path.exists(tmp): os.remove(tmp)
    vg = _vgmstream()
    if vg and ext != ".wav":
        tmp = tempfile.mktemp(suffix=".wav")
        try:
            subprocess.run([vg, "-o", tmp, path], check=True, capture_output=True, creationflags=0x08000000); return _read_wav(_to_mono_44k(tmp))
        except Exception: pass
        finally:
            if os.path.exists(tmp): os.remove(tmp)
    if ext == ".wav": return _read_wav(path)
    raise RuntimeError("Converting %s files needs ffmpeg, which wasn't found. Use a .wav or a ready-made .wem, or put ffmpeg.exe next to the app." % (ext or "this"))

def pcm_wem(pcm):
    pk = max((abs(x) for x in pcm), default=1) or 1; g = 0.9 * 32767 / pk; data = array.array("h", [max(-32768, min(32767, int(x * g))) for x in pcm]).tobytes()
    guid = bytes.fromhex("0100000000001000800000aa00389b71")
    fmt = struct.pack("<HHIIHHHHI", 0xFFFE, 1, RATE, RATE * 2, 2, 16, 22, 16, 4) + guid
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body

def make_wem(path, max_seconds=6, boost_db=12.0, dynamics="Evened out"):
    if path.lower().endswith(".wem"):
        d = open(path, "rb").read(); tag = struct.unpack_from("<H", d, 20)[0] if d[:4] == b"RIFF" and d[12:16] == b"fmt " else None
        if tag is None: raise RuntimeError("That .wem isn't a RIFF audio file.")
        return d, tag != 0xFFFF, "ready-made .wem used as is (%s)" % ("Vorbis" if tag == 0xFFFF else "uncompressed")
    wc, proj = wwise_tools()
    if not wc: raise RuntimeError("To use your own audio the app needs LtMAO's Wwise converter, but LtMAO wasn't found. Click 'Find LtMAO...' in the Custom sound box and pick the LtMAO folder (the one with start.bat), or choose a ready-made .wem.")
    pcm = load_pcm(path); secs = len(pcm) / RATE
    if secs > max_seconds: pcm = pcm[:int(max_seconds * RATE)]
    return wwise_convert(wc, proj, pcm, boost_db, DYN_RATIOS.get(dynamics, 1.0)), False, "converted to a Wwise Vorbis .wem (%.1f s, %s)%s" % (min(secs, max_seconds), dynamics.lower(), "; trimmed" if secs > max_seconds else "")

WWISE_REL = os.path.join("res", "wiwawe", "WwiseApp", "Authoring", "x64", "Release", "bin", "WwiseConsole.exe")
PROJ_REL = os.path.join("res", "wiwawe", "WwiseLeagueProjects")
VGM_REL = os.path.join("res", "tools", "vgmstream", "vgmstream-cli.exe")

def _settings_path():
    from emoteqol.core import emotes as C; return os.path.join(C.APPDATA, "settings.json")
def _load_settings():
    import json
    try: return json.load(open(_settings_path()))
    except Exception: return {}
def _save_settings(s):
    import json; json.dump(s, open(_settings_path(), "w"))

def is_ltmao_dir(p): return bool(p) and os.path.exists(os.path.join(p, WWISE_REL)) and os.path.isdir(os.path.join(p, PROJ_REL))

def find_ltmao(extra=None):
    cands = [extra, _load_settings().get("ltmao")]
    for c in cands:
        if is_ltmao_dir(c): return c
    home = os.path.expanduser("~"); roots = [os.path.join(home, d) for d in ("Downloads", "Desktop", "Documents")] + [os.path.dirname(os.path.abspath(sys.executable)), os.getcwd()]
    roots += [d + ":" + os.sep for d in "DCEFG" if os.path.exists(d + ":" + os.sep)]
    skip = {"windows", "program files", "program files (x86)", "$recycle.bin", "system volume information", "appdata", "riot games", "steam", "steamlibrary", "node_modules", ".git"}
    for r in roots:
        base = r.rstrip("\\").count(os.sep)
        for dp, dns, fns in os.walk(r):
            if is_ltmao_dir(dp): s = _load_settings(); s["ltmao"] = dp; _save_settings(s); return dp
            if dp.count(os.sep) - base >= 4: dns[:] = []; continue
            dns[:] = [d for d in dns if d.lower() not in skip and not d.startswith(".")]
    return None

def set_ltmao(p):
    if not is_ltmao_dir(p): return False
    s = _load_settings(); s["ltmao"] = p; _save_settings(s); return True

def _vgmstream():
    p = find_ltmao(); v = os.path.join(p, VGM_REL) if p else None
    return v if v and os.path.exists(v) else None

def wwise_tools():
    p = find_ltmao()
    if not p: return None, None
    from emoteqol.core import emotes as C; dst = os.path.join(C.APPDATA, "wwise_project")
    if not os.path.exists(os.path.join(dst, "WWiseLeagueProjects.wproj")): shutil.copytree(os.path.join(p, PROJ_REL), dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".cache"))
    return os.path.join(p, WWISE_REL), os.path.join(dst, "WWiseLeagueProjects.wproj")

def _to_mono_44k(path):
    pcm = _read_wav(path); out = path[:-4] + "_44k.wav"; _write_wav(out, pcm); return out

DYN_RATIOS = {"Natural": 1.0, "Evened out": 3.0, "Very even": 6.0}

def even_out(x, ratio, thresh_db=-30.0):
    import numpy as np
    if ratio <= 1.0 or len(x) == 0: return x
    att = np.exp(-1.0 / (0.002 * RATE)); rel = np.exp(-1.0 / (0.12 * RATE)); a = np.abs(x).tolist(); env = [0.0] * len(a); e = 0.0
    for i, v in enumerate(a):
        e = att * e + (1 - att) * v if v > e else rel * e + (1 - rel) * v
        env[i] = e
    edb = 20 * np.log10(np.maximum(np.asarray(env), 1e-5)); over = np.maximum(edb - thresh_db, 0.0)
    return x * 10 ** (-(over * (1 - 1 / ratio)) / 20.0)

def _write_wav(path, pcm, boost_db=None, ratio=1.0):
    import numpy as np
    x = np.asarray(pcm, dtype=np.float64) / 32768.0
    if boost_db is None:
        pk = float(np.max(np.abs(x))) if len(x) else 1.0; y = x * (0.9 / pk if pk > 0 else 1.0)
    else:
        x = even_out(x, ratio); rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0; g = (10 ** (-16 / 20.0) / rms if rms > 1e-6 else 1.0) * 10 ** (boost_db / 20.0)
        y = np.tanh(x * g)
    data = array.array("h", (np.clip(y, -1.0, 1.0) * 32000).astype(np.int16).tolist())
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(data.tobytes()); w.close()

def wwise_convert(wc, proj, pcm, boost_db=12.0, ratio=1.0):
    work = tempfile.mkdtemp(prefix="emote_wem_")
    try:
        inp = os.path.join(work, "in"); out = os.path.join(work, "out"); os.makedirs(inp); os.makedirs(out); _write_wav(os.path.join(inp, "clip.wav"), pcm, boost_db, ratio)
        ws = os.path.join(work, "clip.wsources")
        xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<ExternalSourcesList SchemaVersion=\"1\" Root=\"%s\">" % inp, "\t<Source Path=\"clip.wav\" Conversion=\"Vorbis Quality High\" />", "</ExternalSourcesList>"]
        open(ws, "w", encoding="utf-8").write("\n".join(xml))
        r = subprocess.run([wc, "convert-external-source", proj, "--source-file", ws, "--output", out], capture_output=True, text=True, timeout=180, creationflags=0x08000000)
        for dp, dns, fns in os.walk(out):
            for f in fns:
                if f.lower().endswith(".wem"): return open(os.path.join(dp, f), "rb").read()
        raise RuntimeError("Wwise did not produce a .wem: " + (r.stdout + r.stderr)[-400:])
    finally: shutil.rmtree(work, ignore_errors=True)

def _patch_wpk(d, repl):
    d = bytearray(d); n, = struct.unpack_from("<I", d, 8); offs = struct.unpack_from("<%dI" % n, d, 12); repl = dict(repl)
    for o in offs:
        if not o: continue
        fo, fs, nl = struct.unpack_from("<III", d, o); name = d[o + 12:o + 12 + nl * 2].decode("utf-16le").split(".")[0]
        if name in repl:
            data = repl.pop(name); d += b"\0" * ((-len(d)) % 16); newoff = len(d); d += data; struct.pack_into("<II", d, o, newoff, len(data))
    assert not repl, "audio entries not found: %s" % list(repl)
    return bytes(d)

SILENT_WEM = __import__("base64").b64decode("UklGRloBAABXQVZFZm10IEIAAAD//wEARKwAAJwEAAAAAAAAMAAAAAFBAAB0IgAAywAAAOwAAAAAAMwDAAAAAMsAAAABAMwDBEcAAMxIAABIpN6zCAtoYXNoEAAAALY+3pQ9FFdQDEeoEVbl1ppkYXRh7AAAAMkAJiacgEIKKqzAQgsuvABDDD78AEQQQgxBRBFGHIFEEkoswQQ41lyDTTbabMNNN958U01AIGQCgQIoMJABAAcICVIAQGGBoUOECBCjwMC4uLQIQmSGSEQsBokJ1UBRMR0ALC4w5ANAhsZG2sUFdBnggi7uOhBCEIIQxOIACkjAwQk3PPGGJ9zgBJ2iUgcBAADAAQA8AAAcG0BERHMcHR4fICEiIyQlAQAAgA0AfAAAHCZARERzHB0eHyAhIiMkJQEAAAAAQEBAAGAAAQAAAQABAQABAQABAQABAQABAQABAQABAQABAQABAQAB")
POP_EVENT = "Play_sfx_Emotes_02"

def _volume_prop(bnk, objs, sid):
    q = objs[sid][1] + 5
    if bytes(bnk[q + 27:q + 31]) != bytes.fromhex("8a62d90f") or bnk[q + 31] != 0: return None
    n = bnk[q + 32]; ids = list(bnk[q + 33:q + 33 + n])
    for i, pid in enumerate(ids):
        if pid in (6, 0): return q + 33 + n + 4 * i
    return None

def raise_event_volume(bnk, ev, level_db):
    secs, objs = bank.parse_bank(bytes(bnk)); done = []
    for sid, mid in event_sounds(bytes(bnk), ev) or []:
        o = _volume_prop(bnk, objs, sid)
        if o is None: continue
        v, = struct.unpack_from("<f", bnk, o)
        if v > -60: struct.pack_into("<f", bnk, o, float(level_db)); done.append((v, float(level_db)))
    return done

def apply_sounds(game, sounds, base_wpk=None, base_bnk=None, retargets=None, gain_db=None, silence=None):
    cw = common_wad(game); bnk = bytearray(base_bnk or cw.read(SFX_BNK)); wp = base_wpk or cw.read(SFX_WPK); notes = []; repl = {}
    for ev, (wem, is_pcm) in sounds.items():
        snd = event_sounds(bytes(bnk), ev)
        if not snd: notes.append("event %s not found in the emote sound bank" % ev); continue
        secs, objs = bank.parse_bank(bytes(bnk))
        for sid, mid in snd:
            repl[str(mid)] = wem
            if is_pcm: struct.pack_into("<I", bnk, objs[sid][1] + 5 + 4, 0x00010001)
    for ev in sounds:
        gdb = gain_db.get(ev) if isinstance(gain_db, dict) else gain_db
        if gdb is not None and event_sounds(bytes(bnk), ev):
            ch = raise_event_volume(bnk, ev, gdb)
            notes.append("%s: game volume %s" % (ev, ("%g dB (was %s)" % (gdb, ", ".join("%g" % c[0] for c in ch))) if ch else "left as is (no volume setting in the bank, use the file loudness)"))
    for ev in (silence or []):
        snd = event_sounds(bytes(bnk), ev)
        if snd:
            for sid, mid in snd: repl[str(mid)] = SILENT_WEM
        else: notes.append("event %s not found, nothing silenced" % ev)
    for ev, src in (retargets or {}).items():
        try: notes.append(ev + ": " + retarget_event(bnk, ev, src))
        except Exception as e: notes.append(str(e))
    return (_patch_wpk(wp, repl) if repl else wp), bytes(bnk), notes

def _play_targets(bnk, objs, ev):
    t, q, ln = objs[fnv32(ev)]; n = bnk[q + 5 + 4]; out = []
    for i in range(n):
        a = struct.unpack_from("<I", bnk, q + 5 + 5 + 4 * i)[0]
        if a not in objs: continue
        qa = objs[a][1]
        if struct.unpack_from("<H", bnk, qa + 5 + 4)[0] == 0x0403: out.append((qa, struct.unpack_from("<I", bnk, qa + 5 + 6)[0]))
    return out

def retarget_event(bnk, ev, src_ev):
    secs, objs = bank.parse_bank(bytes(bnk))
    if fnv32(ev) not in objs: raise RuntimeError("event %s not in the emote sound bank" % ev)
    if fnv32(src_ev) not in objs: raise RuntimeError("sound event %s not in the emote sound bank" % src_ev)
    mine = _play_targets(bytes(bnk), objs, ev); src = _play_targets(bytes(bnk), objs, src_ev)
    if not mine or not src: raise RuntimeError("could not read the sound actions of %s / %s" % (ev, src_ev))
    n = min(len(mine), len(src))
    for (qa, _), (_, tgt) in zip(mine[:n], src[:n]): struct.pack_into("<I", bnk, qa + 5 + 6, tgt)
    t, q, ln = objs[fnv32(ev)]; keep = [struct.unpack_from("<I", bnk, q + 5 + 5 + 4 * i)[0] for i in range(bnk[q + 5 + 4])]
    acts = [a for a in keep if a in objs and struct.unpack_from("<H", bnk, objs[a][1] + 5 + 4)[0] == 0x0403][:n]
    for i, a in enumerate(acts): struct.pack_into("<I", bnk, q + 5 + 5 + 4 * i, a)
    bnk[q + 5 + 4] = len(acts); return "plays the sound of %s" % src_ev

def sound_catalogue(game, cat, bins, cache_path=None):
    import json
    if cache_path and os.path.exists(cache_path):
        try: return json.load(open(cache_path))
        except Exception: pass
    bk = common_wad(game).read(SFX_BNK); secs, objs = bank.parse_bank(bk); by_vfx = {e["vfx"].lower(): e for e in cat}; out = {}
    pat = re.compile(rb"assets/loadouts/summoneremotes/[a-z0-9_/\- .]*?_vfx\.tex")
    for bh in bins:
        d = game.read(bh)
        if not d: continue
        BP.RANGES.clear()
        try: ents = BP.parse(bytes(d))
        except Exception: continue
        for h, (t, f) in ents.items():
            ev = next((v for fh, ft, v in f if fh == 0xe0c375ae and isinstance(v, str) and v), None)
            if not ev or fnv32(ev) not in objs or objs[fnv32(ev)][0] != 4 or not _play_targets(bk, objs, ev): continue
            for m in pat.findall(d[BP.RANGES[h][0]:BP.RANGES[h][1]].lower()):
                em = by_vfx.get(m.decode())
                if em: out[em["key"]] = dict(name=em["name"], event=ev)
    res = sorted(out.values(), key=lambda x: x["name"].lower())
    if cache_path:
        try: json.dump(res, open(cache_path, "w"))
        except Exception: pass
    return res
