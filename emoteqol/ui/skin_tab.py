import os, queue, threading, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from emoteqol.core import emotes as C; from emoteqol.core import skins as S

class RectEditor(tk.Frame):
    HANDLE_ID = ["nw", "n", "ne", "e", "se", "s", "sw", "w"]
    CURSORS = {"nw": "size_nw_se", "se": "size_nw_se", "ne": "size_ne_sw", "sw": "size_ne_sw", "n": "sb_v_double_arrow", "s": "sb_v_double_arrow", "e": "sb_h_double_arrow", "w": "sb_h_double_arrow", "move": "fleur"}
    def __init__(self, parent, fw, fh, margin=26, circle=False, hint="no picture yet"):
        super().__init__(parent); self.fw, self.fh, self.M, self.circle, self.hint = fw, fh, margin, circle, hint
        self.cv = tk.Canvas(self, width=fw + 2 * margin, height=fh + 2 * margin, bg="#262626", highlightthickness=0); self.cv.pack()
        self.img = None; self.rect = (0.0, 0.0, 1.0, 1.0); self.drag = None; self.photo = None; self.checker = self._checker()
        self.cv.bind("<Button-1>", self._down); self.cv.bind("<B1-Motion>", self._move); self.cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None)); self.cv.bind("<Motion>", self._hover); self.cv.bind("<MouseWheel>", self._wheel)
        self.draw()
    def _checker(self):
        im = Image.new("RGBA", (self.fw, self.fh), (90, 90, 90, 255)); px = im.load()
        for y in range(self.fh):
            for x in range(self.fw):
                if ((x // 10) + (y // 10)) % 2: px[x, y] = (120, 120, 120, 255)
        return im
    def set_image(self, img, mode="cover"):
        im = img.convert("RGBA")
        if max(im.size) > 900: im.thumbnail((900, 900), Image.LANCZOS)
        self.img = im; self.reset(mode)
    def reset(self, mode="cover"):
        if self.img is not None: self.rect = S.default_rect(self.img.width, self.img.height, self.fw, self.fh, mode)
        self.draw()
    def clear(self): self.img = None; self.draw()
    def _box(self): x0, y0, x1, y1 = self.rect; M = self.M; return (M + x0 * self.fw, M + y0 * self.fh, M + x1 * self.fw, M + y1 * self.fh)
    def _handles(self):
        x0, y0, x1, y1 = self._box(); mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return [(x0, y0), (mx, y0), (x1, y0), (x1, my), (x1, y1), (mx, y1), (x0, y1), (x0, my)]
    def draw(self):
        M, fw, fh = self.M, self.fw, self.fh; W, H = fw + 2 * M, fh + 2 * M; dark = Image.new("RGBA", (W, H), (38, 38, 38, 255))
        if self.img is not None:
            x0, y0, x1, y1 = self.rect; w, h = max(1, min(4000, round((x1 - x0) * fw))), max(1, min(4000, round((y1 - y0) * fh)))
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); layer.paste(self.img.resize((w, h), Image.BILINEAR), (M + round(x0 * fw), M + round(y0 * fh)))
            dim = layer.copy(); dim.putalpha(layer.getchannel("A").point(lambda v: int(v * 0.35))); out = Image.alpha_composite(dark, dim)
            inner = self.checker.copy(); inner.alpha_composite(layer.crop((M, M, M + fw, M + fh))); out.paste(inner, (M, M))
        else: out = dark; out.paste(self.checker, (M, M))
        self.photo = ImageTk.PhotoImage(out.convert("RGB")); self.cv.delete("all"); self.cv.create_image(0, 0, image=self.photo, anchor="nw")
        if self.circle: self.cv.create_oval(M, M, M + fw, M + fh, outline="#ffffff", width=2)
        self.cv.create_rectangle(M, M, M + fw, M + fh, outline="#ffffff" if not self.circle else "#777777", width=2 if not self.circle else 1)
        if self.img is not None:
            bx0, by0, bx1, by1 = self._box(); self.cv.create_rectangle(bx0, by0, bx1, by1, outline="#4da3ff", dash=(4, 3))
            for hx, hy in self._handles(): self.cv.create_rectangle(hx - 5, hy - 5, hx + 5, hy + 5, fill="#4da3ff", outline="white")
        else: self.cv.create_text(W // 2, H // 2, text=self.hint, fill="#bbbbbb", width=fw - 10, justify="center")
    def _hit(self, x, y):
        if self.img is None: return None
        for (hx, hy), n in zip(self._handles(), self.HANDLE_ID):
            if abs(x - hx) <= 9 and abs(y - hy) <= 9: return n
        x0, y0, x1, y1 = self._box(); return "move" if x0 <= x <= x1 and y0 <= y <= y1 else None
    def _hover(self, ev): self.cv.configure(cursor=self.CURSORS.get(self._hit(ev.x, ev.y), ""))
    def _down(self, ev):
        h = self._hit(ev.x, ev.y)
        if h: self.drag = dict(hit=h, x=ev.x, y=ev.y, rect=self.rect)
    def _move(self, ev):
        d = self.drag
        if not d: return
        dx, dy = (ev.x - d["x"]) / self.fw, (ev.y - d["y"]) / self.fh; x0, y0, x1, y1 = d["rect"]; hit = d["hit"]; mn = 0.03
        if hit == "move": x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy
        else:
            nx0, ny0, nx1, ny1 = x0, y0, x1, y1
            if "w" in hit: nx0 = min(x0 + dx, x1 - mn)
            if "e" in hit: nx1 = max(x1 + dx, x0 + mn)
            if "n" in hit: ny0 = min(y0 + dy, y1 - mn)
            if "s" in hit: ny1 = max(y1 + dy, y0 + mn)
            if len(hit) == 2 and not (ev.state & 0x0001):
                ow, oh = x1 - x0, y1 - y0; k = max((nx1 - nx0) / ow, (ny1 - ny0) / oh); k = max(k, mn / min(ow, oh)); nw, nh = ow * k, oh * k
                nx0, nx1 = (x1 - nw, x1) if "w" in hit else (x0, x0 + nw); ny0, ny1 = (y1 - nh, y1) if "n" in hit else (y0, y0 + nh)
            x0, y0, x1, y1 = nx0, ny0, nx1, ny1
        self.rect = (x0, y0, x1, y1); self.draw()
    def _wheel(self, ev):
        if self.img is None: return
        k = 1.06 if ev.delta > 0 else 1 / 1.06; x0, y0, x1, y1 = self.rect; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; hw, hh = (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
        if hw * 2 < 0.03 or hh * 2 < 0.03 or hw * 2 > 8: return
        self.rect = (cx - hw, cy - hh, cx + hw, cy + hh); self.draw()

class SkinTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app = app; self.champs = []; self.cur_champ = None; self.skin_list = []; self.cur_skin = None; self.refs = {}; self.jobs = queue.Queue()
        self.load_path = None; self.hud_path = None; self.pending_skin = None
        left = ttk.Frame(self); left.pack(side="left", fill="y", padx=(0, 6))
        sf = ttk.Frame(left); sf.pack(fill="x"); ttk.Label(sf, text="Search champions:").pack(side="left"); self.sv = tk.StringVar(); self.sv.trace_add("write", lambda *a: self.fill_champs())
        ttk.Entry(sf, textvariable=self.sv, width=14).pack(side="left", fill="x", expand=True, padx=6)
        fr = ttk.Frame(left); fr.pack(fill="y", expand=True)
        self.ct = ttk.Treeview(fr, show="tree", selectmode="browse", height=14); self.ct.column("#0", width=190); sb = ttk.Scrollbar(fr, command=self.ct.yview); self.ct.configure(yscrollcommand=sb.set); self.ct.pack(side="left", fill="y", expand=True, pady=4); sb.pack(side="left", fill="y", pady=4)
        self.ct.bind("<<TreeviewSelect>>", self.on_champ)
        mid = ttk.Frame(self); mid.pack(side="left", fill="y", padx=6); ttk.Label(mid, text="Skins (the art that exists is replaced)").pack(anchor="w")
        fr2 = ttk.Frame(mid); fr2.pack(fill="y", expand=True)
        self.st = ttk.Treeview(fr2, show="tree", selectmode="browse", height=14); self.st.column("#0", width=210); sb2 = ttk.Scrollbar(fr2, command=self.st.yview); self.st.configure(yscrollcommand=sb2.set); self.st.pack(side="left", fill="y", expand=True, pady=4); sb2.pack(side="left", fill="y", pady=4)
        self.st.bind("<<TreeviewSelect>>", self.on_skin)
        right = ttk.Frame(self); right.pack(side="left", fill="both", expand=True, padx=6)
        self.title = ttk.Label(right, text="Pick a champion and a skin on the left", font=("Segoe UI", 13, "bold")); self.title.pack(anchor="w")
        cur = ttk.LabelFrame(right, text="Right now in the game"); cur.pack(fill="x", pady=4)
        self.cur_ls = ttk.Label(cur); self.cur_ls.pack(side="left", padx=8, pady=6); self.cur_circle = ttk.Label(cur); self.cur_circle.pack(side="left", padx=8); self.cur_sq = ttk.Label(cur); self.cur_sq.pack(side="left", padx=8)
        self.cur_info = ttk.Label(cur, text="", foreground="#666", wraplength=230); self.cur_info.pack(side="left", padx=8)
        ed = ttk.Frame(right); ed.pack(fill="x", pady=4)
        b1 = ttk.LabelFrame(ed, text="Loading screen"); b1.pack(side="left", padx=4); self.ed_load = RectEditor(b1, 140, 255, 22, False, "choose a loading screen picture"); self.ed_load.pack(padx=6, pady=6)
        r1 = ttk.Frame(b1); r1.pack(fill="x", padx=6, pady=(0, 6)); ttk.Button(r1, text="Choose picture...", command=lambda: self.pick("load")).pack(side="left"); ttk.Button(r1, text="Reset", command=lambda: self.ed_load.reset("cover")).pack(side="left", padx=4); ttk.Button(r1, text="Clear", command=lambda: self.clear("load")).pack(side="left")
        b2 = ttk.LabelFrame(ed, text="In-game HUD / minimap portrait (round)"); b2.pack(side="left", padx=4); self.ed_hud = RectEditor(b2, 170, 170, 22, True, "choose a portrait picture"); self.ed_hud.pack(padx=6, pady=6)
        r2 = ttk.Frame(b2); r2.pack(fill="x", padx=6, pady=(0, 6)); ttk.Button(r2, text="Choose picture...", command=lambda: self.pick("hud")).pack(side="left"); ttk.Button(r2, text="Reset", command=lambda: self.ed_hud.reset("cover")).pack(side="left", padx=4); ttk.Button(r2, text="Clear", command=lambda: self.clear("hud")).pack(side="left")
        self.same_v = tk.BooleanVar(value=False); ttk.Checkbutton(b2, text="Use the loading screen picture here too", variable=self.same_v, command=self.use_same).pack(anchor="w", padx=6, pady=(0, 6))
        self.add_btn = ttk.Button(right, text="Add to pack  >>", command=self.add, state="disabled"); self.add_btn.pack(anchor="w", pady=6)
        ttk.Label(right, text="Works on any skin or champion - and on a fantome you already have: open it first (top right), add your art here, then Save. The pictures replace that fantome's loading screen / portrait and everything else in it stays.",
                  foreground="#666", wraplength=520, justify="left").pack(anchor="w")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            fn = self.jobs.get()
            try: fn()
            except Exception: pass
    def final(self): return self.app.game.dir if self.app.game else None
    def photo(self, img, w, h, key=None):
        im = img.copy(); im.thumbnail((w, h)); bg = Image.new("RGBA", im.size, (60, 60, 60, 255)); bg.alpha_composite(im.convert("RGBA")); p = ImageTk.PhotoImage(bg.convert("RGB")); self.refs[key or id(p)] = p; return p
    def start(self):
        if self.champs or not self.final(): return
        self.champs = S.champions(self.final()); self.fill_champs()
    def fill_champs(self):
        q = self.sv.get().strip().lower(); self.ct.delete(*self.ct.get_children()); self.shown = []
        for disp, name in self.champs:
            if q in disp.lower() or q in name.lower():
                k = ("c", name); self.shown.append((disp, name)); self.ct.insert("", "end", iid=name, text="  " + disp, image=self.refs.get(k, self.app.placeholder))
                if k not in self.refs: self.jobs.put(lambda name=name: self._champ_icon(name))
    def _champ_icon(self, name):
        try:
            W = S.open_wad(self.final(), name); c = name.lower(); data = None
            for p in S.art_paths(c, 0)[1]:
                data = S.read(W, p)
                if data: break
            if not data: return
            im = C.decode_tex(data); self.app.q.put(lambda: self._set_icon(self.ct, ("c", name), name, im))
        except Exception: pass
    def _set_icon(self, tree, key, iid, im):
        self.refs[key] = self.photo(im, 40, 40, key)
        if tree.exists(iid): tree.item(iid, image=self.refs[key])

    def on_champ(self, ev):
        s = self.ct.selection()
        if not s: return
        self.cur_champ = s[0]; self.cur_skin = None; self.st.delete(*self.st.get_children()); self.title.configure(text=self.cur_champ + " - loading skins..."); self.update_add()
        name = self.cur_champ
        def work():
            sk = S.skins(self.final(), name); self.app.q.put(lambda: self._skins_ready(name, sk))
            W = S.open_wad(self.final(), name)
            for d in sk:
                try:
                    p = d["load"] or d["circle"]
                    if p: im = C.decode_tex(S.read(W, p)); self.app.q.put(lambda n=d["n"], im=im: self._set_icon(self.st, ("s", name, n), "s%d" % n, im))
                except Exception: pass
        self.jobs.put(work)
    def _skins_ready(self, name, sk):
        if name != self.cur_champ: return
        self.skin_list = sk; self.st.delete(*self.st.get_children()); disp = dict((n, d) for d, n in self.champs).get(name, name) if False else name
        for d in sk:
            k = ("s", name, d["n"]); flags = "".join(x for x, ok in (("loading", d["load"]), ("HUD", d["circle"])) if ok)
            miss = ", ".join("no " + x for x, ok in (("loading screen", d["load"]), ("HUD", d["circle"])) if not ok)
            self.st.insert("", "end", iid="s%d" % d["n"], text="  %s%s" % ("Default skin" if d["n"] == 0 else "Skin %d" % d["n"], "  (%s)" % miss if miss else ""), image=self.refs.get(k, self.app.placeholder))
        self.title.configure(text=name + " - pick a skin")
        want = getattr(self, "pending_skin", None); self.pending_skin = None
        ids = ["s%d" % d["n"] for d in sk]; pick = "s%d" % want if want is not None and ("s%d" % want) in ids else (ids[0] if ids else None)
        if pick: self.st.selection_set(pick); self.st.see(pick)
    def source_bytes(self, champ, path):
        target = "WAD/%s.wad.client/%s" % (champ, path)
        for a in self.app.pack.art.values():
            for n, d in a["files"].items():
                if C._same_game_file(n, target): return d, "pack"
        for n, d in self.app.pack.other.items():
            if C._same_game_file(n, target): return d, "fantome"
        return S.read(S.open_wad(self.final(), champ), path), "game"
    def on_pack_opened(self):
        found = None
        for n in self.app.pack.other:
            parts = n.replace("\\", "/").split("/")
            if len(parts) >= 3 and parts[0].upper() == "WAD" and parts[1].lower().endswith(".wad.client"):
                champ = next((c for d, c in self.champs if c.lower() == parts[1][:-len(".wad.client")].lower()), None)
                if champ: found = champ; break
        if not found: return
        skins = S.skins(self.final(), found); hit = None
        for d in skins:
            for k in ("load", "circle", "square"):
                if d[k] and any(C._same_game_file(n, "WAD/%s.wad.client/%s" % (found, d[k])) for n in self.app.pack.other): hit = d["n"]; break
            if hit is not None: break
        self.sv.set(""); self.fill_champs(); self.pending_skin = hit if hit is not None else 0
        if self.ct.exists(found): self.ct.selection_set(found); self.ct.see(found)
    def on_skin(self, ev):
        s = self.st.selection()
        if not s or not self.cur_champ: return
        n = int(s[0][1:]); self.cur_skin = next((d for d in self.skin_list if d["n"] == n), None); self.title.configure(text="%s - %s" % (self.cur_champ, "default skin" if n == 0 else "skin %d" % n)); self.update_add()
        d = self.cur_skin; name = self.cur_champ
        if not d: return
        def work():
            out = {}; origin = set()
            for k in ("load", "circle", "square"):
                if d[k]:
                    try: data, where = self.source_bytes(name, d[k]); out[k] = C.decode_tex(data); origin.add(where)
                    except Exception: pass
            self.app.q.put(lambda: self._cur_ready(name, n, out, origin))
        self.jobs.put(work)
    def _cur_ready(self, name, n, out, origin=()):
        if name != self.cur_champ or not self.cur_skin or self.cur_skin["n"] != n: return
        for k, lab, sz in (("load", self.cur_ls, (78, 140)), ("circle", self.cur_circle, (64, 64)), ("square", self.cur_sq, (64, 64))):
            if k in out: lab.configure(image=self.photo(out[k], *sz, ("cur", k)));
            else: lab.configure(image="")
        miss = [x for x, k in (("loading screen", "load"), ("portrait", "circle")) if k not in out]
        where = "Showing the art from your opened fantome. " if "fantome" in origin else ("Showing the art you added to the pack. " if "pack" in origin else "")
        self.cur_info.configure(text=where + (("Not found in this champion's files: " + ", ".join(miss) + " - the picture is still written, but it may not replace anything.") if miss else "Your pictures replace these."))
    def pick(self, which):
        p = filedialog.askopenfilename(title="Choose a picture", filetypes=[("Pictures", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tga"), ("All files", "*.*")])
        if not p: return
        try: im = Image.open(p); im.load()
        except Exception as e: return messagebox.showerror("Could not open", str(e))
        if which == "load":
            self.ed_load.set_image(im); self.load_path = p
            if self.same_v.get(): self.ed_hud.set_image(im); self.hud_path = p
        else: self.ed_hud.set_image(im); self.hud_path = p; self.same_v.set(False)
        self.update_add()
    def clear(self, which):
        if which == "load": self.ed_load.clear(); self.load_path = None
        else: self.ed_hud.clear(); self.hud_path = None
        self.update_add()
    def use_same(self):
        if self.same_v.get() and self.ed_load.img is not None: self.ed_hud.set_image(self.ed_load.img); self.hud_path = self.load_path; self.update_add()
    def update_add(self): self.add_btn.configure(state="normal" if (self.cur_champ and self.cur_skin and (self.ed_load.img is not None or self.ed_hud.img is not None) and self.app.game) else "disabled")
    def add(self):
        name = self.cur_champ; n = self.cur_skin["n"]; final = self.final()
        li, lr = (self.ed_load.img, self.ed_load.rect) if self.ed_load.img is not None else (None, None); hi, hr = (self.ed_hud.img, self.ed_hud.rect) if self.ed_hud.img is not None else (None, None)
        self.app.busy("Building the art for %s skin %d..." % (name, n)); self.add_btn.configure(state="disabled")
        def work():
            try: files, notes = S.build(final, name, n, li, lr, hi, hr); err = None
            except Exception: files, notes, err = None, None, traceback.format_exc()
            self.app.q.put(lambda: self._added(name, n, files, notes, err))
        self.jobs.put(work)
    def _added(self, name, n, files, notes, err):
        self.update_add()
        if err: self.app.busy("Failed."); return messagebox.showerror("Error", err[-600:])
        src = ", ".join(os.path.basename(p) for p in (self.load_path, self.hud_path) if p) or "picture"
        self.app.pack.art["%s:%d" % (name, n)] = dict(name="%s %s - %s" % (name, "default skin" if n == 0 else "skin %d" % n, " + ".join(notes)), files=files, source=src, note=", ".join(notes))
        self.on_skin(None); self.app.refresh_pack(); self.app.busy("Added %s %s art to the pack (%s)." % (name, "default skin" if n == 0 else "skin %d" % n, ", ".join(notes)))
