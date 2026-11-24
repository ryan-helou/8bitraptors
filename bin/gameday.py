#!/usr/bin/env python3
"""Game-day autopilot (2026-11-09, for Ryan's China trip; works from any time zone).
Runs every hour from launchd (com.8bitraptors.gameday). Once per Toronto date, from 11 AM Toronto time on:
  - Raptors game today: build + QA the starter poll and queue it 75 min before tip-off (Toronto time).
    (Warriors get no poll: their account only gets reach on its first posts of the day, which the Instagram scheduler fills.)
  - Either team plays today: queue its post-game recap watcher at tip-off.
Everything is in Toronto time and converted to the Mac's clock. Results and failures go through bin/notify.py.
usage: python3 bin/gameday.py [--dry]
"""
import os, sys, json, plistlib, subprocess, pathlib, datetime as dt
from zoneinfo import ZoneInfo
os.environ["PATH"] = os.path.dirname(sys.executable) + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "gen")); sys.path.insert(0, str(ROOT / "bin"))
import espn
from notify import notify
TOR = ZoneInfo("America/Toronto"); PY = sys.executable; DRY = "--dry" in sys.argv
now = dt.datetime.now(TOR); day = now.date()
log = open(ROOT / "data/logs/gameday.log", "a"); P = lambda *a: print(dt.datetime.now().isoformat(timespec="seconds"), *a, file=log, flush=True)
mark = ROOT / f"data/gameday_{day}.done"
if (mark.exists() or now.hour < 11 or now.hour >= 20) and not DRY: sys.exit(0)
# 2026-11-18 Ryan: mirror @8bitwolves one day behind. While data/mirror_mode exists, game-day polls/recaps come only from the mirror plan.
if ((ROOT / "data/mirror_mode").exists() or (ROOT / "data/no_autopilot").exists()) and not DRY: P("mirror mode: skipping game-day autopilot"); sys.exit(0)


def run(args, timeout=1800):
    try: return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired: return subprocess.CompletedProcess(args, 1, "", "timed out")


def tipoff(team):
    for e in espn.schedule(espn.TEAMS[team]):
        t = dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TOR)
        if t.date() == day: return t
    return None


def watcher(team, t):
    # 2026-11-14: start the watcher process directly instead of a one-shot launchd calendar job. launchd evaluated those
    # in Toronto time while we converted to the Mac's China time, so recaps and polls fired 13 h late. The watcher waits
    # for tip-off itself.
    label = f"{team[0]}_recap_{day:%m%d}"
    if DRY: return f"{team} recap watcher for {t:%H:%M} Toronto [dry]"
    if subprocess.run(["pgrep", "-f", f"post_game_watcher.py {label}"], capture_output=True).returncode == 0: return f"{team} recap watcher already running"
    subprocess.Popen([PY, "-I", str(ROOT / "bin/post_game_watcher.py"), label, team, team], cwd=str(ROOT), start_new_session=True,
                     stdout=open(ROOT / f"data/logs/{label}.launchd.log", "a"), stderr=subprocess.STDOUT)
    return f"{team} recap watcher started for {t:%H:%M} Toronto"


done, problems = [], []
for team in ("raptors", "warriors"):
    try: t = tipoff(team)
    except Exception as ex: problems.append(f"{team}: ESPN schedule failed: {ex}"); continue
    if not t: P(team, "no game today"); continue
    done.append(watcher(team, t))
    if team != "raptors": continue
    poll = t - dt.timedelta(minutes=75)
    if DRY: done.append(f"raptors starter poll at {poll:%H:%M} Toronto [dry]"); continue
    b = run([PY, "-I", str(ROOT / "gen/build.py"), "starter", "raptors"])
    q = run([PY, "-I", str(ROOT / "gen/qa.py"), str(ROOT / "out/raptors_starter")])
    st = json.loads((ROOT / "out/raptors_starter.qa.json").read_text()) if (ROOT / "out/raptors_starter.qa.json").exists() else {}
    if b.returncode != 0 or st.get("issues") != 0:
        problems.append(f"raptors starter poll not posted: {'build failed ' + b.stderr[-150:] if b.returncode else 'QA found ' + str(st.get('issues')) + ' issue(s)'}"); continue
    # 2026-11-14: queue on the every-5-min API dispatcher (Toronto time), not a launchd calendar job (fired 13 h late).
    s = run([PY, "-I", str(ROOT / "bin/api_queue.py"), f"api_r_starter_{day:%m%d}", "raptors", "out/raptors_starter.mp4", "out/raptors_starter.caption.txt", f"{day}", f"{poll:%H:%M}"])
    (done if "queued for" in s.stdout else problems).append(f"raptors starter poll: {(s.stdout + s.stderr).strip()[-200:]}")

P("done", done, "problems", problems)
if not DRY:
    mark.write_text(json.dumps({"done": done, "problems": problems}))
    if problems: notify("game day FAILED", " | ".join(problems)[:600])
    elif done: notify("game day", "Queued: " + "; ".join(done))
print("\n".join(done + problems) or "no games today")
