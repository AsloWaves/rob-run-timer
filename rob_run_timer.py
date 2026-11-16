"""Rob Run harvest timer (native tkinter app + CLI sharing one state file).

Verified 2026-11-16: upgrades CUT grow time additively: time = base * (1 - sum of upgrade %).
Base (no upgrades) = 60 min. Fan 12%, Water Pump 14%, UV Lamp 24%.

GUI:   pythonw rob_run_timer.py
CLI:   python rob_run_timer.py start [--ago MIN]      harvest happened MIN minutes ago
       python rob_run_timer.py ready [--ago MIN]      log actual ready moment (calibration)
       python rob_run_timer.py set [--base 60] [--ups fan,pump]
       python rob_run_timer.py status
"""
import argparse, json, os, sys, time
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state.json")
UPS = {"fan": 0.12, "pump": 0.14, "uv": 0.24}
NAMES = {"fan": "Fan  -12%", "pump": "Water Pump  -14%", "uv": "UV Lamp  -24%"}


def default():
    return {"base": 60.0, "ups": ["fan", "pump"], "start": None, "open": None, "cycles": []}


def load():
    try:
        with open(STATE, encoding="utf-8-sig") as f:
            s = json.load(f)
    except Exception:
        return default()
    if "tables" in s:  # migrate from the two-table version
        b = s["tables"].get("B", {})
        s = {"base": s.get("base", 60.0), "ups": b.get("ups", ["fan", "pump"]),
             "start": b.get("start"), "open": b.get("open"), "cycles": s.get("cycles", [])}
    return {**default(), **s}


def save(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE)


def minutes(s):
    return s["base"] * (1 - sum(UPS[u] for u in s["ups"]))


def fmt(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, x = divmod(r, 60)
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m:02d}:{x:02d}"


def do_start(s, ago=0.0):
    s["start"] = time.time() - ago * 60
    s["open"] = {"start": s["start"], "ups": list(s["ups"])}
    save(s)


def do_ready(s, ago=0.0):
    c = s.get("open")
    if not c:
        return None
    c["ready"] = time.time() - ago * 60
    c["minutes"] = round((c["ready"] - c["start"]) / 60, 3)
    s["cycles"].append(c)
    s["open"] = None
    s["start"] = None
    save(s)
    return c


def status(s):
    line = f"base={s['base']} ups={s['ups']} -> {minutes(s):.1f} min/cycle"
    if s["start"]:
        left = s["start"] + minutes(s) * 60 - time.time()
        line += " | " + ("READY" if left <= 0 else f"ready in {fmt(left)} at {datetime.fromtimestamp(time.time()+left):%H:%M:%S}")
    print(line)
    for c in s["cycles"]:
        print("logged:", c.get("table", "-"), c["minutes"], "min, ups", c["ups"])


def cli(a):
    s = load()
    if a.cmd == "start":
        do_start(s, a.ago)
    elif a.cmd == "ready":
        c = do_ready(s, a.ago)
        print("logged" if c else "no open cycle", c or "")
    elif a.cmd == "set":
        if a.base is not None: s["base"] = a.base
        if a.ups is not None: s["ups"] = [u for u in a.ups.split(",") if u in UPS]
        save(s)
    status(load())


def gui():
    import tkinter as tk
    root = tk.Tk()
    root.title("Rob Run Harvest Timer")
    root.attributes("-topmost", True)
    s0 = load()
    flag = {"alerted": False}

    big = tk.Label(root, text="--:--", font=("Consolas", 48))
    big.pack(padx=20, pady=(10, 0))
    info = tk.Label(root, text="", font=("Segoe UI", 9))
    info.pack()

    ago = tk.StringVar(value="0")
    r = tk.Frame(root); r.pack(pady=4)
    tk.Label(r, text="Harvested").pack(side="left")
    tk.Entry(r, textvariable=ago, width=4).pack(side="left", padx=3)
    tk.Label(r, text="min ago").pack(side="left")

    def start():
        try: a = float(ago.get())
        except ValueError: a = 0
        do_start(load(), a); ago.set("0"); flag["alerted"] = False

    def reset():
        st = load(); st["start"] = None; st["open"] = None; save(st)

    tk.Button(root, text="Harvested - start timer", command=start, bg="#3a9d3a", fg="white",
              font=("Segoe UI", 11), height=2).pack(fill="x", padx=12, pady=2)
    tk.Button(root, text="Actually ready now (log time)", command=lambda: do_ready(load())).pack(fill="x", padx=12)
    tk.Button(root, text="Reset", command=reset).pack(fill="x", padx=12, pady=2)

    box = tk.LabelFrame(root, text="Table upgrades", padx=6, pady=2); box.pack(fill="x", padx=12, pady=6)
    vs = {}

    def apply():
        st = load(); st["ups"] = [u for u in UPS if vs[u].get()]; save(st)

    for u in UPS:
        vs[u] = tk.BooleanVar(value=u in s0["ups"])
        tk.Checkbutton(box, text=NAMES[u], variable=vs[u], command=apply).pack(anchor="w")

    def tick():
        st = load()
        mins = minutes(st)
        if st["start"]:
            left = st["start"] + mins * 60 - time.time()
            if left > 0:
                big.config(text=fmt(left), fg="black")
                info.config(text=f"{mins:.1f} min cycle - ready {datetime.fromtimestamp(time.time()+left):%H:%M:%S}")
            else:
                big.config(text="READY!", fg="green")
                info.config(text=f"Go harvest (ready since {datetime.fromtimestamp(st['start']+mins*60):%H:%M:%S})")
                if not flag["alerted"]:
                    flag["alerted"] = True
                    try:
                        import winsound; winsound.Beep(1000, 400); winsound.Beep(1400, 400)
                    except Exception: pass
                    root.deiconify(); root.lift()
        else:
            last = st["cycles"][-1] if st["cycles"] else None
            big.config(text="--:--", fg="black")
            info.config(text=f"{mins:.1f} min cycle" + (f" - last logged {last['minutes']:.2f} min" if last else ""))
        root.after(500, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        gui()
    else:
        p = argparse.ArgumentParser()
        p.add_argument("cmd", choices=["start", "ready", "set", "status"])
        p.add_argument("--ago", type=float, default=0.0)
        p.add_argument("--base", type=float)
        p.add_argument("--ups")
        cli(p.parse_args())
