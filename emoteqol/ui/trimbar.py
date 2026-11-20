import tkinter as tk

class TrimBar(tk.Canvas):
    H = 44
    PAD = 12

    def __init__(self, parent, width, on_change):
        super().__init__(parent, width=width, height=self.H, bg="#262626", highlightthickness=0)
        self.w = width
        self.on_change = on_change
        self.total = 0.0
        self.t0 = 0.0
        self.t1 = 0.0
        self.head = None
        self.mark = None
        self.speed = 1.0
        self.drag = None
        self.bind("<Button-1>", self._down)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.bind("<Motion>", self._hover)
        self.draw()

    def _x(self, t):
        span = self.w - 2 * self.PAD
        return self.PAD + (span * t / self.total if self.total else 0)

    def _t(self, x):
        span = self.w - 2 * self.PAD
        return max(0.0, min(self.total, (x - self.PAD) / span * self.total)) if self.total else 0.0

    def set_clip(self, total):
        self.total = float(total)
        self.t0 = 0.0
        self.t1 = self.total
        self.head = None
        self.draw()

    def set_playhead(self, t):
        self.head = t
        self.draw()

    def set_marker(self, t):
        self.mark = t
        self.draw()

    def set_speed(self, sp):
        self.speed = sp
        self.draw()

    def draw(self):
        self.delete("all")
        top, bottom = 10, 26
        if not self.total:
            self.create_rectangle(self.PAD, top, self.w - self.PAD, bottom, fill="#3a3a3a", outline="")
            self.create_text(self.w // 2, 36, text="load a GIF or video to trim it", fill="#999999", font=("Segoe UI", 8))
            return
        self.create_rectangle(self.PAD, top, self.w - self.PAD, bottom, fill="#3a3a3a", outline="")
        a, b = self._x(self.t0), self._x(self.t1)
        self.create_rectangle(a, top, b, bottom, fill="#2f6fb5", outline="")
        if self.mark is not None and self.t0 <= self.mark <= self.t1:
            m = self._x(self.mark)
            self.create_line(m, top - 4, m, bottom + 4, fill="#ffb000", width=2)
        if self.head is not None and self.t0 <= self.head <= self.t1:
            h = self._x(self.head)
            self.create_line(h, top - 2, h, bottom + 2, fill="#ffffff", width=2)
        for x in (a, b):
            self.create_rectangle(x - 4, top - 5, x + 4, bottom + 5, fill="#dfe9f7", outline="#4da3ff")
        text = "%.1f s - %.1f s   (%.1f s of %.1f s)" % (self.t0, self.t1, self.t1 - self.t0, self.total)
        if abs(self.speed - 1.0) > 0.005:
            text = "%.1f s - %.1f s   (%.1f s, plays in %.1f s at %d%%)" % (self.t0, self.t1, self.t1 - self.t0, (self.t1 - self.t0) / self.speed, round(self.speed * 100))
        self.create_text(self.w // 2, 37, text=text, fill="#dddddd", font=("Segoe UI", 8))

    def _hit(self, x):
        if not self.total:
            return None
        a, b = self._x(self.t0), self._x(self.t1)
        if abs(x - a) <= 7 and abs(x - a) <= abs(x - b):
            return "a"
        if abs(x - b) <= 7:
            return "b"
        if a < x < b:
            return "move"
        return "a" if abs(x - a) < abs(x - b) else "b"

    def _hover(self, ev):
        h = self._hit(ev.x)
        self.configure(cursor={"a": "sb_h_double_arrow", "b": "sb_h_double_arrow", "move": "fleur"}.get(h, ""))

    def _down(self, ev):
        h = self._hit(ev.x)
        if h:
            self.drag = (h, self._t(ev.x) - self.t0, self.t1 - self.t0)
            self._move(ev)

    def _move(self, ev):
        if not self.drag or not self.total:
            return
        h, grab, length = self.drag
        t = self._t(ev.x)
        mn = min(0.2, self.total)
        if h == "a":
            self.t0 = max(0.0, min(t, self.t1 - mn))
        elif h == "b":
            self.t1 = min(self.total, max(t, self.t0 + mn))
        else:
            start = max(0.0, min(t - grab, self.total - length))
            self.t0, self.t1 = start, start + length
        self.draw()
        self.on_change(self.t0, self.t1)
