#!/usr/bin/env python3
"""Report card for every post ever (Ryan 2026-11-27: "analyze all our posts ever and know exactly how good all our videos are").
Input: Business Suite export CSV(s) in data/exports/ (Views, Reach, Likes, Shares, Saves, Comments, FOLLOWS, Duration per post)
joined with our Insights pulls (average watch time) by permalink. Output: data/learn/report_all_posts.md, and every post's
follows appended to data/learn/follows.jsonl so the learning loop scores on real follows.
usage: python3 bin/analyze_all.py"""
import csv, json, glob, os, re, statistics as st, datetime as dt, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parent.parent; OUT = ROOT / "data/learn"
med = lambda xs: st.median(xs) if xs else 0


def fmt(t):
    t = (t or "").upper()
    if "HAD A POK" in t: return "pokemon_trainer"
    if "POKÉMON" in t or "POKEMON" in t: return "pokemon_team"
    if "TRADE COURT" in t or "WHO WON THE" in t: return "trade_court"
    if "CHOOSE YOUR" in t or "PAUSE AND PICK" in t or t.startswith("OUR GOAT"): return "poll"
    if re.match(r"^(RAPTORS|WARRIORS) \d+, |^(VICTORY|FINAL|WIN|LOSS|W |L )", t) or re.search(r"\b\d{2,3}-\d{2,3}\b", t[:30]): return "recap"
    if re.search(r"HIGH SCORE|HOW WE BUILT|GOT HOME|GAMES IN|STARTING FIVE|PARTY CHECK|IS OUT|GAME DAY", t): return "game_day/explainer"
    return "story"


def hook(t):
    first = (t or "").split("🎮")[0].split("🦖")[0].strip().upper()
    tags = []
    if re.search(r"\d", first): tags.append("number in hook")
    if "?" in first: tags.append("question hook")
    if re.search(r"\bWE\b|\bOUR\b|\bUS\b", first): tags.append("we/our hook")
    if len(first.split()) <= 4: tags.append("short hook (<=4 words)")
    return tags or ["plain"]


rows = []
for f in sorted(glob.glob(str(ROOT / "data/exports/*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        if r.get("Post type", "").lower().find("reel") < 0 and r.get("Post type") not in ("IG reel", "IG carousel", "IG image"): continue
        try:
            rows.append(dict(acc=r["Account username"].replace("8bit", ""), pl=r["Permalink"].rstrip("/") + "/", desc=r["Description"],
                             title=r["Description"].split("\n")[0][:90], secs=float(r["Duration (sec)"] or 0),
                             t=dt.datetime.strptime(r["Publish time"], "%m/%d/%Y %H:%M"), views=int(r["Views"] or 0), reach=int(r["Reach"] or 0),
                             likes=int(r["Likes"] or 0), shares=int(r["Shares"] or 0), follows=int(r["Follows"] or 0),
                             comments=int(r["Comments"] or 0), saves=int(r["Saves"] or 0)))
        except Exception: continue
seen = {}
for r in rows: seen[r["pl"]] = r          # one row per post (newest export wins)
rows = list(seen.values())
watch = {}
for p in sorted(glob.glob(str(ROOT / "data/insights/*.json")), key=os.path.getmtime):
    try:
        for x in json.load(open(p)):
            if isinstance(x, dict) and x.get("permalink"): watch[x["permalink"].rstrip("/") + "/"] = x.get("avg_watch_s")
    except Exception: pass
for r in rows:
    r["fmt"] = fmt(r["title"]); r["watch"] = watch.get(r["pl"])
    r["wshare"] = (r["watch"] / r["secs"]) if r["watch"] and r["secs"] else None
    r["fpk"] = r["follows"] * 1000 / r["views"] if r["views"] else 0
    r["len"] = "<25 s" if r["secs"] < 25 else "25-35 s" if r["secs"] < 35 else "35-45 s" if r["secs"] < 45 else "45 s+"

md = [f"# Report card: every post ({dt.date.today()})", "",
      "Source: Business Suite export (views, follows, shares, saves per post) + our Insights pulls (average watch time).",
      "fpk = follows per 1,000 views. Watched = average watch time / reel length.", ""]


def table(title, groups, minn=3):
    out = [f"### {title}", "| group | posts | median views | follows | fpk | median watched |", "|---|---|---|---|---|---|"]
    stats = []
    for k, rs in groups.items():
        if len(rs) < minn: continue
        v = sum(r["views"] for r in rs); f = sum(r["follows"] for r in rs)
        stats.append((f * 1000 / v if v else 0, k, rs, v, f))
    for fpk, k, rs, v, f in sorted(stats, reverse=True):
        ws = [r["wshare"] for r in rs if r["wshare"]]
        out.append(f"| {k} | {len(rs)} | {int(med([r['views'] for r in rs]))} | {f} | {fpk:.2f} | {med(ws):.0%} |" if ws else f"| {k} | {len(rs)} | {int(med([r['views'] for r in rs]))} | {f} | {fpk:.2f} | - |")
    return out + [""]


for acc in ("raptors", "warriors"):
    rs = [r for r in rows if r["acc"] == acc]
    if not rs: continue
    V = sum(r["views"] for r in rs); F = sum(r["follows"] for r in rs)
    md += [f"## @8bit{acc}: {len(rs)} posts, {V:,} views, {F} follows from posts ({F * 1000 / V:.2f} per 1K views)", ""]
    g = lambda key: dict(sorted(collections.defaultdict(list, {}).items()))
    def grp(key):
        d = collections.defaultdict(list)
        for r in rs:
            ks = key(r)
            for k in (ks if isinstance(ks, list) else [ks]): d[k].append(r)
        return d
    md += table("By format", grp(lambda r: r["fmt"]))
    md += table("By length", grp(lambda r: r["len"]))
    md += table("By post hour (Toronto)", grp(lambda r: f"{r['t'].hour:02d}:00"), minn=4)
    md += table("By weekday", grp(lambda r: r["t"].strftime("%a")), minn=4)
    md += table("By hook style", grp(lambda r: hook(r["title"])), minn=4)
    md += table("By week", grp(lambda r: "week of " + (r["t"] - dt.timedelta(days=r["t"].weekday())).strftime("%b %d")), minn=1)
    top = sorted(rs, key=lambda r: (-r["follows"], -r["views"]))[:10]
    md += ["### Top 10 by follows", "| follows | views | fpk | watched | posted | title |", "|---|---|---|---|---|---|"]
    md += [f"| {r['follows']} | {r['views']:,} | {r['fpk']:.1f} | {(f'{r[chr(119)+chr(115)+chr(104)+chr(97)+chr(114)+chr(101)]:.0%}' if r['wshare'] else '-')} | {r['t']:%b %d %H:%M} | {r['title'][:60].replace('|', '/')} |" for r in top] + [""]
    big = [r for r in rs if r["views"] >= 500]
    md += ["### Most views without a single follow (views 500+)", "| views | watched | title |", "|---|---|---|"]
    md += [f"| {r['views']:,} | {(f'{r[chr(119)+chr(115)+chr(104)+chr(97)+chr(114)+chr(101)]:.0%}' if r['wshare'] else '-')} | {r['title'][:70].replace('|', '/')} |" for r in sorted([r for r in big if r["follows"] == 0], key=lambda r: -r["views"])[:8]] + [""]
(OUT / "report_all_posts.md").write_text("\n".join(md)); print("\n".join(md))
with open(OUT / "follows.jsonl", "a") as f:
    for r in rows: f.write(json.dumps(dict(date=str(dt.date.today()), account=r["acc"], posted=r["t"].strftime("%Y-%m-%d %H:%M"), caption_start=r["desc"][:40], follows=r["follows"], views=r["views"], source="export")) + "\n")
