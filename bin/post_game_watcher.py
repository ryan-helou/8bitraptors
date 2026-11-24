#!/usr/bin/env python3
"""One-shot post-game watcher. usage: post_game_watcher.py LABEL ACCOUNT TEAM
Polls ESPN every 60s (up to 6h). When tonight's game is FINAL: builds the recap reel and publishes it, then removes its own launchd job."""
import sys, os, time, subprocess, datetime as dt, pathlib
import os; os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "gen"))
import espn
sys.path.insert(0, str(ROOT / "bin")); from notify import notify
label, account, team = sys.argv[1:4]; tid = espn.TEAMS[team]
log = open(ROOT / "data/logs" / f"{label}.log", "a"); P = lambda *a: print(dt.datetime.now().isoformat(timespec="seconds"), *a, file=log, flush=True)
def done(): subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/com.8bitraptors.{label}"], capture_output=True)
subprocess.Popen(['caffeinate', '-i', '-w', str(os.getpid())])  # keep the Mac awake while this watcher runs
t0 = time.time(); target = None
# 2026-11-14: gameday.py now starts this watcher directly (launchd calendar jobs fired 13 h late: launchd kept Toronto time
# while the Mac is on China time). Wait here until 5 min before tip-off, then poll. The window is 16 h so a watcher that was
# suspended by a closed lid still finds the game on wake and posts a next-morning recap (held to 8:30 AM ET below).
try:
    _up = [e for e in espn.schedule(tid) if 0 < (dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00")) - dt.datetime.now(dt.timezone.utc)).total_seconds() < 16 * 3600]
    if _up:
        _wait = (dt.datetime.fromisoformat(_up[0]["date"].replace("Z", "+00:00")) - dt.datetime.now(dt.timezone.utc)).total_seconds() - 300
        if _wait > 0: P("waiting", round(_wait / 60), "min for tip-off"); time.sleep(_wait); t0 = time.time()
except Exception as ex: P("pre-wait error", ex)
while time.time() - t0 < 16 * 3600:
    try:
        now = dt.datetime.now(dt.timezone.utc)
        evs = [e for e in espn.schedule(tid) if abs((dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00")) - now).total_seconds()) < 16 * 3600]
        if not evs: P("no game within 16h, exiting"); done(); sys.exit(0)
        e = evs[0]; target = e
        if e["state"] == "post": break
    except Exception as ex: P("poll error", ex)
    time.sleep(60)
else:
    P("timed out waiting for final"); notify(f"{label} no recap", f"{team.title()} recap: no final score from ESPN after 16 hours, nothing posted."); done(); sys.exit(0)
time.sleep(90)  # let ESPN finish box score
P("final detected:", target["id"], target["opp_name"], target["my"], target["their"])
t_build = time.time()
b = subprocess.run([sys.executable, "-I", str(ROOT / "gen/build.py"), "recap", team, target["id"]], cwd=str(ROOT), capture_output=True, text=True); P(b.stdout[-300:], b.stderr[-600:])
if not (ROOT / f"out/{team}_recap.mp4").exists() or (ROOT / f"out/{team}_recap.mp4").stat().st_mtime < t_build:
    P("recap build failed; not posting a stale file"); notify(f"{label} BUILD FAILED", f"{team.title()} recap did not build, nothing posted. " + b.stderr.strip()[-160:]); done(); sys.exit(1)
q = subprocess.run([sys.executable, "-I", str(ROOT / "gen/qa.py"), str(ROOT / f"out/{team}_recap")], cwd=str(ROOT), capture_output=True, text=True); P("QA:", q.stdout[-1500:])
mp4 = ROOT / f"out/{team}_recap.mp4"; cap = (ROOT / f"out/{team}_recap.caption.txt").read_text()
import hashlib, json
_st = json.loads((ROOT / f"out/{team}_recap.qa.json").read_text()) if (ROOT / f"out/{team}_recap.qa.json").exists() else {}
if _st.get("issues", 1) != 0 or _st.get("mp4_md5") != hashlib.md5(open(mp4, "rb").read()).hexdigest():
    P("BLOCKED: recap failed QA, not posting:", _st.get("detail", [])[:5]); notify(f"{label} BLOCKED", f"{team.title()} recap failed QA ({_st.get('issues', '?')} issues), not posted. First: " + "; ".join(x.strip() for x in _st.get("detail", [])[:2])); done(); sys.exit(0)
# A recap posted after midnight dies (Warriors recap at 12:40 AM got 7 views): if the game ends late, hold it for 8:30 AM ET.
now_et = dt.datetime.now(espn.ET)
if 1 <= now_et.hour < 7:   # Ryan 2026-11-07: post right after the game; the 1 AM Bucks recap still did 1.9K views
    wake = (now_et).replace(hour=8, minute=30, second=0, microsecond=0)
    P("late final; holding recap until", wake.isoformat(timespec="minutes")); time.sleep(max(0, (wake - dt.datetime.now(espn.ET)).total_seconds()))
r = subprocess.run([sys.executable, "-I", str(ROOT / "bin/ig_publish.py"), str(mp4), cap, "--publish", "--thumb-offset", "1300"], cwd=str(ROOT), env={**os.environ, "IG_ACCOUNT": account}, capture_output=True, text=True)
P(r.stdout[-1500:], r.stderr[-800:])
if r.returncode != 0 or '"permalink"' not in r.stdout: notify(f"{label} FAILED", f"{team.title()} recap failed to publish: " + (r.stderr.strip() or r.stdout.strip())[-160:])
done()
