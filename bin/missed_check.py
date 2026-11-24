#!/usr/bin/env python3
"""Runs at every login (launchd com.8bitraptors.missed, RunAtLoad). launchd does not run a calendar job whose time
passed while the Mac was off or sitting at the login screen (Nov 7: crash at 19:44, login 23:43 -> Siakam, Future and
the Warriors recap never fired, silently). This finds today's posts whose time has passed with no sign they ran,
and alerts. It never posts late on its own: a post at the wrong hour can be worse than none, so Ryan decides.
usage: python3 bin/missed_check.py
"""
import os, sys, json, plistlib, pathlib, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "bin"))
from notify import notify

now = dt.datetime.now(); missed = []
posted = {pathlib.Path(r.get("file", "")).stem for r in json.loads((ROOT / "data/posts.json").read_text())} if (ROOT / "data/posts.json").exists() else set()
for pl in (pathlib.Path.home() / "Library/LaunchAgents").glob("com.8bitraptors.*.plist"):
    try: d = plistlib.load(open(pl, "rb"))
    except Exception: continue
    ci = d.get("StartCalendarInterval") or {}
    if "Month" not in ci or (ci["Month"], ci["Day"]) != (now.month, now.day): continue   # one-shot jobs for today only
    due = now.replace(hour=ci["Hour"], minute=ci["Minute"], second=0, microsecond=0)
    if due > now: continue
    label = pl.stem.split(".")[-1]
    lg = ROOT / "data/logs" / f"{label}.log"
    ran = lg.exists() and dt.datetime.fromtimestamp(lg.stat().st_mtime) >= due - dt.timedelta(minutes=1)
    if not ran and label not in posted:
        missed.append(f"{label} (due {due:%H:%M})")
if missed:
    notify("MISSED posts", "These were due while the Mac was off or logged out and never ran: " + ", ".join(missed) + ". Nothing was posted late; tell Claude whether to reschedule.")
print("missed:", missed or "none")
