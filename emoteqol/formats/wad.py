import struct, sys, gzip, os
import xxhash
from compression import zstd

def h(path):
    return xxhash.xxh64_intdigest(path.lower().encode())

class Wad:
    def __init__(self, path):
        self.f = open(path, 'rb')
        d = self.f.read(4)
        assert d[:2] == b'RW', d
        self.major = d[2]
        if self.major == 3:
            self.f.seek(4 + 256 + 8)
        elif self.major == 2:
            self.f.seek(4 + 84)
        n = struct.unpack('<I', self.f.read(4))[0]
        self.entries = {}
        for _ in range(n):
            ph, off, csz, usz, typ, dup, _p, sha = struct.unpack('<QIIIBBHQ', self.f.read(32))
            self.entries[ph] = (off, csz, usz, typ)

    def read(self, path):
        ph = h(path) if isinstance(path, str) else path
        if ph not in self.entries:
            return None
        off, csz, usz, typ = self.entries[ph]; typ &= 0xF
        self.f.seek(off)
        raw = self.f.read(csz)
        if typ == 0:
            return raw
        if typ == 1:
            return gzip.decompress(raw)
        if typ in (3, 4):
            return zstd.decompress(raw)
        if typ == 2:
            n = struct.unpack('<I', raw[:4])[0]
            return ('LINK', raw[4:4 + n].decode())
        raise Exception('type %d' % typ)

if __name__ == '__main__':
    w = Wad(sys.argv[1])
    print(len(w.entries), 'entries')
    for p in sys.argv[2:]:
        d = w.read(p)
        print(p, None if d is None else len(d))

