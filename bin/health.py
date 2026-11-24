#!/usr/bin/env python3
"""Daily self-check of the whole autonomous system (Ryan 2026-11-23: "always double check and monitor your work just
like a human"). Runs after learn.py in the morning report; no Claude tokens. Notifies Ryan only when something is wrong,
and writes data/learn/health.md every day (the weekly refill reads it).
Checks: cloud post runs failing, posts due in the last 24 h that did not go out, queue running low, sync / learn / news
/ weekly refill not running, a stuck news run."""
import json, sys, pathlib, subprocess, datetime as dt, time
from zoneinfo import ZoneInfo
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "bin"))
TOR = ZoneInfo("America/Toronto"); now = dt.datetime.now(TOR); REPO = "ryan-helou/8bitraptors-ops"
age_h = lambda p: (time.time() - p.stat().st_mtime) / 3600 if p.exists() else 1e9
bad, ok = [], []

# 1. cloud runs in the last 24 h
r = subprocess.run(["gh", "run", "list", "-R", REPO, "-w", "post.yml", "-L", "40", "--json", "conclusion,createdAt,event"], capture_output=True, text=True)
try:
    runs = [x for x in json.loads(r.stdout) if (now - dt.datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00"))).total_seconds() < 86400]
    fails = [x for x in runs if x["conclusion"] == "failure"]
    (bad if fails else ok).append(f"cloud poster: {len(runs)} runs in 24 h, {len(fails)} failed")
except Exception: bad.append("cloud poster: could not read GitHub runs (gh not logged in?)")

# 2. posts due in the last 24 h that did not go out
q = json.loads((ROOT / "data/api_queue.json").read_text())
due = [j for j in q if now - dt.timedelta(hours=24) <= dt.datetime.fromisoformat(j["due_et"]) <= now - dt.timedelta(minutes=45)]
missed = [f"{j['label']} ({j['state']}{': ' + j.get('cloud_why', '')[:60] if j.get('cloud_why') else ''})" for j in due if j["state"] not in ("posted", "held")]
(bad if missed else ok).append(f"posts due in 24 h: {len(due)}, not posted: {len(missed)} " + "; ".join(missed))

# 3. queue depth
for acc, need in (("raptors", 3), ("warriors", 2)):
    days = len({j["due_et"][:10] for j in q if j["account"] == acc and j["state"] == "queued" and dt.datetime.fromisoformat(j["due_et"]) > now})
    (bad if days < need else ok).append(f"{acc}: {days} days queued")

# 4. the moving parts ran recently
for name, p, hours in (("cloud sync", ROOT / "data/logs/cloudsync.log", 30), ("learn (daily)", ROOT / "data/learn/latest.md", 30),
                       ("news check", ROOT / "data/logs/news.launchd.log", 30), ("weekly refill", ROOT / "data/learn/decisions.md", 24 * 8)):
    a = age_h(p); (bad if a > hours else ok).append(f"{name}: last ran {a:.0f} h ago" if a < 1e8 else f"{name}: never ran")
lock = ROOT / "data/news/running.lock"
if lock.exists() and age_h(lock) > 3: bad.append(f"news run stuck for {age_h(lock):.0f} h (data/news/running.lock); see data/logs/news_run.log")

md = [f"# Health {now:%a %b %d %H:%M}", "", "## Problems" if bad else "## All good", *[f"- {b}" for b in bad], "", "## OK", *[f"- {o}" for o in ok]]
(ROOT / "data/learn").mkdir(parents=True, exist_ok=True); (ROOT / "data/learn/health.md").write_text("\n".join(md)); print("\n".join(md))
if bad and "--no-send" not in sys.argv:
    from notify import notify
    notify("8bit system check", f"{len(bad)} problem(s): " + " | ".join(bad)[:300])
