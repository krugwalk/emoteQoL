import struct
def parse_wpk(d):
    assert d[:4] == b"r3d2" and struct.unpack_from("<I", d, 4)[0] == 1
    n, = struct.unpack_from("<I", d, 8); offs = struct.unpack_from("<%dI" % n, d, 12); out = []
    for o in offs:
        if o == 0: out.append(None); continue
        fo, fs, nl = struct.unpack_from("<III", d, o); name = d[o + 12:o + 12 + nl * 2].decode("utf-16le"); out.append((name, fo, fs))
    return out
