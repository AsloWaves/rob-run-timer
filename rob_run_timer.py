"""Rob Run harvest timer - any number of tables, each with its own upgrades
(native tkinter app + CLI sharing one state file).

Verified 2026-11-16: upgrades CUT grow time additively: time = base * (1 - sum of upgrade %).
Base (no upgrades) = 60 min. Fan 12%, Water Pump 14%, UV Lamp 24% (all editable in Settings).

GUI:   pythonw rob_run_timer.py
CLI:   python rob_run_timer.py start [--timer N] [--ago MIN]   N = 1-based timer number (default 1)
       python rob_run_timer.py ready [--timer N] [--ago MIN]   log actual ready moment
       python rob_run_timer.py set [--base 60] [--clock 12|24] [--timer N --ups fan,pump --name TEXT]
       python rob_run_timer.py add [--name TEXT] [--ups fan,pump]
       python rob_run_timer.py remove --timer N
       python rob_run_timer.py status
"""
import argparse, json, os, sys, time
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state.json")
UP_KEYS = ("fan", "pump", "uv")
UP_NAMES = {"fan": "Fan", "pump": "Water Pump", "uv": "UV Lamp"}
DEF_SETTINGS = {
    "clock": 12,                       # 12 or 24 hour clock for ready times
    "seconds": True,                   # show seconds in clock times
    "beep": True,                      # beep when a timer is ready
    "topmost": True,                   # keep window above the game
    "compact_bar": True,               # slim custom title bar with small buttons (restart to apply)
    "default_ups": ["fan", "pump"],    # upgrades pre-ticked on newly added timers
    "pct": {"fan": 12, "pump": 14, "uv": 24},   # time cut per upgrade, in percent
}
DEF_BASE = 60.0


def new_timer(name, ups):
    return {"id": str(int(time.time() * 1000)), "name": name, "ups": list(ups), "start": None, "open": None}


def default():
    return {"base": DEF_BASE, "settings": json.loads(json.dumps(DEF_SETTINGS)),
            "timers": [new_timer("Table 1", DEF_SETTINGS["default_ups"])], "cycles": []}


def load():
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
    out["settings"] = st
    return out


def save(s):
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
    print(f"base={s['base']} clock={s['settings']['clock']}h")
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


def gui():
    import tkinter as tk
    root = tk.Tk()
    root.title("Rob Run Harvest Timer")
    root.attributes("-topmost", True)

    if load()["settings"].get("compact_bar", True):
        # Windows draws the native title-bar buttons at a fixed size, so replace the bar with a slim one.
        BG = "#2b2b2b"
        root.overrideredirect(True)
        bar = tk.Frame(root, bg=BG, height=18)
        bar.pack(side="top", fill="x")
        ttl = tk.Label(bar, text="Rob Run Timer", bg=BG, fg="#ccc", font=("Segoe UI", 8))
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
            b = tk.Label(bar, text=text, bg=BG, fg="#ddd", font=("Segoe UI", 8), width=3)
            b.pack(side="right", fill="y")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(bg=hover)); b.bind("<Leave>", lambda e: b.config(bg=BG))
        small_btn("✕", root.destroy, "#c42b1c")
        small_btn("–", minimize, "#444")

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
        big = tk.Label(box, text="--:--", font=("Consolas", 38)); big.pack()
        info = tk.Label(box, text="", font=("Segoe UI", 8)); info.pack()
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

        tk.Button(box, text="Harvested - start timer", command=start, bg="#3a9d3a", fg="white",
                  font=("Segoe UI", 10), height=2).pack(fill="x", pady=2)
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
        tk.Button(box, text="Remove this timer", command=remove, fg="#a33").pack(fill="x", pady=(4, 0))
        panels[tid] = {"box": box, "big": big, "info": info, "cbs": cbs}

    def add_timer():
        st = load()
        st["timers"].append(new_timer(f"Table {len(st['timers'])+1}", st["settings"]["default_ups"])); save(st)

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

        # --- time settings
        tf = tk.LabelFrame(w, text="Time", padx=8, pady=4); tf.pack(fill="x", padx=10, pady=(10, 4))
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
        tk.Checkbutton(af, text="Beep when a timer is ready", variable=beep,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("beep", beep.get()))).pack(anchor="w")
        tk.Checkbutton(af, text="Keep window on top of other windows", variable=top,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("topmost", top.get()))).pack(anchor="w")

        cb_var = tk.BooleanVar(value=S.get("compact_bar", True))
        tk.Checkbutton(af, text="Slim title bar with small buttons (restart to apply)", variable=cb_var,
                       command=lambda: commit(lambda st: st["settings"].__setitem__("compact_bar", cb_var.get()))).pack(anchor="w")

        def restore():
            def f(st):
                st["base"] = DEF_BASE
                st["settings"] = json.loads(json.dumps(DEF_SETTINGS))
            commit(f)
            w.destroy(); open_settings()
        bf = tk.Frame(w); bf.pack(fill="x", padx=10, pady=(4, 10))
        tk.Button(bf, text="Restore defaults", command=restore).pack(side="left")
        tk.Button(bf, text="Close", command=w.destroy).pack(side="right")

    bottom = tk.Frame(root); bottom.pack(side="bottom", fill="x", pady=(0, 6))
    tk.Button(bottom, text="+ Add timer", command=add_timer).pack(side="left", padx=8)
    tk.Button(bottom, text="Settings", command=open_settings).pack(side="right", padx=8)

    def tick():
        st = load()
        cfg = st["settings"]
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
                    p["big"].config(text=fmt(left), fg="black")
                    p["info"].config(text=f"{mins:.1f} min - ready {clock(st, end)}")
                else:
                    p["big"].config(text="READY!", fg="green")
                    p["info"].config(text=f"since {clock(st, end)}")
                    if not alerted.get(t["id"]):
                        alerted[t["id"]] = True
                        if cfg["beep"]:
                            try:
                                import winsound; winsound.Beep(1000, 400); winsound.Beep(1400, 400)
                            except Exception: pass
                        root.deiconify(); root.lift()
            else:
                last = [c for c in st["cycles"] if c.get("timer") == t["name"]]
                p["big"].config(text="--:--", fg="black")
                p["info"].config(text=f"{mins:.1f} min" + (f" - last logged {last[-1]['minutes']:.2f}" if last else ""))
        root.after(500, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        gui()
    else:
        p = argparse.ArgumentParser()
        p.add_argument("cmd", choices=["start", "ready", "set", "add", "remove", "status"])
        p.add_argument("--timer", type=int)
        p.add_argument("--ago", type=float, default=0.0)
        p.add_argument("--base", type=float)
        p.add_argument("--clock", type=int, choices=[12, 24])
        p.add_argument("--ups")
        p.add_argument("--name")
        cli(p.parse_args())
