#!/usr/bin/env python3
"""News half of the self-improving loop (Ryan 2026-11-23: "the loop needs to be tied to news").
launchd com.8bitraptors.news runs this every 30 min. It costs NO Claude tokens unless real news shows up:
  - pulls ESPN news for the Raptors and Warriors, scores each headline (trade/signing/firing/major injury = 3,
    career-high/record/milestone/triple-double/40+ = 2), keeps unseen items from the last 36 h scoring 2+
  - if there is one, starts ONE headless Claude run (claude -p) that builds a news reel and queues it into the next
    slot inside the 5-a-day cap. At most 2 news runs per account per day, never two runs at once.
usage: python3 bin/news_watch.py [--dry]
"""
import json, sys, re, pathlib, subprocess, urllib.request, datetime as dt, os
from zoneinfo import ZoneInfo
ROOT = pathlib.Path(__file__).resolve().parent.parent; TOR = ZoneInfo("America/Toronto"); now = dt.datetime.now(TOR)
D = ROOT / "data/news"; D.mkdir(parents=True, exist_ok=True); DRY = "--dry" in sys.argv
TEAMS = {"raptors": ("tor", "RAPTORS|TORONTO"), "warriors": ("gs", "WARRIORS|GOLDEN STATE")}
BIG = [(3, r"\bTRADE[DS]?\b|ACQUIRE|\bSIGN(S|ED|ING)\b|EXTENSION|WAIVE|\bFIRED\b|\bHIRE[DS]?\b|SEASON-ENDING|SURGERY|\bTORN\b|OUT INDEFINITELY|RETIRE"),
       (2, r"CAREER-HIGH|CAREER HIGH|FRANCHISE|RECORD|MILESTONE|TRIPLE-DOUBLE|\b[4-6]\d POINTS|\bSCORES [4-6]\d|BUZZER|GAME-WINNER|ALL-STAR")]
seen_p = D / "seen.json"; seen = set(json.loads(seen_p.read_text())) if seen_p.exists() else set()
runs_p = D / "runs.json"; runs = json.loads(runs_p.read_text()) if runs_p.exists() else []
# runs at any hour (Ryan 2026-11-23: the Mac is reliably on 1-8 AM, so overnight game news is caught then)
if (D / "running.lock").exists() and (now.timestamp() - (D / "running.lock").stat().st_mtime) < 3 * 3600: sys.exit(0)

found = []
for acc, (code, rx) in TEAMS.items():
    try: arts = json.load(urllib.request.urlopen(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news?team={code}&limit=25", timeout=30)).get("articles", [])
    except Exception as e: print(acc, "fetch failed", e); continue
    for a in arts:
        aid = str(a.get("id") or a.get("headline")); h = (a.get("headline") or "").upper(); desc = (a.get("description") or "").upper()
        if aid in seen or a.get("type") in ("Media", "Preview"): continue
        try: age = (now - dt.datetime.fromisoformat(a["published"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception: age = 99
        if age > 36 or not re.search(rx, h + " " + desc): continue
        score = max([s for s, r in BIG if re.search(r, h + " " + desc)] or [0])
        if score >= 2: found.append(dict(acc=acc, id=aid, score=score, headline=a.get("headline"), description=a.get("description"),
                                         url=((a.get("links") or {}).get("web") or {}).get("href"), published=a.get("published")))
today = [r for r in runs if r["day"] == str(now.date())]
found = [f for f in sorted(found, key=lambda f: -f["score"]) if sum(r["acc"] == f["acc"] for r in today) < 2]
print(json.dumps(found, indent=1)[:2000] if found else "no news")
if DRY or not found: sys.exit(0)

item = found[0]; seen.add(item["id"]); seen_p.write_text(json.dumps(sorted(seen)))
runs.append(dict(day=str(now.date()), acc=item["acc"], headline=item["headline"])); runs_p.write_text(json.dumps(runs[-60:], indent=1))
(D / "pending.json").write_text(json.dumps(item, indent=1)); (D / "running.lock").write_text(now.isoformat())
PROMPT = f"""News reel run for @8bit{item['acc']} (repo ~/Developer/8bitraptors). Breaking item from ESPN, in data/news/pending.json:
"{item['headline']}" ({item['url']}).
1. Open the source URL and confirm the facts. If it is not real team news worth a reel (fans would care TODAY), log why
   in data/news/decisions.md, delete data/news/running.lock and stop.
2. Read data/learn/playbook.md and follow it. Build ONE reel with the news-drop format (gen/fmt_news_drop.html; copy the newest specs/*news* spec as a model if one
   exists). 20-35 s, hook in line 1, fan voice we/us/our, no emojis in voiceover or dialog, every number in the spec's facts
   with its source. Build: PATH=/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH zsh gen/batch.sh specs/<spec>.json
   (QA must pass), then python3 gen/factcheck.py specs/<spec>.json must say "facts OK". One build at a time (8 GB Mac).
3. Queue it in the soonest :00 or :30 slot (the cloud poster only runs then) that is at least 90 min after this account's last post and before 22:30 Toronto, keeping the
   account at 5 posts a day or fewer (Warriors 3): if the day is full, push that day's lowest-scoring queued reel
   (data/learn/scores.json) to the end of the queue by editing its due_et in data/api_queue.json, then queue with
   python3 bin/api_queue.py api_{item['acc']}_<stem> {item['acc']} out/<stem>.mp4 out/<stem>.caption.txt <YYYY-MM-DD> <HH:MM>
   Never --force, never print .env tokens, never change account settings.
4. Append one line to data/news/decisions.md (date, headline, what you queued and when), delete data/news/running.lock.
Before step 3, REVIEW: start ONE fresh general-purpose subagent with only the mp4, spec, caption and source URL. Its brief:
"Review this reel like a strict editor before it is posted.
- Pull frames at 0, 2, 5 s and every 5 s after that (ffmpeg); read every number against the source page.
- Rate the HOOK (reason to stay in 1-2 s) and the PAYOFF (does the end deliver it?) 1-5; flag only broken things (wrong fact, typo, cut-off text, not fan voice).
- No style nitpicks.
Reply PASS (both 4+, nothing broken), or FIX with a short list."
Fix and re-review, at most 2 rounds; never queue a reel that still gets FIX.
After queueing, run python3 bin/cloud_sync.py and confirm the label is in ~/Developer/8bit-poster/queue.json.
Be token-efficient: minimal file reads, short final summary."""
log = open(ROOT / "data/logs/news_run.log", "a"); log.write(f"\n=== {now.isoformat(timespec='minutes')} {item['headline']}\n"); log.flush()
subprocess.Popen([str(pathlib.Path.home() / ".local/bin/claude"), "-p", PROMPT, "--permission-mode", "bypassPermissions"],
                 cwd=str(ROOT), stdout=log, stderr=log, start_new_session=True)
print("started news run for", item["acc"])
