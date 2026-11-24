#!/usr/bin/env python3
"""One-shot scheduled post. usage: scheduled_post.py LABEL ACCOUNT TEAM VIDEO CAPTION_FILE THUMB_MS
Skips (logs why) if the team's next game is postponed/cancelled. Publishes a regular reel, then removes its own launchd job."""
import sys, os, subprocess, json, urllib.request, datetime as dt, pathlib
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "gen")); sys.path.insert(0, str(ROOT / "bin"))
from notify import notify
label, account, team, video, cap, thumb = sys.argv[1:7]
log = open(ROOT / "data/logs" / f"{label}.log", "a"); P = lambda *a: print(dt.datetime.now().isoformat(timespec="seconds"), *a, file=log, flush=True)
def done(): subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/com.8bitraptors.{label}"], capture_output=True)
try:
    import espn
    nxt = [e for e in espn.get(f"{espn.SITE}/teams/{espn.TEAMS[team]}/schedule")["events"] if e["competitions"][0]["status"]["type"]["state"] == "pre"]
    bad = nxt and nxt[0]["competitions"][0]["status"]["type"]["description"].lower() in ("postponed", "canceled")
    if bad: P("SKIPPED: next game postponed/cancelled"); done(); sys.exit(0)
except Exception as e:
    P("ESPN check failed, posting anyway:", e)
import hashlib
stp = ROOT / "data" / f"stamp_{label}.json"
if not stp.exists() or json.loads(stp.read_text()).get("mp4_md5") != hashlib.md5(open(video, "rb").read()).hexdigest() or json.loads(stp.read_text()).get("issues", 1) != 0:
    P("BLOCKED: video has no passing QA stamp (or changed after QA); not posting"); notify(f"{label} BLOCKED", f"@8bit{account} post {label} did not go out: no passing QA stamp, or the video changed after QA."); done(); sys.exit(0)
import voicecheck
_vp = voicecheck.check([("caption", voicecheck.caption_body(pathlib.Path(cap).read_text()))], account)
if _vp: P("BLOCKED: caption not in fan voice:", _vp[0]); notify(f"{label} BLOCKED", f"@8bit{account} post {label} held: caption talks about the team in third person. {_vp[0][:120]}"); done(); sys.exit(0)
r = subprocess.run([sys.executable, "-I", str(ROOT / "bin/ig_publish.py"), video, pathlib.Path(cap).read_text(), "--publish", "--thumb-offset", thumb], cwd=str(ROOT), env={**os.environ, "IG_ACCOUNT": account}, capture_output=True, text=True)
P(r.stdout[-1500:], r.stderr[-800:])
if r.returncode != 0 or '"permalink"' not in r.stdout: notify(f"{label} FAILED", f"@8bit{account} post {label} failed to publish: " + (r.stderr.strip() or r.stdout.strip())[-160:])
done()
