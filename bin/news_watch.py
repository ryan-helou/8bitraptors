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
# 2026-11-27: a headless `claude -p` started by launchd cannot sign in ("OAuth session expired"). So this script only
# QUEUES the story; the Claude app's scheduled task 8bit-news-reel (6:05 + 7:00 AM, signed in) builds the reel.
pp = D / "pending.json"; pend = json.loads(pp.read_text()) if pp.exists() else []
pend = pend if isinstance(pend, list) else [pend]
pend.append({**item, "found": now.isoformat(timespec="minutes")}); pp.write_text(json.dumps(pend, indent=1))
print("queued news for", item["acc"], "-", item["headline"])
