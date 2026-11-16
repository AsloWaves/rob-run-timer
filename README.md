# Rob Run Harvest Timer

Small native (Python + tkinter, no dependencies) countdown timer for the Rob Run grow room.

Measured 2026-11-16: grow table upgrades cut time **additively**:
`time = 60 min x (1 - sum of upgrade %)` (Fan 12%, Water Pump 14%, UV Lamp 24%).
Fan+Pump = 44.4 min, all three = 30 min.

## Run
```
pythonw rob_run_timer.py        # GUI (Windows; use python on other OSes)
python rob_run_timer.py status  # CLI: start | ready | set | status
```
Click **+ Add timer** for tables with different upgrades (each timer has its own name, upgrades and countdown). CLI: `add`, `remove`, `--timer N`.

**Settings** button: 12/24-hour clock, seconds on or off, base time, per-upgrade percentages, default upgrades for new timers, beep and always-on-top. Times display in 12-hour by default.

State is saved in `state.json` (git-ignored, per machine).
