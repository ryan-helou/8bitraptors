"""Schedule a one-shot reel post via launchd. usage: schedule.py LABEL ACCOUNT VIDEO CAPTION_FILE HH:MM [THUMB_MS]
Copies VIDEO into scheduled/<LABEL>.mp4 and CAPTION into data/caption_<LABEL>.txt (so later rebuilds can't change a queued post
unless re-scheduled), writes ~/Library/LaunchAgents/com.8bitraptors.<LABEL>.plist for today at HH:MM and loads it."""
import sys, os, shutil, pathlib, plistlib, subprocess, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
FORCE = "--force" in sys.argv; sys.argv = [a for a in sys.argv if a != "--force"]
label, account, video, cap, hm = sys.argv[1:6]; thumb = sys.argv[6] if len(sys.argv) > 6 else "1300"
# Time zone safety (2026-11-09, Ryan travelling with the Mac): "ET18:00" means 18:00 Toronto time today; it is converted to
# the Mac's local clock, which launchd uses, so posts still go out at the right Toronto time from any time zone.
from zoneinfo import ZoneInfo as _Z
if hm.upper().startswith("ET"):
    # SCHED_DATE=YYYY-MM-DD (2026-11-10, Raptors Business Suite uploads spam-limited): queue a future Toronto day, not just today.
    _base = dt.datetime.now(_Z("America/Toronto"))
    if os.environ.get("SCHED_DATE"):
        _sd = dt.date.fromisoformat(os.environ["SCHED_DATE"]); _base = _base.replace(year=_sd.year, month=_sd.month, day=_sd.day)
    _et = _base.replace(hour=int(hm[2:].split(":")[0]), minute=int(hm.split(":")[1]), second=0, microsecond=0)
    _loc = _et.astimezone(); DAY = _loc.date(); ET_H = _et.hour; hm = _loc.strftime("%H:%M")
else:
    DAY = dt.date.today(); ET_H = dt.datetime.now().astimezone().replace(hour=int(hm.split(":")[0])).astimezone(_Z("America/Toronto")).hour
import json, hashlib
stamp = ROOT / (str(video)[:-4] + ".qa.json"); md5 = hashlib.md5(open(ROOT / video, "rb").read()).hexdigest()
if not stamp.exists(): sys.exit(f"{label}: REFUSED - no QA stamp for {video}; run gen/qa.py first")
st = json.loads(stamp.read_text())
if st.get("mp4_md5") != md5: sys.exit(f"{label}: REFUSED - {video} changed after QA; re-run gen/qa.py")
if st.get("issues", 1) != 0: sys.exit(f"{label}: REFUSED - QA found {st.get('issues')} issue(s): {st.get('detail', [])[:3]}")
sys.path.insert(0, str(ROOT / "gen")); import voicecheck
_vp = voicecheck.check([("caption", voicecheck.caption_body((ROOT / cap).read_text()))], "raptors" if account == "raptors" else "warriors")
if _vp: sys.exit(f"{label}: REFUSED - caption is not in fan voice: {_vp[0]}")
# Queue rules (Ryan 2026-11-07, from the day-1 numbers): posts on one account at least 90 min apart, and never the same story twice.
# --force overrides both, only on Ryan's say-so (e.g. reposting a fixed reel he deleted).
GAP = 90; h0, m0 = map(int, hm.split(":")); tmin = h0 * 60 + m0; today = DAY; clash = []
for q in (pathlib.Path.home() / "Library/LaunchAgents").glob("com.8bitraptors.*.plist"):
    try: d_ = plistlib.load(open(q, "rb"))
    except Exception: continue
    a_ = d_.get("ProgramArguments", []); ci = d_.get("StartCalendarInterval", {})
    if q.stem.split(".")[-1] == label or "scheduled_post.py" not in " ".join(a_) or len(a_) < 6 or a_[5] != account: continue
    if (ci.get("Month"), ci.get("Day")) != (today.month, today.day): continue
    if abs(ci["Hour"] * 60 + ci["Minute"] - tmin) < GAP: clash.append(f"{q.stem.split('.')[-1]} queued at {ci['Hour']}:{ci['Minute']:02d}")
posts = json.loads((ROOT / "data/posts.json").read_text()) if (ROOT / "data/posts.json").exists() else []
title = lambda c: (c or "").strip().splitlines()[0].split("🎮")[0].strip().upper() if (c or "").strip() else ""
new_title = title((ROOT / cap).read_text())
for r_ in posts:
    if r_.get("account") != account: continue
    lg = dt.datetime.fromisoformat(r_["logged"]) if r_.get("logged") else None
    if lg and lg.date() == today and abs(lg.hour * 60 + lg.minute - tmin) < GAP: clash.append(f"{pathlib.Path(r_.get('file', '')).stem} posted at {lg:%H:%M}")
    # Game-day formats recur every game (starter poll, party check, starting five, recap, N games in): those are only
    # a repeat if the whole caption matches. Stories repeat on the title alone.
    recurring = new_title in ("CHOOSE YOUR STARTER", "PARTY CHECK", "STARTING FIVE PC", "VICTORY", "DEFEAT") or new_title.endswith("GAMES IN")
    same = (voicecheck.caption_body(r_.get("caption") or "").strip() == voicecheck.caption_body((ROOT / cap).read_text()).strip()) if recurring else (title(r_.get("caption")) == new_title)
    if r_.get("trial"): same = False   # 2026-11-23: a trial reel never blocks its winner going to the feed
    if pathlib.Path(r_.get("file", "")).stem == label or (new_title and same):
        clash.append(f"repeat: {pathlib.Path(r_.get('file', '')).stem} already posted {r_.get('logged', '')[:16]} ({new_title})")
# Fact check: a reel built from a hand-written spec needs every number backed (gen/factcheck.py)
import glob as _g
_stem = pathlib.Path(video).stem
for _sf in _g.glob(str(ROOT / "specs/*.json")):
    try: _sd = json.loads(open(_sf).read())
    except Exception: continue
    if f"{_sd.get('team')}_{_sd.get('name')}" == _stem and not pathlib.Path(_sf).name.startswith("test_"):
        import factcheck
        _fp = factcheck.check(_sf)
        if _fp: clash.append(f"fact check failed for {pathlib.Path(_sf).name}: " + "; ".join(_fp[:3]))
# Daily cap (Ryan 2026-11-08): @8bitwarriors only gets reach on its first 1-2 posts a day (posts 3+ got 23-163 views),
# so it gets at most 2 scheduled posts a day. Post-game recaps go through the watcher and don't count.
# Strategy v2 (2026-11-09): the cap adapts. bin/morning_report.py raises it to 3 when every non-recap post the day
# before got pushed (800+ views), like Raptors did on day 2, and drops it back when posts miss. See research/strategy-2026-11-09.md.
CAP = {"warriors": 2}
try: CAP.update({k: int(v) for k, v in json.loads((ROOT / "data/caps.json").read_text()).items() if k in CAP})
except Exception: pass
# No posts before noon (strategy v2): the only pre-noon Raptors post (11:01 dunk poll) got 349 views, mostly not from Reels.
# 2026-11-18 Ryan: copy @8bitwolves' post times exactly (they post ~11:30-12:00). In mirror mode the noon rule is off; gaps/repeats/facts still apply.
if ET_H < 12 and not (ROOT / "data/mirror_mode").exists(): clash.append(f"{hm} is before noon Toronto time; morning posts don't get pushed")
if account in CAP:
    n_q = 0
    for q in (pathlib.Path.home() / "Library/LaunchAgents").glob("com.8bitraptors.*.plist"):
        try: d_ = plistlib.load(open(q, "rb"))
        except Exception: continue
        a_ = d_.get("ProgramArguments", []); ci = d_.get("StartCalendarInterval", {})
        if q.stem.split(".")[-1] != label and "scheduled_post.py" in " ".join(a_) and len(a_) > 5 and a_[5] == account and (ci.get("Month"), ci.get("Day")) == (today.month, today.day):
            n_q += 1
    n_p = sum(1 for r_ in posts if r_.get("account") == account and str(r_.get("logged", ""))[:10] == str(today) and "recap" not in pathlib.Path(r_.get("file", "")).stem)
    if n_q + n_p >= CAP[account]: clash.append(f"@8bit{account} already has {n_q + n_p} post(s) today (cap {CAP[account]})")
if clash and not FORCE: sys.exit(f"{label}: REFUSED - " + "; ".join(clash) + f". (Rules: {GAP}+ min apart, no repeat stories, facts checked. --force only if Ryan says so.)")
if os.environ.get("SCHED_DRY"): sys.exit(f"{label}: OK (dry run, nothing queued)")
v = ROOT / "scheduled" / f"{label}.mp4"; shutil.copy(ROOT / video, v)
(ROOT / "data" / f"stamp_{label}.json").write_text(json.dumps({**st, "label": label, "due_et": _et.isoformat() if "_et" in globals() else None}))
c = ROOT / "data" / f"caption_{label}.txt"; shutil.copy(ROOT / cap, c)
h, m = map(int, hm.split(":")); d = DAY
pl = pathlib.Path.home() / "Library/LaunchAgents" / f"com.8bitraptors.{label}.plist"
subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/com.8bitraptors.{label}"], capture_output=True)
plistlib.dump({"Label": f"com.8bitraptors.{label}", "WorkingDirectory": str(ROOT),
               "ProgramArguments": ["/Library/Frameworks/Python.framework/Versions/3.12/bin/python3", "-I", str(ROOT / "bin/scheduled_post.py"), label, account, account, str(v), str(c), thumb],
               "StartCalendarInterval": {"Month": d.month, "Day": d.day, "Hour": h, "Minute": m},
               "StandardOutPath": str(ROOT / f"data/logs/{label}.launchd.log"), "StandardErrorPath": str(ROOT / f"data/logs/{label}.launchd.log")}, open(pl, "wb"))
r = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(pl)], capture_output=True, text=True)
print(f"{label}: {account} at {hm} -> {'loaded' if r.returncode == 0 else r.stderr.strip()}")
