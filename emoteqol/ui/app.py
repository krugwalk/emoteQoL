import os, sys, json, threading, queue, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from emoteqol.core import emotes as C
from emoteqol.ui import skin_tab
from emoteqol.ui import size_preview
from emoteqol.core import styles as PS
import time
from emoteqol.ui import trimbar
import bisect
from emoteqol import updater
from emoteqol import installer

SETTINGS = os.path.join(C.APPDATA, "settings.json")
def load_settings():
    try: return json.load(open(SETTINGS))
    except Exception: return {}
def save_settings(s): json.dump(s, open(SETTINGS, "w"))

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("EmoteQoL v%s - emotes, loading screens and HUD portraits with your own pictures" % updater.VERSION); self.geometry("1180x1050"); self.minsize(1000, 800)
        self.set = load_settings(); self.game = None; self.cat = []; self.cur = None; self.pack = C.Pack(); self.icons = {}; self.photo_refs = {}; self.q = queue.Queue()
        self.cur_i = 0; self.times = []; self.clip_total = 0.0; self.trim_t = (0.0, 0.0); self.trim_idx = (0, 0); self.popup_T = 2.3; self.style_src = None; self.style_templates = []; self.popup_job = None; self.popup_playing = False; self.sound_keep = None; self.repl_path = None; self.mem_frames = None; self.repl_frames = []; self.repl_durs = []; self.anim_job = None; self.matches = []
        self._ui(); self.after(100, self._poll); self.after(200, self.open_game); self.after(2500, lambda: updater.check_async(lambda r: self.q.put(lambda: self.show_update(r))))

    def _ui(self):
        st = ttk.Style(self); st.configure("Treeview", rowheight=44)
        self.update_bar = tk.Frame(self, bg="#fff4cc"); self.update_lbl = tk.Label(self.update_bar, bg="#fff4cc", fg="#4a3b00", anchor="w", padx=10, pady=5); self.update_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(self.update_bar, text="Dismiss", command=self.dismiss_update, relief="flat", bg="#fff4cc").pack(side="right", padx=6); self.update_btn = tk.Button(self.update_bar, text="Update now", relief="groove"); self.update_btn.pack(side="right", padx=4)
        top = ttk.Frame(self); top.pack(fill="x", padx=8, pady=6); self.top_frame = top
        self.game_lbl = ttk.Label(top, text="Game folder: (not set)"); self.game_lbl.pack(side="left"); ttk.Button(top, text="Change...", command=self.pick_game).pack(side="left", padx=8)
        ttk.Button(top, text="Open .fantome...", command=self.open_fantome).pack(side="right"); ttk.Button(top, text="New pack", command=self.new_pack).pack(side="right", padx=6); self.check_btn = ttk.Button(top, text="Check for updates", command=self.check_updates_now); self.check_btn.pack(side="right")
        nb = ttk.Notebook(self); self.nb = nb; tab_e = ttk.Frame(nb); nb.add(tab_e, text="  Emotes  ")
        main = ttk.PanedWindow(tab_e, orient="horizontal"); main.pack(fill="both", expand=True, padx=4, pady=4)
        left = ttk.Frame(main); main.add(left, weight=1)
        sf = ttk.Frame(left); sf.pack(fill="x"); ttk.Label(sf, text="Search emotes:").pack(side="left"); self.sv = tk.StringVar(); self.sv.trace_add("write", lambda *a: self.refilter())
        ttk.Entry(sf, textvariable=self.sv).pack(side="left", fill="x", expand=True, padx=6); self.count_lbl = ttk.Label(sf, text=""); self.count_lbl.pack(side="right")
        self.tree = ttk.Treeview(left, columns=("group",), show="tree headings", selectmode="browse"); self.tree.heading("#0", text="Emote"); self.tree.heading("group", text="Folder"); self.tree.column("#0", width=260); self.tree.column("group", width=140)
        sb = ttk.Scrollbar(left, command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set); self.tree.pack(side="left", fill="both", expand=True, pady=4); sb.pack(side="left", fill="y", pady=4)
        self.tree.bind("<<TreeviewSelect>>", self.on_select); self.placeholder = ImageTk.PhotoImage(Image.new("RGB", (40, 40), (70, 70, 70))); self.iconq = queue.Queue(); self.requested = set()
        threading.Thread(target=self._icon_worker, daemon=True).start(); self.after(300, self._icon_tick)
        right = ttk.Frame(main); main.add(right, weight=1)
        self.cur_name = ttk.Label(right, text="Pick an emote on the left", font=("Segoe UI", 13, "bold")); self.cur_name.pack(anchor="w")
        row = ttk.Frame(right); row.pack(fill="x", pady=6)
        box1 = ttk.LabelFrame(row, text="In game, above your champion"); box1.pack(side="left", padx=4); self.scene_lbl = ttk.Label(box1); self.scene_lbl.pack(padx=6, pady=(6, 2)); self.scene_photo = None
        self.pop_btn = ttk.Button(box1, text="Pop up", command=self.play_popup, state="disabled"); self.pop_btn.pack(pady=(0, 6))
        box2 = ttk.LabelFrame(row, text="Your replacement - drag to move, drag the edges / corners to stretch"); box2.pack(side="left", padx=4)
        self.cv = tk.Canvas(box2, width=self.CS, height=self.CS, bg="#262626", highlightthickness=0); self.cv.pack(padx=6, pady=6)
        self.rect = (0.0, 0.0, 1.0, 1.0); self.drag = None; self.cv_photo = None; self.edit_src = []; self.checker = self._make_checker()
        self.cv.bind("<Button-1>", self._cv_down); self.cv.bind("<B1-Motion>", self._cv_move); self.cv.bind("<ButtonRelease-1>", self._cv_up); self.cv.bind("<Motion>", self._cv_hover); self.cv.bind("<MouseWheel>", self._cv_wheel)
        self.trim = trimbar.TrimBar(box2, self.CS, self.on_trim); self.trim.pack(padx=6, pady=(0, 6))
        self.draw_editor()
        self.src_lbl = ttk.Label(right, text="No image chosen"); self.src_lbl.pack(anchor="w")
        pr = ttk.Frame(right); pr.pack(fill="x", pady=4); ttk.Button(pr, text="Choose GIF / image / video...", command=self.pick_image).pack(side="left")
        self.vid_sound_v = tk.BooleanVar(value=False); self.vid_sound_cb = ttk.Checkbutton(pr, text="Use this video's sound", variable=self.vid_sound_v, command=self.toggle_video_sound, state="disabled"); self.vid_sound_cb.pack(side="left", padx=12); ttk.Button(pr, text="Reset position / size", command=self.reset_adj).pack(side="left", padx=6); ttk.Label(pr, text="Popup animation:").pack(side="left", padx=(14, 4)); self.style_v = tk.StringVar(value=self.STYLE_OWN)
        self.style_cb = ttk.Combobox(pr, textvariable=self.style_v, values=[self.STYLE_OWN], width=27, state="disabled"); self.style_cb.pack(side="left"); self.style_cb.bind("<<ComboboxSelected>>", self.on_style_choice)
        opt = ttk.LabelFrame(right, text="Options"); opt.pack(fill="x", pady=4)
        self.anim_v = tk.BooleanVar(value=True); ttk.Checkbutton(opt, text="Animate in game (GIF -> flipbook)", variable=self.anim_v).grid(row=0, column=0, columnspan=2, sticky="w", padx=6)
        self.size_v = tk.DoubleVar(value=100.0); self.size_lbl = ttk.Label(opt, text="In-game size: 100%", width=18); self.size_lbl.grid(row=0, column=2, sticky="e", padx=(14, 4))
        self.size_scale = ttk.Scale(opt, from_=20, to=200, variable=self.size_v, length=170, command=self._size_changed); self.size_scale.grid(row=0, column=3, columnspan=2, sticky="w")
        ttk.Label(opt, text="Fit:").grid(row=1, column=0, sticky="w", padx=6); self.fit_v = tk.StringVar(value="contain"); cb = ttk.Combobox(opt, textvariable=self.fit_v, values=["contain", "cover", "stretch"], width=10, state="readonly"); cb.grid(row=1, column=1, sticky="w"); cb.bind("<<ComboboxSelected>>", lambda ev: self.refresh_preview())
        ttk.Label(opt, text="GIF speed (%):").grid(row=1, column=2, sticky="e", padx=(14, 4)); self.loops_v = tk.DoubleVar(value=100.0); self.loops_v.trace_add("write", lambda *a: self.after_idle(self.update_marker)); ttk.Spinbox(opt, from_=10, to=500, increment=10, textvariable=self.loops_v, width=6).grid(row=1, column=3, sticky="w"); ttk.Label(opt, text="100 = the GIF's own speed", foreground="#666").grid(row=1, column=4, sticky="w", padx=6)
        sl = ttk.Frame(right); sl.pack(fill="x", pady=2); ttk.Label(sl, text="Sound length:").pack(side="left", padx=6)
        self.snd_max_v = tk.DoubleVar(value=6.0); self.snd_len = ttk.Scale(sl, from_=0.3, to=6.0, variable=self.snd_max_v, command=lambda v: self._len_label(), length=300); self.snd_len.pack(side="left", padx=4); self.snd_len.state(["disabled"])
        self.snd_len_lbl = ttk.Label(sl, text="(pick a sound first)", foreground="#666"); self.snd_len_lbl.pack(side="left", padx=6); self.snd_total = 6.0
        sb_ = ttk.LabelFrame(right, text="Sound (optional - leave empty to keep the emote's normal sound)"); sb_.pack(fill="x", pady=4); self.sound_path = None; self.sound_game = None
        ttk.Button(sb_, text="Choose sound...", command=self.pick_sound).grid(row=0, column=0, padx=6, pady=4); self.sound_lbl = ttk.Label(sb_, text="none - the emote keeps its normal sound", wraplength=330); self.sound_lbl.grid(row=0, column=1, sticky="w")
        ttk.Button(sb_, text="Clear", command=self.clear_sound).grid(row=0, column=2, padx=6); ttk.Button(sb_, text="Use another emote's sound...", command=self.pick_game_sound).grid(row=0, column=3, padx=6)
        r3 = ttk.Frame(sb_); r3.grid(row=1, column=0, columnspan=4, sticky='w', padx=6)
        ttk.Label(r3, text="Volume (dB, 0 = the game's own):").pack(side='left'); self.snd_boost_v = tk.DoubleVar(value=0.0); ttk.Spinbox(r3, from_=-30, to=30, increment=1, textvariable=self.snd_boost_v, width=5).pack(side='left', padx=4); ttk.Button(r3, text='Play preview', command=self.play_preview).pack(side='left', padx=(10, 2)); ttk.Button(r3, text='Stop', command=self.stop_preview).pack(side='left'); ttk.Button(r3, text='Find LtMAO...', command=self.find_ltmao).pack(side='left', padx=10)
        self.ltmao_lbl = ttk.Label(r3, text='', foreground='#666'); self.ltmao_lbl.pack(side='left')
        ttk.Label(sb_, text='Your own mp3/wav/ogg/mp4 is converted with the Wwise that comes with LtMAO. Shorten it with the Sound length slider.', foreground='#666', wraplength=520).grid(row=2, column=0, columnspan=4, sticky='w', padx=6, pady=(0, 4))
        self.profile_lbl = ttk.Label(sb_, text="", foreground="#444", wraplength=520, justify="left"); self.profile_lbl.grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 4)); self.profile_job = None
        self.snd_boost_v.trace_add("write", lambda *a: self.after_idle(self.refresh_profile))
        self.after(600, self._ltmao_status)
        self.add_btn = ttk.Button(right, text="Add replacement to pack  >>", command=self.add_to_pack, state="disabled"); self.add_btn.pack(anchor="w", pady=6)
        self.log = tk.Text(right, height=1, wrap="word", state="disabled"); self.log.pack(fill="x")
        bot = ttk.LabelFrame(self, text="Pack (what will be in the .fantome)"); bot.pack(fill="both", padx=8, pady=6)
        self.ptree = ttk.Treeview(bot, columns=("src", "note"), show="tree headings", height=3); self.ptree.heading("#0", text="Emote replaced"); self.ptree.heading("src", text="Replacement"); self.ptree.heading("note", text="Notes")
        self.ptree.column("#0", width=230); self.ptree.column("src", width=220); self.ptree.column("note", width=520); self.ptree.pack(fill="x", padx=4, pady=4)
        r2 = ttk.Frame(bot); r2.pack(fill="x", padx=4, pady=4)
        ttk.Button(r2, text="Remove selected", command=self.remove_selected).pack(side="left"); ttk.Button(r2, text="View / edit selected", command=self.view_selected).pack(side="left", padx=6)
        self.ptree.bind("<Double-Button-1>", self.view_selected)
        self.name_v, self.auth_v, self.lic_v = tk.StringVar(value="My Emotes"), tk.StringVar(), tk.StringVar()
        for lab, v, w in (("Name", self.name_v, 18), ("Author", self.auth_v, 14), ("License", self.lic_v, 12)):
            ttk.Label(r2, text="  " + lab + ":").pack(side="left"); ttk.Entry(r2, textvariable=v, width=w).pack(side="left")
        ttk.Button(r2, text="Save .fantome...", command=self.save_fantome).pack(side="right")
        self.pop_v = tk.BooleanVar(value=True); ttk.Checkbutton(r2, text="Silence the emote pop (all emotes)", variable=self.pop_v, command=lambda: setattr(self.pack, "silence_pop", self.pop_v.get())).pack(side="right", padx=10)
        sbar = ttk.Frame(self); sbar.pack(fill="x", padx=8, pady=(0, 6))
        self.status = ttk.Label(sbar, text="", anchor="w"); self.status.pack(side="left", fill="x", expand=True)
        cr = ttk.Label(sbar, text="Sound replacement method: LtMAO by tarngaina", foreground="#2a6fd6", cursor="hand2"); cr.pack(side="right")
        cr.bind("<Button-1>", lambda ev: __import__("webbrowser").open("https://github.com/tarngaina/LtMAO"))
        self.skin_tab = skin_tab.SkinTab(nb, self); nb.add(self.skin_tab, text='  Loading screen / HUD  ')
        for w_ in (nb, bot, sbar): w_.pack_forget()
        sbar.pack(side="bottom", fill="x", padx=8, pady=(0, 6)); bot.pack(side="bottom", fill="x", padx=8, pady=6); nb.pack(fill="both", expand=True, padx=8)

    def say(self, msg):
        self.log.configure(state="normal"); self.log.insert("end", msg + "\n"); self.log.see("end"); self.log.configure(state="disabled")
    def busy(self, msg): self.status.configure(text=msg); self.update_idletasks()
    def run_bg(self, fn, done):
        def w():
            try: r = fn(); self.q.put(lambda: done(r, None))
            except Exception as e: tb = traceback.format_exc(); self.q.put(lambda: done(None, tb))
        threading.Thread(target=w, daemon=True).start()
    def check_updates_now(self):
        self.check_btn.configure(state="disabled", text="Checking...")
        def done(r, err):
            self.check_btn.configure(state="normal", text="Check for updates")
            status, info = r if r else ("error", None)
            if status == "update": self.show_update(info, force=True)
            elif status == "current": messagebox.showinfo("Check for updates", "You have the latest version (v%s)." % updater.VERSION)
            else: messagebox.showinfo("Check for updates", "Could not reach GitHub to look for a new version. Check your internet connection and try again.")
        self.run_bg(updater.check_status, done)
    def show_update(self, result, force=False):
        if not result: return
        tag = result["tag"]
        if self.set.get("dismissed_update") == tag and not force: return
        self.update_info = result; self.update_tag = tag
        can_install = bool(getattr(sys, "frozen", False) and result.get("asset_url"))
        self.update_lbl.configure(text="A newer version is available: %s (you are running v%s)." % (tag, updater.VERSION))
        self.update_btn.configure(text="Update now" if can_install else "Open download page", state="normal", command=self.install_update if can_install else self.open_update_page)
        self.update_bar.pack(side="top", fill="x", before=self.top_frame)
    def open_update_page(self): __import__("webbrowser").open(self.update_info["url"])
    def install_update(self):
        info = self.update_info; tag = info["tag"]; dest = os.path.join(__import__("tempfile").gettempdir(), "EmoteQoL_update.exe")
        self.update_btn.configure(state="disabled", text="Updating..."); self.update_lbl.configure(text="Downloading EmoteQoL %s ..." % tag)
        def progress(done, total): self.q.put(lambda: self.update_lbl.configure(text="Downloading EmoteQoL %s ... %d%%" % (tag, (100 * done // total) if total else 0)))
        def work(): return updater.download(info["asset_url"], dest, info.get("size"), info.get("digest"), progress)
        def done(r, err):
            if err:
                self.update_lbl.configure(text="The update could not be installed (%s)." % (err.strip().splitlines()[-1][:120] if err else ""))
                self.update_btn.configure(text="Open download page", state="normal", command=self.open_update_page); return
            self.update_lbl.configure(text="Installing %s and restarting..." % tag); self.update()
            updater.apply_and_restart(r, installer.exe_path()); self.after(400, self.destroy)
        self.run_bg(work, done)
    def dismiss_update(self):
        self.set["dismissed_update"] = getattr(self, "update_tag", ""); save_settings(self.set); self.update_bar.pack_forget()
    def _poll(self):
        try:
            while True: self.q.get_nowait()()
        except queue.Empty: pass
        self.after(100, self._poll)
    def photo(self, img, size, key=None):
        im = img.copy(); im.thumbnail((size, size)); bg = Image.new("RGBA", im.size, (60, 60, 60, 255)); bg.alpha_composite(im); p = ImageTk.PhotoImage(bg.convert("RGB"))
        self.photo_refs[key or id(p)] = p; return p

    def pick_game(self):
        d = filedialog.askdirectory(title="Pick your League of Legends folder (the one that contains the 'Game' folder)")
        if not d: return
        r = C.resolve_final(d)
        if not r: return messagebox.showerror("Not League", "Could not find Global.wad.client inside that folder. Pick the 'League of Legends' folder.")
        self.set["game"] = r; save_settings(self.set); self.open_game()
    def open_game(self):
        path = self.set.get("game")
        if not path or not os.path.exists(os.path.join(path, "Global.wad.client")):
            path = C.detect_league()
            if path: self.set["game"] = path; save_settings(self.set)
            else:
                messagebox.showinfo("League of Legends", "I couldn't find your League installation automatically. Please pick the League of Legends folder.")
                return self.pick_game()
        self.game_lbl.configure(text="Game folder: " + path); self.busy("Reading the emote list from your game (first time takes a few seconds)...")
        def job(): g = C.Game(path); return g, C.build_catalogue(g)
        def done(r, err):
            if err: self.busy("Could not read the game files."); return messagebox.showerror("Error", err)
            self.game, self.cat = r; self.busy("%d emotes found. Pick one, choose your image, add it to the pack." % len(self.cat)); self.refilter(); self.skin_tab.start(); self.run_bg(lambda: PS.harvest(self.game), lambda r, e: self.styles_loaded())
        self.run_bg(job, done)
    def refilter(self):
        q = self.sv.get().strip().lower(); words = q.split()
        self.matches = [e for e in self.cat if all(w in (e["name"] + " " + e["group"] + " " + e["key"]).lower() for w in words)] if q else list(self.cat); self.fill()
    def fill(self):
        self.tree.delete(*self.tree.get_children()); self.count_lbl.configure(text="%d emote%s" % (len(self.matches), "" if len(self.matches) == 1 else "s"))
        for i, e in enumerate(self.matches):
            k = (e["key"], 40); self.tree.insert("", "end", iid=str(i), text="  " + e["name"], values=(e["group"],), image=self.photo_refs.get(k, self.placeholder))
        self.tree.yview_moveto(0)
    def icon_for(self, e, size):
        k = (e["key"], size)
        if k not in self.photo_refs: self.request_icon(e)
        return self.photo_refs.get(k, self.placeholder)
    def request_icon(self, e):
        if e["key"] in self.requested or not self.game: return
        self.requested.add(e["key"]); self.iconq.put(e)
    def _icon_worker(self):
        while True:
            e = self.iconq.get()
            try: im = C.decode_tex(self.game.read(e["inv"]))
            except Exception: continue
            self.q.put(lambda e=e, im=im: self._icon_ready(e, im))
    def _icon_ready(self, e, im):
        k = (e["key"], 40); self.photo_refs[k] = self.photo(im, 40, k)
        for iid in self._visible_iids():
            if self.matches[int(iid)]["key"] == e["key"]: self.tree.item(iid, image=self.photo_refs[k])
        if self.ptree.exists(e["key"]): self.ptree.item(e["key"], image=self.photo_refs[k])
    def _visible_iids(self):
        n = len(self.matches); 
        if not n: return []
        a, b = self.tree.yview(); lo = max(0, int(a * n) - 3); hi = min(n, int(b * n) + 4); return [str(i) for i in range(lo, hi)]
    def _icon_tick(self):
        try:
            if self.game and self.iconq.qsize() < 80:
                for iid in self._visible_iids():
                    e = self.matches[int(iid)]
                    if (e["key"], 40) not in self.photo_refs: self.request_icon(e)
                    else: self.tree.item(iid, image=self.photo_refs[(e["key"], 40)])
        finally: self.after(150, self._icon_tick)
    def on_select(self, ev):
        s = self.tree.selection()
        if not s: return
        self.cur = self.matches[int(s[0])]; self.cur_name.configure(text=self.cur["name"] + "   (" + self.cur["group"] + ")")
        self.update_add(); self.update_scene(); self.refresh_popup_len()
        if not getattr(self, "loading_pack", False): self.reset_for_emote(self.cur)
        self.refresh_profile()
    def reset_for_emote(self, em):
        self.stop_popup(); self.clear_sound(); self.snd_boost_v.set(0.0); self.size_v.set(100); self._size_changed(); self.anim_v.set(True); self.loops_v.set(100.0); self.set_style(None, play=False)
        if self.mem_frames is not None:
            if self.anim_job: self.after_cancel(self.anim_job); self.anim_job = None
            self.repl_path = None; self.repl_frames = []; self.repl_durs = []; self.edit_src = []; self.mem_frames = None
            self.src_lbl.configure(text="No image chosen"); self.times = []; self.setup_clip(); self.draw_editor(); self.update_add()
        entry = self.pack.emotes.get(em["key"])
        if not entry: return
        try: res = C.extract_frames(em, entry["files"], self.pack.other)
        except Exception: res = None
        if res: self.edit_from_pack(em, res[0], res[1])
        else:
            st = entry.get("settings") or {}
            self.restore_sound_and_size(em); self.restore_style(em); self.update_add()
    def big_icon(self, e):
        k = (e["key"], 160)
        if k not in self.photo_refs:
            try: self.photo_refs[k] = self.photo(C.decode_tex(self.game.read(e["inv"])), 160, k)
            except Exception: self.photo_refs[k] = ImageTk.PhotoImage(Image.new("RGB", (160, 160), (70, 70, 70)))
        return self.photo_refs[k]

    def pick_image(self):
        p = filedialog.askopenfilename(title="Choose a GIF, image or video", filetypes=[("GIF / images / video", "*.gif *.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.webm *.mov *.mkv *.avi *.m4v"), ("All files", "*.*")])
        if not p: return
        self.mem_frames = None
        try: self.repl_frames, self.repl_durs = C.load_frames(p)
        except Exception as e: return messagebox.showerror("Could not open", str(e))
        self.edit_src = []
        for f in self.repl_frames:
            if f.mode == "RGBA" and max(f.size) <= 700: self.edit_src.append(f)
            else: g = f.convert("RGBA"); g.thumbnail((700, 700), Image.LANCZOS); self.edit_src.append(g)
        if self.sound_path and self.sound_path == self.repl_path and self.sound_path != p: self.clear_sound()
        self.repl_path = p; self.setup_clip(); kind = "video, converted to a GIF" if C.is_video(p) else ""
        self.src_lbl.configure(text="%s   (%d frame%s%s)" % (os.path.basename(p), len(self.repl_frames), "" if len(self.repl_frames) == 1 else "s", ", " + kind if kind else "")); self.reset_adj(); self.play(0); self.update_add()
        self.vid_sound_v.set(False); self.vid_sound_cb.configure(state="disabled")
        if C.is_video(p):
            from emoteqol.core import audio as A
            self.run_bg(lambda: A.audio_duration(p), lambda r, err: self.vid_sound_cb.configure(state="normal" if (r and self.repl_path == p) else "disabled"))
    def adj(self): return tuple(float(v) for v in self.rect)
    def reset_adj(self):
        if self.repl_frames: w, h = self.repl_frames[0].size; self.rect = C.preset_rect(w, h, self.fit_v.get())
        else: self.rect = (0.0, 0.0, 1.0, 1.0)
        self.draw_editor()
    def refresh_preview(self): self.reset_adj()
    CS, F, M = 242, 166, 38
    def _make_checker(self):
        im = Image.new("RGBA", (self.F, self.F), (90, 90, 90, 255)); px = im.load()
        for y in range(self.F):
            for x in range(self.F):
                if ((x // 10) + (y // 10)) % 2: px[x, y] = (120, 120, 120, 255)
        return im
    def draw_editor(self):
        M, F, CS = self.M, self.F, self.CS; self.cv.delete("all"); dark = Image.new("RGBA", (CS, CS), (38, 38, 38, 255))
        if self.edit_src:
            src = self.edit_src[self.cur_i % len(self.edit_src)]; x0, y0, x1, y1 = self.rect
            w, h = max(1, min(4000, round((x1 - x0) * F))), max(1, min(4000, round((y1 - y0) * F))); res = src.resize((w, h), Image.BILINEAR)
            layer = Image.new("RGBA", (CS, CS), (0, 0, 0, 0)); layer.paste(res, (M + round(x0 * F), M + round(y0 * F)))
            dim = layer.copy(); dim.putalpha(layer.getchannel("A").point(lambda v: int(v * 0.35)))
            out = Image.alpha_composite(dark, dim); inner = self.checker.copy(); inner.alpha_composite(layer.crop((M, M, M + F, M + F))); out.paste(inner, (M, M))
        else:
            out = dark; out.paste(self.checker, (M, M))
        self.cv_photo = ImageTk.PhotoImage(out.convert("RGB")); self.cv.create_image(0, 0, image=self.cv_photo, anchor="nw"); self.update_scene()
        self.cv.create_rectangle(M, M, M + F, M + F, outline="#ffffff", width=2)
        if self.edit_src:
            bx0, by0, bx1, by1 = self._box(); self.cv.create_rectangle(bx0, by0, bx1, by1, outline="#4da3ff", dash=(4, 3))
            for hx, hy in self._handles(): self.cv.create_rectangle(hx - 5, hy - 5, hx + 5, hy + 5, fill="#4da3ff", outline="white")
        else: self.cv.create_text(CS // 2, CS // 2, text="Choose a GIF / image", fill="#bbbbbb")
    def _box(self): x0, y0, x1, y1 = self.rect; M, F = self.M, self.F; return (M + x0 * F, M + y0 * F, M + x1 * F, M + y1 * F)
    def _handles(self):
        x0, y0, x1, y1 = self._box(); mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return [(x0, y0), (mx, y0), (x1, y0), (x1, my), (x1, y1), (mx, y1), (x0, y1), (x0, my)]
    HANDLE_ID = ["nw", "n", "ne", "e", "se", "s", "sw", "w"]
    CURSORS = {"nw": "size_nw_se", "se": "size_nw_se", "ne": "size_ne_sw", "sw": "size_ne_sw", "n": "sb_v_double_arrow", "s": "sb_v_double_arrow", "e": "sb_h_double_arrow", "w": "sb_h_double_arrow", "move": "fleur"}
    def _hit(self, x, y):
        if not self.edit_src: return None
        for (hx, hy), name in zip(self._handles(), self.HANDLE_ID):
            if abs(x - hx) <= 9 and abs(y - hy) <= 9: return name
        x0, y0, x1, y1 = self._box()
        return "move" if x0 <= x <= x1 and y0 <= y <= y1 else None
    def _cv_hover(self, ev): hit = self._hit(ev.x, ev.y); self.cv.configure(cursor=self.CURSORS.get(hit, ""))
    def _cv_down(self, ev):
        hit = self._hit(ev.x, ev.y)
        if hit: self.drag = dict(hit=hit, x=ev.x, y=ev.y, rect=self.rect)
    def _cv_up(self, ev): self.drag = None
    def _cv_move(self, ev):
        d = self.drag
        if not d: return
        F = self.F; dx, dy = (ev.x - d["x"]) / F, (ev.y - d["y"]) / F; x0, y0, x1, y1 = d["rect"]; hit = d["hit"]; mn = 0.03
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
        self.rect = (x0, y0, x1, y1); self.draw_editor()
    def _cv_wheel(self, ev):
        if not self.edit_src: return
        k = 1.06 if ev.delta > 0 else 1 / 1.06; x0, y0, x1, y1 = self.rect; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; hw, hh = (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
        if hw * 2 < 0.03 or hh * 2 < 0.03 or hw * 2 > 8: return
        self.rect = (cx - hw, cy - hh, cx + hw, cy + hh); self.draw_editor()
    def play(self, i):
        if self.anim_job: self.after_cancel(self.anim_job); self.anim_job = None
        if not self.repl_frames: return
        lo, hi = self.trim_idx
        if len(self.repl_frames) > 1 and (i < lo or i > hi): i = lo
        self.cur_i = i % len(self.repl_frames); self.draw_editor()
        if self.times and self.cur_i < len(self.times): self.trim.set_playhead(self.times[self.cur_i])
        if len(self.repl_frames) > 1: self.anim_job = self.after(self.frame_delay_ms(i), lambda: self.play(i + 1))
    def setup_clip(self):
        self.times = []; t = 0.0
        for d in self.repl_durs: self.times.append(t); t += d
        self.clip_total = t if len(self.repl_frames) > 1 else 0.0; self.trim_t = (0.0, self.clip_total); self.trim_idx = (0, max(0, len(self.repl_frames) - 1))
        self.trim.set_clip(self.clip_total); self.update_marker()
    def on_trim(self, t0, t1):
        n = len(self.times)
        if not n: return
        lo = bisect.bisect_left(self.times, t0 - 1e-6); hi = bisect.bisect_left(self.times, t1 - 1e-6) - 1
        lo = min(lo, n - 1); hi = max(lo, min(hi, n - 1)); self.trim_t = (t0, t1); self.trim_idx = (lo, hi); self.update_marker(); self.play(lo)
    def update_marker(self):
        try: sp = max(0.1, float(self.loops_v.get()) / 100.0)
        except Exception: sp = 1.0
        self.trim.set_speed(sp); self.trim.set_marker(self.trim_t[0] + self.popup_T * sp)
    def refresh_popup_len(self):
        if not self.cur or not self.game: return
        em = self.cur; game = self.game
        def work():
            best = 0.0
            for bh in C.emote_bins(game):
                d = game.read(bh)
                if d and em["vfx"].lower().encode() in d.lower():
                    try: best = max(best, C.popup_length(d, em["vfx"]))
                    except Exception: pass
            return best
        def done(r, err):
            if self.cur is em and r: self.popup_T = r; self.update_marker()
        self.run_bg(work, done)
    def frame_delay_ms(self, i):
        try: sp = max(0.1, float(self.loops_v.get()) / 100.0)
        except Exception: sp = 1.0
        return max(15, int(self.repl_durs[i % len(self.repl_durs)] * 1000 / sp))
    def update_scene(self):
        if not hasattr(self, "scene_lbl") or self.popup_playing: return
        pic = None
        if self.edit_src:
            try: pic = C.fit_frame(self.edit_src[self.cur_i % len(self.edit_src)], 160, self.fit_v.get(), self.adj())
            except Exception: pic = None
        try: pct = int(round(self.size_v.get()))
        except Exception: pct = 100
        self.scene_photo = ImageTk.PhotoImage(size_preview.render_small(pct, pic, 0.37)); self.scene_lbl.configure(image=self.scene_photo)
    def _size_changed(self, v=None):
        r = int(round(float(self.size_v.get()) / 5.0) * 5); self.size_v.set(r); self.size_lbl.configure(text="In-game size: %d%%" % r); self.update_add()
        self.update_scene()
    def update_add(self): self.add_btn.configure(state="normal" if (self.cur and self.game and (self.repl_path or self.sound_path or self.sound_game or self.style_src or int(round(self.size_v.get())) != 100)) else "disabled")
    def _len_label(self):
        v = self.snd_max_v.get(); self.snd_len_lbl.configure(text="%.1f s of %.1f s%s" % (v, self.snd_total, "   (long sound effects get cut by the game)" if v > 8 else ""))
    def set_sound_file(self, path):
        from emoteqol.core import audio as A
        self.sound_path = path; self.sound_game = None; self.sound_lbl.configure(text=os.path.basename(path)); self.snd_len_lbl.configure(text="reading the length..."); self.update_add()
        def done(r, err):
            if self.sound_path != path: return
            if not r: self.snd_total = 6.0; self.snd_len.state(["disabled"]); self.snd_len_lbl.configure(text="(a ready-made .wem is used as it is)" if path.lower().endswith(".wem") else "length unknown"); return
            self.snd_total = min(15.0, max(0.5, r)); self.snd_len.configure(from_=0.3, to=self.snd_total); self.snd_len.state(["!disabled"]); self.snd_max_v.set(self.snd_total if self.snd_total <= 6 else 6.0); self._len_label()
        self.run_bg(lambda: A.audio_duration(path), done)
    def toggle_video_sound(self):
        if self.vid_sound_v.get() and self.repl_path and C.is_video(self.repl_path): self.set_sound_file(self.repl_path); self.sound_lbl.configure(text="sound of the video: " + os.path.basename(self.repl_path))
        elif self.sound_path and self.sound_path == self.repl_path: self.clear_sound()

    def add_to_pack(self):
        e = self.cur; path = self.repl_path; animated = self.anim_v.get(); fit = self.fit_v.get(); loops = float(self.loops_v.get()); adj = self.adj()
        size = int(round(self.size_v.get())); flat = True; opa = 0; qual = "compact"
        self.busy("Building the replacement for '%s'..." % e["name"]); self.add_btn.configure(state="disabled")
        t0, t1 = self.trim_t; popup_T = self.popup_T; lo, hi = self.trim_idx; cut = bool(path and len(self.repl_frames) > 1 and (hi - lo + 1) < len(self.repl_frames)); piece = (self.repl_frames[lo:hi + 1], self.repl_durs[lo:hi + 1]) if cut else None
        vstart = t0 if (self.sound_path and self.sound_path == path and C.is_video(path)) else 0.0
        sty = self.style_src; spath = self.sound_path; sgame = self.sound_game; keep = self.sound_keep if not (self.sound_path or self.sound_game) else None; mem = (piece or (self.repl_frames, self.repl_durs)) if (path and not os.path.exists(path) and self.repl_frames) else None
        try: smax = max(0.3, float(self.snd_max_v.get()))
        except Exception: smax = 6.0
        try: sboost = min(30.0, max(-30.0, float(self.snd_boost_v.get())))
        except Exception: sboost = 0.0
        def job():
            import tempfile; from emoteqol.core import audio as A
            pre = mem or (C.load_video_range(path, t0, min(t1, t0 + max(4.0, popup_T * loops / 100.0 + 1.0))) if (path and C.is_video(path)) else piece)
            style = None
            if sty:
                src = PS.source_for(self.game, sty["vfx"])
                if src: style = (src[0], src[1], sty["label"])
            files, notes = C.build_replacement(self.game, e, path, animated, fit, loops, None, adj, opa, qual, size, pre, flat, style) if path else (C.build_size_only(self.game, e, size, flat, style) if (size != 100 or style) else ({}, [])); snd = None
            if spath or sgame:
                from emoteqol.core import audio as A
                ev = A.event_for_emote(self.game, e, C.emote_bins(self.game))
                if not ev: notes.append("sound: this emote's sound event wasn't found, so its sound is unchanged")
                elif not A.bank_pair_for_event(self.game, ev): notes.append("sound: event %s wasn't found in any of the game's sound banks, so its sound is unchanged" % ev)
                elif sgame and A.bank_pair_for_event(self.game, ev) != A.bank_pair_for_event(self.game, sgame["event"]):
                    swem, slv = A.first_audible_wem(self.game, sgame["event"])
                    if not swem: notes.append("sound: the sound of '%s' could not be read, so the sound is unchanged" % sgame["name"])
                    else:
                        wav = tempfile.mktemp(suffix=".wav"); note = "plays the in-game sound of %s" % sgame["name"]
                        if A.wem_to_wav(swem, wav):
                            try: swem, pcm, note = A.make_wem(wav, smax, -4.0, "Evened out", 0.0)[0], False, "plays the in-game sound of %s (evened to the loudness of custom sounds)" % sgame["name"]
                            except Exception: pass
                            try: os.remove(wav)
                            except Exception: pass
                        snd = dict(event=ev, wem=swem, pcm=False, level=A.stock_level(self.game, ev) + sboost, source="sound of '%s'" % sgame["name"], note=note); notes.append("sound: plays the in-game sound of '%s'" % sgame["name"])
                elif sgame:
                    snd = dict(event=ev, wem=None, pcm=False, retarget=sgame["event"], source="sound of '%s'" % sgame["name"], note="plays the in-game sound of %s" % sgame["name"]); notes.append("sound: plays the in-game sound of '%s'" % sgame["name"])
                else:
                    wem, pcm, note = A.make_wem(spath, min(smax, (t1 - t0) if vstart else smax), -4.0, "Evened out", vstart); snd = dict(event=ev, wem=wem, pcm=pcm, level=A.stock_level(self.game, ev) + sboost, source=os.path.basename(spath), note=note); notes.append("sound (%s): %s" % (ev, note))
            elif keep and keep.get("level") is not None and abs(A.stock_level(self.game, keep["event"]) + sboost - keep["level"]) > 0.01:
                from emoteqol.core import audio as A
                snd = dict(event=keep["event"], keep=True, wem=None, pcm=False, level=A.stock_level(self.game, keep["event"]) + sboost, source="current sound, volume changed", note="volume %+g dB from the game's own" % sboost); notes.append("sound: kept, volume %+g dB from the game's own" % sboost)
            return files, notes, snd
        def done(r, err):
            self.update_add()
            if err: self.busy("Failed."); self.say("ERROR: " + err); return messagebox.showerror("Error", err[-600:])
            files, notes, snd = r; self.pack.add(e, files, os.path.basename(path) if path else ("(size only)" if not spath and not sgame else "(sound only)"), "; ".join(notes), dict(animate=bool(animated), speed=float(loops), fit=fit, size=int(size), style=(dict(label=sty["label"], vfx=sty["vfx"], name=sty.get("name")) if sty else None)))
            if snd: self.pack.sounds[e["key"]] = snd
            else: self.pack.sounds.pop(e["key"], None)
            lost = [n for n in notes if n.startswith("sound:") and "unchanged" in n]
            if (spath or sgame) and not snd and lost: messagebox.showwarning("The sound was not added", chr(10).join(lost))
            self.say("%s: %s" % (e["name"], "; ".join(notes) or ("icons and popup replaced" if path else "nothing changed"))); self.refresh_pack(); self.busy("Added '%s' to the pack." % e["name"])
        self.run_bg(job, done)
    def pick_sound(self):
        p = filedialog.askopenfilename(title="Choose a sound", filetypes=[("Sound", "*.wem *.wav *.mp3 *.ogg *.mp4 *.m4a *.flac"), ("All files", "*.*")])
        if p: self.vid_sound_v.set(False); self.sound_keep = None; self.set_sound_file(p)
    def _ltmao_status(self):
        from emoteqol.core import audio as A
        def work():
            return A.find_ltmao()
        self.run_bg(work, lambda r, err: self.ltmao_lbl.configure(text=("LtMAO found - your own sounds will work" if r else "LtMAO not found - click 'Find LtMAO...'")))
    def find_ltmao(self):
        from emoteqol.core import audio as A
        p = filedialog.askdirectory(title="Pick the LtMAO folder (the one with start.bat)")
        if not p: return
        if A.set_ltmao(p): self.ltmao_lbl.configure(text="LtMAO found - your own sounds will work")
        else: messagebox.showerror("Not LtMAO", "That folder doesn't contain LtMAO's Wwise converter (res/wiwawe/...). Pick the LtMAO folder that has start.bat in it.")
    def refresh_profile(self):
        if not self.cur or not self.game: return
        em = self.cur; game = self.game
        try: off = float(self.snd_boost_v.get())
        except Exception: off = 0.0
        def work():
            from emoteqol.core import audio as A
            ev = A.event_for_emote(game, em, C.emote_bins(game)); return A.ingame_profile(game, ev, off)["text"] if ev else "This emote's sound could not be found in the game's sound files."
        def done(r, err):
            if self.cur is em: self.profile_lbl.configure(text=r if r else "")
        self.run_bg(work, done)
    def stop_preview(self):
        try:
            import winsound; winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception: pass
    def play_preview(self):
        if not self.cur or not self.game: return messagebox.showinfo("Pick an emote", "Pick an emote and a sound first.")
        spath, sgame = self.sound_path, self.sound_game; keep = self.sound_keep; em = self.cur; game = self.game
        pstart = self.trim_t[0] if (self.sound_path and self.sound_path == self.repl_path and self.repl_path and C.is_video(self.repl_path)) else 0.0
        try: smax = max(0.3, float(self.snd_max_v.get())); off = float(self.snd_boost_v.get())
        except Exception: smax, off = 6.0, 0.0
        if not (spath or sgame or keep): return messagebox.showinfo("No sound", "Choose a sound first (or pick one from another emote).")
        self.busy("Preparing the preview...")
        def work():
            from emoteqol.core import audio as A
            ev = A.event_for_emote(game, em, C.emote_bins(game))
            if spath: prof = A.ingame_profile(game, ev, off); return A.preview_wav(spath, smax, prof, None, pstart), prof["text"]
            if sgame: prof = A.ingame_profile(game, sgame["event"], 0.0); wem, lv = A.first_audible_wem(game, sgame["event"]); return (A.preview_wav(None, 0, prof, wem) if wem else None), prof["text"]
            if keep and keep.get("wem"): prof = A.ingame_profile(game, ev, off); return A.preview_wav(None, 0, prof, keep["wem"]), prof["text"]
            return None, ""
        def done(r, err):
            self.busy("")
            if err or not r or not r[0]: return messagebox.showinfo("Cannot preview", "The preview needs LtMAO's decoder to read game sounds, and a readable sound file." if not err else err[-300:])
            import winsound; winsound.PlaySound(r[0], winsound.SND_FILENAME | winsound.SND_ASYNC); self.busy("Playing at the level League plays it for your volume settings. Turn your PC volume up to hear quiet sounds, the same as in the game.")
        self.run_bg(work, done)
    def clear_sound(self):
        self.sound_path = None; self.sound_game = None; self.sound_keep = None; self.vid_sound_v.set(False); self.sound_lbl.configure(text="none - the emote keeps its normal sound"); self.snd_len.state(["disabled"]); self.snd_len_lbl.configure(text="(pick a sound first)"); self.update_add()
    def pick_game_sound(self):
        from emoteqol.core import audio as A
        dlg = tk.Toplevel(self); dlg.title("Use the sound of another emote"); dlg.geometry("460x520"); dlg.transient(self)
        sv = tk.StringVar(); ttk.Label(dlg, text="Search an emote - its popup sound will play for your emote:").pack(anchor="w", padx=8, pady=(8, 2)); ttk.Entry(dlg, textvariable=sv).pack(fill="x", padx=8)
        fr = ttk.Frame(dlg); fr.pack(fill="both", expand=True, padx=8, pady=6); lb = tk.Listbox(fr, activestyle="dotbox"); sb = ttk.Scrollbar(fr, command=lb.yview); lb.configure(yscrollcommand=sb.set); lb.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        info = ttk.Label(dlg, text="Loading sounds...", foreground="#666"); info.pack(anchor="w", padx=8); shown = []; items = []
        def fill(*_):
            q = sv.get().lower().strip(); lb.delete(0, "end"); shown.clear()
            for it in items:
                if q in it["name"].lower(): shown.append(it); lb.insert("end", it["name"])
            info.configure(text="%d sounds%s" % (len(shown), "" if not q else " match"))
        def choose(*_):
            if not lb.curselection(): return
            it = shown[lb.curselection()[0]]; self.sound_game = it; self.sound_path = None; self.vid_sound_v.set(False); self.snd_len.state(["disabled"]); self.snd_len_lbl.configure(text="(the game's own sound is used as it is)"); self.sound_lbl.configure(text="game sound: " + it["name"]); self.update_add(); dlg.destroy()
        ttk.Button(dlg, text="Use this sound", command=choose).pack(pady=(0, 8)); lb.bind("<Double-Button-1>", choose); sv.trace_add("write", fill)
        cache = os.path.join(C.APPDATA, "sound_catalogue.json")
        def done(r, err):
            if err or not r: info.configure(text="Could not load the sound list."); return
            items.extend(r); fill()
        self.run_bg(lambda: A.sound_catalogue(self.game, self.cat, C.emote_bins(self.game), cache), done)
    STYLE_OWN = "Normal (the emote's own)"
    STYLE_PICK = "Another emote's animation..."
    def styles_loaded(self):
        try: self.style_templates = PS.templates(self.game)
        except Exception: self.style_templates = []
        self.style_cb.configure(values=[self.STYLE_OWN] + [self.style_text(dict(label=t["label"])) for t in self.style_templates] + [self.STYLE_PICK], state="readonly"); self.pop_btn.configure(state="normal"); self.show_style_text()
    def style_text(self, s):
        if not s: return self.STYLE_OWN
        t = next((t for t in self.style_templates if t["label"] == s["label"]), None)
        if t: return "%s - %d emotes" % (t["label"], t["count"])
        return ("Like %s (%s)" % (s["name"], s["label"])) if s.get("name") else s["label"]
    def show_style_text(self): self.style_v.set(self.style_text(self.style_src))
    def on_style_choice(self, ev=None):
        i = self.style_cb.current(); n = len(self.style_templates)
        if i <= 0: self.set_style(None)
        elif i > n: self.show_style_text(); self.pick_style_emote()
        else: t = self.style_templates[i - 1]; self.set_style(dict(label=t["label"], vfx=t["vfx"]))
    def set_style(self, s, play=True):
        self.style_src = s; self.show_style_text(); self.update_add(); self.update_scene()
        if play and self.cur and self.game: self.play_popup()
    def restore_style(self, em):
        entry = self.pack.emotes.get(em["key"]) or {}; st = (entry.get("settings") or {}).get("style")
        try: sty = st if isinstance(st, dict) and st.get("vfx") else PS.detect(self.game, em, entry.get("files", {}), self.pack.other)
        except Exception: sty = None
        self.set_style(sty, play=False)
    def pick_style_emote(self):
        dlg = tk.Toplevel(self); dlg.title("Use the popup animation of another emote"); dlg.geometry("460x520"); dlg.transient(self)
        sv = tk.StringVar(); ttk.Label(dlg, text="Search an emote - your emote's popup will move like its popup does:").pack(anchor="w", padx=8, pady=(8, 2)); ttk.Entry(dlg, textvariable=sv).pack(fill="x", padx=8)
        fr = ttk.Frame(dlg); fr.pack(fill="both", expand=True, padx=8, pady=6); lb = tk.Listbox(fr, activestyle="dotbox"); sb = ttk.Scrollbar(fr, command=lb.yview); lb.configure(yscrollcommand=sb.set); lb.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        info = ttk.Label(dlg, text="", foreground="#666"); info.pack(anchor="w", padx=8); shown = []; items = []
        for e in self.cat:
            lab = PS.label_of(self.game, e["vfx"])
            if lab: items.append((e, lab))
        def fill(*_):
            q = sv.get().lower().strip(); lb.delete(0, "end"); shown.clear()
            for e, lab in items:
                if q in e["name"].lower() or q in lab.lower():
                    shown.append((e, lab)); lb.insert("end", "%s   -  %s" % (e["name"], lab))
                    if len(shown) >= 400: break
            info.configure(text="%d emote%s%s" % (len(shown), "" if len(shown) == 1 else "s", " (type to narrow the list down)" if len(shown) >= 400 else ""))
        def choose(*_):
            if not lb.curselection(): return
            e, lab = shown[lb.curselection()[0]]; dlg.destroy(); self.set_style(dict(label=lab, vfx=e["vfx"], name=e["name"]))
        ttk.Button(dlg, text="Use this animation", command=choose).pack(pady=(0, 8)); lb.bind("<Double-Button-1>", choose); sv.trace_add("write", fill); fill()
        dlg.protocol("WM_DELETE_WINDOW", lambda: (dlg.destroy(), self.show_style_text()))
    def stop_popup(self):
        self.popup_playing = False
        if self.popup_job: self.after_cancel(self.popup_job); self.popup_job = None
    def play_popup(self):
        self.stop_popup()
        if not self.cur or not self.game: return self.busy("Pick an emote first.")
        try:
            if self.style_src: src = PS.source_for(self.game, self.style_src["vfx"]); lay = PS.layers(src[0], src[1]) if src else []
            else: lay = PS.own_layers(self.game, self.cur["vfx"])
        except Exception: lay = []
        vis = PS.visible_layers(lay)
        if not vis: return self.busy("This popup has no animation that can be shown.")
        ref = PS.reference_size(lay); T = PS.length(lay) + 0.2; label = self.style_src["label"] if self.style_src else "Normal"
        try: sp = max(0.1, float(self.loops_v.get()) / 100.0)
        except Exception: sp = 1.0
        try: pct = int(round(self.size_v.get()))
        except Exception: pct = 100
        t0, t1 = self.trim_t; window = max(0.05, min(max(0.05, t1 - t0), self.popup_T * sp)); fit = self.fit_v.get(); adj = self.adj(); pics = {}; start = time.time(); self.popup_playing = True
        def tick():
            t = time.time() - start
            if t >= T or not self.popup_playing: self.popup_job = None; self.popup_playing = False; self.update_scene(); return
            idx = 0
            if len(self.edit_src) > 1 and self.anim_v.get() and self.times: idx = min(len(self.edit_src) - 1, max(0, bisect.bisect_right(self.times, t0 + (t * sp) % window) - 1))
            if idx not in pics:
                try: pics[idx] = C.fit_frame(self.edit_src[idx], 160, fit, adj) if self.edit_src else None
                except Exception: pics[idx] = None
            poses = [p for p in (PS.pose(l, t) for l in vis) if p]
            self.scene_photo = ImageTk.PhotoImage(size_preview.render_motion(pct, pics[idx], poses, ref, "%s  %.1f s" % (label, t), 0.37)); self.scene_lbl.configure(image=self.scene_photo)
            self.popup_job = self.after(33, tick)
        tick()
    def refresh_pack(self):
        self.ptree.delete(*self.ptree.get_children())
        for key, e in self.pack.emotes.items():
            em = next((x for x in self.cat if x["key"] == key), None); img = self.icon_for(em, 40) if em else ""
            cur = e["files"].get(em["inv"].lower()) if em else None
            if cur:
                try: img = self.photo(C.decode_tex(cur), 40, ("packicon", key, id(cur)))
                except Exception: pass
            self.ptree.insert("", "end", iid=key, text="  " + e["name"], values=(e["source"], e["note"]), image=img)
        for key, a in self.pack.art.items(): self.ptree.insert("", "end", iid="art|" + key, text="  " + a["name"], values=(a.get("source", ""), a.get("note", "")), image=self.placeholder)
    def detect_pop_state(self):
        from emoteqol.core import audio as A
        try:
            if self.pack.other.get("WAD/Common.wad.client/%016x.wpk" % A.PK_HASH):
                em = next((x for x in self.cat if x["key"] in self.pack.emotes), None) or self.cat[0]
                self.pack.silence_pop = bool(A.detect_pack_sound(self.game, em, {}, self.pack.other)["pop_silenced"])
        except Exception: pass
    def view_selected(self, ev=None):
        sel = [k for k in self.ptree.selection() if not k.startswith("art|")]
        if not sel: return messagebox.showinfo("Pick an emote", "Select an emote in the pack list first.")
        key = sel[0]; entry = self.pack.emotes.get(key); em = next((x for x in self.cat if x["key"] == key), None)
        if not entry or not em: return
        try: res = C.extract_frames(em, entry["files"], self.pack.other)
        except Exception: return messagebox.showerror("Could not read it", traceback.format_exc()[-500:])
        if not res: return messagebox.showinfo("No picture", "This pack only changes the sound or size of '%s', it holds no picture for it." % entry["name"])
        frames, durs, fps = res; dlg = tk.Toplevel(self); dlg.title(entry["name"] + " - what is in the pack"); dlg.transient(self); dlg.resizable(False, False)
        S = 280; bg = Image.new("RGBA", (S, S), (60, 60, 60, 255)); shots = []
        for f in frames:
            im = f.convert("RGBA"); im.thumbnail((S, S), Image.LANCZOS); t = bg.copy(); t.alpha_composite(im, ((S - im.width) // 2, (S - im.height) // 2)); shots.append(ImageTk.PhotoImage(t.convert("RGB")))
        lab = ttk.Label(dlg, image=shots[0]); lab.pack(padx=14, pady=(14, 6)); state = {"i": 0, "job": None}
        def tick():
            state["i"] = (state["i"] + 1) % len(shots); lab.configure(image=shots[state["i"]]); state["job"] = dlg.after(int(max(30, durs[0] * 1000)), tick)
        if len(shots) > 1: state["job"] = dlg.after(int(max(30, durs[0] * 1000)), tick)
        from emoteqol.core import audio as A
        try: snd = A.detect_pack_sound(self.game, em, entry["files"], self.pack.other)
        except Exception: snd = None
        total = sum(durs); ttk.Label(dlg, text="%d frame%s, %dx%d px%s" % (len(frames), "" if len(frames) == 1 else "s", frames[0].width, frames[0].height, (", %.1f s long" % total) if len(frames) > 1 else ""), foreground="#555").pack()
        def close():
            if state["job"]: dlg.after_cancel(state["job"])
            dlg.destroy()
        def edit_now(): close(); self.edit_from_pack(em, frames, durs)
        def save_gif():
            p = filedialog.asksaveasfilename(title="Save as GIF", defaultextension=".gif", initialfile=entry["name"] + ".gif", filetypes=[("GIF", "*.gif")])
            if not p: return
            fr = [f.convert("RGBA") for f in frames]; fr[0].save(p, save_all=True, append_images=fr[1:], duration=[int(d * 1000) for d in durs], loop=0, disposal=2, optimize=False)
            messagebox.showinfo("Saved", "Saved:\n" + p)
        if snd and snd["found"]:
            kind = "plays another emote's sound" if snd["retargeted"] else ("custom sound" if snd["custom"] else "the game's normal sound")
            info = "Sound: %s%s, volume %s dB%s" % (kind, (", %.1f s" % snd["seconds"]) if (snd["custom"] and snd["seconds"]) else "", ("%g" % snd["level"]) if snd["level"] is not None else "-", ("   (pop silenced)" if snd["pop_silenced"] else ""))
            ttk.Label(dlg, text=info, foreground="#555", wraplength=300, justify="center").pack(pady=(6, 0))
            if snd["custom"] and snd["wem"]:
                def play():
                    import tempfile, winsound
                    p = tempfile.mktemp(suffix=".wav")
                    if not A.wem_to_wav(snd["wem"], p): return messagebox.showinfo("Cannot play", "Playing needs LtMAO (its decoder). Click 'Find LtMAO...' in the Sound box first.")
                    winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC)
                ttk.Button(dlg, text="Play the sound", command=play).pack(pady=(4, 0))
        row = ttk.Frame(dlg); row.pack(pady=12); ttk.Button(row, text="Edit this in the editor", command=edit_now).pack(side="left", padx=6); ttk.Button(row, text="Save as GIF...", command=save_gif).pack(side="left", padx=6); ttk.Button(row, text="Close", command=close).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", close)
    def edit_from_pack(self, em, frames, durs):
        self.loading_pack = True
        try: self.edit_from_pack_inner(em, frames, durs)
        finally: self.after(300, lambda: setattr(self, "loading_pack", False))
    def restore_sound_and_size(self, em):
        from emoteqol.core import audio as A
        try: size, layers, flat = C.popup_settings(self.game, em, self.pack.emotes[em["key"]]["files"], self.pack.other)
        except Exception: size, layers, flat = 100, 0, False
        self.sound_keep = None
        try: snd = A.detect_pack_sound(self.game, em, self.pack.emotes[em["key"]]["files"], self.pack.other)
        except Exception: snd = None
        if snd and snd["found"] and (snd["custom"] or snd["retargeted"]) and not (self.sound_path or self.sound_game):
            if snd["level"] is not None: self.snd_boost_v.set(round(snd["level"] - (snd["orig_level"] if snd["orig_level"] is not None else 0.0), 1))
            restored = False
            if snd["custom"] and snd["wem"]:
                import tempfile
                wav = tempfile.mktemp(suffix=".wav")
                if A.wem_to_wav(snd["wem"], wav):
                    self.vid_sound_v.set(False); self.set_sound_file(wav); self.sound_lbl.configure(text="the sound from the pack%s - change its length or volume, or pick another" % ((", %.1f s" % snd["seconds"]) if snd["seconds"] else "")); restored = True
            if not restored:
                self.sound_keep = snd
                self.sound_lbl.configure(text="keeping the sound already in the pack%s (pick another to replace it)" % ((", %.1f s" % snd["seconds"]) if snd["seconds"] else ""))
        self.size_v.set(size); self._size_changed()
    def edit_from_pack_inner(self, em, frames, durs):
        from emoteqol.core import audio as A
        self.clear_sound(); self.snd_boost_v.set(0.0)
        self.nb.select(0)
        if self.sv.get(): self.sv.set("")
        idx = next((i for i, x in enumerate(self.matches) if x["key"] == em["key"]), None)
        if idx is not None and self.tree.selection() != (str(idx),): self.tree.selection_set(str(idx))
        if idx is not None: self.tree.see(str(idx))
        self.cur = em; self.repl_frames = [f.convert("RGBA") for f in frames]; self.repl_durs = list(durs); self.mem_frames = (self.repl_frames, self.repl_durs)
        self.edit_src = []
        for f in self.repl_frames:
            if max(f.size) <= 700: self.edit_src.append(f)
            else: g = f.copy(); g.thumbnail((700, 700), Image.LANCZOS); self.edit_src.append(g)
        self.repl_path = "(from the pack) " + em["name"]; self.fit_v.set("stretch")
        st = self.pack.emotes[em["key"]].get("settings") or {}; speed = float(st.get("speed", 100.0)) or 100.0
        self.loops_v.set(speed); self.anim_v.set(bool(st.get("animate", len(frames) > 1)))
        if speed != 100.0: self.repl_durs = [x * speed / 100.0 for x in durs]; self.mem_frames = (self.repl_frames, self.repl_durs)
        self.setup_clip(); self.restore_sound_and_size(em); self.restore_style(em)
        self.src_lbl.configure(text="%s   (%d frame%s, loaded from the pack - move, stretch or change it, then press Add)" % (em["name"], len(self.repl_frames), "" if len(self.repl_frames) == 1 else "s"))
        self.reset_adj(); self.play(0); self.update_add(); self.refresh_profile(); self.busy("Loaded '%s' from the pack into the editor." % em["name"])
    def remove_selected(self):
        for k in self.ptree.selection():
            if k.startswith("art|"): self.pack.art.pop(k[4:], None)
            else: self.pack.remove(k)
        self.refresh_pack()
    def new_pack(self):
        self.pack = C.Pack(); self.pop_v.set(self.pack.silence_pop); self.name_v.set("My Emotes"); self.auth_v.set(""); self.lic_v.set(""); self.refresh_pack(); self.busy("New empty pack.")
    def open_fantome(self):
        if not self.cat: return messagebox.showinfo("Wait", "The emote list is still loading.")
        p = filedialog.askopenfilename(title="Open a .fantome", filetypes=[("Fantome mods", "*.fantome *.zip"), ("All files", "*.*")])
        if not p: return
        try: self.pack = C.import_fantome(p, self.cat); self.old_fixed = C.fix_old_popups(self.pack, self.cat)
        except Exception as e: return messagebox.showerror("Could not open", traceback.format_exc()[-600:])
        i = self.pack.info; self.name_v.set(i.get("Name", "")); self.auth_v.set(i.get("Author", "")); self.lic_v.set(i.get("License", "")); self.detect_pop_state(); self.pop_v.set(self.pack.silence_pop); self.refresh_pack(); self.skin_tab.on_pack_opened()
        self.busy("Opened %s: %d emote replacement(s), %d skin art; %d other file(s) are kept untouched.%s" % (os.path.basename(p), len(self.pack.emotes), len(self.pack.art), len(self.pack.other), (" Cleaned the popup of %d emote(s) saved by an older version." % self.old_fixed) if getattr(self, "old_fixed", 0) else ""))
    def save_fantome(self):
        if not self.pack.emotes and not self.pack.other and not self.pack.art: return messagebox.showinfo("Nothing to save", "Add an emote replacement or a loading screen / HUD picture first.")
        p = filedialog.asksaveasfilename(title="Save .fantome", defaultextension=".fantome", initialfile=(self.name_v.get() or "My Emotes") + ".fantome", filetypes=[("Fantome mod", "*.fantome")])
        if not p: return
        self.pack.info.update(Name=self.name_v.get() or "My Emotes", Author=self.auth_v.get(), License=self.lic_v.get())
        try: C.export_fantome(self.pack, p, None, self.game)
        except Exception: return messagebox.showerror("Could not save", traceback.format_exc()[-600:])
        self.busy("Saved " + p); messagebox.showinfo("Saved", "Saved:\n%s\n\nImport it in LTK Manager like your other mods." % p)

def main():
    from emoteqol import installer
    if getattr(sys, "frozen", False) and installer.installed_here(): installer.copy_source(os.path.dirname(installer.exe_path()))
    if getattr(sys, "frozen", False) and not installer.installed_here():
        dst = installer.run_installer()
        if dst:
            import subprocess; subprocess.Popen([dst], cwd=os.path.dirname(dst), creationflags=0x00000008)
        sys.exit(0)
    App().mainloop()
