#!/usr/bin/env python3
"""Self-improving loop, daily half (Ryan 2026-11-23). Runs after the morning report; no Claude tokens.
  1. SCORE what grows the page: per post, vs the account median: views (30%), shares+saves per 1K views (35%) and the
     share of the reel actually watched, avg watch / length (35%). Scored per FORMAT and per POST HOUR, shrunk toward
     the account average until a group has ~5 posts.
  2. RE-ORDER the next 7 days of queued posts: best formats first, no format twice in a row; every 5th slot explores
     (least-tested format, and its time moves to the least-tested nearby hour, keeping 90 min gaps, 12:00-22:30).
     Trial reels ("trial": true) are never moved.
  3. TRIALS: pairs labelled ..._xa / ..._xb (trial reels, non-followers only) are compared after 48 h -> trials.md.
  4. Writes data/learn/scores.json, latest.md, <date>.md and refill_needed when the queue runs low.
usage: python3 bin/learn.py [--dry]"""
import json, sys, pathlib, re, subprocess, statistics as stx, datetime as dt
from zoneinfo import ZoneInfo
ROOT = pathlib.Path(__file__).resolve().parent.parent; TOR = ZoneInfo("America/Toronto")
DRY = "--dry" in sys.argv; now = dt.datetime.now(TOR); OUT = ROOT / "data/learn"; OUT.mkdir(parents=True, exist_ok=True)
MIN_DAYS = {"raptors": 5, "warriors": 3}; K = 5
med = lambda xs: stx.median(xs) if xs else 0


def fmt(title):
    t = (title or "").upper()
    if "HAD A POK" in t: return "pokemon_trainer"
    if "POKÉMON" in t or "POKEMON" in t: return "pokemon_team"
    if "TRADE COURT" in t or "WHO WON THE" in t: return "trade_court"
    if "CHOOSE YOUR" in t or "PAUSE AND PICK" in t or t.startswith("OUR GOAT"): return "poll"
    if re.match(r"^(RAPTORS|WARRIORS) \d+, |^(VICTORY|FINAL|WIN|LOSS)\b", t): return "recap"
    if re.search(r"GAMES IN|STARTING FIVE|PARTY CHECK|IS OUT|GAME DAY|WHAT'S WRONG", t): return "game_day"
    if re.search(r"HIGH SCORE|HOW WE BUILT|HOW .* GOT HOME", t): return "explainer"
    if re.search(r"\bNEWS\b|BREAKING|JUST IN", t): return "news"
    return "story"


def hour_of(r):
    try: return int(r["posted"].split()[1][:2])
    except Exception: return None


def grp(rs, key):
    g = {}
    for r in rs:
        k = key(r)
        if k is not None: g.setdefault(k, []).append(r)
    return {k: dict(n=len(v), median_views=int(med([r["views"] for r in v])), score=round(med([r["_s"] for r in v]), 2)) for k, v in g.items()}


# reel lengths (permalink -> s), cached, from the publish log's file paths
posts = json.loads((ROOT / "data/posts.json").read_text()) if (ROOT / "data/posts.json").exists() else []
lp = OUT / "lengths.json"; LEN = json.loads(lp.read_text()) if lp.exists() else {}
FILE = {r.get("permalink"): r.get("file", "") for r in posts if r.get("permalink")}
TRIAL = {r.get("permalink") for r in posts if r.get("trial")}
for pl, f in FILE.items():
    if pl not in LEN and f and pathlib.Path(f).exists():
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
        if d: LEN[pl] = float(d)
lp.write_text(json.dumps(LEN))

latest = {}
for p in sorted((ROOT / "data/insights").glob("*.json"), key=lambda p: p.stat().st_mtime):
    try: rows = json.loads(p.read_text())
    except Exception: continue
    if not isinstance(rows, list): continue
    for r in rows:
        if isinstance(r, dict) and r.get("permalink"): latest[r["permalink"]] = r
rows = [r for r in latest.values() if 24 <= (r.get("age_h") or 0) <= 21 * 24 + 48 and r.get("views")]

# follows per post, read daily from Business Suite by the 8bit-bs-schedule task (data/learn/follows.jsonl)
FOL = {}
fp = OUT / "follows.jsonl"
if fp.exists():
    for line in fp.read_text().splitlines():
        try: d = json.loads(line); FOL[(d["account"], (d.get("caption_start") or "").upper().strip())] = d.get("follows")
        except Exception: pass
def fol_of(acc, title):   # caption starts match either way round (titles and caption_start can differ in length)
    t = (title or "").upper().strip()
    for (a, c), v in FOL.items():
        if a == acc and len(c) >= 8 and (t.startswith(c[:30]) or c.startswith(t[:30])): return v
    return None
scores, hours, base, lens = {}, {}, {}, {}
for acc in ("raptors", "warriors"):
    mine = [r for r in rows if r["acc"] == acc and r["permalink"] not in TRIAL]
    if not mine: continue
    eng = lambda r: ((r.get("shares") or 0) + (r.get("saves") or 0)) * 1000 / max(r["views"], 1)
    wat = lambda r: (r.get("avg_watch_s") or 0) / LEN[r["permalink"]] if LEN.get(r["permalink"]) else None
    mv, me = med([r["views"] for r in mine]) or 1, med([eng(r) for r in mine]) or 1
    mws = med([w for w in (wat(r) for r in mine) if w is not None]); mwa = med([(r.get("avg_watch_s") or 0) for r in mine]) or 1
    for r in mine:
        w = wat(r); wn = (w / mws) if (w is not None and mws) else ((r.get("avg_watch_s") or 0) / mwa)
        en = eng(r) / me
        if r["views"] < 300: en, wn = 1.0, min(wn, 1.0)   # rates on a tiny audience are noise (self-review 2026-11-23)
        r["_s"] = 0.30 * min(r["views"] / mv, 4) + 0.35 * min(en, 2.5) + 0.35 * min(wn, 2.5)
        f = fol_of(acc, r.get("title"))
        if f is not None: r["_f"] = f
    # once enough posts have follows, they become half the score (follows per 1K views vs the account median)
    withf = [r for r in mine if "_f" in r and r["views"] >= 300]
    if len(withf) >= 10:
        mf = med([r["_f"] * 1000 / r["views"] for r in withf]) or 0.5
        for r in withf: r["_s"] = 0.5 * r["_s"] + 0.5 * min((r["_f"] * 1000 / r["views"]) / mf, 3)
    base_f = len(withf)
    scores[acc] = grp(mine, lambda r: fmt(r["title"])); hours[acc] = grp(mine, hour_of)
    lens[acc] = grp(mine, lambda r: (lambda L: None if L is None else ("<25 s" if L < 25 else "25-35 s" if L < 35 else "35-45 s" if L < 45 else "45 s+"))(LEN.get(r["permalink"])))
    base[acc] = dict(median_views=int(mv), shares_saves_per_1k=round(me, 1), watched_share=round(mws or 0, 2), lengths_known=sum(1 for r in mine if LEN.get(r["permalink"])), posts=len(mine), posts_with_follows=base_f)


def shrunk(table, acc, k):
    v = table.get(acc, {}).get(k) or {}; n = v.get("n", 0)
    return (n * v.get("score", 1.0) + K) / (n + K)


# re-order the next 7 days
qp = ROOT / "data/api_queue.json"; q = json.loads(qp.read_text())
title_of = lambda j: (pathlib.Path(j["caption"]).read_text().split("\n")[0] if pathlib.Path(j["caption"]).exists() else "")
moves, depth = [], {}
for acc in ("raptors", "warriors"):
    lo, hi = now + dt.timedelta(hours=2), now + dt.timedelta(days=7)
    allq = [j for j in q if j["account"] == acc and j["state"] == "queued" and dt.datetime.fromisoformat(j["due_et"]) > now]
    depth[acc] = len({j["due_et"][:10] for j in allq if not j.get("trial")})
    js = [j for j in allq if lo <= dt.datetime.fromisoformat(j["due_et"]) <= hi and not j.get("trial")]
    if len(js) < 2: continue
    fixed = [dt.datetime.fromisoformat(j["due_et"]) for j in allq if j not in js]
    slots = sorted(dt.datetime.fromisoformat(j["due_et"]) for j in js); pool = [dict(j=j, f=fmt(title_of(j))) for j in js]
    tested = lambda f: (scores.get(acc, {}).get(f) or {}).get("n", 0)
    prev, plan = None, []
    for i, slot in enumerate(slots):
        cand = [c for c in pool if c["f"] != prev] or pool
        explore = i % 5 == 4
        pick = min(cand, key=lambda c: (tested(c["f"]), -shrunk(scores, acc, c["f"]))) if explore else max(cand, key=lambda c: shrunk(scores, acc, c["f"]))
        pool.remove(pick); prev = pick["f"]; plan.append([pick, slot, explore])
    # explore slots also test a new time: the least-tested :00/:30 within +-60 min, 12:00-22:30, 90+ min from every other post
    hn = lambda h: (hours.get(acc, {}).get(h) or {}).get("n", 0)
    for k, item in enumerate(plan):
        pick, t, explore = item
        if not explore: continue
        others = [x[1] for x in plan if x is not item] + fixed
        opts = [t + dt.timedelta(minutes=m) for m in (-60, -30, 30, 60)]
        opts = [o for o in opts if (12, 0) <= (o.hour, o.minute) <= (22, 30) and all(abs((o - x).total_seconds()) >= 90 * 60 for x in others)]
        if opts:
            best = min(opts, key=lambda o: hn(o.hour))
            if hn(best.hour) < hn(t.hour): item[1] = best
    # series stay in order (2026-11-27: Trade Court #3/#4 went out before #1/#2): numbered episodes of the same series
    # ("CASE #N", "PART N") swap times among themselves so the lower number always posts first
    SER = re.compile(r"^(.*?)(?:CASE|PART|EPISODE|EP\.?)\s*#?\s*(\d+)", re.I)
    groups = {}
    for item in plan:
        m = SER.match(title_of(item[0]["j"]).upper())
        if m: groups.setdefault(m.group(1).strip(" ,:-"), []).append((int(m.group(2)), item))
    for eps in groups.values():
        times = sorted(it[1] for _, it in eps)
        for (n, it), tm in zip(sorted(eps, key=lambda e: e[0]), times): it[1] = tm
    for pick, t, explore in plan:
        new = t.isoformat()
        if pick["j"]["due_et"] != new: moves.append((acc, pick["j"]["label"], pick["j"]["due_et"][5:16], new[5:16], pick["f"] + (" EXPLORE" if explore else "")))
        pick["j"]["_new"] = new
for j in q:
    if "_new" in j: j["due_et"] = j.pop("_new")
if not DRY and moves:
    (ROOT / "data/api_queue.json.bak_learn").write_text(qp.read_text()); qp.write_text(json.dumps(q, indent=1, ensure_ascii=False))

# trials: compare ..._xa vs ..._xb after 48 h
lab_of = {pl: pathlib.Path(f).stem for pl, f in FILE.items() if f}
tri = {}
for pl, r in latest.items():
    m = re.match(r"(.+)_x([ab])$", lab_of.get(pl, ""))
    if m: tri.setdefault(m.group(1), {})[m.group(2)] = r
tl = ["# Trial reels (non-followers only): hook A vs hook B", ""]
sc = lambda r: (r.get("views") or 0) * (1 + ((r.get("shares") or 0) + (r.get("saves") or 0)) * 10 / max(r.get("views") or 1, 1)) * (r.get("avg_watch_s") or 1)
for b0, d in sorted(tri.items()):
    if len(d) < 2: tl.append(f"- {b0}: waiting for both versions"); continue
    a, b = d["a"], d["b"]
    if min(a.get("age_h") or 0, b.get("age_h") or 0) < 48: tl.append(f"- {b0}: under 48 h, too early"); continue
    w = "A" if sc(a) >= sc(b) else "B"
    tl.append(f"- {b0}: WINNER {w} | A {a['views']} views, {a.get('avg_watch_s')} s, {a.get('shares', 0)} shares {a.get('saves', 0)} saves | "
              f"B {b['views']} views, {b.get('avg_watch_s')} s, {b.get('shares', 0)} shares {b.get('saves', 0)} saves")
if len(tl) == 2: tl.append("- no trials yet")
(OUT / "trials.md").write_text("\n".join(tl))

need = {a: d for a, d in depth.items() if d < MIN_DAYS[a]}
(OUT / "scores.json").write_text(json.dumps(dict(at=now.isoformat(timespec="minutes"), scores=scores, hours=hours, lengths=lens, baselines=base, queued_days=depth, refill=need), indent=1))
flag = OUT / "refill_needed"; flag.write_text(json.dumps(need)) if need else flag.unlink(missing_ok=True)
md = [f"# Learn {now:%a %b %d}", "", "Score = 30% views + 35% shares & saves per 1K views + 35% share of the reel watched (each vs the account median).", ""]
for acc, fs in scores.items():
    md += [f"## {acc} (queued days: {depth.get(acc)}; baselines {base[acc]})", "| format | posts | median views | score |", "|---|---|---|---|"]
    md += [f"| {f} | {v['n']} | {v['median_views']} | {v['score']} |" for f, v in sorted(fs.items(), key=lambda x: -x[1]["score"])]
    md += ["", "| hour | posts | median views | score |", "|---|---|---|---|"]
    md += [f"| {h}:00 | {v['n']} | {v['median_views']} | {v['score']} |" for h, v in sorted(hours[acc].items())]
    md += ["", "| length | posts | median views | score |", "|---|---|---|---|"] + [f"| {k} | {v['n']} | {v['median_views']} | {v['score']} |" for k, v in sorted(lens[acc].items())] + [""]
md += ["## Queue moves" + (" (dry run)" if DRY else ""), *([f"- {a} {l}: {o} -> {n} ({f})" for a, l, o, n, f in moves] or ["- none"]), "",
       f"Refill needed: {need or 'no'}", "", "Trials: see trials.md"]
(OUT / f"{now.date()}.md").write_text("\n".join(md)); (OUT / "latest.md").write_text("\n".join(md)); print("\n".join(md))
