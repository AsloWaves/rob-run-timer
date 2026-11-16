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
import argparse, json, os, queue, re, shutil, sys, time
from datetime import datetime

VERSION = "1.1.2"
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

    # ---- design-pass skins: these change the shape of the display, not just the colours ----
    # Modern: flat, light, quiet. Big thin numerals, one teal accent, hairline cards, slim progress line.
    "Modern": dict(bg="#e6eaee", panel="#ffffff", screen="#ffffff", fg="#17212b", muted="#6b7885", entry="#f2f5f8",
                   btn="#e9eef3", btn_fg="#17212b", accent="#0b7285", accent_fg="#ffffff", danger="#c92a2a",
                   timer="#17212b", ready="#2b8a3e", logged="#1c7ed6", bar="#17212b", bar_fg="#cfd8e0",
                   bar_hover="#2b3a48", link="#0b7285", font="Segoe UI Light", ui_font="Segoe UI",
                   style="text", prog="flat", flat=True, panel_bw=1, border="#d3dae1", track="#e3e8ed", round=12),
    # Rob Run: the game is a gritty urban crime sandbox, so: asphalt, caution-tape yellow, a stamped hazard
    # plate for the countdown, and police red/blue flashing when a bush is ready.
    "Rob Run": dict(bg="#1b1c1e", panel="#26272a", screen="#26272a", fg="#ececec", muted="#9a9a9a", entry="#151517",
                    btn="#34353a", btn_fg="#f2f2f2", accent="#ffc400", accent_fg="#111111", danger="#ff6b6b",
                    timer="#111111", ready="#ffffff", logged="#7ec8ff", bar="#0e0e0f", bar_fg="#ffc400",
                    bar_hover="#3a3b40", link="#ffc400", font="Impact", ui_font="Bahnschrift SemiBold",
                    style="plate", prog="hazard", flat=True, panel_bw=1, border="#3d3e44", track="#111111",
                    plate="#ffc400", plate_idle="#8a7420", plate_fg="#111111", flash=("#d62828", "#1f4fd8")),
    # Futuristic: black glass, cyan seven-segment readout, segmented LED progress, thin neon outlines.
    "Futuristic": dict(bg="#04070c", panel="#09111c", screen="#050b12", fg="#cfeaf2", muted="#5f8794", entry="#0c1826",
                       btn="#0c1826", btn_fg="#00e5ff", accent="#00e5ff", accent_fg="#02121a", danger="#ff4d6d",
                       timer="#00e5ff", ready="#9dff00", logged="#b388ff", bar="#02050a", bar_fg="#00b8cc",
                       bar_hover="#0f2a38", link="#00e5ff", font="Consolas", ui_font="Bahnschrift SemiLight",
                       style="seg7", seg_off="#0b2a33", prog="segments", flat=True, outline=True, panel_bw=1,
                       border="#0e6b7a", track="#0b2a33"),
    # Flip Clock: walnut and brass, split-flap cards with a centre hinge, tick-mark progress rail.
    "Flip Clock": dict(bg="#2b1d14", panel="#3a281b", screen="#3a281b", fg="#efe3c8", muted="#b79f77", entry="#241810",
                       btn="#4a3423", btn_fg="#f1e6cc", accent="#b8924a", accent_fg="#1d130c", danger="#ff9a8a",
                       timer="#f1e8d0", ready="#ffd166", logged="#a5cfa9", bar="#1d130c", bar_fg="#d4b06a",
                       bar_hover="#4a3423", link="#d4b06a", font="Arial Black", ui_font="Cambria",
                       style="flip", card="#1d1d20", card2="#141416", card_edge="#0a0a0b", split="#050506",
                       brass="#b8924a", prog="ticks", flat=False, panel_bw=2, border="#b8924a", track="#241810"),
}


def _fill(name, th):
    """Give every skin the optional keys, so drawing code can rely on them."""
    base = dict(name=name, panel=th["bg"], style="text", prog="flat", flat=False, outline=False, panel_bw=0,
                ui_font="Segoe UI", flash=None, round=0)
    base.update(th)
    base.setdefault("screen", base["panel"])
    base.setdefault("border", base["bar"])
    base.setdefault("track", base["btn"])
    return base


THEMES = {k: _fill(k, v) for k, v in THEMES.items()}

DEF_SETTINGS = {
    "skin": "Dark",                    # one of THEMES
    "mini": False,                     # clock-only view (just the countdowns)
    "clock": 12,                       # 12 or 24 hour clock for ready times
    "seconds": True,                   # show seconds in clock times
    "beep": True,                      # play a sound when a timer is ready
    "sound_path": "",                  # custom finish sound (.wav/.mp3/.wma); empty = built-in beep
    "topmost": True,                   # keep window above the game
    "compact_bar": True,               # slim custom title bar with small buttons (restart to apply)
    "welcomed": False,                 # first-run welcome already shown
    "default_ups": ["fan", "pump"],    # upgrades pre-ticked on newly added timers
    "pct": {"fan": 12, "pump": 14, "uv": 24},   # time cut per upgrade, in percent
    "verified": ["fan", "pump"],       # upgrades whose % is confirmed in game (UV is still an estimate)
    "toast": True,                     # Windows notification when a timer is ready / about to be
    "flash": True,                     # flash the taskbar button when a timer is ready
    "warn_min": 2,                     # early warning this many minutes before ready (0 = off)
    "hotkeys": {"next": "Ctrl+Alt+H", "all": "Ctrl+Alt+A", "mini": "Ctrl+Alt+M", "through": "Ctrl+Alt+C"},
    "opacity": 100,                    # window opacity in percent
    "clickthrough": False,             # clock-only view ignores the mouse (toggle with its hotkey)
    "check_updates": True,             # look for a newer release on GitHub at start-up
    "pos": None,                       # last window position [x, y]
    "size": {},                        # last window size per view
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
        # First run (or an unreadable file): write the defaults straight away. Returning a fresh
        # default() each call would give the timer a new id every load, and the GUI would rebuild
        # its panel (and reset the window size) on every tick until something happened to save.
        if os.path.exists(STATE):
            try:
                os.replace(STATE, STATE + ".bad")
            except Exception:
                pass
        s = default()
        try:
            save(s)
        except Exception:
            pass
        return s
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
    st["hotkeys"] = {**DEF_SETTINGS["hotkeys"], **st.get("hotkeys", {})}
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


# ---------------------------------------------------------------- Windows helpers: alerts, hotkeys, startup, updates
REPO = "AsloWaves/rob-run-timer"     # where the update checker looks for newer releases
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


AUMID = "RobRunTimer.HarvestTimer"


def toast_identity():
    """Register the app's own name and icon for notifications (per user, no admin needed)."""
    if toast_identity.done:
        return
    toast_identity.done = True
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\AppUserModelId\\" + AUMID) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Rob Run Harvest Timer")
            ico = os.path.join(getattr(sys, "_MEIPASS", DIR), "assets", "icon.ico")
            if os.path.isfile(ico):
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, ico)
    except Exception:
        pass


toast_identity.done = False


def toast(title, body):
    """Windows toast notification via PowerShell (no extra packages). Fire and forget."""
    toast_identity()
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
          "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
          "$x=$t.GetElementsByTagName('text');"
          "$x.Item(0).AppendChild($t.CreateTextNode($env:RR_TITLE)) | Out-Null;"
          "$x.Item(1).AppendChild($t.CreateTextNode($env:RR_BODY)) | Out-Null;"
          "$n=[Windows.UI.Notifications.ToastNotification]::new($t);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
          "$env:RR_AUMID).Show($n)")
    try:
        import subprocess
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
                         env=dict(os.environ, RR_TITLE=title, RR_BODY=body, RR_AUMID=AUMID), creationflags=0x08000000,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def flash_window(win):
    """Flash the taskbar button until the window is brought to the front."""
    try:
        import ctypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p), ("dwFlags", ctypes.c_uint),
                        ("uCount", ctypes.c_uint), ("dwTimeout", ctypes.c_uint)]
        u = ctypes.windll.user32
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        u.FlashWindowEx(ctypes.byref(FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0xE, 0, 0)))   # tray, until foreground
    except Exception:
        pass


def blip(freq=1200, ms=60):
    try:
        import winsound
        winsound.Beep(freq, ms)
    except Exception:
        pass


MODS = {"alt": 1, "ctrl": 2, "control": 2, "shift": 4, "win": 8}


def parse_hotkey(spec):
    """'Ctrl+Alt+H' -> (modifier mask, virtual-key code), or None if it isn't usable."""
    parts = [p.strip().lower() for p in (spec or "").split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for p in parts[:-1]:
        if p not in MODS:
            return None
        mods |= MODS[p]
    k, fkey = parts[-1], False
    if len(k) == 1 and k.isalnum():
        vk = ord(k.upper())
    elif k[0] == "f" and k[1:].isdigit() and 1 <= int(k[1:]) <= 24:
        vk, fkey = 0x6F + int(k[1:]), True
    else:
        vk = {"space": 0x20, "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E,
              "pageup": 0x21, "pagedown": 0x22}.get(k)
    if vk is None or not (mods or fkey):
        return None
    return mods, vk


class Hotkeys:
    """System-wide hotkeys on a background thread. Presses arrive on `.q` as action names."""
    def __init__(self, specs):
        import queue, threading
        self.q, self.ok, self.failed, self._tid = queue.Queue(), set(), set(), None
        self._ready = threading.Event()
        self.t = threading.Thread(target=self._run, args=(dict(specs),), daemon=True)
        self.t.start()
        self._ready.wait(2)

    def _run(self, specs):
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)      # make sure this thread has a message queue
        ids = {}
        for i, (act, spec) in enumerate(specs.items(), 1):
            p = parse_hotkey(spec)
            if p is None:
                continue
            if u.RegisterHotKey(None, i, p[0] | 0x4000, p[1]):   # 0x4000 = no auto-repeat
                ids[i] = act; self.ok.add(act)
            else:
                self.failed.add(act)
        self._ready.set()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x312 and msg.wParam in ids:
                self.q.put(ids[msg.wParam])
        for i in ids:
            u.UnregisterHotKey(None, i)

    def stop(self):
        try:
            import ctypes
            if self._tid:
                ctypes.windll.user32.PostThreadMessageW(self._tid, 0x12, 0, 0)    # WM_QUIT
            self.t.join(1.0)
        except Exception:
            pass


def autostart_get():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, "RobRunTimer")
        return True
    except Exception:
        return False


def autostart_set(on):
    import winreg
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{os.path.abspath(__file__)}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "RobRunTimer", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "RobRunTimer")
            except FileNotFoundError:
                pass


def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3])


def check_update(q):
    """Ask GitHub for the latest release; queue (version, url) if it is newer. Silent on any failure."""
    try:
        import urllib.request
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                     headers={"User-Agent": "RobRunTimer", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.load(r)
        tag = d.get("tag_name", "")
        if _ver(tag) > _ver(VERSION):
            q.put((tag.lstrip("vV"), d.get("html_url", "")))
    except Exception:
        pass


def suggest_pcts(s):
    """For upgrades not yet verified in game, estimate their % from logged cycles in which they are the
    only unverified upgrade: {upgrade: (percent, number of cycles)}."""
    cfg, ver, out = s["settings"], set(s["settings"].get("verified", [])), {}
    for u in UP_KEYS:
        if u in ver:
            continue
        vals = []
        for c in s["cycles"]:
            ups = c.get("ups", [])
            if u in ups and c.get("minutes") and all(k in ver or k == u for k in ups):
                vals.append((1 - c["minutes"] / s["base"]) * 100 - sum(cfg["pct"][k] for k in ups if k != u))
        if vals:
            out[u] = (sum(vals) / len(vals), len(vals))
    return out


def apply_region(win, radius):
    """Round the corners of a borderless window by clipping it. Returns True if it handled the window."""
    try:
        import ctypes
        from ctypes import wintypes
        if not win.overrideredirect():
            return False
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        if radius:
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            rgn = g.CreateRoundRectRgn(0, 0, r.right - r.left + 1, r.bottom - r.top + 1, radius * 2, radius * 2)
            u.SetWindowRgn(hwnd, rgn, True)       # the system owns the region from here
        else:
            u.SetWindowRgn(hwnd, None, True)
        return True
    except Exception:
        return False


def set_clickthrough(win, on):
    """Let mouse clicks pass straight through the window to whatever is underneath."""
    try:
        import ctypes
        u = ctypes.windll.user32
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        ex = u.GetWindowLongW(hwnd, -20)
        u.SetWindowLongW(hwnd, -20, (ex | 0x80020) if on else (ex & ~0x20))
    except Exception:
        pass


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


try:
    import tkinter as tk
    import tkinter.font as tkfont
except Exception:   # the CLI keeps working without Tk
    tk = tkfont = None


def _restyle_font(w, family):
    """Swap a widget's font family but keep its size and weight."""
    try:
        f = tkfont.Font(root=w, font=w.cget("font")).actual()
        w.config(font=(family, abs(int(f["size"])), f["weight"]))
    except Exception:
        pass


def paint(w, th, bg=None):
    """Recursively apply a skin. Widgets can carry a `_role` for special treatment."""
    bg = bg or th["bg"]
    outer = bg
    cls, role, flat = w.winfo_class(), getattr(w, "_role", None), th["flat"]
    if cls == "Canvas" and role == "panel":
        bg = th["panel"]
    try:
        if cls in ("Frame", "Toplevel", "Tk"):
            if role == "bar":
                w.config(bg=th["bar"])
            elif role == "panel":
                bg = th["panel"]
                w.config(bg=bg, highlightthickness=th["panel_bw"], highlightbackground=th["border"],
                         highlightcolor=th["border"])
            else:
                w.config(bg=bg)
                if cls in ("Tk", "Toplevel"):
                    w.config(highlightthickness=1, highlightbackground=th["bar"], highlightcolor=th["bar"])
        elif cls == "Labelframe":
            w.config(bg=bg, fg=th["fg"])
            _restyle_font(w, th["ui_font"])
        elif cls == "Label":
            if role in ("bar_text", "bar_btn"):
                w.config(bg=th["bar"], fg=th["bar_fg"])
            elif role == "muted":
                w.config(bg=bg, fg=th["muted"])
            elif role == "link":
                w.config(bg=bg, fg=th["link"])
            else:
                w.config(bg=bg, fg=th["fg"])
            _restyle_font(w, th["ui_font"])
        elif cls == "Button":
            solid = role in ("accent", "danger")
            b, f = (th["accent"], th["accent_fg"]) if role == "accent" else \
                   (th["btn"], th["danger"]) if role == "danger" else (th["btn"], th["btn_fg"])
            w.config(bg=b, fg=f, activebackground=b if solid else th["entry"], activeforeground=f)
            if flat:
                w.config(relief="flat", bd=0, padx=8, pady=3, highlightbackground=th["border"],
                         highlightcolor=th["accent"], highlightthickness=1 if (th["outline"] and role != "accent") else 0)
            else:
                w.config(relief="raised", bd=2, padx=6, pady=1, highlightthickness=0)
            _restyle_font(w, th["ui_font"])
        elif cls == "Entry":
            w.config(bg=th["entry"], fg=th["fg"], insertbackground=th["fg"])
            if flat:
                w.config(relief="flat", bd=0, highlightthickness=1, highlightbackground=th["border"],
                         highlightcolor=th["accent"])
            else:
                w.config(relief="sunken", bd=2, highlightthickness=0)
            _restyle_font(w, th["ui_font"])
        elif cls in ("Checkbutton", "Radiobutton"):
            if role != "chip":
                w.config(bg=bg, fg=th["fg"], selectcolor=th["entry"], activebackground=bg, activeforeground=th["fg"])
                _restyle_font(w, th["ui_font"])
        elif cls == "Scale":
            w.config(bg=bg, fg=th["fg"], troughcolor=th["entry"], highlightthickness=0, activebackground=th["accent"])
        elif cls == "Canvas" and role == "display":
            w.config(bg=th["screen"])
    except Exception:
        pass
    for c in w.winfo_children():
        paint(c, th, bg)
    rp = getattr(w, "_rp", None)     # rounded wrappers (RPanel / Btn / REntry) redraw once their children are styled
    if rp:
        rp(th, outer)


# ---------------------------------------------------------------- the countdown display
SEGS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
        "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g"}


def _seg_poly(n, x, y, w, h, t, g, shear=0.10):
    """Polygon for one seven-segment bar; shear leans the digit forward."""
    def hs(yc):
        x1, x2 = x + t / 2 + g, x + w - t / 2 - g
        return [(x1, yc), (x1 + t / 2, yc - t / 2), (x2 - t / 2, yc - t / 2), (x2, yc), (x2 - t / 2, yc + t / 2), (x1 + t / 2, yc + t / 2)]

    def vs(xc, y1, y2):
        return [(xc, y1), (xc + t / 2, y1 + t / 2), (xc + t / 2, y2 - t / 2), (xc, y2), (xc - t / 2, y2 - t / 2), (xc - t / 2, y1 + t / 2)]
    mid = y + h / 2
    pts = {"a": hs(y + t / 2), "g": hs(mid), "d": hs(y + h - t / 2),
           "f": vs(x + t / 2, y + t / 2 + g, mid - g), "b": vs(x + w - t / 2, y + t / 2 + g, mid - g),
           "e": vs(x + t / 2, mid + g, y + h - t / 2 - g), "c": vs(x + w - t / 2, mid + g, y + h - t / 2 - g)}[n]
    return [(px + (y + h - py) * shear, py) for px, py in pts]


def _clip_x(pts, lo, hi):
    """Clip a polygon to lo <= x <= hi (Sutherland-Hodgman)."""
    def clip(pts, inside, xv):
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            cross = (xv, q[1] + (p[1] - q[1]) * (xv - q[0]) / (p[0] - q[0])) if p[0] != q[0] else None
            if inside(p):
                if not inside(q) and cross: out.append(cross)
                out.append(p)
            elif inside(q) and cross:
                out.append(cross)
        return out
    pts = clip(pts, lambda p: p[0] >= lo, lo)
    return clip(pts, lambda p: p[0] <= hi, hi) if pts else pts


def _hazard(cv, x0, y0, x1, y1, c1, c2):
    """Diagonal caution-tape stripes."""
    if x1 <= x0:
        return
    cv.create_rectangle(x0, y0, x1, y1, fill=c1, outline="")
    h = y1 - y0
    period = max(8, h * 1.6)
    s = x0 - h
    while s < x1:
        poly = _clip_x([(s, y1), (s + period / 2, y1), (s + period / 2 + h, y0), (s + h, y0)], x0, x1)
        if len(poly) >= 3:
            cv.create_polygon(poly, fill=c2, outline="")
        s += period


if tk:
    class Display(tk.Canvas):
        """Countdown readout. The skin's `style` picks how the digits are drawn:
        text (plain font), plate (hazard plate), seg7 (seven-segment), flip (split-flap cards)."""
        W, H = 240, 98

        def __init__(self, parent, w=240, h=98):
            super().__init__(parent, width=w, height=h, highlightthickness=0, bd=0)
            self._role, self._key, self._last = "display", None, None
            self.W, self.H = w, h
            self._geo()
            self.bind("<Configure>", self._resize)
            self._ftxt, self._ftheme, self._tok, self._wins = None, None, 0, []

        def _geo(self):
            self._s = max(0.4, min(self.W / 240, self.H / 98))   # everything scales from the 240x98 design size
            self._bot = max(3, int(6 * self._s))                    # progress bar thickness

        def _resize(self, e):
            if e.width < 20 or (e.width, e.height) == (self.W, self.H):
                return
            self.W, self.H = e.width, e.height
            self._geo()
            if self._last:
                self._key = None
                self.show(*self._last)

        def _clear_wins(self):
            for w in self._wins:
                try:
                    w.destroy()
                except Exception:
                    pass
            self._wins = []

        def show(self, th, text, state, frac, flash=0):
            self._last = (th, text, state, frac, flash)
            key = (th["name"], text, state, int(frac * self.W), flash if state == "ready" else 0)
            if key == self._key:
                return
            self._key = key
            self._tok += 1
            self._clear_wins()
            self.delete("all")
            self.config(bg=th["screen"])
            col = th["ready"] if state == "ready" else th["timer"]
            old, self._ftxt = self._ftxt, text
            prev_theme, self._ftheme = self._ftheme, th["name"]
            if th["style"] == "flip" and old and prev_theme == th["name"] and len(old) == len(text) and old != text:
                self._anim(th, old, text, col, state, flash, frac, 0, self._tok)
                return
            getattr(self, "_" + th["style"])(th, text, col, state, flash)
            self._progress(th, 1.0 if state == "ready" else frac, state)

        FLIP_FRAMES, FLIP_MS = 10, 32

        def _anim(self, th, old, new, col, state, flash, frac, i, tok):
            if tok != self._tok:
                return
            try:
                self._clear_wins()
                self.delete("all")
                n = self.FLIP_FRAMES
                self._flip(th, new, col, state, flash, (old, i / n) if i < n else None)
                self._progress(th, 1.0 if state == "ready" else frac, state)
                if i < n:
                    self.after(self.FLIP_MS, lambda: self._anim(th, old, new, col, state, flash, frac, i + 1, tok))
            except tk.TclError:
                pass

        def _fit(self, family, text, size, maxw, weight="normal"):
            while size > 10 and tkfont.Font(root=self, family=family, size=size, weight=weight).measure(text) > maxw:
                size -= 2
            return size

        def _text(self, th, text, col, state, flash):
            size = self._fit(th["font"], text, int(40 * self._s), self.W - 16)
            self.create_text(self.W / 2, (self.H - self._bot - 8) / 2 + 2, text=text, fill=col, font=(th["font"], size))

        def _plate(self, th, text, col, state, flash):
            x0, y0, x1, y1 = 6, 4, self.W - 6, self.H - self._bot - 10
            if state == "ready" and th["flash"]:
                pc, fg = th["flash"][flash % 2], "#ffffff"      # police lights
            elif state == "idle":
                pc, fg = th["plate_idle"], th["plate_fg"]
            else:
                pc, fg = th["plate"], th["plate_fg"]
            self.create_rectangle(x0, y0, x1, y1, fill=pc, outline="#000000", width=2)
            _hazard(self, x0 + 3, y0 + 3, x1 - 3, y0 + 9, "#111111", th["plate"])
            _hazard(self, x0 + 3, y1 - 9, x1 - 3, y1 - 3, "#111111", th["plate"])
            size = self._fit(th["font"], text, int(34 * self._s), self.W - int(40 * min(1, self._s)))
            self.create_text(self.W / 2, (y0 + y1) / 2, text=text, fill=fg, font=(th["font"], size))

        def _seg7(self, th, text, col, state, flash):
            if state == "ready":    # seven segments can't spell READY, so use the font
                return self._text(th, text, col, state, flash)
            dw, dh, t, gap, cw = 32, 64, 7, 9, 14
            toks = [("c",) if ch == ":" else ("d", ch) for ch in text if ch == ":" or ch in SEGS]
            total = sum(cw if k[0] == "c" else dw for k in toks) + gap * (len(toks) - 1)
            av = self.H - self._bot - 14
            sc = min((self.W - 16) / total, av / dh)
            x, y = (self.W - total * sc) / 2, 4 + (av - dh * sc) / 2
            for k in toks:
                if k[0] == "c":
                    for fy in (0.3, 0.7):
                        cy = y + dh * sc * fy
                        self.create_rectangle(x + cw * sc / 2 - 3 * sc, cy - 3 * sc, x + cw * sc / 2 + 3 * sc, cy + 3 * sc, fill=col, outline="")
                    x += (cw + gap) * sc
                else:
                    for n in "abcdefg":
                        self.create_polygon(_seg_poly(n, x, y, dw * sc, dh * sc, t * sc, 1.6 * sc),
                                            fill=col if n in SEGS[k[1]] else th["seg_off"], outline="")
                    x += (dw + gap) * sc

        def _half(self, th, x, y, w, hh, ch, col, top):
            """One clipped half of a card, as a tiny child canvas (tk can't clip text on a canvas)."""
            if hh < 1.5:
                return
            c = tk.Canvas(self, width=max(1, int(w)), height=max(1, int(hh)), highlightthickness=1,
                          highlightbackground=th["card_edge"], bg=th["card"] if top else th["card2"], bd=0)
            c.create_text(w / 2, hh if top else 0, text=ch, fill=col, font=(th["font"], -int(self._fh * 0.6)))
            self._wins.append(c)
            self.create_window(x, y - hh if top else y, window=c, anchor="nw")

        def _flip(self, th, text, col, state, flash, anim=None):
            cw, chh, gap, colw = 44, 66, 5, 12
            toks = [("c",) if ch == ":" else ("k", ch) for ch in text]
            total = sum(colw if k[0] == "c" else cw for k in toks) + gap * (len(toks) - 1)
            av = self.H - self._bot - 14
            sc = min((self.W - 12) / total, av / chh)
            w, h = cw * sc, chh * sc
            self._fh = h
            x, y = (self.W - total * sc) / 2, 4 + (av - h) / 2
            for idx, k in enumerate(toks):
                if k[0] == "c":
                    for fy in (0.32, 0.68):
                        cy = y + h * fy
                        self.create_rectangle(x + colw * sc / 2 - 3, cy - 3, x + colw * sc / 2 + 3, cy + 3, fill=th["brass"], outline="")
                    x += (colw + gap) * sc
                    continue
                mid = y + h / 2
                if anim and anim[0][idx] != k[1]:
                    old, t = anim[0][idx], anim[1]
                    h2 = h / 2
                    # resting halves: new digit above the hinge, old digit below it
                    self._half(th, x, mid, w, h2, k[1], col, True)
                    self._half(th, x, mid, w, h2, old, col, False)
                    if t < 0.5:     # old top flap falls toward the hinge
                        self._half(th, x, mid, w, h2 * (1 - 2 * t), old, col, True)
                    else:           # new bottom flap lands below the hinge
                        self._half(th, x, mid, w, h2 * (2 * t - 1), k[1], col, False)
                else:
                    self.create_rectangle(x, y, x + w, mid, fill=th["card"], outline=th["card_edge"])
                    self.create_rectangle(x, mid, x + w, y + h, fill=th["card2"], outline=th["card_edge"])
                    self.create_text(x + w / 2, mid, text=k[1], fill=col, font=(th["font"], -int(h * 0.6)))
                self.create_line(x, mid, x + w, mid, fill=th["split"], width=2)
                for hx in (x - 1, x + w - 2):    # hinge pins
                    self.create_rectangle(hx, mid - 4, hx + 3, mid + 4, fill=th["brass"], outline="")
                x += (cw + gap) * sc

        def _progress(self, th, frac, state):
            x0, x1, y0, y1 = 8, self.W - 8, self.H - 5 - self._bot, self.H - 5
            frac = max(0.0, min(1.0, frac))
            fill = th["ready"] if state == "ready" else th["accent"]
            p, span = th["prog"], x1 - x0
            if p == "flat" and th["round"]:
                ym, lw = (y0 + y1) / 2, y1 - y0
                self.create_line(x0 + lw / 2, ym, x1 - lw / 2, ym, fill=th["track"], width=lw, capstyle="round")
                if frac > 0:
                    self.create_line(x0 + lw / 2, ym, max(x0 + lw / 2, x0 + span * frac - lw / 2), ym,
                                     fill=fill, width=lw, capstyle="round")
            elif p == "flat":
                self.create_rectangle(x0, y0, x1, y1, fill=th["track"], outline="")
                if frac > 0:
                    self.create_rectangle(x0, y0, x0 + span * frac, y1, fill=fill, outline="")
            elif p == "segments":
                n = 24
                sw = (span - (n - 1) * 2) / n
                for i in range(n):
                    sx = x0 + i * (sw + 2)
                    self.create_rectangle(sx, y0, sx + sw, y1, fill=fill if i < int(frac * n + 0.0001) else th["track"], outline="")
            elif p == "hazard":
                self.create_rectangle(x0, y0, x1, y1, fill=th["track"], outline="")
                _hazard(self, x0, y0, x0 + span * frac, y1, "#111111", th["plate"])
            elif p == "ticks":
                ym = (y0 + y1) / 2
                self.create_line(x0, ym, x1, ym, fill=th["track"], width=2)
                if frac > 0:
                    self.create_line(x0, ym, x0 + span * frac, ym, fill=th["brass"], width=4)
                for i in range(11):
                    tx = x0 + span * i / 10
                    self.create_line(tx, y0 - (2 if i % 5 == 0 else 0), tx, y1 + (2 if i % 5 == 0 else 0), fill=th["brass"])

def _rrect(cv, x0, y0, x1, y1, r, **kw):
    """Rounded rectangle (a plain one when r is 0)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    if r < 1:
        kw.setdefault("outline", "")
        return cv.create_rectangle(x0, y0, x1, y1, **kw)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return cv.create_polygon(pts, smooth=True, **kw)


if tk:
    class RPanel(tk.Canvas):
        """A card whose corners follow the skin's `round` radius. Put children in `.body`."""
        def __init__(self, parent):
            super().__init__(parent, highlightthickness=0, bd=0)
            self._role, self.body, self._th, self._ins = "panel", tk.Frame(self), None, 0
            self._win = self.create_window(0, 0, window=self.body, anchor="nw")
            self.body.bind("<Configure>", lambda e: self._size())
            self.bind("<Configure>", self._stretch)

        def _stretch(self, e):
            i = self._ins
            self.itemconfigure(self._win, width=max(1, e.width - 2 * i), height=max(1, e.height - 2 * i))
            self._draw()

        def _size(self):
            i = self._ins
            self._wh = (self.body.winfo_reqwidth() + 2 * i, self.body.winfo_reqheight() + 2 * i)
            self.config(width=self._wh[0], height=self._wh[1])
            self.coords(self._win, i, i)
            self._draw()

        def _draw(self):
            self.delete("bg")
            th = self._th
            if not th or not getattr(self, "_wh", None):
                return
            bw = th["panel_bw"]
            W, H = max(self.winfo_width(), self._wh[0]), max(self.winfo_height(), self._wh[1])
            _rrect(self, bw / 2, bw / 2, W - bw / 2 - 1, H - bw / 2 - 1, th["round"],
                   fill=th["panel"], outline=th["border"] if bw else "", width=bw, tags="bg")
            self.tag_lower("bg")

        def _rp(self, th, outer):
            self._th, self._ins = th, th["panel_bw"] + th["round"] // 2
            self.config(bg=outer)
            self._size()

    class Btn(tk.Canvas):
        """A tk.Button that draws itself with rounded corners when the skin asks for them."""
        def __init__(self, parent, **kw):
            super().__init__(parent, highlightthickness=0, bd=0)
            self.b = tk.Button(self, **kw)
            self._win = self.create_window(0, 0, window=self.b, anchor="nw")
            self._th, self._hov, self._r = None, False, None
            self.bind("<Configure>", self._conf)
            self.bind("<Enter>", lambda e: self._hover(True))
            self.bind("<Leave>", lambda e: self._hover(False))
            self.bind("<ButtonRelease-1>", self._click)

        @property
        def _role(self):
            return self._r

        @_role.setter
        def _role(self, v):
            self._r = v
            self.b._role = v

        def _round(self):
            return bool(self._th and self._th["round"])

        def _hover(self, on):
            self._hov = on
            if self._round():
                self._draw()

        def _click(self, e):
            if self._round() and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
                self.b.invoke()

        def _conf(self, e):
            if self._round():
                self._draw()
            else:
                self.itemconfigure(self._win, width=e.width, height=e.height)

        def _draw(self):
            self.delete("all")
            b, w, h = self.b, self.winfo_width(), self.winfo_height()
            if w < 4:
                return
            fill = b.cget("activebackground") if self._hov else b.cget("bg")
            _rrect(self, 0, 0, w - 1, h - 1, self._th["round"], fill=fill)
            self.create_text(w / 2, h / 2, text=b.cget("text"), fill=b.cget("fg"), font=b.cget("font"))

        def _rp(self, th, outer):
            self._th = th
            self.config(bg=outer)
            self.b.update_idletasks()
            self.config(width=self.b.winfo_reqwidth(), height=self.b.winfo_reqheight())
            if th["round"]:
                self.itemconfigure(self._win, state="hidden")
                self.config(cursor="hand2")
                self._draw()
            else:
                self.itemconfigure(self._win, state="normal", width=self.winfo_width(), height=self.winfo_height())
                self.config(cursor="")

    class REntry(tk.Canvas):
        """A tk.Entry inside a rounded field when the skin asks for rounded corners."""
        PX, PY = 7, 4

        def __init__(self, parent, **kw):
            super().__init__(parent, highlightthickness=0, bd=0)
            self.e = tk.Entry(self, **kw)
            self._win = self.create_window(0, 0, window=self.e, anchor="nw")
            self._th, self._focus = None, False
            self.bind("<Configure>", lambda e: self._layout())
            self.e.bind("<FocusIn>", lambda e: self._set_focus(True), add="+")
            self.e.bind("<FocusOut>", lambda e: self._set_focus(False), add="+")

        def get(self):
            return self.e.get()

        def _set_focus(self, on):
            self._focus = on
            if self._th and self._th["round"]:
                self._layout()

        def _layout(self):
            w, h = self.winfo_width(), self.winfo_height()
            self.delete("bg")
            if w < 4:
                return
            if self._th and self._th["round"]:
                _rrect(self, 0, 0, w - 1, h - 1, self._th["round"], fill=self.e.cget("bg"),
                       outline=self._th["accent"] if self._focus else self._th["border"], tags="bg")
                self.tag_lower("bg")
                self.coords(self._win, self.PX, self.PY)
                self.itemconfigure(self._win, width=max(1, w - 2 * self.PX), height=max(1, h - 2 * self.PY))
            else:
                self.coords(self._win, 0, 0)
                self.itemconfigure(self._win, width=w, height=h)

        def _rp(self, th, outer):
            self._th = th
            self.config(bg=outer)
            px, py = (self.PX, self.PY) if th["round"] else (0, 0)
            if th["round"]:
                self.e.config(bd=0, highlightthickness=0, relief="flat")
            self.e.update_idletasks()
            self.config(width=self.e.winfo_reqwidth() + 2 * px, height=self.e.winfo_reqheight() + 2 * py)
            self._layout()


def set_corners(win, rounded):
    """Ask Windows 11 to round (or not) the outer corners of a top-level window."""
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        v = ctypes.c_int(2 if rounded else 1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(v), 4)
    except Exception:
        pass



def dbg(msg):
    if os.environ.get("ROBRUN_DEBUG"):
        with open(os.environ["ROBRUN_DEBUG"], "a") as f:
            f.write("%.2f %s\n" % (time.time() % 1000, msg))


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
    hk, ct, op, warned = {"obj": None}, {"v": False}, {"v": 100}, {}
    S0 = load()["settings"]
    if S0.get("pos"):
        try:
            x, y = S0["pos"]
            root.geometry("+%d+%d" % (max(0, min(x, root.winfo_screenwidth() - 120)),
                                      max(0, min(y, root.winfo_screenheight() - 80))))
        except Exception:
            pass

    rr = {"id": None}

    def reround(*_):
        """Clip the borderless window to rounded corners (only for skins that ask for them)."""
        if rr["id"]:
            root.after_cancel(rr["id"])

        def go():
            rr["id"] = None
            apply_region(root, 12 if cur["th"]["round"] else 0)
        rr["id"] = root.after(120, go)
    root.bind("<Configure>", lambda e: reround() if e.widget is root else None)

    def save_pos():
        try:
            if root.state() == "normal":
                st = load(); st["settings"]["pos"] = [root.winfo_x(), root.winfo_y()]; save(st)
        except Exception:
            pass

    def quit_app():
        try:
            if root.state() == "normal":
                saved[view["mini"]] = (root.winfo_width(), root.winfo_height())
            st = load()
            if root.state() == "normal":
                st["settings"]["pos"] = [root.winfo_x(), root.winfo_y()]
            st["settings"]["size"] = {str(k): list(v) for k, v in saved.items()}
            save(st)
        except Exception:
            pass
        if hk["obj"]:
            hk["obj"].stop()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", quit_app)

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
            wdg.bind("<ButtonRelease-1>", lambda e: save_pos())

        away = {"v": False}      # True from the moment we iconify until the window is restored

        def minimize():
            # A borderless (overrideredirect) window can't be iconified, so give it a normal frame first.
            # Doing that makes Windows remap the window, which must not be mistaken for a restore.
            dbg("minimize() called")
            root.overrideredirect(False)
            root.update_idletasks()

            def go():
                away["v"] = True
                root.iconify()
                dbg("iconify issued; state=%s" % root.state())
            root.after(80, go)

        def on_map(e):
            if e.widget is root and away["v"] and not root.overrideredirect():
                away["v"] = False       # genuinely restored from the taskbar: go borderless again
                dbg("restored; re-applying borderless")
                root.after(50, lambda: (root.overrideredirect(True), taskbar(), reround()))
        root.bind("<Map>", on_map)

        def small_btn(text, cmd, hover):
            b = tag(tk.Label(bar, text=text, font=("Segoe UI", 8), width=3), "bar_btn")
            b.pack(side="right", fill="y")
            b.bind("<Button-1>", lambda e: (dbg("click on %r" % text), cmd()))
            b.bind("<Enter>", lambda e: b.config(bg=hover or cur["th"]["bar_hover"]))
            b.bind("<Leave>", lambda e: b.config(bg=cur["th"]["bar"]))
        small_btn("✕", quit_app, "#c42b1c")
        small_btn("–", minimize, None)
        small_btn("▭", lambda: toggle_mini(), None)

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
        set_corners(root, cur["th"]["round"])
        reround()
        w = settings_win["w"]
        if w is not None and w.winfo_exists():
            paint(w, cur["th"])
            set_corners(w, cur["th"]["round"])

    def build_panel(t):
        tid = t["id"]
        box = RPanel(holder)
        box.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        inner = tk.Frame(box.body)
        inner.pack(fill="both", expand=True, padx=8, pady=6)
        name = tk.StringVar(value=t["name"])

        def upd(fn):
            st = load(); tt = find(st, tid)
            if tt is not None:
                fn(st, tt); save(st)

        name.trace_add("write", lambda *_: upd(lambda st, tt: tt.__setitem__("name", name.get())))
        REntry(inner, textvariable=name, justify="center", font=("Segoe UI", 10, "bold")).pack(fill="x")
        disp = Display(inner); disp.pack(fill="both", expand=True, pady=(4, 0))
        info = tag(tk.Label(inner, text="", font=("Segoe UI", 8)), "muted"); info.pack()
        ago = tk.StringVar(value="0")
        r = tk.Frame(inner); r.pack(pady=2)
        tk.Label(r, text="Harvested").pack(side="left")
        REntry(r, textvariable=ago, width=4).pack(side="left", padx=3)
        tk.Label(r, text="min ago").pack(side="left")

        def start():
            try: a = float(ago.get())
            except ValueError: a = 0
            st = load(); tt = find(st, tid)
            if tt is not None:
                do_start(st, tt, a)
            ago.set("0"); alerted[tid] = False; warned[tid] = False

        def ready():
            st = load(); tt = find(st, tid)
            if tt is not None and do_ready(st, tt):
                root.after(150, offer_calibration)

        def reset():
            def f(st, tt): tt["start"] = None; tt["open"] = None
            upd(f)

        tag(Btn(inner, text="Harvested - start timer", command=start, font=("Segoe UI", 10), height=2),
            "accent").pack(fill="x", pady=2)
        Btn(inner, text="Actually ready now (log)", command=ready).pack(fill="x")
        Btn(inner, text="Reset", command=reset).pack(fill="x", pady=2)
        srow = tk.Frame(inner); srow.pack(fill="x", pady=(4, 0))
        slbl = tag(tk.Label(srow, text="", font=("Segoe UI", 8), anchor="w"), "muted")
        slbl.pack(side="left")

        def pick_sound():
            from tkinter import filedialog
            f = filedialog.askopenfilename(parent=root, title="Sound for this timer",
                                           filetypes=[("Audio (wav, mp3, wma)", "*.wav *.mp3 *.wma"), ("All files", "*.*")])
            if f:
                upd(lambda st, tt: tt.__setitem__("sound", f)); play_alert(f)
        Btn(srow, text="x", command=lambda: upd(lambda st, tt: tt.__setitem__("sound", ""))).pack(side="right")
        Btn(srow, text="Sound...", command=pick_sound).pack(side="right", padx=2)
        vs, cbs = {}, {}
        for u in UP_KEYS:
            vs[u] = tk.BooleanVar(value=u in t["ups"])
            def cb(u=u):
                upd(lambda st, tt: tt.__setitem__("ups", [k for k in UP_KEYS if vs[k].get()]))
            cbs[u] = tk.Checkbutton(inner, text=UP_NAMES[u], variable=vs[u], command=cb)
            cbs[u].pack(anchor="w")

        def remove():
            st = load()
            if len(st["timers"]) > 1:
                st["timers"] = [x for x in st["timers"] if x["id"] != tid]; save(st)
        tag(Btn(inner, text="Remove this timer", command=remove), "danger").pack(fill="x", pady=(4, 0))
        panels[tid] = {"box": box, "disp": disp, "info": info, "cbs": cbs, "slbl": slbl}
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
        Btn(w, text="Got it", command=done, width=12).pack(pady=(0, 12))
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
        cols = tk.Frame(w); cols.pack(fill="both")
        left = tk.Frame(cols); left.pack(side="left", fill="both", anchor="n")
        right = tk.Frame(cols); right.pack(side="left", fill="both", anchor="n")

        def commit(fn):
            st = load(); fn(st); save(st)

        # --- skin
        kf = tk.LabelFrame(left, text="Skin", padx=8, pady=6); kf.pack(fill="x", padx=10, pady=(10, 4))
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
        tf = tk.LabelFrame(left, text="Time", padx=8, pady=4); tf.pack(fill="x", padx=10, pady=4)
        clk = tk.IntVar(value=S["clock"])
        tk.Label(tf, text="Clock format:").pack(anchor="w")
        for v, t in ((12, "12-hour (3:45:10 PM)"), (24, "24-hour (15:45:10)")):
            tk.Radiobutton(tf, text=t, variable=clk, value=v,
                           command=lambda: commit(lambda st: st["settings"].__setitem__("clock", clk.get()))).pack(anchor="w")
        sec = tk.BooleanVar(value=S["seconds"])
        tk.Checkbutton(tf, text="Show seconds in clock times", variable=sec,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("seconds", sec.get()))).pack(anchor="w")

        # --- grow time + upgrade percentages
        gf = tk.LabelFrame(left, text="Grow time", padx=8, pady=4); gf.pack(fill="x", padx=10, pady=4)
        row = tk.Frame(gf); row.pack(anchor="w")
        tk.Label(row, text="Base time, no upgrades (min):").pack(side="left")
        base = tk.StringVar(value=f"{st0['base']:g}")
        REntry(row, textvariable=base, width=7).pack(side="left", padx=4)

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
            REntry(r, textvariable=pvars[u], width=7).pack(side="left", padx=4)

            def pchanged(*_, u=u):
                try: v = float(pvars[u].get())
                except ValueError: return
                if 0 <= v < 100: commit(lambda st: st["settings"]["pct"].__setitem__(u, v))
            pvars[u].trace_add("write", pchanged)

        # --- defaults for new timers
        df = tk.LabelFrame(left, text="Defaults for new timers", padx=8, pady=4); df.pack(fill="x", padx=10, pady=4)
        dvars = {}
        for u in UP_KEYS:
            dvars[u] = tk.BooleanVar(value=u in S["default_ups"])
            tk.Checkbutton(df, text=UP_NAMES[u], variable=dvars[u],
                           command=lambda: commit(lambda st: st["settings"].__setitem__(
                               "default_ups", [k for k in UP_KEYS if dvars[k].get()]))).pack(anchor="w")

        # --- window / alerts
        af = tk.LabelFrame(right, text="Sound and window", padx=8, pady=4); af.pack(fill="x", padx=10, pady=4)
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
        Btn(sf, text="Choose...", command=choose_sound).pack(side="left")
        Btn(sf, text="Test", command=lambda: play_alert(load()["settings"]["sound_path"])).pack(side="left", padx=2)
        Btn(sf, text="Default", command=default_sound).pack(side="left")
        tk.Checkbutton(af, text="Keep window on top of other windows", variable=top,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("topmost", top.get()))).pack(anchor="w")
        cb_var = tk.BooleanVar(value=S.get("compact_bar", True))
        tk.Checkbutton(af, text="Slim title bar with small buttons (restart to apply)", variable=cb_var,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("compact_bar", cb_var.get()))).pack(anchor="w")

        # --- alerts
        nf = tk.LabelFrame(right, text="Alerts", padx=8, pady=4); nf.pack(fill="x", padx=10, pady=4)
        tvar, fvar, wvar = tk.BooleanVar(value=S["toast"]), tk.BooleanVar(value=S["flash"]), tk.StringVar(value=f"{S['warn_min']:g}")
        tk.Checkbutton(nf, text="Windows notification when ready", variable=tvar,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("toast", tvar.get()))).pack(anchor="w")
        tk.Checkbutton(nf, text="Flash the taskbar button when ready", variable=fvar,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("flash", fvar.get()))).pack(anchor="w")
        wr = tk.Frame(nf); wr.pack(anchor="w")
        tk.Label(wr, text="Warn this many minutes early (0 = off):").pack(side="left")
        REntry(wr, textvariable=wvar, width=4).pack(side="left", padx=4)

        def warn_changed(*_):
            try: v = float(wvar.get())
            except ValueError: return
            if v >= 0: commit(lambda st: st["settings"].__setitem__("warn_min", v))
        wvar.trace_add("write", warn_changed)

        # --- hotkeys
        hf = tk.LabelFrame(right, text="Global hotkeys (work while you are in the game)", padx=8, pady=4)
        hf.pack(fill="x", padx=10, pady=4)
        hnames = {"next": "Start next ready timer", "all": "Start all ready timers",
                  "mini": "Toggle clock-only view", "through": "Toggle click-through"}
        hvars = {}
        for k, label in hnames.items():
            r = tk.Frame(hf); r.pack(anchor="w")
            tk.Label(r, text=label, width=22, anchor="w").pack(side="left")
            hvars[k] = tk.StringVar(value=S["hotkeys"].get(k, ""))
            REntry(r, textvariable=hvars[k], width=14).pack(side="left", padx=4)

        def hk_changed(*_):
            commit(lambda st: st["settings"]["hotkeys"].update({k: v.get().strip() for k, v in hvars.items()}))
        for v in hvars.values():
            v.trace_add("write", hk_changed)
        hmsg = tag(tk.Label(hf, text="e.g. Ctrl+Alt+H, F9, Ctrl+Shift+F8. Press Apply after editing.", font=("Segoe UI", 7),
                            anchor="w", justify="left"), "muted")

        def apply_hk():
            h = start_hotkeys()
            bad = [hnames[k] for k in hvars if hvars[k].get().strip() and k not in h.ok]
            hmsg.config(text=("Could not register: " + ", ".join(bad) + " (invalid or used by another app)") if bad
                        else "Hotkeys active.")
        Btn(hf, text="Apply", command=apply_hk).pack(anchor="w", pady=(2, 0))
        hmsg.pack(anchor="w")

        # --- window extras
        xf = tk.LabelFrame(right, text="Window", padx=8, pady=4); xf.pack(fill="x", padx=10, pady=4)
        tk.Label(xf, text="Opacity (%):").pack(anchor="w")
        osc = tk.Scale(xf, from_=30, to=100, orient="horizontal", length=200,
                       command=lambda v: root.attributes("-alpha", int(float(v)) / 100))
        osc.set(S["opacity"]); osc.pack(anchor="w")
        osc.bind("<ButtonRelease-1>", lambda e: commit(lambda st: st["settings"].__setitem__("opacity", int(osc.get()))))
        cvar, avar, uvar = tk.BooleanVar(value=S["clickthrough"]), tk.BooleanVar(value=autostart_get()), tk.BooleanVar(value=S["check_updates"])
        tk.Checkbutton(xf, text="Clock-only view ignores the mouse\n(use the click-through hotkey to turn it off)",
                       variable=cvar, justify="left",
                       command=lambda: commit(lambda st: st["settings"].__setitem__("clickthrough", cvar.get()))).pack(anchor="w")

        def set_auto():
            try: autostart_set(avar.get())
            except Exception: avar.set(autostart_get())
        tk.Checkbutton(xf, text="Start with Windows", variable=avar, command=set_auto).pack(anchor="w")
        tk.Checkbutton(xf, text="Check for updates at start-up", variable=uvar,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("check_updates", uvar.get()))).pack(anchor="w")

        def restore():
            def f(st):
                st["base"] = DEF_BASE
                keep = st["settings"].get("welcomed", True)
                st["settings"] = json.loads(json.dumps(DEF_SETTINGS)); st["settings"]["welcomed"] = keep
            commit(f)
            set_skin(DEF_SETTINGS["skin"])
            w.destroy(); open_settings()
        bf = tk.Frame(w); bf.pack(fill="x", padx=10, pady=(4, 2))
        Btn(bf, text="Restore defaults", command=restore).pack(side="left")
        Btn(bf, text="History / calibrate...", command=open_history).pack(side="left", padx=6)
        Btn(bf, text="Close", command=w.destroy).pack(side="right")
        tag(tk.Label(w, text=f"Rob Run Harvest Timer v{VERSION}  -  unofficial fan tool, not affiliated with the "
                             "ROB RUN developer", font=("Segoe UI", 7)), "muted").pack(pady=(0, 8))
        paint(w, cur["th"])

    # ---------------------------------------------------------------- history + calibration
    hist = {"w": None}

    def set_pct(u, v):
        def f(st): st["settings"]["pct"][u] = round(v, 1)
        st = load(); f(st); save(st)

    def mark_verified(u):
        st = load(); vs = set(st["settings"].get("verified", [])); vs.add(u)
        st["settings"]["verified"] = sorted(vs); save(st)

    def open_history():
        if hist["w"] is not None and hist["w"].winfo_exists():
            hist["w"].lift(); return
        w = tk.Toplevel(root); w.title("History and calibration"); w.attributes("-topmost", True)
        hist["w"] = w
        body = tk.Frame(w); body.pack(fill="both", padx=12, pady=10)

        def render():
            for c in body.winfo_children():
                c.destroy()
            st = load(); cfg = st["settings"]
            tag(tk.Label(body, text="Calibration", font=("Segoe UI", 10, "bold")), "muted").pack(anchor="w")
            sug = suggest_pcts(st)
            if not sug:
                tk.Label(body, justify="left", text="Press \"Actually ready now (log)\" the moment a bush is really ready.\n"
                         "The app then compares the real time with the formula and can correct the\n"
                         "percentage of any upgrade that is not yet marked as verified.").pack(anchor="w", pady=(0, 6))
            for u, (pct, n) in sug.items():
                r = tk.Frame(body); r.pack(anchor="w", fill="x", pady=2)
                tk.Label(r, text=f"{UP_NAMES[u]}: logged cycles imply {pct:.1f}% (set to {cfg['pct'][u]:g}%), {n} cycle(s)").pack(side="left")
                Btn(r, text="Mark verified", command=lambda u=u: (mark_verified(u), render())).pack(side="right")
                Btn(r, text=f"Use {pct:.1f}%", command=lambda u=u, pct=pct: (set_pct(u, pct), render())).pack(side="right", padx=3)
            unv = [UP_NAMES[u] for u in UP_KEYS if u not in cfg.get("verified", [])]
            if unv:
                tag(tk.Label(body, text="Not yet verified in game: " + ", ".join(unv), font=("Segoe UI", 8)), "muted").pack(anchor="w")
            tag(tk.Label(body, text="Logged cycles (latest first)", font=("Segoe UI", 10, "bold")), "muted").pack(anchor="w", pady=(8, 2))
            g = tk.Frame(body); g.pack(anchor="w")
            for c, h in enumerate(("Timer", "Upgrades", "Formula", "Actual", "Off by")):
                tag(tk.Label(g, text=h, font=("Segoe UI", 8, "bold")), "muted").grid(row=0, column=c, padx=6, sticky="w")
            rows = list(reversed(st["cycles"]))[:12]
            for i, cy in enumerate(rows, 1):
                exp = st["base"] * (1 - sum(cfg["pct"].get(k, 0) for k in cy.get("ups", [])) / 100)
                act = cy.get("minutes", 0)
                vals = (cy.get("timer", cy.get("table", "-")), "+".join(UP_NAMES[k] for k in cy.get("ups", []) if k in UP_NAMES) or "none",
                        f"{exp:.1f} min", f"{act:.1f} min", f"{act - exp:+.1f} min")
                for c, v in enumerate(vals):
                    tk.Label(g, text=v).grid(row=i, column=c, padx=6, sticky="w")
            if not rows:
                tk.Label(g, text="Nothing logged yet.").grid(row=1, column=0, columnspan=5, sticky="w", padx=6)
            paint(body, cur["th"])
        render()
        Btn(w, text="Close", command=w.destroy).pack(pady=(0, 10))
        paint(w, cur["th"]); set_corners(w, cur["th"]["round"])

    def offer_calibration():
        from tkinter import messagebox
        st = load()
        for u, (pct, n) in suggest_pcts(st).items():
            if abs(pct - st["settings"]["pct"][u]) >= 0.5:
                if messagebox.askyesno("Calibrate", f"Your logged cycles suggest {UP_NAMES[u]} cuts {pct:.1f}% "
                                       f"(currently {st['settings']['pct'][u]:g}%), from {n} cycle(s).\n\nUpdate it?", parent=root):
                    set_pct(u, pct)
                break

    # ---------------------------------------------------------------- harvest actions (buttons + hotkeys)
    def is_ready(st, t):
        return t["start"] is None or time.time() >= t["start"] + minutes(st, t) * 60

    def harvest(which):
        st = load()
        due = [t for t in st["timers"] if is_ready(st, t)]
        if which == "next":       # a finished timer first, otherwise one that is idle
            due = ([t for t in due if t["start"]] or due)[:1]
        for t in due:
            do_start(st, t); alerted[t["id"]] = False; warned[t["id"]] = False
        blip(1300 if due else 400, 80)
        refresh()

    def toggle_through():
        st = load(); st["settings"]["clickthrough"] = not st["settings"].get("clickthrough", False); save(st)
        refresh()

    def start_hotkeys():
        if hk["obj"]:
            hk["obj"].stop()
        hk["obj"] = Hotkeys(load()["settings"].get("hotkeys", {}))
        return hk["obj"]

    def poll():
        try:
            while True:
                act = hk["obj"].q.get_nowait()
                {"next": lambda: harvest("next"), "all": lambda: harvest("all"),
                 "mini": toggle_mini, "through": toggle_through}[act]()
        except Exception:
            pass
        root.after(100, poll)

    bottom = tk.Frame(root); bottom.pack(side="bottom", fill="x", pady=(0, 6))
    Btn(bottom, text="+ Add timer", command=add_timer).pack(side="left", padx=8)
    Btn(bottom, text="Harvest all", command=lambda: harvest("all")).pack(side="left")
    upd_lbl = tag(tk.Label(bottom, text="", cursor="hand2", font=("Segoe UI", 8, "underline")), "link")
    Btn(bottom, text="Settings", command=open_settings).pack(side="right", padx=(0, 22))
    Btn(bottom, text="Clock only", command=lambda: toggle_mini()).pack(side="right", padx=6)

    # ---------------------------------------------------------------- clock-only view + window resizing
    minibox = tk.Frame(root)
    minis, view, saved = {}, {"mini": None}, {}
    for k, v in (S0.get("size") or {}).items():
        try: saved[k == "True"] = (max(200, int(v[0])), max(80, int(v[1])))
        except Exception: pass
    mdrag = {}

    def mpress(e): mdrag["x"], mdrag["y"] = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()
    def mmove(e): root.geometry(f"+{e.x_root - mdrag['x']}+{e.y_root - mdrag['y']}")

    def apply_view(mini):
        if view["mini"] == mini:
            return
        if view["mini"] is not None:
            saved[view["mini"]] = (root.winfo_width(), root.winfo_height())
        if mini:
            holder.pack_forget(); bottom.pack_forget()
            minibox.pack(side="top", fill="both", expand=True)
        else:
            minibox.pack_forget()
            bottom.pack(side="bottom", fill="x", pady=(0, 6))
            holder.pack(side="top", fill="both", expand=True)
        root.geometry("")
        if saved.get(mini):
            root.geometry("%dx%d" % saved[mini])
        view["mini"] = mini

    def toggle_mini():
        st = load()
        st["settings"]["mini"] = not st["settings"].get("mini", False)
        save(st)
        refresh()

    def ensure_mini(t, many):
        m = minis.get(t["id"])
        if m is None:
            f = tk.Frame(minibox)
            f.pack(side="left", fill="both", expand=True, padx=3, pady=3)
            lbl = tag(tk.Label(f, text="", font=("Segoe UI", 7)), "muted")
            d = Display(f, 150, 58)
            d.pack(side="bottom", fill="both", expand=True)
            for wdg in (f, lbl, d):
                wdg.bind("<ButtonPress-1>", mpress); wdg.bind("<B1-Motion>", mmove)
                wdg.bind("<Double-Button-1>", lambda e: toggle_mini())
            m = minis[t["id"]] = {"f": f, "lbl": lbl, "d": d}
            paint(f, cur["th"])
        if many:
            if not m["lbl"].winfo_manager():
                m["lbl"].pack(side="top", anchor="w", before=m["d"])
            m["lbl"].config(text=t["name"])
        elif m["lbl"].winfo_manager():
            m["lbl"].pack_forget()
        return m["d"]

    grip = tag(tk.Label(root, text="◢", font=("Segoe UI", 8), cursor="size_nw_se"), "muted")
    grip.place(relx=1.0, rely=1.0, anchor="se")
    gd = {}

    def gpress(e): gd.update(x=e.x_root, y=e.y_root, w=root.winfo_width(), h=root.winfo_height())
    def gmove(e):
        nw = max(root.winfo_reqwidth(), gd["w"] + e.x_root - gd["x"])
        nh = max(root.winfo_reqheight(), gd["h"] + e.y_root - gd["y"])
        root.geometry(f"{nw}x{nh}")
    grip.bind("<ButtonPress-1>", gpress); grip.bind("<B1-Motion>", gmove)

    def refresh():
        st = load()
        cfg = st["settings"]
        th = cur["th"]
        if cfg["skin"] != cur["name"]:
            set_skin(cfg["skin"]); th = cur["th"]
        if topmost["v"] != cfg["topmost"]:
            topmost["v"] = cfg["topmost"]; root.attributes("-topmost", cfg["topmost"])
        al = max(30, min(100, int(cfg.get("opacity", 100))))
        if op["v"] != al:
            op["v"] = al; root.attributes("-alpha", al / 100)
        want = bool(cfg.get("clickthrough") and cfg.get("mini") and hk["obj"] and "through" in hk["obj"].ok)
        if ct["v"] != want:
            ct["v"] = want; set_clickthrough(root, want)
        ids = [t["id"] for t in st["timers"]]
        changed = False
        for tid in list(panels):          # drop removed
            if tid not in ids:
                panels.pop(tid)["box"].destroy(); changed = True
        for tid in list(minis):
            if tid not in ids:
                minis.pop(tid)["f"].destroy(); changed = True
        for t in st["timers"]:            # add new
            if t["id"] not in panels:
                build_panel(t); changed = True
        mini = bool(cfg.get("mini"))
        apply_view(mini)
        if changed:
            root.geometry("")
        flash = int(time.time() * 2) % 2
        many = len(st["timers"]) > 1
        for t in st["timers"]:
            p = panels[t["id"]]
            for u in UP_KEYS:
                p["cbs"][u].config(text=f"{UP_NAMES[u]} -{cfg['pct'][u]:g}%")
            mins = minutes(st, t)
            p["slbl"].config(text="Sound: " + (os.path.basename(t["sound"]) if t.get("sound") else "default"))
            disp = ensure_mini(t, many) if mini else p["disp"]
            if t["start"]:
                end = t["start"] + mins * 60
                left = end - time.time()
                if left > 0:
                    disp.show(th, fmt(left), "run", 1 - left / (mins * 60))
                    p["info"].config(text=f"{mins:.1f} min - ready {clock(st, end)}")
                    alerted[t["id"]] = False
                    wm = cfg.get("warn_min", 2)
                    if wm and mins > wm:
                        if left > wm * 60:
                            warned[t["id"]] = False
                        elif not warned.get(t["id"]):
                            warned[t["id"]] = True
                            if cfg["beep"]:
                                blip(900, 90); blip(1100, 90)
                            if cfg.get("toast", True):
                                toast("Rob Run: almost ready", f"{t['name']} is ready in about {int(left // 60) + 1} min.")
                else:
                    disp.show(th, "READY!", "ready", 1.0, flash)
                    p["info"].config(text=f"since {clock(st, end)}")
                    if not alerted.get(t["id"]):
                        alerted[t["id"]] = True
                        if cfg["beep"]:
                            play_alert(t.get("sound") or cfg["sound_path"])
                        if cfg.get("toast", True):
                            toast("Rob Run: READY!", f"{t['name']} has regrown - time to harvest.")
                        root.deiconify(); root.lift()
                        if cfg.get("flash", True):
                            flash_window(root)
            else:
                last = [c for c in st["cycles"] if c.get("timer") == t["name"]]
                disp.show(th, "--:--", "idle", 0.0)
                p["info"].config(text=f"{mins:.1f} min" + (f" - last logged {last[-1]['minutes']:.2f}" if last else ""))
        grip.lift()

    def tick():
        refresh()
        root.after(500, tick)

    set_skin(cur["name"])
    if not load()["settings"]["welcomed"]:
        root.after(500, welcome)
    start_hotkeys()
    poll()
    if load()["settings"].get("check_updates", True):
        import threading, webbrowser
        uq = queue.Queue()
        threading.Thread(target=check_update, args=(uq,), daemon=True).start()

        def show_update():
            try:
                ver, url = uq.get_nowait()
            except queue.Empty:
                root.after(2000, show_update); return
            upd_lbl.config(text=f"Update v{ver} available")
            upd_lbl.bind("<Button-1>", lambda e: webbrowser.open(url or f"https://github.com/{REPO}/releases"))
            upd_lbl.pack(side="left", padx=8)
            paint(upd_lbl, cur["th"])
        root.after(3000, show_update)
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
