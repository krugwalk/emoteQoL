import os, sys, shutil, subprocess, json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from emoteqol.core import emotes as C

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

def remove_old_version():
    try:
        old = os.path.join(desktop_dir(), "Emote Maker.lnk")
        if os.path.exists(old): os.remove(old)
    except Exception: pass
    try: shutil.rmtree(os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "EmoteMaker"), ignore_errors=True)
    except Exception: pass

def do_install(final_dir, shortcut=True, dest=None):
    d = dest or install_dir(); os.makedirs(d, exist_ok=True); dst = os.path.join(d, APP + ".exe")
    if os.path.normcase(exe_path()) != os.path.normcase(dst): shutil.copy2(exe_path(), dst)
    ico = os.path.join(d, "icon.ico"); shutil.copy2(resource("icon.ico"), ico)
    s = {}
    try: s = json.load(open(os.path.join(C.APPDATA, "settings.json")))
    except Exception: pass
    if final_dir: s["game"] = final_dir
    s["install_dir"] = d
    if os.path.normcase(exe_path()) != os.path.normcase(dst): s["source_exe"] = exe_path()
    os.makedirs(C.APPDATA, exist_ok=True); json.dump(s, open(os.path.join(C.APPDATA, "settings.json"), "w"))
    if shortcut: make_shortcut(os.path.join(desktop_dir(), APP + ".lnk"), dst, ico, d)
    remove_old_version()
    return dst

def maybe_update():
    try:
        s = json.load(open(os.path.join(C.APPDATA, "settings.json"))); src = s.get("source_exe"); dst = exe_path()
        if not src or not os.path.exists(src) or os.path.normcase(os.path.abspath(src)) == os.path.normcase(dst): return False
        if os.path.getmtime(src) <= os.path.getmtime(dst) + 2: return False
        bat = os.path.join(os.environ.get("TEMP", "."), "emoteqol_update.bat")
        open(bat, "w").write('@echo off\nping -n 3 127.0.0.1 >nul\ncopy /y "%s" "%s" >nul\nstart "" "%s"\n' % (src, dst, dst))
        subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000008, close_fds=True); return True
    except Exception: return False

def run_installer():
    root = tk.Tk(); root.title("Install " + APP); root.geometry("560x372"); root.resizable(False, False)
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
    where = ttk.LabelFrame(root, text="Install location"); where.pack(fill="x", padx=16, pady=(8, 4))
    dest_lbl = ttk.Label(where, text=state["dest"], wraplength=500, foreground="#444"); dest_lbl.pack(anchor="w", padx=8, pady=(6, 2))
    def change_dest():
        p = filedialog.askdirectory(title="Pick the folder to install EmoteQoL into")
        if p: state["dest"] = target_folder(p); dest_lbl.configure(text=state["dest"])
    ttk.Button(where, text="Change...", command=change_dest).pack(anchor="w", padx=8, pady=(0, 8))
    def go():
        if not state["final"]: pick()
        if not state["final"]: return
        try: state["done"] = do_install(state["final"], sc.get(), state["dest"]); root.destroy()
        except Exception as e: messagebox.showerror("Install failed", str(e))
    row = ttk.Frame(root); row.pack(pady=6); ttk.Button(row, text="Install", command=go).pack(side="left", padx=6); ttk.Button(row, text="Cancel", command=root.destroy).pack(side="left", padx=6)
    root.mainloop(); return state["done"]
