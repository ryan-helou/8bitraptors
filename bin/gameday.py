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
if (mark.exists() or now.hour < 5 or now.hour >= 20) and not DRY: sys.exit(0)   # 2026-11-27: from 5 AM, so polls are queued before the 8:09 Business Suite run
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


CAP = {"raptors": 5, "warriors": 3}


def make_room(team, when):
    """Keep the day at the cap and 90 min apart: push that day's lowest-scoring queued post(s) to the end of the queue."""
    qp = ROOT / "data/api_queue.json"; q = json.loads(qp.read_text())
    try: sc = json.loads((ROOT / "data/learn/scores.json").read_text())["scores"].get(team, {})
    except Exception: sc = {}
    sys.path.insert(0, str(ROOT / "bin"))
    try: from learn_fmt import fmt
    except Exception: fmt = lambda t: "story"
    title = lambda j: pathlib.Path(j["caption"]).read_text().split("\n")[0] if pathlib.Path(j["caption"]).exists() else ""
    day_q = [j for j in q if j["account"] == team and j["state"] == "queued" and j["due_et"][:10] == str(day)]
    clash = [j for j in day_q if abs((dt.datetime.fromisoformat(j["due_et"]) - when).total_seconds()) < 90 * 60]
    extra = sorted([j for j in day_q if j not in clash], key=lambda j: (sc.get(fmt(title(j))) or {}).get("score", 1.0))
    move = clash + extra[:max(0, len(day_q) - len(clash) + 1 - CAP[team])]
    for j in move:
        last = max(x["due_et"] for x in q if x["account"] == team and x["state"] == "queued")
        d = dt.datetime.fromisoformat(last).date() + dt.timedelta(days=1); t0 = dt.datetime.fromisoformat(j["due_et"])
        j["due_et"] = t0.replace(year=d.year, month=d.month, day=d.day).isoformat()
    if move and not DRY: qp.write_text(json.dumps(q, indent=1, ensure_ascii=False))
    return [j["label"] for j in move]


done, problems = [], []
for team in ("raptors", "warriors"):
    try: t = tipoff(team)
    except Exception as ex: problems.append(f"{team}: ESPN schedule failed: {ex}"); continue
    if not t: P(team, "no game today"); continue
    # 2026-11-27 (all-posts report): no recaps (lowest follows); starter polls for BOTH teams (game-day polls are top follow-getters)
    poll = t - dt.timedelta(minutes=75)
    poll = poll.replace(minute=(poll.minute // 5) * 5, second=0, microsecond=0)
    if DRY: done.append(f"{team} starter poll at {poll:%H:%M} Toronto [dry]"); continue
    b = run([PY, "-I", str(ROOT / "gen/build.py"), "starter", team])
    q = run([PY, "-I", str(ROOT / "gen/qa.py"), str(ROOT / f"out/{team}_starter")])
    st = json.loads((ROOT / f"out/{team}_starter.qa.json").read_text()) if (ROOT / f"out/{team}_starter.qa.json").exists() else {}
    if b.returncode != 0 or st.get("issues") != 0:
        problems.append(f"{team} starter poll not posted: {'build failed ' + b.stderr[-150:] if b.returncode else 'QA found ' + str(st.get('issues')) + ' issue(s)'}"); continue
    # 2026-11-14: queue on the every-5-min API dispatcher (Toronto time), not a launchd calendar job (fired 13 h late).
    qa_ = json.loads((ROOT / "data/api_queue.json").read_text())
    locked = [j["label"] for j in qa_ if j["account"] == team and j["state"] == "bs_scheduled" and j["due_et"][:10] == str(day)
              and abs((dt.datetime.fromisoformat(j["due_et"]) - poll).total_seconds()) < 90 * 60]
    if locked: problems.append(f"{team} starter poll skipped: within 90 min of {', '.join(locked)}, already scheduled in Business Suite"); continue
    moved = make_room(team, poll)
    s = run([PY, "-I", str(ROOT / "bin/api_queue.py"), f"api_{team[0]}_starter_{day:%m%d}", team, f"out/{team}_starter.mp4", f"out/{team}_starter.caption.txt", f"{day}", f"{poll:%H:%M}"])
    (done if "queued for" in s.stdout else problems).append(f"{team} starter poll: {(s.stdout + s.stderr).strip()[-200:]}" + (f" (moved to the end: {', '.join(moved)})" if moved else ""))

P("done", done, "problems", problems)
if not DRY:
    mark.write_text(json.dumps({"done": done, "problems": problems}))
    if problems: notify("game day FAILED", " | ".join(problems)[:600])
    elif done: notify("game day", "Queued: " + "; ".join(done))
print("\n".join(done + problems) or "no games today")
