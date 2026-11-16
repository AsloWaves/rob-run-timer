"""Rob Run Harvest Timer - any number of grow tables, each with its own upgrades.
Native tkinter app + CLI sharing one state file. Unofficial fan tool.

Measured: upgrades CUT grow time additively: time = base * (1 - sum of upgrade %).
Base (no upgrades) = 60 min. Fan 12%, Water Pump 14%, UV Lamp 24% (all editable in Settings).

GUI:   pythonw rob_run_timer.py          (or the packaged RobRunTimer.exe)
CLI:   python rob_run_timer.py start [--timer N] [--ago MIN]   N = 1-based timer number (default 1)
       python rob_run_timer.py ready [--timer N] [--ago MIN]   log actual ready moment
       python rob_run_timer.py set [--base 60] [--clock 12|24] [--skin NAME] [--timer N --ups fan,pump --name TEXT]
       python rob_run_timer.py add [--name TEXT] [--ups fan,pump]
       python rob_run_timer.py remove --timer N
       python rob_run_timer.py status
"""
import argparse, json, os, shutil, sys, time
from datetime import datetime

VERSION = "1.0.0"
DIR = os.path.dirname(os.path.abspath(__file__))
# Saved data lives in %APPDATA%\RobRunTimer so it survives updates and works from a packaged .exe.
# ROBRUN_STATE can point somewhere else (testing).
_APPDATA = os.environ.get("APPDATA")
DATA_DIR = os.path.join(_APPDATA, "RobRunTimer") if _APPDATA else DIR
STATE = os.environ.get("ROBRUN_STATE") or os.path.join(DATA_DIR, "state.json")
LEGACY_STATE = os.path.join(DIR, "state.json")   # older versions kept it next to the script

UP_KEYS = ("fan", "pump", "uv")
UP_NAMES = {"fan": "Fan", "pump": "Water Pump", "uv": "UV Lamp"}

# --------------------------------------------------------------------------- skins
THEMES = {
    "Classic": dict(bg="#f0f0f0", fg="#000000", muted="#444444", entry="#ffffff", btn="#e1e1e1", btn_fg="#000000",
                    accent="#3a9d3a", accent_fg="#ffffff", danger="#aa3333", timer="#000000", ready="#1a9a1a",
                    logged="#0000ff", bar="#2b2b2b", bar_fg="#cccccc", bar_hover="#444444", link="#0066cc", font="Consolas"),
    "Dark": dict(bg="#1e1e1e", fg="#e6e6e6", muted="#9a9a9a", entry="#2d2d2d", btn="#3a3a3a", btn_fg="#eeeeee",
                 accent="#2e8b57", accent_fg="#ffffff", danger="#ff6b6b", timer="#f2f2f2", ready="#5cff7a",
                 logged="#6cb2ff", bar="#111111", bar_fg="#bbbbbb", bar_hover="#333333", link="#6cb2ff", font="Consolas"),
    "Forest": dict(bg="#14231a", fg="#dff3df", muted="#8fb59a", entry="#1f3427", btn="#2b4a37", btn_fg="#e6f7e6",
                   accent="#3f9b45", accent_fg="#ffffff", danger="#ff8a80", timer="#b9f6ca", ready="#69ff47",
                   logged="#80deea", bar="#0b150f", bar_fg="#a5d6a7", bar_hover="#24402f", link="#80deea", font="Consolas"),
    "Ocean": dict(bg="#0d2137", fg="#e3f2fd", muted="#8fb3d0", entry="#17324d", btn="#1f4568", btn_fg="#e3f2fd",
                  accent="#1e88e5", accent_fg="#ffffff", danger="#ff8a80", timer="#bbdefb", ready="#69f0ae",
                  logged="#ffd54f", bar="#07141f", bar_fg="#90caf9", bar_hover="#173653", link="#82b1ff", font="Consolas"),
    "Synthwave": dict(bg="#1a1033", fg="#f5e9ff", muted="#b39ddb", entry="#2a1850", btn="#3d2370", btn_fg="#ffe6ff",
                      accent="#e0207f", accent_fg="#ffffff", danger="#ff6e6e", timer="#00e5ff", ready="#ffee58",
                      logged="#ff80ab", bar="#0e0720", bar_fg="#e1bee7", bar_hover="#3d2370", link="#00e5ff", font="Consolas"),
    "Paper": dict(bg="#f6f1e7", fg="#2b2b2b", muted="#6d6556", entry="#fffdf7", btn="#e8dfcc", btn_fg="#2b2b2b",
                  accent="#5f7f1f", accent_fg="#ffffff", danger="#b03a2e", timer="#3b3024", ready="#2e7d32",
                  logged="#1565c0", bar="#d9cfb8", bar_fg="#3b3024", bar_hover="#c9bd9f", link="#1565c0", font="Georgia"),
}

DEF_SETTINGS = {
    "skin": "Dark",                    # one of THEMES
    "clock": 12,                       # 12 or 24 hour clock for ready times
    "seconds": True,                   # show seconds in clock times
    "beep": True,                      # play a sound when a timer is ready
    "sound_path": "",                  # custom finish sound (.wav/.mp3/.wma); empty = built-in beep
    "topmost": True,                   # keep window above the game
    "compact_bar": True,               # slim custom title bar with small buttons (restart to apply)
    "welcomed": False,                 # first-run welcome already shown
    "default_ups": ["fan", "pump"],    # upgrades pre-ticked on newly added timers
    "pct": {"fan": 12, "pump": 14, "uv": 24},   # time cut per upgrade, in percent
}
DEF_BASE = 60.0


def new_timer(name, ups):
    return {"id": str(int(time.time() * 1000)), "name": name, "ups": list(ups), "start": None, "open": None}


def default():
    return {"base": DEF_BASE, "settings": json.loads(json.dumps(DEF_SETTINGS)),
            "timers": [new_timer("Table 1", DEF_SETTINGS["default_ups"])], "cycles": []}


def _migrate_legacy():
    """Bring an older next-to-the-script state.json into the data folder, once."""
    if os.path.exists(STATE) or not os.path.exists(LEGACY_STATE) or os.environ.get("ROBRUN_STATE"):
        return
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        shutil.copy2(LEGACY_STATE, STATE)
        with open(STATE, encoding="utf-8-sig") as f:
            s = json.load(f)
        s.setdefault("settings", {})["welcomed"] = True   # existing user: skip the welcome
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


def load():
    _migrate_legacy()
    try:
        with open(STATE, encoding="utf-8-sig") as f:
            s = json.load(f)
    except Exception:
        return default()
    if "timers" not in s:  # migrate from single-timer / two-table versions
        if "tables" in s:
            b = s["tables"].get("B", {})
            ups, start, op = b.get("ups", ["fan", "pump"]), b.get("start"), b.get("open")
        else:
            ups, start, op = s.get("ups", ["fan", "pump"]), s.get("start"), s.get("open")
        t = new_timer("Table 1", ups)
        t["start"], t["open"] = start, op
        s = {"base": s.get("base", DEF_BASE), "timers": [t], "cycles": s.get("cycles", [])}
    out = {**default(), **s}
    st = {**json.loads(json.dumps(DEF_SETTINGS)), **s.get("settings", {})}
    st["pct"] = {**DEF_SETTINGS["pct"], **st.get("pct", {})}
    if st["skin"] not in THEMES:
        st["skin"] = DEF_SETTINGS["skin"]
    out["settings"] = st
    return out


def save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE)


def minutes(s, t):
    return s["base"] * (1 - sum(s["settings"]["pct"][u] / 100 for u in t["ups"]))


def fmt(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, x = divmod(r, 60)
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m:02d}:{x:02d}"


def clock(s, ts):
    """Format a timestamp as a clock time per the settings (12h by default)."""
    d = datetime.fromtimestamp(ts)
    cfg = s["settings"]
    if cfg["clock"] == 24:
        return d.strftime("%H:%M:%S" if cfg["seconds"] else "%H:%M")
    out = d.strftime("%I:%M:%S %p" if cfg["seconds"] else "%I:%M %p")
    return out.lstrip("0")


def play_alert(path=""):
    """Play the user's chosen sound (wav/mp3/wma via Windows MCI, no extra packages); fall back to a beep."""
    try:
        if path and os.path.isfile(path):
            import ctypes
            mci = ctypes.windll.winmm.mciSendStringW
            mci("close rrsnd", None, 0, 0)
            kind = {".mp3": "mpegvideo", ".wma": "mpegvideo", ".wav": "waveaudio"}.get(os.path.splitext(path)[1].lower(), "")
            opened = mci(f'open "{path}" ' + (f"type {kind} " if kind else "") + "alias rrsnd", None, 0, 0)
            if opened == 0 and mci("play rrsnd", None, 0, 0) == 0:
                return
        import winsound
        winsound.Beep(1000, 400); winsound.Beep(1400, 400)
    except Exception:
        pass


def find(s, tid):
    for t in s["timers"]:
        if t["id"] == tid:
            return t


def do_start(s, t, ago=0.0):
    t["start"] = time.time() - ago * 60
    t["open"] = {"timer": t["name"], "start": t["start"], "ups": list(t["ups"])}
    save(s)


def do_ready(s, t, ago=0.0):
    c = t.get("open")
    if not c:
        return None
    c["ready"] = time.time() - ago * 60
    c["minutes"] = round((c["ready"] - c["start"]) / 60, 3)
    s["cycles"].append(c)
    t["open"] = None
    t["start"] = None
    save(s)
    return c


def status(s):
    print(f"v{VERSION} base={s['base']} clock={s['settings']['clock']}h skin={s['settings']['skin']}")
    for i, t in enumerate(s["timers"], 1):
        line = f"{i}. {t['name']} ups={t['ups']} -> {minutes(s, t):.1f} min"
        if t["start"]:
            end = t["start"] + minutes(s, t) * 60
            left = end - time.time()
            line += " | " + ("READY" if left <= 0 else f"ready in {fmt(left)} at {clock(s, end)}")
        print(line)
    for c in s["cycles"]:
        print("logged:", c.get("timer", c.get("table", "-")), c["minutes"], "min, ups", c["ups"])


def cli(a):
    s = load()
    idx = (a.timer or 1) - 1
    if a.cmd in ("start", "ready", "remove") or (a.cmd == "set" and a.timer):
        if not 0 <= idx < len(s["timers"]):
            sys.exit(f"no timer {a.timer}")
    if a.cmd == "start":
        do_start(s, s["timers"][idx], a.ago)
    elif a.cmd == "ready":
        c = do_ready(s, s["timers"][idx], a.ago)
        print("logged" if c else "no open cycle", c or "")
    elif a.cmd == "set":
        if a.base is not None: s["base"] = a.base
        if a.clock: s["settings"]["clock"] = a.clock
        if a.skin:
            match = [k for k in THEMES if k.lower() == a.skin.lower()]
            if not match: sys.exit("skins: " + ", ".join(THEMES))
            s["settings"]["skin"] = match[0]
        if a.timer:
            if a.ups is not None: s["timers"][idx]["ups"] = [u for u in a.ups.split(",") if u in UP_KEYS]
            if a.name: s["timers"][idx]["name"] = a.name
        save(s)
    elif a.cmd == "add":
        ups = [u for u in a.ups.split(",") if u in UP_KEYS] if a.ups is not None else s["settings"]["default_ups"]
        s["timers"].append(new_timer(a.name or f"Table {len(s['timers'])+1}", ups))
        save(s)
    elif a.cmd == "remove":
        if len(s["timers"]) > 1:
            del s["timers"][idx]
            save(s)
    status(load())


# --------------------------------------------------------------------------- GUI
def single_instance():
    """Return False if another copy of the app is already running (Windows named mutex)."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        single_instance.handle = k.CreateMutexW(None, False, "Local\\RobRunHarvestTimer")
        return k.GetLastError() != 183
    except Exception:
        return True


def paint(w, th):
    """Recursively apply skin colours. Widgets can carry a `_role` to get special treatment."""
    cls, role = w.winfo_class(), getattr(w, "_role", None)
    try:
        if cls in ("Frame", "Toplevel", "Tk"):
            w.config(bg=th["bar"] if role == "bar" else th["bg"])
            if cls in ("Tk", "Toplevel"):
                w.config(highlightthickness=1, highlightbackground=th["bar"], highlightcolor=th["bar"])
        elif cls == "Labelframe":
            w.config(bg=th["bg"], fg=th["fg"])
        elif cls == "Label":
            if role == "bar_text":
                w.config(bg=th["bar"], fg=th["bar_fg"])
            elif role == "bar_btn":
                w.config(bg=th["bar"], fg=th["bar_fg"])
            elif role == "big":
                w.config(bg=th["bg"], font=(th["font"], 38))
            elif role == "muted":
                w.config(bg=th["bg"], fg=th["muted"])
            elif role == "link":
                w.config(bg=th["bg"], fg=th["link"])
            else:
                w.config(bg=th["bg"], fg=th["fg"])
        elif cls == "Button":
            if role == "accent":
                w.config(bg=th["accent"], fg=th["accent_fg"], activebackground=th["accent"], activeforeground=th["accent_fg"])
            elif role == "danger":
                w.config(bg=th["btn"], fg=th["danger"], activebackground=th["btn"], activeforeground=th["danger"])
            else:
                w.config(bg=th["btn"], fg=th["btn_fg"], activebackground=th["entry"], activeforeground=th["btn_fg"])
        elif cls == "Entry":
            w.config(bg=th["entry"], fg=th["fg"], insertbackground=th["fg"])
        elif cls in ("Checkbutton", "Radiobutton"):
            if role != "chip":
                w.config(bg=th["bg"], fg=th["fg"], selectcolor=th["entry"], activebackground=th["bg"], activeforeground=th["fg"])
    except Exception:
        pass
    for c in w.winfo_children():
        paint(c, th)


def gui():
    import tkinter as tk
    if not single_instance():
        sys.exit(0)
    root = tk.Tk()
    root.title("Rob Run Harvest Timer")
    root.attributes("-topmost", True)
    try:   # window / taskbar icon (bundled inside the packaged .exe, or next to the script)
        root.iconbitmap(os.path.join(getattr(sys, "_MEIPASS", DIR), "assets", "icon.ico"))
    except Exception:
        pass
    cur = {"name": load()["settings"]["skin"]}
    cur["th"] = THEMES[cur["name"]]

    def tag(widget, role):
        widget._role = role
        return widget

    if load()["settings"].get("compact_bar", True):
        # Windows draws the native title-bar buttons at a fixed size, so replace the bar with a slim one.
        root.overrideredirect(True)
        bar = tag(tk.Frame(root, height=18), "bar")
        bar.pack(side="top", fill="x")
        ttl = tag(tk.Label(bar, text=f"Rob Run Timer", font=("Segoe UI", 8)), "bar_text")
        ttl.pack(side="left", padx=6)
        drag = {}

        def press(e): drag["x"], drag["y"] = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()
        def move(e): root.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")
        for wdg in (bar, ttl):
            wdg.bind("<ButtonPress-1>", press); wdg.bind("<B1-Motion>", move)

        def minimize():
            root.overrideredirect(False); root.iconify()
        restoring = {"v": False}

        def on_map(e):
            if e.widget is root and not restoring["v"] and not root.overrideredirect():
                restoring["v"] = True
                root.after(50, lambda: (root.overrideredirect(True), restoring.update(v=False), taskbar()))
        root.bind("<Map>", on_map)

        def small_btn(text, cmd, hover):
            b = tag(tk.Label(bar, text=text, font=("Segoe UI", 8), width=3), "bar_btn")
            b.pack(side="right", fill="y")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(bg=hover or cur["th"]["bar_hover"]))
            b.bind("<Leave>", lambda e: b.config(bg=cur["th"]["bar"]))
        small_btn("✕", root.destroy, "#c42b1c")
        small_btn("–", minimize, None)

        def taskbar():   # keep a taskbar button even though the window is borderless
            try:
                import ctypes
                u = ctypes.windll.user32
                hwnd = u.GetParent(root.winfo_id())
                u.SetWindowLongW(hwnd, -20, (u.GetWindowLongW(hwnd, -20) & ~0x80) | 0x40000)
                root.withdraw(); root.after(10, root.deiconify)
            except Exception:
                pass
        root.after(100, taskbar)

    panels = {}   # timer id -> dict of widgets
    alerted = {}
    topmost = {"v": True}
    settings_win = {"w": None}
    holder = tk.Frame(root)
    holder.pack(side="top", fill="both", expand=True)

    def set_skin(name):
        cur["name"], cur["th"] = name, THEMES[name]
        paint(root, cur["th"])
        w = settings_win["w"]
        if w is not None and w.winfo_exists():
            paint(w, cur["th"])

    def build_panel(t):
        tid = t["id"]
        box = tk.LabelFrame(holder, padx=6, pady=4)
        box.pack(side="left", fill="y", padx=6, pady=6, anchor="n")
        name = tk.StringVar(value=t["name"])

        def upd(fn):
            st = load(); tt = find(st, tid)
            if tt is not None:
                fn(st, tt); save(st)

        name.trace_add("write", lambda *_: upd(lambda st, tt: tt.__setitem__("name", name.get())))
        tk.Entry(box, textvariable=name, justify="center", font=("Segoe UI", 10, "bold")).pack(fill="x")
        big = tag(tk.Label(box, text="--:--"), "big"); big.pack()
        info = tag(tk.Label(box, text="", font=("Segoe UI", 8)), "muted"); info.pack()
        ago = tk.StringVar(value="0")
        r = tk.Frame(box); r.pack(pady=2)
        tk.Label(r, text="Harvested").pack(side="left")
        tk.Entry(r, textvariable=ago, width=4).pack(side="left", padx=3)
        tk.Label(r, text="min ago").pack(side="left")

        def start():
            try: a = float(ago.get())
            except ValueError: a = 0
            st = load(); tt = find(st, tid)
            if tt is not None:
                do_start(st, tt, a)
            ago.set("0"); alerted[tid] = False

        def ready():
            st = load(); tt = find(st, tid)
            if tt is not None: do_ready(st, tt)

        def reset():
            def f(st, tt): tt["start"] = None; tt["open"] = None
            upd(f)

        tag(tk.Button(box, text="Harvested - start timer", command=start, font=("Segoe UI", 10), height=2),
            "accent").pack(fill="x", pady=2)
        tk.Button(box, text="Actually ready now (log)", command=ready).pack(fill="x")
        tk.Button(box, text="Reset", command=reset).pack(fill="x", pady=2)
        vs, cbs = {}, {}
        for u in UP_KEYS:
            vs[u] = tk.BooleanVar(value=u in t["ups"])
            def cb(u=u):
                upd(lambda st, tt: tt.__setitem__("ups", [k for k in UP_KEYS if vs[k].get()]))
            cbs[u] = tk.Checkbutton(box, text=UP_NAMES[u], variable=vs[u], command=cb)
            cbs[u].pack(anchor="w")

        def remove():
            st = load()
            if len(st["timers"]) > 1:
                st["timers"] = [x for x in st["timers"] if x["id"] != tid]; save(st)
        tag(tk.Button(box, text="Remove this timer", command=remove), "danger").pack(fill="x", pady=(4, 0))
        panels[tid] = {"box": box, "big": big, "info": info, "cbs": cbs}
        paint(box, cur["th"])

    def add_timer():
        st = load()
        st["timers"].append(new_timer(f"Table {len(st['timers'])+1}", st["settings"]["default_ups"])); save(st)

    # ---------------------------------------------------------------- welcome (first run)
    def welcome():
        w = tk.Toplevel(root)
        w.title("Welcome")
        w.attributes("-topmost", True)
        msg = ("Welcome to the Rob Run Harvest Timer!\n\n"
               "1.  Tick the upgrades installed on each grow table.\n"
               "2.  Press \"Harvested - start timer\" the moment you harvest.\n"
               "3.  You get a sound (and READY!) when the bush has regrown.\n\n"
               "Grow time = 60 min x (1 - upgrade %).  Everything is adjustable in Settings\n"
               "(skins, 12/24-hour clock, custom sound, upgrade percentages).\n\n"
               "Use \"+ Add timer\" for tables with different upgrades.\n\n"
               "Unofficial fan tool - not affiliated with the ROB RUN developer.")
        tk.Label(w, text=msg, justify="left", padx=16, pady=12).pack()

        def done():
            st = load(); st["settings"]["welcomed"] = True; save(st); w.destroy()
        tk.Button(w, text="Got it", command=done, width=12).pack(pady=(0, 12))
        w.protocol("WM_DELETE_WINDOW", done)
        paint(w, cur["th"])

    # ---------------------------------------------------------------- settings page
    def open_settings():
        if settings_win["w"] is not None and settings_win["w"].winfo_exists():
            settings_win["w"].lift(); return
        st0 = load()
        w = tk.Toplevel(root)
        w.title("Settings")
        w.attributes("-topmost", True)
        settings_win["w"] = w
        S = st0["settings"]

        def commit(fn):
            st = load(); fn(st); save(st)

        # --- skin
        kf = tk.LabelFrame(w, text="Skin", padx=8, pady=6); kf.pack(fill="x", padx=10, pady=(10, 4))
        skin = tk.StringVar(value=S["skin"])

        def pick_skin():
            commit(lambda st: st["settings"].__setitem__("skin", skin.get())); set_skin(skin.get())
        for i, (nm, th) in enumerate(THEMES.items()):   # each chip previews its own skin
            chip = tk.Radiobutton(kf, text=nm, variable=skin, value=nm, command=pick_skin, indicatoron=False,
                                  bg=th["bg"], fg=th["fg"], selectcolor=th["accent"], activebackground=th["accent"],
                                  activeforeground=th["accent_fg"], width=11, pady=4, relief="raised", bd=2)
            chip._role = "chip"
            chip.grid(row=i // 3, column=i % 3, padx=3, pady=3)

        # --- time settings
        tf = tk.LabelFrame(w, text="Time", padx=8, pady=4); tf.pack(fill="x", padx=10, pady=4)
        clk = tk.IntVar(value=S["clock"])
        tk.Label(tf, text="Clock format:").pack(anchor="w")
        for v, t in ((12, "12-hour (3:45:10 PM)"), (24, "24-hour (15:45:10)")):
            tk.Radiobutton(tf, text=t, variable=clk, value=v,
                           command=lambda: commit(lambda st: st["settings"].__setitem__("clock", clk.get()))).pack(anchor="w")
        sec = tk.BooleanVar(value=S["seconds"])
        tk.Checkbutton(tf, text="Show seconds in clock times", variable=sec,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("seconds", sec.get()))).pack(anchor="w")

        # --- grow time + upgrade percentages
        gf = tk.LabelFrame(w, text="Grow time", padx=8, pady=4); gf.pack(fill="x", padx=10, pady=4)
        row = tk.Frame(gf); row.pack(anchor="w")
        tk.Label(row, text="Base time, no upgrades (min):").pack(side="left")
        base = tk.StringVar(value=f"{st0['base']:g}")
        tk.Entry(row, textvariable=base, width=7).pack(side="left", padx=4)

        def base_changed(*_):
            try: v = float(base.get())
            except ValueError: return
            if v > 0: commit(lambda st: st.__setitem__("base", v))
        base.trace_add("write", base_changed)
        pvars = {}
        for u in UP_KEYS:
            r = tk.Frame(gf); r.pack(anchor="w")
            tk.Label(r, text=f"{UP_NAMES[u]} cuts time by (%):", width=26, anchor="w").pack(side="left")
            pvars[u] = tk.StringVar(value=f"{S['pct'][u]:g}")
            tk.Entry(r, textvariable=pvars[u], width=7).pack(side="left", padx=4)

            def pchanged(*_, u=u):
                try: v = float(pvars[u].get())
                except ValueError: return
                if 0 <= v < 100: commit(lambda st: st["settings"]["pct"].__setitem__(u, v))
            pvars[u].trace_add("write", pchanged)

        # --- defaults for new timers
        df = tk.LabelFrame(w, text="Defaults for new timers", padx=8, pady=4); df.pack(fill="x", padx=10, pady=4)
        dvars = {}
        for u in UP_KEYS:
            dvars[u] = tk.BooleanVar(value=u in S["default_ups"])
            tk.Checkbutton(df, text=UP_NAMES[u], variable=dvars[u],
                           command=lambda: commit(lambda st: st["settings"].__setitem__(
                               "default_ups", [k for k in UP_KEYS if dvars[k].get()]))).pack(anchor="w")

        # --- window / alerts
        af = tk.LabelFrame(w, text="Window and alerts", padx=8, pady=4); af.pack(fill="x", padx=10, pady=4)
        beep = tk.BooleanVar(value=S["beep"]); top = tk.BooleanVar(value=S["topmost"])
        tk.Checkbutton(af, text="Play a sound when a timer is ready", variable=beep,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("beep", beep.get()))).pack(anchor="w")
        sf = tk.Frame(af); sf.pack(anchor="w", fill="x")
        snd = tk.StringVar(value=os.path.basename(S["sound_path"]) or "Built-in beep")
        tk.Label(sf, text="Sound:").pack(side="left")
        tag(tk.Label(sf, textvariable=snd, width=20, anchor="w"), "link").pack(side="left", padx=4)

        def choose_sound():
            from tkinter import filedialog
            p = filedialog.askopenfilename(parent=w, title="Choose a finish sound",
                                           filetypes=[("Audio (wav, mp3, wma)", "*.wav *.mp3 *.wma"), ("All files", "*.*")])
            if p:
                commit(lambda st: st["settings"].__setitem__("sound_path", p))
                snd.set(os.path.basename(p)); play_alert(p)

        def default_sound():
            commit(lambda st: st["settings"].__setitem__("sound_path", "")); snd.set("Built-in beep")
        tk.Button(sf, text="Choose...", command=choose_sound).pack(side="left")
        tk.Button(sf, text="Test", command=lambda: play_alert(load()["settings"]["sound_path"])).pack(side="left", padx=2)
        tk.Button(sf, text="Default", command=default_sound).pack(side="left")
        tk.Checkbutton(af, text="Keep window on top of other windows", variable=top,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("topmost", top.get()))).pack(anchor="w")
        cb_var = tk.BooleanVar(value=S.get("compact_bar", True))
        tk.Checkbutton(af, text="Slim title bar with small buttons (restart to apply)", variable=cb_var,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("compact_bar", cb_var.get()))).pack(anchor="w")

        def restore():
            def f(st):
                st["base"] = DEF_BASE
                keep = st["settings"].get("welcomed", True)
                st["settings"] = json.loads(json.dumps(DEF_SETTINGS)); st["settings"]["welcomed"] = keep
            commit(f)
            set_skin(DEF_SETTINGS["skin"])
            w.destroy(); open_settings()
        bf = tk.Frame(w); bf.pack(fill="x", padx=10, pady=(4, 2))
        tk.Button(bf, text="Restore defaults", command=restore).pack(side="left")
        tk.Button(bf, text="Close", command=w.destroy).pack(side="right")
        tag(tk.Label(w, text=f"Rob Run Harvest Timer v{VERSION}  -  unofficial fan tool, not affiliated with the "
                             "ROB RUN developer", font=("Segoe UI", 7)), "muted").pack(pady=(0, 8))
        paint(w, cur["th"])

    bottom = tk.Frame(root); bottom.pack(side="bottom", fill="x", pady=(0, 6))
    tk.Button(bottom, text="+ Add timer", command=add_timer).pack(side="left", padx=8)
    tk.Button(bottom, text="Settings", command=open_settings).pack(side="right", padx=8)

    def tick():
        st = load()
        cfg = st["settings"]
        th = cur["th"]
        if cfg["skin"] != cur["name"]:
            set_skin(cfg["skin"]); th = cur["th"]
        if topmost["v"] != cfg["topmost"]:
            topmost["v"] = cfg["topmost"]; root.attributes("-topmost", cfg["topmost"])
        ids = [t["id"] for t in st["timers"]]
        for tid in list(panels):          # drop removed
            if tid not in ids:
                panels.pop(tid)["box"].destroy()
        for t in st["timers"]:            # add new
            if t["id"] not in panels:
                build_panel(t)
        for t in st["timers"]:
            p = panels[t["id"]]
            for u in UP_KEYS:
                p["cbs"][u].config(text=f"{UP_NAMES[u]} -{cfg['pct'][u]:g}%")
            mins = minutes(st, t)
            if t["start"]:
                end = t["start"] + mins * 60
                left = end - time.time()
                if left > 0:
                    p["big"].config(text=fmt(left), fg=th["timer"])
                    p["info"].config(text=f"{mins:.1f} min - ready {clock(st, end)}")
                else:
                    p["big"].config(text="READY!", fg=th["ready"])
                    p["info"].config(text=f"since {clock(st, end)}")
                    if not alerted.get(t["id"]):
                        alerted[t["id"]] = True
                        if cfg["beep"]:
                            play_alert(cfg["sound_path"])
                        root.deiconify(); root.lift()
            else:
                last = [c for c in st["cycles"] if c.get("timer") == t["name"]]
                p["big"].config(text="--:--", fg=th["timer"])
                p["info"].config(text=f"{mins:.1f} min" + (f" - last logged {last[-1]['minutes']:.2f}" if last else ""))
        root.after(500, tick)

    set_skin(cur["name"])
    if not load()["settings"]["welcomed"]:
        root.after(500, welcome)
    tick()
    root.mainloop()


def main():
    if len(sys.argv) == 1:
        gui()
    else:
        p = argparse.ArgumentParser(description="Rob Run Harvest Timer (no arguments = open the GUI)")
        p.add_argument("cmd", choices=["start", "ready", "set", "add", "remove", "status"])
        p.add_argument("--timer", type=int)
        p.add_argument("--ago", type=float, default=0.0)
        p.add_argument("--base", type=float)
        p.add_argument("--clock", type=int, choices=[12, 24])
        p.add_argument("--skin")
        p.add_argument("--ups")
        p.add_argument("--name")
        cli(p.parse_args())


if __name__ == "__main__":
    main()
