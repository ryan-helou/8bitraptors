"""Fact check for hand-written specs: every number a viewer sees must be backed by ESPN data or a cited source.

A spec lists its facts:
  "facts": [
    {"player": "3149673", "season": "2018-19", "stat": "PTS", "value": 16.9},             # ESPN regular-season average
    {"player": "3149673", "season": "2018-19", "stat": "PTS", "value": 19.0, "type": "playoffs"},
    {"game": "401131766", "score": "118-109"},                                          # ESPN final score
    {"game": "401131766", "player": "3149673", "stat": "PTS", "value": 32},              # ESPN box score line
    {"game": "401131766", "player": "3149673", "stat": "FG", "value": "14-17"},
    {"claim": "Siakam drafted 27th in 2016", "source": "https://..."}                     # anything else: cite it
    {"sim": "data/sim/raptors_2026-11-18.json", "path": "outputs.rings.at_least_one_pct", "value": 24.2,
     "said": "24% ... about 1 in 4"}                                                       # fan-sim output (gen/sim_era.py)
  ]
Checks: (1) each automatic fact matches ESPN, (2) each claim has an https source, (3) every number shown on screen
(dialogue, poll text, poll stats) or in the caption appears in some fact.
usage: python3 gen/factcheck.py specs/<name>.json      exit 1 on any problem
"""
import sys, re, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import espn

WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
_cache = {}


def _get(u):
    if u not in _cache: _cache[u] = espn.get(u)
    return _cache[u]


def season_avg(pid, season, stat, kind="regular"):
    d = _get(f"{WEB}/athletes/{pid}/stats?seasontype={3 if kind == 'playoffs' else 2}")
    for c in d.get("categories", []):
        if c.get("name") != "averages": continue
        lab = c["labels"]
        for s in c.get("statistics", []):
            if s.get("season", {}).get("displayName") == season:
                return dict(zip(lab, s["stats"])).get(stat)
    return None


def game_line(gid, pid, stat):
    for t in espn.boxscore(gid)["teams"].values():
        for r in t["rows"]:
            if str(r["id"]) == str(pid): return r.get(stat)
    return None


def game_score(gid):
    comp = espn.boxscore(gid)["competitors"]
    return sorted((int(c["score"]) for c in comp.values()), reverse=True)


def nums(s):
    """Numbers as a viewer reads them: 16.9, 14-OF-17 -> 14 and 17, 2,974 -> 2974, 2016-17 -> 2016 and 17."""
    s = re.sub(r"#[0-9a-fA-F]{6}\b", "", s or "")          # colours are not facts
    s = re.sub(r"\d\ufe0f?\u20e3", "", s)                  # 1️⃣ 2️⃣ 3️⃣ poll option markers
    s = re.sub(r"(?i)comment\s+\d(?:\s*,\s*\d)*\s*(?:,?\s*or\s+\d)?", "", s)   # "Comment 1, 2 or 3"
    s = re.sub(r"(?i)(?:case|court)\s*#?\s*\d+", "", s)                # series episode label "CASE #3"
    s = re.sub(r"(\d),(\d{3})", r"\1\2", s)
    return set(re.findall(r"\d+(?:\.\d+)?", s))


def check(spec_path):
    spec = json.loads(pathlib.Path(spec_path).read_text()); facts = spec.get("facts")
    if not facts: return ["no \"facts\" list: every number in the reel needs a fact"]
    probs, covered = [], set()
    for f in facts:
        try:
            if "claim" in f:
                if not str(f.get("source", "")).startswith("https://"): probs.append(f"claim has no https source: {f['claim']!r}")
                covered |= nums(f["claim"])
            elif "game" in f and "score" in f:
                want = sorted((int(x) for x in re.findall(r"\d+", f["score"])), reverse=True); got = game_score(f["game"])
                if want != got: probs.append(f"game {f['game']}: score {f['score']} but ESPN has {'-'.join(map(str, got))}")
                covered |= nums(f["score"])
            elif "game" in f:
                got = game_line(f["game"], f["player"], f["stat"])
                if str(got) != str(f["value"]): probs.append(f"game {f['game']} player {f['player']} {f['stat']}: spec {f['value']} but ESPN has {got}")
                covered |= nums(str(f["value"]))
            elif "sim" in f:
                got = json.loads((pathlib.Path(__file__).resolve().parent.parent / f["sim"]).read_text())
                for k in f["path"].split("."): got = got[int(k)] if isinstance(got, list) else got[k]
                ok = abs(float(got) - float(f["value"])) < 1e-9 if isinstance(got, (int, float)) and not isinstance(got, bool) else got == f["value"]
                if not ok: probs.append(f"sim {f['sim']} {f['path']}: spec {f['value']!r} but the file has {got!r}")
                covered |= nums(str(f["value"])) | nums(f.get("said", ""))
            elif "season" in f:
                got = season_avg(f["player"], f["season"], f["stat"], f.get("type", "regular"))
                if got is None or abs(float(got) - float(f["value"])) > 0.051: probs.append(f"player {f['player']} {f['season']} {f.get('type', 'regular')} {f['stat']}: spec {f['value']} but ESPN has {got}")
                covered |= nums(str(f["value"])) | nums(f["season"])
            else: probs.append(f"unknown fact shape: {f}")
        except Exception as e:
            probs.append(f"could not check {f}: {e}")
    shown = []
    for i, b in enumerate(spec.get("beats", [])):
        shown += [(f"beat {i}", json.dumps({k: v for k, v in b.items() if k not in ("vo", "kind", "sel", "i", "first", "stat", "hold") and not str(v).startswith(("p:", "l:", "auto:"))}))]
    for k_, c in enumerate(spec.get("party", [])):
        shown += [(f"party {k_}", json.dumps({k: c.get(k) for k in ("nick", "label", "stat")}))]
    for c in spec.get("cands", []):
        shown += [(f"cand {c.get('name')}", json.dumps({k: c.get(k) for k in ("season", "stats", "type", "jersey")}))]
    shown += [("poll text", " ".join(str(spec.get(k, "")) for k in ("l1", "q", "boxA", "boxB", "rest"))), ("caption", spec.get("caption", ""))]
    for where, txt in shown:
        miss = sorted(n for n in nums(txt) if n not in covered and n.lstrip("0") not in covered)
        if miss: probs.append(f"{where}: numbers with no fact behind them: {', '.join(miss)}")
    return probs


if __name__ == "__main__":
    p = check(sys.argv[1])
    print("\n".join(p) or "facts OK")
    sys.exit(1 if p else 0)
