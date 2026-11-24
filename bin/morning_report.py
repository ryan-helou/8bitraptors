#!/usr/bin/env python3
"""Morning report: yesterday's posts on both accounts, what won, what to post more of. Sent to Ryan at 9 AM (launchd
com.8bitraptors.morning). Full table -> data/reports/<date>.md; a short version goes out through bin/notify.py.
usage: python3 bin/morning_report.py [--no-send]
"""
import os, sys, json, subprocess, pathlib, datetime as dt, statistics as stx
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "bin"))
from notify import notify

import datetime as _d
if (ROOT / "data/reports" / f"{_d.datetime.now(_d.timezone(_d.timedelta(hours=-5))).date()}.md").exists() and "--again" not in sys.argv: sys.exit(0)
subprocess.run([sys.executable, "-I", str(ROOT / "bin/insights.py")], cwd=str(ROOT), capture_output=True, timeout=900)
snap = max((ROOT / "data/insights").glob("*.json"), key=lambda p: p.stat().st_mtime)
rows = json.loads(snap.read_text())
ET = dt.timezone(dt.timedelta(hours=-5)); now = dt.datetime.now(ET); yday = (now - dt.timedelta(days=1)).date()
if (ROOT / "data/reports" / f"{now.date()}.md").exists() and "--again" not in sys.argv: sys.exit(0)   # extra launchd times are retries


def kind(title):
    t = title.upper()
    if "CHOOSE YOUR STARTER" in t: return "poll"
    if t.startswith(("VICTORY", "FINAL", "GYM", "WIN", "LOSS", "W ", "L ")): return "recap"
    if "GAMES IN" in t: return "games-in"
    if t.startswith(("PARTY CHECK", "STARTING FIVE", "WHAT?", "NEW HIGH SCORE")): return "game-day"
    return "story"


# followers history so the report can say +N
fh = ROOT / "data/followers.json"; hist = json.loads(fh.read_text()) if fh.exists() else {}
cf = ROOT / "data/caps.json"; CAPS = {"warriors": 2, **(json.loads(cf.read_text()) if cf.exists() else {})}
lines_md = [f"# 8bit morning report, {now:%a %b %d}", ""]; short = []
for acc in ("raptors", "warriors"):
    mine = [r for r in rows if r["acc"] == acc]
    if not mine: continue
    fol = mine[0].get("followers"); prev = next((v for d_, v in sorted(hist.get(acc, {}).items(), reverse=True) if d_ < str(now.date())), None)
    hist.setdefault(acc, {})[str(now.date())] = fol
    # posts made yesterday (ET); their numbers are 9-33h old, a fair comparison
    yd = [r for r in mine if r["age_h"] is not None and (now - dt.timedelta(hours=r["age_h"])).date() == yday]
    allr = [r for r in mine if (r.get("views") or 0) > 0 and (r["age_h"] or 0) >= 12]   # fresh posts are still climbing; leave them out
    med = stx.median([r["views"] for r in allr]) if allr else 0
    by = {}
    for r in allr: by.setdefault(kind(r["title"]), []).append(r["views"] or 0)
    kinds = sorted(((k, stx.median(v), len(v)) for k, v in by.items() if len(v) >= 2), key=lambda x: -x[1])   # 1 post is not a pattern
    lines_md += [f"## @8bit{acc}: {fol} followers ({'+' if prev is not None and fol - prev >= 0 else ''}{fol - prev if prev is not None else '?'} since last report)", ""]
    lines_md += ["| posted | title | views | avg watch | likes | comments | shares |", "|---|---|---|---|---|---|---|"]
    for r in sorted(yd, key=lambda r: -(r["views"] or 0)):
        lines_md.append(f"| {r['posted']} | {r['title']} | {r['views']} | {r['avg_watch_s']}s | {r['likes']} | {r['comments']} | {r['shares']} |")
    lines_md += ["", "Median views by format (posts 12h+ old, 2+ posts each): " + ", ".join(f"{k} {int(m)} ({n})" for k, m, n in kinds), ""]
    if yd:
        best = max(yd, key=lambda r: r["views"] or 0); worst = min(yd, key=lambda r: r["views"] or 0)
        short.append(f"@8bit{acc}: {fol} followers ({'+' if prev is not None and fol - prev >= 0 else ''}{fol - prev if prev is not None else '?'}). "
                     f"{len(yd)} posts yesterday, {sum(r['views'] or 0 for r in yd)} views. Best: {best['title'][:30]} ({best['views']}, {best['avg_watch_s']}s watch). "
                     f"Weakest: {worst['title'][:30]} ({worst['views']}).")
    else:
        short.append(f"@8bit{acc}: {fol} followers. No posts yesterday.")
    # Strategy v2: reach is a gate. Pushed = shown to strangers (800+ views after 12h); a miss is a slot/trust problem.
    yd_ok = [r for r in yd if (r["age_h"] or 0) >= 12 and "recap" != kind(r["title"])]
    pushed = [r for r in yd_ok if (r["views"] or 0) >= 800]; missed = [r for r in yd_ok if (r["views"] or 0) < 800]
    if yd_ok:
        line = f"  Pushed {len(pushed)}/{len(yd_ok)}" + (": missed " + ", ".join(f"{r['title'][:22]} at {r['posted'][4:]} ({r['views']})" for r in missed) if missed else ".")
        short.append(line); lines_md += [f"**Pushed:** {len(pushed)} of {len(yd_ok)} non-recap posts reached strangers (800+ views).", ""]
    if acc in CAPS and yd_ok:
        CAPS[acc] = 3 if (len(yd_ok) >= 2 and not missed) else 2
        _man = ROOT / "data/caps_manual.json"   # Ryan's explicit override (2026-11-12: Warriors 5/day) beats the adaptive cap
        if _man.exists(): CAPS[acc] = max(CAPS[acc], int(json.loads(_man.read_text()).get(acc, 0)))
        short.append(f"  Daily cap today: {CAPS[acc]}" + (" (every post got pushed yesterday)" if CAPS[acc] > 2 else ""))
    if len(kinds) < 2: short.append("  Not enough posts per format yet to call a winner.")
    if len(kinds) >= 2:
        top = kinds[0]; low = kinds[-1]
        tip = f"Post more {top[0]} (median {int(top[1])} views)" + (f", fewer {low[0]} ({int(low[1])})." if len(kinds) > 1 and low[0] != top[0] else ".")
        short.append("  " + tip); lines_md += [f"**Next:** {tip}", ""]
fh.write_text(json.dumps(hist, indent=1)); cf.write_text(json.dumps(CAPS))
(ROOT / "data/reports").mkdir(parents=True, exist_ok=True)
rep = ROOT / f"data/reports/{now.date()}.md"; rep.write_text("\n".join(lines_md))
msg = "\n".join(short) + f"\nFull table: {rep.relative_to(ROOT)}"
print(msg)
if "--no-send" not in sys.argv: notify("morning report", msg)

# Self-improving loop, daily half (2026-11-23): score formats, re-order the next 7 days, flag a refill. No Claude tokens.
try: subprocess.run([sys.executable, "-I", str(ROOT / "bin/learn.py")], cwd=str(ROOT), capture_output=True, timeout=300)
except Exception as e: print("learn.py failed:", e)
# Self-check (2026-11-23): notify Ryan only if a part of the system is failing.
try: subprocess.run([sys.executable, "-I", str(ROOT / "bin/health.py")], cwd=str(ROOT), capture_output=True, timeout=300)
except Exception as e: print("health.py failed:", e)
# Mondays: refresh what works for other NBA fan pages (data/learn/fanpages.md) before the Tuesday refill.
if True:   # daily (Ryan 2026-11-24: why not more often? free, no tokens)
    try: subprocess.run([sys.executable, "-I", str(ROOT / "bin/fanpages.py")], cwd=str(ROOT), capture_output=True, timeout=300)
    except Exception as e: print("fanpages.py failed:", e)
# Push the re-ordered queue to the cloud right away, before the Mac can go back to sleep (2026-11-24).
try: subprocess.run([sys.executable, "-I", str(ROOT / "bin/cloud_sync.py")], cwd=str(ROOT), capture_output=True, timeout=900)
except Exception as e: print("cloud_sync failed:", e)
# Daily backup of the whole project to GitHub (2026-11-24).
try: subprocess.run(["/bin/zsh", str(ROOT / "bin/backup.sh")], cwd=str(ROOT), capture_output=True, timeout=600)
except Exception as e: print("backup failed:", e)
