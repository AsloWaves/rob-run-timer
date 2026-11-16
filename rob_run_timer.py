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

    # ---- design-pass skins: these change the shape of the display, not just the colours ----
    # Modern: flat, light, quiet. Big thin numerals, one teal accent, hairline cards, slim progress line.
    "Modern": dict(bg="#e6eaee", panel="#ffffff", screen="#ffffff", fg="#17212b", muted="#6b7885", entry="#f2f5f8",
                   btn="#e9eef3", btn_fg="#17212b", accent="#0b7285", accent_fg="#ffffff", danger="#c92a2a",
                   timer="#17212b", ready="#2b8a3e", logged="#1c7ed6", bar="#17212b", bar_fg="#cfd8e0",
                   bar_hover="#2b3a48", link="#0b7285", font="Segoe UI Light", ui_font="Segoe UI",
                   style="text", prog="flat", flat=True, panel_bw=1, border="#d3dae1", track="#e3e8ed"),
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
                ui_font="Segoe UI", flash=None)
    base.update(th)
    base.setdefault("screen", base["panel"])
    base.setdefault("border", base["bar"])
    base.setdefault("track", base["btn"])
    return base


THEMES = {k: _fill(k, v) for k, v in THEMES.items()}

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
    cls, role, flat = w.winfo_class(), getattr(w, "_role", None), th["flat"]
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
        elif cls == "Canvas" and role == "display":
            w.config(bg=th["screen"])
    except Exception:
        pass
    for c in w.winfo_children():
        paint(c, th, bg)


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

        def __init__(self, parent):
            super().__init__(parent, width=self.W, height=self.H, highlightthickness=0, bd=0)
            self._role, self._key = "display", None

        def show(self, th, text, state, frac, flash=0):
            key = (th["name"], text, state, int(frac * self.W), flash if state == "ready" else 0)
            if key == self._key:
                return
            self._key = key
            self.delete("all")
            self.config(bg=th["screen"])
            col = th["ready"] if state == "ready" else th["timer"]
            getattr(self, "_" + th["style"])(th, text, col, state, flash)
            self._progress(th, 1.0 if state == "ready" else frac, state)

        def _fit(self, family, text, size, maxw, weight="normal"):
            while size > 10 and tkfont.Font(root=self, family=family, size=size, weight=weight).measure(text) > maxw:
                size -= 2
            return size

        def _text(self, th, text, col, state, flash):
            size = self._fit(th["font"], text, 40, self.W - 16)
            self.create_text(self.W / 2, (self.H - 14) / 2 + 2, text=text, fill=col, font=(th["font"], size))

        def _plate(self, th, text, col, state, flash):
            x0, y0, x1, y1 = 6, 4, self.W - 6, self.H - 16
            if state == "ready" and th["flash"]:
                pc, fg = th["flash"][flash % 2], "#ffffff"      # police lights
            elif state == "idle":
                pc, fg = th["plate_idle"], th["plate_fg"]
            else:
                pc, fg = th["plate"], th["plate_fg"]
            self.create_rectangle(x0, y0, x1, y1, fill=pc, outline="#000000", width=2)
            _hazard(self, x0 + 3, y0 + 3, x1 - 3, y0 + 9, "#111111", th["plate"])
            _hazard(self, x0 + 3, y1 - 9, x1 - 3, y1 - 3, "#111111", th["plate"])
            size = self._fit(th["font"], text, 34, self.W - 40)
            self.create_text(self.W / 2, (y0 + y1) / 2, text=text, fill=fg, font=(th["font"], size))

        def _seg7(self, th, text, col, state, flash):
            if state == "ready":    # seven segments can't spell READY, so use the font
                return self._text(th, text, col, state, flash)
            dw, dh, t, gap, cw = 32, 64, 7, 9, 14
            toks = [("c",) if ch == ":" else ("d", ch) for ch in text if ch == ":" or ch in SEGS]
            total = sum(cw if k[0] == "c" else dw for k in toks) + gap * (len(toks) - 1)
            sc = min(1.0, (self.W - 16) / total)
            x, y = (self.W - total * sc) / 2, 4 + (self.H - 20 - dh * sc) / 2
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

        def _flip(self, th, text, col, state, flash):
            cw, chh, gap, colw = 44, 66, 5, 12
            toks = [("c",) if ch == ":" else ("k", ch) for ch in text]
            total = sum(colw if k[0] == "c" else cw for k in toks) + gap * (len(toks) - 1)
            sc = min(1.0, (self.W - 12) / total)
            w, h = cw * sc, chh * sc
            x, y = (self.W - total * sc) / 2, 4 + (self.H - 20 - h) / 2
            for k in toks:
                if k[0] == "c":
                    for fy in (0.32, 0.68):
                        cy = y + h * fy
                        self.create_rectangle(x + colw * sc / 2 - 3, cy - 3, x + colw * sc / 2 + 3, cy + 3, fill=th["brass"], outline="")
                    x += (colw + gap) * sc
                    continue
                mid = y + h / 2
                self.create_rectangle(x, y, x + w, mid, fill=th["card"], outline=th["card_edge"])
                self.create_rectangle(x, mid, x + w, y + h, fill=th["card2"], outline=th["card_edge"])
                self.create_text(x + w / 2, mid, text=k[1], fill=col, font=(th["font"], -int(h * 0.6)))
                self.create_line(x, mid, x + w, mid, fill=th["split"], width=2)
                for hx in (x - 1, x + w - 2):    # hinge pins
                    self.create_rectangle(hx, mid - 4, hx + 3, mid + 4, fill=th["brass"], outline="")
                x += (cw + gap) * sc

        def _progress(self, th, frac, state):
            x0, x1, y0, y1 = 8, self.W - 8, self.H - 11, self.H - 5
            frac = max(0.0, min(1.0, frac))
            fill = th["ready"] if state == "ready" else th["accent"]
            p, span = th["prog"], x1 - x0
            if p == "flat":
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
        box = tag(tk.Frame(holder), "panel")
        box.pack(side="left", fill="y", padx=6, pady=6, anchor="n")
        inner = tk.Frame(box)
        inner.pack(padx=8, pady=6)
        name = tk.StringVar(value=t["name"])

        def upd(fn):
            st = load(); tt = find(st, tid)
            if tt is not None:
                fn(st, tt); save(st)

        name.trace_add("write", lambda *_: upd(lambda st, tt: tt.__setitem__("name", name.get())))
        tk.Entry(inner, textvariable=name, justify="center", font=("Segoe UI", 10, "bold")).pack(fill="x")
        disp = Display(inner); disp.pack(pady=(4, 0))
        info = tag(tk.Label(inner, text="", font=("Segoe UI", 8)), "muted"); info.pack()
        ago = tk.StringVar(value="0")
        r = tk.Frame(inner); r.pack(pady=2)
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

        tag(tk.Button(inner, text="Harvested - start timer", command=start, font=("Segoe UI", 10), height=2),
            "accent").pack(fill="x", pady=2)
        tk.Button(inner, text="Actually ready now (log)", command=ready).pack(fill="x")
        tk.Button(inner, text="Reset", command=reset).pack(fill="x", pady=2)
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
        tag(tk.Button(inner, text="Remove this timer", command=remove), "danger").pack(fill="x", pady=(4, 0))
        panels[tid] = {"box": box, "disp": disp, "info": info, "cbs": cbs}
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
        flash = int(time.time() * 2) % 2
        for t in st["timers"]:
            p = panels[t["id"]]
            for u in UP_KEYS:
                p["cbs"][u].config(text=f"{UP_NAMES[u]} -{cfg['pct'][u]:g}%")
            mins = minutes(st, t)
            if t["start"]:
                end = t["start"] + mins * 60
                left = end - time.time()
                if left > 0:
                    p["disp"].show(th, fmt(left), "run", 1 - left / (mins * 60))
                    p["info"].config(text=f"{mins:.1f} min - ready {clock(st, end)}")
                else:
                    p["disp"].show(th, "READY!", "ready", 1.0, flash)
                    p["info"].config(text=f"since {clock(st, end)}")
                    if not alerted.get(t["id"]):
                        alerted[t["id"]] = True
                        if cfg["beep"]:
                            play_alert(cfg["sound_path"])
                        root.deiconify(); root.lift()
            else:
                last = [c for c in st["cycles"] if c.get("timer") == t["name"]]
                p["disp"].show(th, "--:--", "idle", 0.0)
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
