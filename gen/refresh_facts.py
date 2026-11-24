"""Refresh a spec's current-season stat facts to ESPN's current values (2026-11-14).
usage: python3 gen/refresh_facts.py specs/X.json [--write]
Prints each stale fact (old -> new) and every caption/beat/cand line that still carries the old value or game count,
so the text can be updated with exact replacements. With --write, only the fact values themselves are updated."""
import json, sys, re, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import factcheck as F
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text()); stale = []
for f in d.get("facts", []):
    if "player" in f and "season" in f and "game" not in f:
        got = F.season_avg(f["player"], f["season"], f["stat"], f.get("type", "regular"))
        if got is not None and abs(float(got) - float(f["value"])) > 0.051:
            stale.append((f["player"], f["stat"], f["value"], got)); f["value"] = int(float(got)) if f["stat"] == "GP" else float(got)
txt = json.dumps({k: v for k, v in d.items() if k != "facts"}, ensure_ascii=False, indent=1).split("\n")
for pid, st, old, new in stale:
    print(f"{pid} {st}: {old} -> {new}")
    pat = re.compile(rf"(?<![\d.]){re.escape(str(old))}(?![\d])")
    for l in txt:
        if pat.search(l): print("    ", l.strip()[:170])
if "--write" in sys.argv: p.write_text(json.dumps(d, indent=1, ensure_ascii=False)); print("facts updated")
