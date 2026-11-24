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
# Nov 8: the Mac woke from sleep at 13:53 and ran two missed posts before WiFi was back ("nodename nor servname"),
# so both failed. Wait up to 20 min for the network before doing anything.
import socket, time as _t
for _i in range(80):
    try: socket.getaddrinfo("graph.facebook.com", 443); break
    except OSError: _t.sleep(15)
else:
    P("FAILED: no network for 20 min"); notify(f"{label} FAILED", f"@8bit{account} post {label}: no internet for 20 min, not posted."); done(); sys.exit(0)
try:
    import espn
    nxt = [e for e in espn.get(f"{espn.SITE}/teams/{espn.TEAMS[team]}/schedule")["events"] if e["competitions"][0]["status"]["type"]["state"] == "pre"]
    bad = nxt and nxt[0]["competitions"][0]["status"]["type"]["description"].lower() in ("postponed", "canceled")
    if bad: P("SKIPPED: next game postponed/cancelled"); done(); sys.exit(0)
except Exception as e:
    P("ESPN check failed, posting anyway:", e)
import hashlib
stp = ROOT / "data" / f"stamp_{label}.json"
# Lateness guard (2026-11-10, Ryan travelling with the Mac): launchd runs a missed job when the Mac wakes. If that is more
# than 2 h after the planned Toronto time, don't post (a 4 AM post gets no reach, and several would go out at once).
try:
    _due = json.loads(stp.read_text()).get("due_et")
    if _due:
        _late = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(_due)).total_seconds() / 3600
        if _late > 2:
            P(f"SKIPPED: {_late:.1f} h late (Mac asleep or offline at post time)"); notify(f"{label} MISSED", f"@8bit{account} post {label} was {_late:.1f} h late (Mac asleep or offline), so it was not posted."); done(); sys.exit(0)
except Exception as e:
    P("lateness check failed, continuing:", e)
if not stp.exists() or json.loads(stp.read_text()).get("mp4_md5") != hashlib.md5(open(video, "rb").read()).hexdigest() or json.loads(stp.read_text()).get("issues", 1) != 0:
    P("BLOCKED: video has no passing QA stamp (or changed after QA); not posting"); notify(f"{label} BLOCKED", f"@8bit{account} post {label} did not go out: no passing QA stamp, or the video changed after QA."); done(); sys.exit(0)
import voicecheck
_vp = voicecheck.check([("caption", voicecheck.caption_body(pathlib.Path(cap).read_text()))], account)
if _vp: P("BLOCKED: caption not in fan voice:", _vp[0]); notify(f"{label} BLOCKED", f"@8bit{account} post {label} held: caption talks about the team in third person. {_vp[0][:120]}"); done(); sys.exit(0)
for _try in range(3):                     # one retry if the upload dies on a network error
    r = subprocess.run([sys.executable, "-I", str(ROOT / "bin/ig_publish.py"), video, pathlib.Path(cap).read_text(), "--publish", "--thumb-offset", thumb], cwd=str(ROOT), env={**os.environ, "IG_ACCOUNT": account}, capture_output=True, text=True)
    if r.returncode == 0 and '"permalink"' in r.stdout: break
    if 'PUBLISHED_ID' in r.stdout: break    # it went out; never retry after Instagram accepted it
    if not any(k in (r.stderr + r.stdout) for k in ('URLError', 'nodename', 'timed out', 'Connection', 'tunnel')): break
    P('network error, retrying in 60s:', (r.stderr or r.stdout)[-200:]); _t.sleep(60)
P(r.stdout[-1500:], r.stderr[-800:])
if r.returncode != 0 or '"permalink"' not in r.stdout: notify(f"{label} FAILED", f"@8bit{account} post {label} failed to publish: " + (r.stderr.strip() or r.stdout.strip())[-160:])
done()
