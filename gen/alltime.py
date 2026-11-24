"""'Choose your starter' poll (our best format) with hand-picked players: all-time, rookies, what-ifs.

usage: python3 gen/alltime.py specs/<name>.json  -> out/<team>_<name>.mp4 + .caption.txt
Spec: {"team": "raptors", "name": "alltime", "l1": "...", "q": "...", "boxA": "...", "boxB": "...", "rest": "...", "caption": "...",
       "cands": [{"id": "1713", "name": "VINCE", "full": "VINCE CARTER", "jersey": "15", "type": "HIGH-FLYER",
                  "season": "RAPTORS 1998-2004", "stats": [["23.4", "PPG"], ["5X", "ALL-STAR"], ["2000", "DUNK CHAMP"]]}, ...]}
Every stat in a spec must be checked before it is built.
"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build as B

spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
slug, name = spec["team"], spec["name"]
tid, team, assets = B.common(slug)
colors = ["#b3283f", "#2a5ab3", "#2a8a4a"]; cands = []
for i, c in enumerate(spec["cands"]):
    k = c["id"] + c.get("team", "")
    if c.get("team"): assets["p_" + k], assets["h_" + k] = B.sprite_team(c["id"], c["team"])
    else: assets["p_" + k] = B.sprite_player(c["id"]); assets["h_" + k] = B.sprite_hi(c["id"])
    cands.append({"key": "p_" + k, "name": c["name"], "full": c["full"], "first": c["name"], "jersey": c["jersey"], "type": c["type"], "color": colors[i],
                  "stats": c["stats"], "season": c.get("season", ""), "fullc": c["full"].title()})
opp = {"abbr": team["abbr"], "name": team["name"], "short": team["short"], "logo": team["logo"], "color": "#2a3040"}
data = {"team": team, "opp": opp, "game": {"vs": "", "when": "", "when_c": "", "venue": "", "home": True}, "restName": "", "assets": assets,
        "starter": {"season": "", "out": "", "l1": spec["l1"], "q": spec["q"], "boxA": spec["boxA"], "boxB": spec["boxB"], "rest": spec.get("rest", ""), "cands": cands}}
sp, tot = B.spans([("lab", 2.4), ("pk0", 1.0), ("cq", 2.6), ("pk1", 1.0), ("cw", 2.6), ("pk2", 1.0), ("ch", 2.6), ("pick", 3.4), ("end", 2.2)])
mp4 = B.render(slug, name, data, sp, tot)
(B.OUT / f"{slug}_{name}.caption.txt").write_text(spec["caption"].strip() + f"\n\n#NBA {B.HASH.get(slug, '')} #Basketball #NBAHistory")
print(mp4)
