import os, sys
import tkinter as tk
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

W, H = 260, 270
POPUP = 84
BAR = 100
CENTER = (W // 2, 128)

def _font(size, bold=False):
    for name in (("segoeuib.ttf" if bold else "segoeui.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()

def render_fallback(percent, picture=None):
    img = Image.new("RGB", (W, H), (38, 52, 44))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 26):
        d.line((x, 0, x, H), fill=(44, 60, 51))
    for y in range(0, H, 26):
        d.line((0, y, W, y), fill=(44, 60, 51))

    cx = W // 2
    d.ellipse((cx - 34, 214, cx + 34, 262), fill=(70, 86, 120))
    d.ellipse((cx - 14, 196, cx + 14, 224), fill=(88, 106, 142))

    bar_top = 190
    d.text((cx, bar_top - 14), "Your champion", font=_font(11), fill=(235, 235, 235), anchor="mm")
    d.rectangle((cx - BAR // 2 - 2, bar_top - 2, cx + BAR // 2 + 2, bar_top + 15), fill=(20, 22, 26))
    d.rectangle((cx - BAR // 2, bar_top, cx + BAR // 2, bar_top + 9), fill=(70, 170, 70))
    d.rectangle((cx - BAR // 2, bar_top + 10, cx + BAR // 2, bar_top + 13), fill=(60, 120, 190))

    half_normal = POPUP // 2
    nx0, ny0, nx1, ny1 = CENTER[0] - half_normal, CENTER[1] - half_normal, CENTER[0] + half_normal, CENTER[1] + half_normal
    size = max(6, int(round(POPUP * percent / 100.0)))
    half = size // 2
    box = (CENTER[0] - half, CENTER[1] - half, CENTER[0] + half, CENTER[1] + half)

    if picture is not None:
        pic = picture.convert("RGBA")
        pic.thumbnail((size, size), Image.LANCZOS)
        bg = Image.new("RGBA", (size, size), (70, 70, 70, 255))
        bg.alpha_composite(pic, ((size - pic.width) // 2, (size - pic.height) // 2))
        img.paste(bg.convert("RGB"), (box[0], box[1]))
    else:
        d.rectangle(box, fill=(255, 203, 71))
        r = max(2, size // 12)
        d.ellipse((CENTER[0] - size // 5 - r, CENTER[1] - size // 8 - r, CENTER[0] - size // 5 + r, CENTER[1] - size // 8 + r), fill=(60, 40, 10))
        d.ellipse((CENTER[0] + size // 5 - r, CENTER[1] - size // 8 - r, CENTER[0] + size // 5 + r, CENTER[1] - size // 8 + r), fill=(60, 40, 10))
        d.arc((CENTER[0] - size // 4, CENTER[1] - size // 6, CENTER[0] + size // 4, CENTER[1] + size // 4), 20, 160, fill=(60, 40, 10), width=max(2, size // 20))
    d.rectangle(box, outline=(255, 255, 255), width=2)

    dash = (120, 200, 255)
    for a, b, c, e in ((nx0, ny0, nx1, ny0), (nx0, ny1, nx1, ny1), (nx0, ny0, nx0, ny1), (nx1, ny0, nx1, ny1)):
        steps = max(abs(c - a), abs(e - b))
        for t in range(0, steps, 8):
            p0 = (a + (c - a) * t / steps, b + (e - b) * t / steps)
            p1 = (a + (c - a) * min(t + 4, steps) / steps, b + (e - b) * min(t + 4, steps) / steps)
            d.line((p0[0], p0[1], p1[0], p1[1]), fill=dash, width=1)

    d.text((10, 8), "In-game size: %d%%" % percent, font=_font(15, True), fill=(255, 255, 255))
    d.text((10, 30), "dashed box = normal size", font=_font(11), fill=dash)
    return img

class SizePreview(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.label = tk.Label(self, bd=2, relief="solid", bg="#222")
        self.label.pack()
        self.photo = None

    def show(self, percent, picture, anchor):
        self.photo = ImageTk.PhotoImage(render(percent, picture))
        self.label.configure(image=self.photo)
        self.update_idletasks()
        x, y = anchor
        x = max(0, min(x, self.winfo_screenwidth() - self.winfo_reqwidth() - 8))
        y = max(0, min(y, self.winfo_screenheight() - self.winfo_reqheight() - 48))
        self.geometry("+%d+%d" % (x, y))
        self.deiconify()
        self.lift()

    def hide(self):
        self.withdraw()

PAD = 110
BAR_CENTER_X = 270
BAR_TOP_Y = 163
POPUP_UP = 112
POPUP_REAL = 140
SHOW_SCALE = 0.66
_scene_cache = []

def _scene():
    if _scene_cache:
        return _scene_cache[0]
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(getattr(sys, "_MEIPASS", here), "scene.png"), os.path.join(here, "..", "assets", "scene.png"), os.path.join(here, "scene.png")):
        if os.path.exists(path):
            arr = np.asarray(Image.open(path).convert("RGB"))
            arr = np.pad(arr, ((PAD, 0), (0, 0), (0, 0)), mode="reflect")
            _scene_cache.append(Image.fromarray(arr))
            return _scene_cache[0]
    _scene_cache.append(None)
    return None

def render(percent, picture=None):
    base = _scene()
    if base is None:
        return render_fallback(percent, picture)
    img = base.copy()
    d = ImageDraw.Draw(img)
    cx, cy = BAR_CENTER_X + 3, BAR_TOP_Y - POPUP_UP + PAD
    half0 = POPUP_REAL // 2
    size = max(8, int(round(POPUP_REAL * percent / 100.0)))
    half = size // 2
    box = (cx - half, cy - half, cx + half, cy + half)
    if picture is not None:
        pic = picture.convert("RGBA")
        pic.thumbnail((size, size), Image.LANCZOS)
        bg = Image.new("RGBA", (size, size), (70, 70, 70, 255))
        bg.alpha_composite(pic, ((size - pic.width) // 2, (size - pic.height) // 2))
        img.paste(bg.convert("RGB"), (box[0], box[1]))
    else:
        d.rectangle(box, fill=(255, 203, 71))
        r = max(3, size // 14)
        ex, ey = size // 5, size // 8
        d.ellipse((cx - ex - r, cy - ey - r, cx - ex + r, cy - ey + r), fill=(60, 40, 10))
        d.ellipse((cx + ex - r, cy - ey - r, cx + ex + r, cy - ey + r), fill=(60, 40, 10))
        d.arc((cx - size // 4, cy - size // 6, cx + size // 4, cy + size // 4), 20, 160, fill=(60, 40, 10), width=max(3, size // 20))
    d.rectangle(box, outline=(255, 255, 255), width=3)
    dash = (120, 220, 255)
    nx0, ny0, nx1, ny1 = cx - half0, cy - half0, cx + half0, cy + half0
    for a, b, c, e in ((nx0, ny0, nx1, ny0), (nx0, ny1, nx1, ny1), (nx0, ny0, nx0, ny1), (nx1, ny0, nx1, ny1)):
        steps = max(abs(c - a), abs(e - b))
        for t in range(0, steps, 14):
            t2 = min(t + 7, steps)
            d.line((a + (c - a) * t / steps, b + (e - b) * t / steps, a + (c - a) * t2 / steps, b + (e - b) * t2 / steps), fill=dash, width=2)
    out = img.resize((int(img.width * SHOW_SCALE), int(img.height * SHOW_SCALE)), Image.LANCZOS)
    o = ImageDraw.Draw(out, "RGBA")
    o.rectangle((0, 0, out.width, 50), fill=(0, 0, 0, 150))
    o.text((10, 6), "In-game size: %d%%" % percent, font=_font(15, True), fill=(255, 255, 255))
    o.text((10, 29), "dashed box = normal size", font=_font(11), fill=dash)
    return out

_small_cache = {}

def render_small(percent, picture=None, scale=0.42):
    base = _scene()
    if base is None:
        return render_fallback(percent, picture)
    key = round(scale, 3)
    if key not in _small_cache:
        _small_cache[key] = base.resize((int(base.width * scale), int(base.height * scale)), Image.LANCZOS)
    img = _small_cache[key].copy()
    d = ImageDraw.Draw(img)
    cx, cy = int((BAR_CENTER_X + 3) * scale), int((BAR_TOP_Y - POPUP_UP + PAD) * scale)
    half0 = int(POPUP_REAL * scale / 2)
    size = max(6, int(round(POPUP_REAL * scale * percent / 100.0)))
    half = size // 2
    box = (cx - half, cy - half, cx + half, cy + half)
    if picture is not None:
        pic = picture.convert("RGBA").resize((size, size), Image.BILINEAR)
        bg = Image.new("RGBA", (size, size), (70, 70, 70, 255))
        bg.alpha_composite(pic)
        img.paste(bg.convert("RGB"), (box[0], box[1]))
    else:
        d.rectangle(box, fill=(255, 203, 71))
        r = max(2, size // 14)
        ex, ey = size // 5, size // 8
        d.ellipse((cx - ex - r, cy - ey - r, cx - ex + r, cy - ey + r), fill=(60, 40, 10))
        d.ellipse((cx + ex - r, cy - ey - r, cx + ex + r, cy - ey + r), fill=(60, 40, 10))
        d.arc((cx - size // 4, cy - size // 6, cx + size // 4, cy + size // 4), 20, 160, fill=(60, 40, 10), width=max(2, size // 20))
    d.rectangle(box, outline=(255, 255, 255), width=1)
    dash = (120, 220, 255)
    nx0, ny0, nx1, ny1 = cx - half0, cy - half0, cx + half0, cy + half0
    for a, b, c, e in ((nx0, ny0, nx1, ny0), (nx0, ny1, nx1, ny1), (nx0, ny0, nx0, ny1), (nx1, ny0, nx1, ny1)):
        steps = max(abs(c - a), abs(e - b), 1)
        for t in range(0, steps, 6):
            t2 = min(t + 3, steps)
            d.line((a + (c - a) * t / steps, b + (e - b) * t / steps, a + (c - a) * t2 / steps, b + (e - b) * t2 / steps), fill=dash, width=1)
    o = ImageDraw.Draw(img, "RGBA")
    o.rectangle((0, 0, img.width, 18), fill=(0, 0, 0, 150))
    o.text((5, 3), "Size %d%%  (dashed = normal)" % percent, font=_font(10), fill=(255, 255, 255))
    return img

_placeholder_cache = {}

def _placeholder(size=160):
    if size not in _placeholder_cache:
        im = Image.new("RGBA", (size, size), (255, 203, 71, 255))
        d = ImageDraw.Draw(im)
        r, ex, ey = max(3, size // 14), size // 5, size // 8
        c = size // 2
        d.ellipse((c - ex - r, c - ey - r, c - ex + r, c - ey + r), fill=(60, 40, 10))
        d.ellipse((c + ex - r, c - ey - r, c + ex + r, c - ey + r), fill=(60, 40, 10))
        d.arc((c - size // 4, c - size // 6, c + size // 4, c + size // 4), 20, 160, fill=(60, 40, 10), width=max(3, size // 20))
        _placeholder_cache[size] = im
    return _placeholder_cache[size]

def render_motion(percent, picture, poses, ref, caption="", scale=0.37):
    base = _scene()
    if base is None:
        return render_fallback(percent, picture)
    key = round(scale, 3)
    if key not in _small_cache:
        _small_cache[key] = base.resize((int(base.width * scale), int(base.height * scale)), Image.LANCZOS)
    img = _small_cache[key].copy().convert("RGBA")
    cx, cy = int((BAR_CENTER_X + 3) * scale), int((BAR_TOP_Y - POPUP_UP + PAD) * scale)
    full = POPUP_REAL * scale * percent / 100.0
    ppu = POPUP_REAL * scale / max(1e-6, ref)
    src = (picture.convert("RGBA") if picture is not None else _placeholder(160))
    for p in poses:
        w, h = int(round(full * p["sx"] / ref)), int(round(full * p["sy"] / ref))
        if w < 2 or h < 2 or p["alpha"] <= 0.01:
            continue
        sp = Image.new("RGBA", src.size, (70, 70, 70, 255))
        sp.alpha_composite(src)
        sp = sp.resize((w, h), Image.BILINEAR)
        if abs(p["rot"]) > 0.05:
            sp = sp.rotate(-p["rot"], resample=Image.BILINEAR, expand=True)
        if p["alpha"] < 0.999:
            a = sp.getchannel("A").point(lambda v: int(v * p["alpha"]))
            sp.putalpha(a)
        x, y = int(round(cx + p["dx"] * ppu - sp.width / 2)), int(round(cy + p["dy"] * ppu - sp.height / 2))
        _paste_clipped(img, sp, x, y)
    o = ImageDraw.Draw(img, "RGBA")
    o.rectangle((0, 0, img.width, 18), fill=(0, 0, 0, 150))
    o.text((5, 3), caption, font=_font(10), fill=(255, 255, 255))
    return img.convert("RGB")

def _paste_clipped(img, sp, x, y):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(sp, (x, y))
    img.alpha_composite(layer)
