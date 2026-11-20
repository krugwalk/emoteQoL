import struct, sys
def fnv(s):
    h = 0x811c9dc5
    for c in s.lower().encode(): h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h
RANGES = {}
class V3(tuple):
    off = -1
class Str(str):
    off = -1
class R:
    def __init__(self, d, p=0): self.d = d; self.p = p
    def u8(self): v = self.d[self.p]; self.p += 1; return v
    def u16(self): v, = struct.unpack_from("<H", self.d, self.p); self.p += 2; return v
    def u32(self): v, = struct.unpack_from("<I", self.d, self.p); self.p += 4; return v
    def i32(self): v, = struct.unpack_from("<i", self.d, self.p); self.p += 4; return v
    def f32(self): v, = struct.unpack_from("<f", self.d, self.p); self.p += 4; return v
    def fl(self, n): v = struct.unpack_from("<%df" % n, self.d, self.p); self.p += 4 * n; return tuple(round(x, 4) for x in v)
def value(r, t):
    if t >= 128: t = t - 128 + 19
    if t == 0: return None
    if t == 1: return bool(r.u8())
    if t == 2: v, = struct.unpack_from("<b", r.d, r.p); r.p += 1; return v
    if t == 3: return r.u8()
    if t == 4: v, = struct.unpack_from("<h", r.d, r.p); r.p += 2; return v
    if t == 5: return r.u16()
    if t == 6: return r.i32()
    if t == 7: return r.u32()
    if t == 8: v, = struct.unpack_from("<q", r.d, r.p); r.p += 8; return v
    if t == 9: v, = struct.unpack_from("<Q", r.d, r.p); r.p += 8; return v
    if t == 10: return round(r.f32(), 4)
    if t == 11: return r.fl(2)
    if t == 12:
        o = r.p; v = V3(r.fl(3)); v.off = o; return v
    if t == 13: return r.fl(4)
    if t == 14: return r.fl(16)
    if t == 15: return tuple(r.u8() for _ in range(4))
    if t == 16:
        n = r.u16(); o = r.p; s = Str(r.d[r.p:r.p + n].decode("latin1")); s.off = o; r.p += n; return s
    if t == 17: return "#%08x" % r.u32()
    if t == 18: v, = struct.unpack_from("<Q", r.d, r.p); r.p += 8; return "file#%016x" % v
    if t in (19, 20):
        et = r.u8(); size = r.u32(); end = r.p + size; cnt = r.u32(); items = []
        for _ in range(cnt): items.append(value(r, et))
        r.p = end; return ("list", et, items)
    if t in (21, 22):
        nh = r.u32()
        if nh == 0: return ("null",)
        size = r.u32(); end = r.p + size; cnt = r.u16(); fields = []
        for _ in range(cnt):
            fh = r.u32(); ft = r.u8(); fields.append((fh, ft, value(r, ft)))
        r.p = end; return ("obj", nh, fields)
    if t == 23: return "link#%08x" % r.u32()
    if t == 24:
        et = r.u8(); c = r.u8(); return ("opt", None if c == 0 else value(r, et))
    if t == 25:
        kt = r.u8(); vt = r.u8(); size = r.u32(); end = r.p + size; cnt = r.u32(); items = []
        for _ in range(cnt): k = value(r, kt); v = value(r, vt); items.append((k, v))
        r.p = end; return ("map", items)
    if t == 26: return bool(r.u8())
    raise ValueError("type %d at %d" % (t, r.p))
def parse(d):
    r = R(d); assert d[:4] == b"PROP"; r.p = 4; ver = r.u32()
    if ver >= 2:
        n = r.u32()
        for _ in range(n): ln = r.u16(); r.p += ln
    cnt = r.u32(); types = [r.u32() for _ in range(cnt)]; ents = {}
    for i in range(cnt):
        ln = r.u32(); end = r.p + ln; ph = r.u32(); fc = r.u16(); fields = []; RANGES[ph] = (r.p - 10, end)
        for _ in range(fc):
            fh = r.u32(); ft = r.u8(); fields.append((fh, ft, value(r, ft)))
        r.p = end; ents[ph] = (types[i], fields)
    return ents
