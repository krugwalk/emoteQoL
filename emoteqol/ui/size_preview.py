import tkinter as tk
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

def render(percent, picture=None):
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
