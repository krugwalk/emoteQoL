import os, sys, shutil, subprocess, json, threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from emoteqol.core import emotes as C
from emoteqol.core import audio as A
from emoteqol.core import ltmao as LF

APP = "EmoteQoL"
def default_dir(): return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "EmoteQoL")
def install_dir():
    if os.environ.get("EMOTEQOL_INSTALL_DIR"): return os.environ["EMOTEQOL_INSTALL_DIR"]
    try: d = json.load(open(os.path.join(C.APPDATA, "settings.json"))).get("install_dir")
    except Exception: d = None
    return d or default_dir()
def target_folder(picked):
    picked = os.path.normpath(picked)
    return picked if os.path.basename(picked).lower() == APP.lower() else os.path.join(picked, APP)
def exe_path(): return os.path.abspath(sys.executable)
def installed_here(): return os.path.normcase(os.path.dirname(exe_path())) == os.path.normcase(install_dir())
def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")); return os.path.join(base, name)

def desktop_dir():
    if os.environ.get("EMOTEQOL_DESKTOP_DIR"): return os.environ["EMOTEQOL_DESKTOP_DIR"]
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"], capture_output=True, text=True, timeout=20, creationflags=0x08000000)
        d = r.stdout.strip()
        if d and os.path.isdir(d): return d
    except Exception: pass
    return os.path.join(os.path.expanduser("~"), "Desktop")

def make_shortcut(lnk, target, icon, workdir):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';$s.IconLocation='%s,0';$s.WorkingDirectory='%s';$s.Description='Replace League emotes with your own GIFs';$s.Save()"
          % (lnk.replace("'", "''"), target.replace("'", "''"), icon.replace("'", "''"), workdir.replace("'", "''")))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=30, creationflags=0x08000000)

SOURCE_FILES = ("README.md", "LICENSE", "requirements.txt", "build.bat", ".gitignore")

def source_root():
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "source")
        return p if os.path.isdir(p) else None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return root if os.path.isdir(os.path.join(root, "emoteqol")) else None

def copy_source(d):
    root = source_root()
    if not root: return
    try:
        shutil.copytree(os.path.join(root, "emoteqol"), os.path.join(d, "emoteqol"), dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for f in SOURCE_FILES:
            if os.path.exists(os.path.join(root, f)): shutil.copy2(os.path.join(root, f), os.path.join(d, f))
    except Exception: pass

def do_install(final_dir, shortcut=True, dest=None):
    d = dest or install_dir(); os.makedirs(d, exist_ok=True); dst = os.path.join(d, APP + ".exe")
    if os.path.normcase(exe_path()) != os.path.normcase(dst): shutil.copy2(exe_path(), dst)
    ico = dst; copy_source(d)
    s = {}
    try: s = json.load(open(os.path.join(C.APPDATA, "settings.json")))
    except Exception: pass
    if final_dir: s["game"] = final_dir
    s["install_dir"] = d
    os.makedirs(C.APPDATA, exist_ok=True); json.dump(s, open(os.path.join(C.APPDATA, "settings.json"), "w"))
    if shortcut: make_shortcut(os.path.join(desktop_dir(), APP + ".lnk"), dst, ico, d)
    return dst

def ltmao_dir(d): return os.path.join(d, "LtMAO")

def install_ltmao(d, progress=None):
    dest = ltmao_dir(d); LF.download(dest, progress); A.set_ltmao(dest); return dest

def ltmao_ready(d):
    try: saved = json.load(open(os.path.join(C.APPDATA, "settings.json"))).get("ltmao")
    except Exception: saved = None
    return A.is_ltmao_dir(saved) or A.is_ltmao_dir(ltmao_dir(d))

def run_installer():
    root = tk.Tk(); root.title("Install " + APP); root.geometry("560x430"); root.resizable(False, False)
    try: root.iconbitmap(resource("icon.ico"))
    except Exception: pass
    state = {"dest": install_dir(), "final": C.resolve_final(json.load(open(os.path.join(C.APPDATA, "settings.json"))).get("game")) if os.path.exists(os.path.join(C.APPDATA, "settings.json")) else None, "done": None}
    if not state["final"]: state["final"] = C.detect_league()
    ttk.Label(root, text="EmoteQoL", font=("Segoe UI", 16, "bold")).pack(pady=(14, 2)); ttk.Label(root, text="Emotes, loading screens and HUD portraits with your own pictures.").pack()
    box = ttk.LabelFrame(root, text="League of Legends"); box.pack(fill="x", padx=16, pady=12)
    lbl = ttk.Label(box, wraplength=500); lbl.pack(anchor="w", padx=8, pady=6)
    def refresh(): lbl.configure(text=("Found: " + state["final"]) if state["final"] else "Not found automatically. Please pick your League of Legends folder.")
    def pick():
        p = filedialog.askdirectory(title="Pick your League of Legends folder")
        if not p: return
        r = C.resolve_final(p)
        if r: state["final"] = r; refresh()
        else: messagebox.showerror("Not League", "Could not find Global.wad.client in that folder.")
    ttk.Button(box, text="Pick folder...", command=pick).pack(anchor="w", padx=8, pady=(0, 8)); refresh()
    sc = tk.BooleanVar(value=True); ttk.Checkbutton(root, text="Create a desktop shortcut", variable=sc).pack(anchor="w", padx=18)
    lt = tk.BooleanVar(value=not ltmao_ready(state["dest"])); ttk.Checkbutton(root, text="Download the sound tools for your own sounds (about 55 MB, from LtMAO's GitHub)", variable=lt).pack(anchor="w", padx=18)
    where = ttk.LabelFrame(root, text="Install location"); where.pack(fill="x", padx=16, pady=(8, 4))
    dest_lbl = ttk.Label(where, text=state["dest"], wraplength=500, foreground="#444"); dest_lbl.pack(anchor="w", padx=8, pady=(6, 2))
    def change_dest():
        p = filedialog.askdirectory(title="Pick the folder to install EmoteQoL into")
        if p: state["dest"] = target_folder(p); dest_lbl.configure(text=state["dest"])
    ttk.Button(where, text="Change...", command=change_dest).pack(anchor="w", padx=8, pady=(0, 8))
    status = ttk.Label(root, text="", foreground="#444"); status.pack(pady=(2, 0))
    def go():
        if not state["final"]: pick()
        if not state["final"]: return
        want = lt.get(); folder = state["dest"]
        try: state["done"] = do_install(state["final"], sc.get(), folder)
        except Exception as e: return messagebox.showerror("Install failed", str(e))
        if not want: return root.destroy()
        install_btn.configure(state="disabled"); cancel_btn.configure(state="disabled"); root.protocol("WM_DELETE_WINDOW", lambda: None); res = {}
        def worker():
            try: install_ltmao(folder, lambda d, t: res.__setitem__("p", (d, t))); res["ok"] = True
            except Exception as e: res["err"] = str(e)
        threading.Thread(target=worker, daemon=True).start()
        def poll():
            if "ok" in res or "err" in res:
                if "err" in res: messagebox.showwarning("Sound tools not downloaded", "EmoteQoL is installed, but the sound tools could not be downloaded (" + res["err"][:200] + ").\n\nYou can download them later with the button in the Sound box.")
                return root.destroy()
            d, t = res.get("p", (0, 1)); status.configure(text="Downloading the sound tools... %d%%" % (100 * d // max(1, t))); root.after(150, poll)
        status.configure(text="Downloading the sound tools... 0%"); poll()
    row = ttk.Frame(root); row.pack(pady=6); install_btn = ttk.Button(row, text="Install", command=go); install_btn.pack(side="left", padx=6); cancel_btn = ttk.Button(row, text="Cancel", command=root.destroy); cancel_btn.pack(side="left", padx=6)
    root.mainloop(); return state["done"]
