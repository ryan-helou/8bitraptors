#!/usr/bin/env python3
"""Publish a local video to @8bitraptors as a Reel via the Instagram Graph API.

  ig_publish.py VIDEO.mp4 ["caption"]  [--publish] [--trial]

DRY RUN by default: prints video + caption + the account the token belongs to, sends nothing.
--publish posts for real. --trial makes it a TRIAL reel (shown to non-followers first, manual graduation).
Pattern copied from ~/Developer/RyanTalks/bin/ig_publish.py: video_url upload through a temporary
cloudflared tunnel (the resumable upload silently drops trial_params), poll until FINISHED, publish, log to data/posts.json.
Safety: refuses to post unless the token's account username equals EXPECTED_IG_USERNAME (default 8bitraptors).
"""
import argparse, datetime as dt, json, pathlib, re, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request
import os; os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAPH = "https://graph.facebook.com/v23.0"
env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#")) if (ROOT / ".env").exists() else {}
import os as _os
ACCOUNT = (_os.environ.get("IG_ACCOUNT") or "raptors").lower()
SUF = "" if ACCOUNT == "raptors" else "_" + ACCOUNT.upper()
TOKEN, IG = env.get("IG_TOKEN" + SUF, "").strip(), env.get("IG_USER_ID" + SUF, "").strip()
WANT = "8bit" + ACCOUNT

def call(url, data=None, method=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, method=method), timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {url.split('?')[0]}: {e.read().decode()[:500]}")

class Tunnel:
    def __init__(self, f):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="igpub_")); shutil.copy2(f, self.dir / "reel.mp4")
    def __enter__(self):
        hl, cl = open(self.dir / "http.log", "w"), open(self.dir / "cf.log", "w")
        self.http = subprocess.Popen([sys.executable, "-u", "-m", "http.server", "0", "--bind", "127.0.0.1"], cwd=self.dir, stdout=hl, stderr=subprocess.STDOUT)
        port, t0 = None, time.time()
        while not port and time.time() - t0 < 10:
            time.sleep(0.3); m = re.search(r"port (\d+)", (self.dir / "http.log").read_text()); port = m and m.group(1)
        self.cf = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"], stdout=cl, stderr=subprocess.STDOUT)
        base = None
        while not base and time.time() - t0 < 60:
            time.sleep(0.5); m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", (self.dir / "cf.log").read_text()); base = m and m.group(0)
        if not base: self.__exit__(); sys.exit("cloudflared tunnel did not come up")
        self.url = f"{base}/reel.mp4"; time.sleep(15)  # let DNS settle (macOS caches early misses)
        for _ in range(30):
            code = subprocess.run(["curl", "-s", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}", "-r", "0-0", self.url], capture_output=True, text=True).stdout
            if code in ("200", "206"): return self
            time.sleep(2)
        self.__exit__(); sys.exit(f"tunnel not reachable: {self.url}")
    def __exit__(self, *a):
        for p in (getattr(self, "cf", None), getattr(self, "http", None)):
            if p: p.terminate()
        shutil.rmtree(self.dir, ignore_errors=True)

def default_caption():
    d = json.loads((ROOT / "prototype/data.json").read_text())
    rows = "\n".join(f"{chr(0x1F534) if p['status']=='OUT' else chr(0x1F7E2)} {p['name']}: {p['stat']}" for p in d["party"])
    return (f"PARTY CHECK {chr(0x1F3AE)}{chr(0x1F995)} {d['tagline'].title()}\n\n{rows}\n\nA wild {d['opp']} appeared!\n"
            f"{d['gameLine']} {d['venue']}\nRaptors {d['teamRecord']}\n\n{d['cta']} {chr(0x1F447)}\n\n#NBA #Raptors #WeTheNorth #Toronto #Basketball")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("video"); a.add_argument("caption", nargs="?")
    a.add_argument("--publish", action="store_true"); a.add_argument("--trial", action="store_true"); a.add_argument("--thumb-offset", type=int, help="cover frame in ms")
    o = a.parse_args(); video = pathlib.Path(o.video).resolve(); cap = o.caption or default_caption()
    print(f"COVER FRAME: {o.thumb_offset} ms\n") if o.thumb_offset is not None else None; print(f"VIDEO: {video} ({video.stat().st_size/1e6:.1f} MB)\nMODE: {'TRIAL' if o.trial else 'regular'} reel\nCAPTION:\n{cap}\n")
    if not (TOKEN and IG):
        print("DRY RUN. No IG_TOKEN/IG_USER_ID yet (run bin/mint_token.py after setup)."); sys.exit(0 if not o.publish else "Cannot publish without credentials.")
    who = call(f"{GRAPH}/{IG}?fields=username&access_token={TOKEN}").get("username")
    print(f"Token belongs to: @{who}")
    if who != WANT: sys.exit(f"REFUSING: expected @{WANT} but token is for @{who}.")
    if not o.publish: print("DRY RUN (nothing sent). Add --publish to post."); sys.exit(0)
    params = {"media_type": "REELS", "caption": cap, "access_token": TOKEN}
    if o.thumb_offset is not None: params["thumb_offset"] = str(o.thumb_offset)
    if o.trial: params["trial_params"] = json.dumps({"graduation_strategy": "MANUAL"})
    def safe(url):   # status checks survive a dropped connection (flaky network abroad)
        for _ in range(6):
            try: return call(url)
            except (urllib.error.URLError, OSError, ValueError) as e: print("status check retry:", str(e)[:80], flush=True); time.sleep(10)
        return {}
    def wait_and_publish(cid, minutes):
        for _ in range(minutes * 12):
            st = safe(f"{GRAPH}/{cid}?fields=status_code,status&access_token={TOKEN}")
            if st.get("status_code") == "FINISHED": break
            if st.get("status_code") in ("ERROR", "EXPIRED"): sys.exit(f"processing error: {st}")
            time.sleep(5)
        else: sys.exit(f"still processing after {minutes} min: {st}")
        if os.environ.get("IG_NO_PUBLISH"): print(f"CONTAINER_READY (IG_NO_PUBLISH set, not published)"); sys.exit(0)
        try: pub = call(f"{GRAPH}/{IG}/media_publish", {"creation_id": cid, "access_token": TOKEN})
        except (urllib.error.URLError, OSError, ValueError) as e:
            # The reply was lost, so we don't know whether it went out. Look before anyone retries: never double-post.
            time.sleep(30); head = cap.strip()[:40]
            recent = safe(f"{GRAPH}/{IG}/media?fields=id,caption,timestamp&limit=3&access_token={TOKEN}").get("data", [])
            hit = [m for m in recent if (m.get("caption") or "").strip()[:40] == head]
            if not hit: sys.exit(f"publish reply lost and the post is not on the account; safe to retry later ({str(e)[:80]})")
            pub = {"id": hit[0]["id"]}
        print(f"PUBLISHED_ID {pub['id']}", flush=True)   # marker: after this line a retry would double-post
        return pub
    if not o.trial:
        # Direct (resumable) upload, 2026-11-10: the video_url + cloudflared tunnel route fails from China (container ERROR
        # 2207077), the direct route works. rupload often answers HTTP 400 ProcessingFailedError on ~60 s videos even though
        # the container still finishes (github.com/waleedse/zaviya.pk/pull/90), so never trust that reply: poll up to 10 min.
        params["upload_type"] = "resumable"; data = open(video, "rb").read()
        for attempt in (1, 2):   # a stuck container (upload body lost on a bad network) gets one fresh try; nothing is published until FINISHED
            cid = call(f"{GRAPH}/{IG}/media", params)["id"]
            req = urllib.request.Request(f"https://rupload.facebook.com/ig-api-upload/v23.0/{cid}", data=data, method="POST",
                  headers={"Authorization": "OAuth " + TOKEN, "offset": "0", "file_size": str(len(data)), "Content-Type": "application/octet-stream"})
            try: print("upload:", urllib.request.urlopen(req, timeout=600).read().decode()[:120], flush=True)
            except Exception as e: print("upload reply (polling anyway):", (getattr(e, "read", lambda: b"")().decode() or str(e))[:200], flush=True)
            try: pub = wait_and_publish(cid, 10); break
            except SystemExit as e:
                if attempt == 2 or "still processing" not in str(e): raise
                print("container stuck, uploading again:", str(e)[:120], flush=True)
    else:
        with Tunnel(video) as t:
            params["video_url"] = t.url; cid = call(f"{GRAPH}/{IG}/media", params)["id"]
            pub = wait_and_publish(cid, 5)
    info = call(f"{GRAPH}/{pub['id']}?fields=permalink,shortcode,timestamp&access_token={TOKEN}")
    row = {"account": ACCOUNT, "media_id": pub["id"], **info, "file": str(video), "caption": cap, "trial": o.trial,
           "logged": dt.datetime.now().isoformat(timespec="seconds")}
    log = ROOT / "data/posts.json"; rows = json.loads(log.read_text()) if log.exists() else []
    rows.append(row); log.write_text(json.dumps(rows, indent=1, ensure_ascii=False)); print(json.dumps(row, indent=1))
