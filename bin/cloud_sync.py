#!/usr/bin/env python3
"""Sync the Mac's post queue with the cloud poster (repo ~/Developer/8bit-poster, GitHub Actions posts it).
launchd com.8bitraptors.cloudsync, every 15 min. 1) pulls state.json from the cloud: posted / skipped / failed become
the local state. 2) pushes every locally queued post: video to release "videos" (only when new or changed),
caption, and queue.json (label, account, due time, md5). Posts held or removed here drop out of the cloud queue.
No Claude tokens. usage: python3 bin/cloud_sync.py [--dry]"""
import json, sys, pathlib, subprocess, hashlib, shutil, fcntl
ROOT = pathlib.Path(__file__).resolve().parent.parent; REPO = ROOT / "cloud"; DRY = "--dry" in sys.argv   # one repo since 2026-11-24 (ryan-helou/8bitraptors); the cloud poster lives in cloud/
lock = open(ROOT / "data/.cloud_sync.lock", "w")
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit(0)
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
git("pull", "-q", "--rebase", "--autostash")
st = json.loads((REPO / "state.json").read_text()); rq = {r["label"]: r for r in json.loads((REPO / "queue.json").read_text())}
qf = ROOT / "data/api_queue.json"; q = json.loads(qf.read_text()); changed = 0
import datetime as _dt
def _requeue(j):   # a post the cloud skipped for lateness goes back in line: same clock time, the day after the account's last queued post
    last = max([x["due_et"] for x in q if x["account"] == j["account"] and x["state"] == "queued"] or [j["due_et"]])
    d = _dt.datetime.fromisoformat(last).date() + _dt.timedelta(days=1); t = _dt.datetime.fromisoformat(j["due_et"])
    j["due_et"] = t.replace(year=d.year, month=d.month, day=d.day).isoformat(); j["state"] = "queued"; j["label_retry"] = j.get("label_retry", 0) + 1
for j in q:                                    # 1. cloud results win
    s = st.get(j["label"], {}).get("state")
    if s in ("posted", "skipped", "failed") and j["state"] in ("queued", "running") and st[j["label"]].get("attempt", 0) >= j.get("label_retry", 0):
        if s == "skipped" and "late" in st[j["label"]].get("why", "") and j.get("label_retry", 0) < 2:
            _requeue(j); changed += 1; continue
        j["state"] = s; j["cloud_why"] = st[j["label"]].get("why", ""); changed += 1
r = subprocess.run(["gh", "release", "view", "videos", "-R", "ryan-helou/8bitraptors-ops", "--json", "assets", "-q", ".assets[].name"], capture_output=True, text=True)
assets = set(r.stdout.split())
out = []
for j in q:                                    # 2. push the queue
    if j["state"] != "queued": continue
    v = pathlib.Path(j["video"]); md5 = hashlib.md5(v.read_bytes()).hexdigest()
    if (f"{j['label']}.mp4" not in assets or rq.get(j["label"], {}).get("md5") != md5) and not DRY:
        up = subprocess.run(["gh", "release", "upload", "videos", str(v), "--clobber", "-R", "ryan-helou/8bitraptors-ops"], capture_output=True, text=True)
        if up.returncode: print("upload failed", j["label"], up.stderr[-200:]); continue
    shutil.copy(j["caption"], REPO / "captions" / f"{j['label']}.txt")
    out.append(dict(label=j["label"], account=j["account"], due_et=j["due_et"], md5=md5, thumb=1300, attempt=j.get("label_retry", 0), **({"trial": True} if j.get("trial") else {})))
# 3. merge the cloud's publish log (permalink -> file) so learn.py can match posts to reels and lengths
try:
    lp = ROOT / "data/posts.json"; loc = json.loads(lp.read_text()); have = {r.get("permalink") for r in loc}
    for r_ in json.loads((REPO / "data/posts.json").read_text()):
        if r_.get("permalink") not in have:
            r_["file"] = str(ROOT / "scheduled" / pathlib.Path(r_.get("file", "")).name); loc.append(r_)
    if not DRY: lp.write_text(json.dumps(loc, indent=1, ensure_ascii=False))
except Exception as e: print("posts merge failed:", e)
if changed and not DRY: qf.write_text(json.dumps(q, indent=1, ensure_ascii=False))
(REPO / "queue.json").write_text(json.dumps(sorted(out, key=lambda x: x["due_et"]), indent=1))
print(f"{len(out)} queued in cloud, {changed} results pulled")
if not DRY:
    git("add", "cloud/queue.json", "cloud/captions")
    if git("diff", "--cached", "--quiet").returncode:
        git("commit", "-qm", "queue sync", "--", "cloud/queue.json", "cloud/captions"); p = git("push", "-q")
        if p.returncode: git("pull", "-q", "--rebase", "--autostash"); print("push retry:", git("push", "-q").returncode)
