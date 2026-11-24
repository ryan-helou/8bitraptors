#!/usr/bin/env python3
"""Weekly: what is working for other NBA fan pages (Ryan 2026-11-23, loop idea 5). No Claude tokens.
Pulls each page's last 30 posts with the Instagram business_discovery lookup, ranks their reels from the last 14 days by
views against that page's own median, and writes data/learn/fanpages.md (top 15 ideas). The weekly refill turns 1-2 of
them into explore reels in OUR style about OUR team. Edit the page list in data/learn/fanpages.json (only
business/creator accounts can be looked up; failures are listed and skipped)."""
import json, re, pathlib, urllib.request, urllib.parse, statistics as stx, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent; OUT = ROOT / "data/learn"; OUT.mkdir(parents=True, exist_ok=True)
env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
lf = OUT / "fanpages.json"
pages = json.loads(lf.read_text()) if lf.exists() else ["8bitwolves", "houseofhighlights", "brhoops", "nbacentral", "hoopshype", "ballislife", "overtime", "nbamemes", "nba.tiktoks", "hoopmixtape"]
lf.write_text(json.dumps(pages, indent=1))
now = dt.datetime.now(dt.timezone.utc); ideas, skipped = [], []
TEAMS = "HAWKS CELTICS NETS HORNETS BULLS CAVALIERS CAVS MAVERICKS MAVS NUGGETS PISTONS WARRIORS ROCKETS PACERS CLIPPERS LAKERS GRIZZLIES HEAT BUCKS TIMBERWOLVES WOLVES PELICANS KNICKS THUNDER MAGIC 76ERS SIXERS SUNS BLAZERS KINGS SPURS RAPTORS JAZZ WIZARDS LEBRON CURRY GIANNIS WEMBY".split()
for u in pages:
    f = f"business_discovery.username({u}){{followers_count,media.limit(30){{timestamp,caption,view_count,like_count,comments_count,permalink,media_product_type}}}}"
    try: b = json.load(urllib.request.urlopen(f"https://graph.facebook.com/v23.0/{env['IG_USER_ID'].strip()}?fields={urllib.parse.quote(f)}&access_token={env['IG_TOKEN'].strip()}", timeout=60))["business_discovery"]
    except Exception as e: skipped.append(f"{u} ({type(e).__name__})"); continue
    reels = [m for m in b["media"]["data"] if m.get("view_count")]
    if len(reels) < 4: skipped.append(f"{u} (too few reels)"); continue
    m_ = stx.median(m["view_count"] for m in reels)
    for m in reels:
        age = (now - dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")).days
        nba = re.search(r"NBA|HOOP|BASKETBALL|DUNK|TRADE|DRAFT|MVP|PLAYOFF|FINALS|" + "|".join(TEAMS), (m.get("caption") or "").upper())
        if age <= 14 and nba: ideas.append(dict(page=u, followers=b.get("followers_count"), x=round(m["view_count"] / max(m_, 1), 1), views=m["view_count"],
                                        title=(m.get("caption") or "").split("\n")[0][:110], url=m["permalink"]))
ideas.sort(key=lambda i: -i["x"])
md = [f"# What works for other NBA fan pages ({now:%b %d})", "", "x = views vs that page's own median. Use the IDEA (format, angle, hook shape), never their art, audio or footage.", "",
      "| x | views | page | title | link |", "|---|---|---|---|---|"]
md += [f"| {i['x']} | {i['views']} | @{i['page']} | {i['title'].replace('|', '/')} | {i['url']} |" for i in ideas[:15]]
md += ["", "Skipped: " + (", ".join(skipped) or "none")]
(OUT / "fanpages.md").write_text("\n".join(md)); print("\n".join(md[:12])); print("skipped:", skipped)
