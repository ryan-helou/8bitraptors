#!/usr/bin/env python3
"""Auto-reply to Instagram comments on @8bitraptors / @8bitwarriors (Ryan approved standing replies, 2026-11-12).

    reply_comments.py            dry run: prints drafted replies, posts nothing
    reply_comments.py --post     posts the drafted replies (needs instagram_manage_comments on the Page token)

Rules: research/comment_reply_rules.md (drafts are written by `claude -p` with those rules, then validated here).
Never replies twice to a comment (data/replied_comments.json), skips comments older than 3 days, max 15 replies per
account per run. Log: data/logs/replies.log. Prints no tokens.
"""
import datetime as dt, json, os, pathlib, re, subprocess, sys, urllib.parse, urllib.request
os.environ["PATH"] = "/Users/ryanhelou/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
ROOT = pathlib.Path(__file__).resolve().parent.parent
G = "https://graph.facebook.com/v23.0"
POST = "--post" in sys.argv
env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
RULES = (ROOT / "research/comment_reply_rules.md").read_text()
DONE_F = ROOT / "data/replied_comments.json"
done = set(json.loads(DONE_F.read_text())) if DONE_F.exists() else set()
LOG = open(ROOT / "data/logs/replies.log", "a")
def log(*a): print(dt.datetime.now().isoformat(timespec="seconds"), *a, file=LOG, flush=True); print(*a, flush=True)

def call(path, data=None, **q):
    url = f"{G}/{path}?" + urllib.parse.urlencode(q)
    body = urllib.parse.urlencode(data).encode() if data else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e: return {"error": e.read().decode()[:300]}

BAD = re.compile(r"(https?://|www\.|@\w|#\w|\bbot\b|\bai\b|automat|follow us|link in bio)", re.I)
def ok_reply(r, caption):
    if not r or len(r) > 120 or BAD.search(r): return False
    nums = re.findall(r"\d+(?:\.\d+)?", r)
    return all(n in caption for n in nums)   # never invent stats

def draft(account, items):
    team = "Raptors" if account == "raptors" else "Warriors"
    prompt = (f"You write replies for the Instagram fan page @8bit{account} (8-bit pixel-art {team} reels). Follow these rules exactly:\n\n{RULES}\n\n"
              "Here are new comments as JSON (comment id, the post caption, the comment text). For each, decide whether to reply under the rules. "
              "Return ONLY a JSON array of objects {\"id\": \"...\", \"reply\": \"...\"} for the ones to reply to; leave out the ones to skip. No other text.\n\n"
              + json.dumps(items, ensure_ascii=False))
    r = subprocess.run(["claude", "-p", prompt, "--model", "claude-sonnet-5-5"], capture_output=True, text=True, timeout=600)
    m = re.search(r"\[.*\]", r.stdout, re.S)
    try: return json.loads(m.group(0)) if m else []
    except Exception: log("could not parse drafts:", r.stdout[:200]); return []

cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)
for suf, account in (("", "raptors"), ("_WARRIORS", "warriors")):
    tok, ig = env["IG_TOKEN" + suf].strip(), env["IG_USER_ID" + suf].strip()
    d = call(f"{ig}/media", fields="caption,timestamp,comments.limit(50){id,text,timestamp,replies{id}}", limit=20, access_token=tok)
    if "error" in d: log(account, "read failed:", d["error"][:150]); continue
    items, caps = [], {}
    for m in d.get("data", []):
        cap = (m.get("caption") or "")[:600]
        for c in (m.get("comments") or {}).get("data", []):
            t = (c.get("text") or "").strip()
            if c["id"] in done or not t or dt.datetime.fromisoformat(c["timestamp"].replace("+0000", "+00:00")) < cutoff: continue
            if (c.get("replies") or {}).get("data"): continue          # already has a reply thread; leave it
            if not re.search(r"[A-Za-z0-9]", t): continue                # emoji-only
            items.append({"id": c["id"], "caption": cap, "comment": t[:300]}); caps[c["id"]] = cap
    if not items: log(account, "no new comments"); continue
    drafts = [x for x in draft(account, items[:40]) if x.get("id") in caps]
    n = 0
    for x in drafts:
        if n >= 15: break
        r = (x.get("reply") or "").strip()
        if not ok_reply(r, caps[x["id"]]): log(account, "REJECTED draft:", repr(r)); continue
        c = next(i for i in items if i["id"] == x["id"])
        if not POST: log(account, "DRAFT:", repr(c["comment"][:60]), "->", repr(r)); n += 1; continue
        res = call(f"{x['id']}/replies", {"message": r}, access_token=tok)
        if "error" in res: log(account, "POST FAILED:", res["error"][:150]); break
        done.add(x["id"]); DONE_F.write_text(json.dumps(sorted(done))); n += 1
        log(account, "REPLIED:", repr(c["comment"][:60]), "->", repr(r))
    log(account, f"{n} {'replies posted' if POST else 'drafts'}; {len(items)} new comments seen")
