#!/usr/bin/env python3
"""Runs every 5 min (launchd com.8bitraptors.apidispatch). Posts each data/api_queue.json item once Toronto time reaches its
due time, using bin/scheduled_post.py (network wait, QA/voice checks, 2-hour lateness guard, publish, notify).
Independent of the Mac's own time zone. One post per run, so missed posts never all go out at once."""
import sys, json, pathlib, subprocess, datetime as dt, fcntl
ROOT = pathlib.Path(__file__).resolve().parent.parent
lock = open(ROOT / "data/.api_dispatch.lock", "w")
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit(0)                     # a post is still uploading
qf = ROOT / "data/api_queue.json"
q = json.loads(qf.read_text()) if qf.exists() else []
now = dt.datetime.now(dt.timezone.utc)
# Stuck-run recovery (2026-11-11): if a run died or hung (Mac offline, killed upload), the item stays "running" forever.
# After 40 min with no live process for it: if the post is on the account, mark it posted; otherwise queue it again (once).
def live(label): return subprocess.run(["pgrep", "-f", f"scheduled_post.py {label}"], capture_output=True).returncode == 0
for it in q:
    if it["state"] == "running" and not live(it["label"]) and now - dt.datetime.fromisoformat(it.get("started", it["due_et"])) > dt.timedelta(minutes=40):
        import urllib.request, urllib.parse
        env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
        suf = "" if it["account"] == "raptors" else "_" + it["account"].upper()
        head = (ROOT / "data" / f"caption_{it['label']}.txt").read_text().strip()[:40] if (ROOT / "data" / f"caption_{it['label']}.txt").exists() else None
        try:
            d = json.loads(urllib.request.urlopen(f"https://graph.facebook.com/v23.0/{env['IG_USER_ID' + suf].strip()}/media?" + urllib.parse.urlencode({"fields": "caption", "limit": 5, "access_token": env["IG_TOKEN" + suf].strip()}), timeout=60).read())["data"]
        except Exception: continue   # can't check right now; never guess
        if head and any((m.get("caption") or "").strip()[:40] == head for m in d): it["state"] = "posted"
        elif it.get("retries", 0) < 1: it["state"] = "queued"; it["retries"] = it.get("retries", 0) + 1
        else: it["state"] = "failed"
        qf.write_text(json.dumps(q, indent=1))
def on_account(it):   # True if a post with this caption is already on the account (never post twice)
    import urllib.request, urllib.parse
    env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
    suf = "" if it["account"] == "raptors" else "_" + it["account"].upper()
    head = pathlib.Path(it["caption"]).read_text().strip()[:40]
    d = json.loads(urllib.request.urlopen(f"https://graph.facebook.com/v23.0/{env['IG_USER_ID' + suf].strip()}/media?" + urllib.parse.urlencode({"fields": "caption", "limit": 8, "access_token": env["IG_TOKEN" + suf].strip()}), timeout=60).read())["data"]
    return any((m.get("caption") or "").strip()[:40] == head for m in d)
def requeue(it):      # a late-skipped post goes back in line: same clock time, the day after the account's last queued post
    last = max([x["due_et"] for x in q if x["account"] == it["account"] and x["state"] == "queued"] or [it["due_et"]])
    d = dt.datetime.fromisoformat(last).date() + dt.timedelta(days=1); t = dt.datetime.fromisoformat(it["due_et"])
    it["due_et"] = t.replace(year=d.year, month=d.month, day=d.day).isoformat(); it["state"] = "queued"; it["label_retry"] = it.get("label_retry", 0) + 1
# Posts scheduled in Meta Business Suite (state "bs_scheduled", by the nightly 8bit-bs-schedule task): Meta publishes them.
# 30 min after their time, confirm they are on the account; after 3 h without it, mark them failed (health.py reports it).
for it in q:
    if it["state"] == "bs_scheduled" and now - dt.datetime.fromisoformat(it["due_et"]) > dt.timedelta(minutes=30):
        try:
            if on_account(it): it["state"] = "posted"; it["why"] = "Business Suite"; qf.write_text(json.dumps(q, indent=1))
            elif now - dt.datetime.fromisoformat(it["due_et"]) > dt.timedelta(hours=3): it["state"] = "failed"; it["why"] = "scheduled in Business Suite but never appeared"; qf.write_text(json.dumps(q, indent=1))
        except Exception: pass
for it in q:
    if it["state"] != "queued" or dt.datetime.fromisoformat(it["due_et"]) > now: continue
    try:
        if on_account(it): it["state"] = "posted"; it["why"] = "already on the account"; qf.write_text(json.dumps(q, indent=1)); continue
    except Exception: break                       # can't check right now (offline); try again in 5 min
    stp = ROOT / "data" / f"stamp_{it['label']}.json"   # the lateness guard reads the stamp: give it the CURRENT due time (learn.py moves posts)
    if stp.exists(): _s = json.loads(stp.read_text()); _s["due_et"] = it["due_et"]; stp.write_text(json.dumps(_s, indent=1))
    it["state"] = "running"; it["started"] = now.isoformat(timespec="seconds"); qf.write_text(json.dumps(q, indent=1))
    subprocess.run([sys.executable, "-I", str(ROOT / "bin/scheduled_post.py"), it["label"], it["account"], it["account"], it["video"], it["caption"], "1300"], cwd=str(ROOT))
    log = (ROOT / "data/logs" / f"{it['label']}.log").read_text() if (ROOT / "data/logs" / f"{it['label']}.log").exists() else ""
    tail = log[-1500:]
    it["state"] = "posted" if '"permalink"' in tail else ("skipped" if "SKIPPED" in tail or "BLOCKED" in tail else "failed")
    if it["state"] == "skipped" and "h late" in tail and it.get("label_retry", 0) < 2: requeue(it)
    qf.write_text(json.dumps(q, indent=1)); break
