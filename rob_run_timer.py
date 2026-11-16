"""Rob Run harvest timer - any number of tables, each with its own upgrades
(native tkinter app + CLI sharing one state file).

Verified 2026-11-16: upgrades CUT grow time additively: time = base * (1 - sum of upgrade %).
Base (no upgrades) = 60 min. Fan 12%, Water Pump 14%, UV Lamp 24%.

GUI:   pythonw rob_run_timer.py
CLI:   python rob_run_timer.py start [--timer N] [--ago MIN]   N = 1-based timer number (default 1)
       python rob_run_timer.py ready [--timer N] [--ago MIN]   log actual ready moment
       python rob_run_timer.py set [--base 60] [--timer N --ups fan,pump] [--name TEXT]
       python rob_run_timer.py add [--name TEXT] [--ups fan,pump]
       python rob_run_timer.py remove --timer N
       python rob_run_timer.py status
"""
import argparse, json, os, sys, time
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state.json")
UPS = {"fan": 0.12, "pump": 0.14, "uv": 0.24}
NAMES = {"fan": "Fan -12%", "pump": "Water Pump -14%", "uv": "UV Lamp -24%"}


def new_timer(name, ups):
    return {"id": str(int(time.time() * 1000)), "name": name, "ups": list(ups), "start": None, "open": None}


def default():
    return {"base": 60.0, "timers": [new_timer("Table 1", ["fan", "pump"])], "cycles": []}


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
        s = {"base": s.get("base", 60.0), "timers": [t], "cycles": s.get("cycles", [])}
    return {**default(), **s}


def save(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE)


def minutes(s, t):
    return s["base"] * (1 - sum(UPS[u] for u in t["ups"]))


def fmt(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, x = divmod(r, 60)
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m:02d}:{x:02d}"


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
    print(f"base={s['base']}")
    for i, t in enumerate(s["timers"], 1):
        line = f"{i}. {t['name']} ups={t['ups']} -> {minutes(s, t):.1f} min"
        if t["start"]:
            left = t["start"] + minutes(s, t) * 60 - time.time()
            line += " | " + ("READY" if left <= 0 else f"ready in {fmt(left)} at {datetime.fromtimestamp(time.time()+left):%H:%M:%S}")
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
        if a.timer:
            if a.ups is not None: s["timers"][idx]["ups"] = [u for u in a.ups.split(",") if u in UPS]
            if a.name: s["timers"][idx]["name"] = a.name
        save(s)
    elif a.cmd == "add":
        ups = [u for u in (a.ups or "").split(",") if u in UPS] if a.ups is not None else s["timers"][-1]["ups"]
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
    panels = {}   # timer id -> dict of widgets/vars
    alerted = {}
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

        def rename(*_): upd(lambda st, tt: tt.__setitem__("name", name.get()))
        name.trace_add("write", rename)
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
        vs = {}
        for u in UPS:
            vs[u] = tk.BooleanVar(value=u in t["ups"])
            def cb(u=u):
                upd(lambda st, tt: tt.__setitem__("ups", [k for k in UPS if vs[k].get()]))
            tk.Checkbutton(box, text=NAMES[u], variable=vs[u], command=cb).pack(anchor="w")

        def remove():
            st = load()
            if len(st["timers"]) > 1:
                st["timers"] = [x for x in st["timers"] if x["id"] != tid]; save(st)
        tk.Button(box, text="Remove this timer", command=remove, fg="#a33").pack(fill="x", pady=(4, 0))
        panels[tid] = {"box": box, "big": big, "info": info}

    def add_timer():
        st = load()
        last = st["timers"][-1]["ups"] if st["timers"] else []
        st["timers"].append(new_timer(f"Table {len(st['timers'])+1}", last)); save(st)

    bottom = tk.Frame(root); bottom.pack(side="bottom", fill="x", pady=(0, 6))
    tk.Button(bottom, text="+ Add timer", command=add_timer).pack(side="left", padx=8)
    base = tk.StringVar(value=str(load()["base"]))
    tk.Label(bottom, text="Base min (no upgrades):").pack(side="left", padx=(12, 2))
    tk.Entry(bottom, textvariable=base, width=6).pack(side="left")

    def base_changed(*_):
        try: v = float(base.get())
        except ValueError: return
        st = load(); st["base"] = v; save(st)
    base.trace_add("write", base_changed)

    def tick():
        st = load()
        ids = [t["id"] for t in st["timers"]]
        for tid in list(panels):          # drop removed
            if tid not in ids:
                panels.pop(tid)["box"].destroy()
        for t in st["timers"]:            # add new
            if t["id"] not in panels:
                build_panel(t)
        # keep panel order in sync with state order
        for t in st["timers"]:
            p = panels[t["id"]]
            mins = minutes(st, t)
            if t["start"]:
                left = t["start"] + mins * 60 - time.time()
                if left > 0:
                    p["big"].config(text=fmt(left), fg="black")
                    p["info"].config(text=f"{mins:.1f} min - ready {datetime.fromtimestamp(time.time()+left):%H:%M:%S}")
                else:
                    p["big"].config(text="READY!", fg="green")
                    p["info"].config(text=f"since {datetime.fromtimestamp(t['start']+mins*60):%H:%M:%S}")
                    if not alerted.get(t["id"]):
                        alerted[t["id"]] = True
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
        p.add_argument("--ups")
        p.add_argument("--name")
        cli(p.parse_args())
