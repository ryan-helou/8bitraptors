#!/usr/bin/env python3
"""Queue a reel for the time-zone-proof API dispatcher (2026-11-11, Ryan travelling: the Mac's clock changes time zone).
usage: api_queue.py LABEL ACCOUNT VIDEO CAPTION_FILE YYYY-MM-DD HH:MM   (date/time are Toronto time)
Runs every schedule.py check as a dry run (QA stamp, fan voice, fact check, gaps, repeats), then freezes copies of the
video, caption and QA stamp and appends the post to data/api_queue.json. bin/api_dispatch.py (launchd, every 5 min)
posts it once Toronto time reaches it."""
import sys, os, json, shutil, pathlib, subprocess, datetime as dt
from zoneinfo import ZoneInfo
ROOT = pathlib.Path(__file__).resolve().parent.parent
label, account, video, cap, day, hm = sys.argv[1:7]
# Length guard (2026-11-14 fade research, research/fade/FINDINGS.md): our reels of 45 s or more averaged ~20% watched
# and ~1.1K views vs ~2K for 20-35 s. Anything that long needs an explicit --long (e.g. a starting-five party reel).
_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ROOT / video)],
                            capture_output=True, text=True).stdout or 0)
if _len >= 45 and "--long" not in sys.argv:
    sys.exit(f"{label}: {_len:.1f} s is too long (45 s+ reels average ~20% watched). Cut it to 20-35 s, or pass --long if it's a deliberate exception.")
# Copy gate (Ryan 2026-11-18, the copy skill): in mirror mode every reel must have passed copy_check.py against the
# @8bitwolves original it copies. Report lives at out/<stem>_copycheck/report.json and must be for THIS exact file.
if (ROOT / "data/mirror_mode").exists():
    _rp = ROOT / (video[:-4] + "_copycheck") / "report.json"
    if not _rp.exists(): sys.exit(f"{label}: no copy check. Run the copy skill: copy_check.py check THEIRS.mp4 {video} {_rp.parent} ...")
    _r = json.loads(_rp.read_text())
    if not _r.get("pass_all"): sys.exit(f"{label}: copy check FAILED ({_rp.parent}/report.md). Fix the reel and re-check.")
    if abs(_r.get("ours_mtime", 0) - os.path.getmtime(ROOT / video)) > 1: sys.exit(f"{label}: reel was rebuilt after its copy check. Re-run the check.")
    _jp = _rp.parent / "judge.json"
    if not _jp.exists(): sys.exit(f"{label}: no blind-judge result. Run copy_check.py judgekit, a fresh agent's verdict, then judgescore.")
    _j = json.loads(_jp.read_text())
    _ov = os.environ.get("COPY_JUDGE_OVERRIDE", "").strip()   # Ryan's explicit "post anyway" for one reel; the measured check still must pass
    if not _j.get("pass_judge") and _ov:
        (ROOT / "data/logs").mkdir(exist_ok=True)
        with open(ROOT / "data/logs/judge_overrides.log", "a") as _f: _f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {label}: {_ov}\n")
        print(f"{label}: blind judge failed, posting anyway on Ryan's override ({_ov})")
    elif not _j.get("pass_judge"): sys.exit(f"{label}: the blind judge could tell ours apart ({_jp}). Fix its list and re-judge.")
    if abs((_j.get("ours_mtime") or 0) - os.path.getmtime(ROOT / video)) > 1 and not _ov: sys.exit(f"{label}: reel changed after it was judged. Re-judge.")
r = subprocess.run([sys.executable, str(ROOT / "bin/schedule.py"), label, account, video, cap, "ET" + hm],
                   env={**os.environ, "SCHED_DRY": "1", "SCHED_DATE": day}, capture_output=True, text=True, cwd=str(ROOT))
if "OK (dry run" not in r.stdout + r.stderr: sys.exit((r.stdout + r.stderr).strip())
due = dt.datetime.fromisoformat(f"{day}T{hm}").replace(tzinfo=ZoneInfo("America/Toronto"))
st = json.loads((ROOT / (video[:-4] + ".qa.json")).read_text())
v = ROOT / "scheduled" / f"{label}.mp4"; shutil.copy(ROOT / video, v)
c = ROOT / "data" / f"caption_{label}.txt"; shutil.copy(ROOT / cap, c)
sys.path.insert(0, str(ROOT / "bin")); import follow_line; follow_line.add(c, account)   # follow line on every post (2026-11-25)
(ROOT / "data" / f"stamp_{label}.json").write_text(json.dumps({**st, "label": label, "due_et": due.isoformat()}))
qf = ROOT / "data/api_queue.json"; q = json.loads(qf.read_text()) if qf.exists() else []
q = [x for x in q if x["label"] != label] + [{**({"trial": True} if "--trial" in sys.argv else {}), "label": label, "account": account, "video": str(v), "caption": str(c), "due_et": due.isoformat(), "state": "queued"}]
qf.write_text(json.dumps(sorted(q, key=lambda x: x["due_et"]), indent=1)); print(f"{label}: queued for {day} {hm} Toronto")
# Follow end card at the end of every reel (2026-11-25), after the queue entry exists.
subprocess.run([sys.executable, str(ROOT / "bin/endcard.py"), label], cwd=str(ROOT))
