import struct
def parse_bank(d):
    p = 0; secs = {}
    while p + 8 <= len(d):
        tag = bytes(d[p:p + 4]); sz, = struct.unpack_from("<I", d, p + 4); secs[tag] = (p + 8, sz); p += 8 + sz
    objs = {}
    if b"HIRC" in secs:
        hp, hs = secs[b"HIRC"]; n, = struct.unpack_from("<I", d, hp); q = hp + 4
        for _ in range(n):
            t = d[q]; sz, = struct.unpack_from("<I", d, q + 1); oid, = struct.unpack_from("<I", d, q + 5); objs[oid] = (t, q, 5 + sz); q += 5 + sz
    return secs, objs
