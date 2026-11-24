"""Narrated history / feature reels (Wolves' narrated story format) from a hand-written spec.

usage: python3 gen/history.py specs/<name>.json   -> out/<team>_<name>.mp4 + .caption.txt

Spec: {"team": "raptors", "name": "run2019", "record": "58-24", "caption": "...",
       "beats": [{"kind": "fire", "head": "...", "vo": "...", "dlg": "LINE 1|LINE 2", ...}, ...]}
Beat kinds are the story kinds in reel_t.html (trainer, fire, gym, bat, final, next, hot, step, log, center).
References inside a beat: any value "p:<espn athlete id>" becomes a player sprite, "l:<ABBR>" a team logo,
and "ocol": "auto:<ABBR>" the team's colour. Every fact in a spec must be checked before it is built.
"""
import json, sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build as B
import espn

spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
slug, name = spec["team"], spec["name"]
tid, team, assets = B.common(slug)
if spec.get("record"): team["record"] = spec["record"]


def resolve(v):
    if isinstance(v, str) and v.startswith("p:"):
        pid, _, tm = v[2:].partition("@")
        if tm: k = f"{pid}{tm}"; assets["p_" + k], assets["h_" + k] = B.sprite_team(pid, tm); return "p_" + k
        assets["p_" + pid] = B.sprite_player(pid); assets["h_" + pid] = B.sprite_hi(pid); return "p_" + pid
    if isinstance(v, str) and v.startswith("pk:"):   # PMD Sprite Collab monster (gen/pmd.py), credited in the caption
        import pmd
        n = v[3:].lower(); im = pmd.get(n); assets["m_" + n] = B.enc(im); return "m_" + n
    if isinstance(v, str) and v.startswith("m:"):   # original pixel monster from assets/monsters (gen/monsters.py)
        from PIL import Image as _I
        n = v[2:]; assets["m_" + n] = B.enc(_I.open(B.ROOT / "assets/monsters" / f"{n}.png").convert("RGBA")); return "m_" + n
    if isinstance(v, str) and v.startswith("l:"):
        ab = v[2:]; assets["l_" + ab] = B.sprite_logo(ab); return "l_" + ab
    if isinstance(v, str) and v.startswith("auto:"): return B.opp_color(v[5:])
    if isinstance(v, list): return [resolve(x) for x in v]
    if isinstance(v, dict): return {k: resolve(x) for k, x in v.items()}
    return v


beats = [resolve(b) for b in spec["beats"]]
vod = B.OUT / f"{slug}_{name}_vo"; lines = [{"id": f"b{i}", "text": b["vo"]} for i, b in enumerate(beats)]
lj = B.OUT / f"{slug}_{name}_vo_lines.json"; lj.write_text(json.dumps(lines))
durs = json.loads(subprocess.run([str(B.ROOT / ".venv/bin/python"), str(B.ROOT / "gen/tts.py"), str(lj), str(vod)], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
sp, vo, t = [], [], 0.0
for i, bt in enumerate(beats):
    d = durs[f"b{i}"]; bt["dur"] = d; vo.append({"t": round(t + .15, 3), "wav": str(vod / f"b{i}.wav")})
    sp.append({"scene": f"st{i}", "start": round(t, 3), "end": round(t + d + .35, 3)}); t += d + .35
total = round(t + .6, 3); sp[-1]["end"] = total
data = {"team": team, "opp": {"abbr": team["abbr"], "short": team["short"], "logo": team["logo"], "color": "#444"}, "game": {}, "assets": assets, "story": {"beats": beats}}
mp4 = B.render(slug, name, data, sp, total, vo)
(B.OUT / f"{slug}_{name}.caption.txt").write_text(spec["caption"].strip() + f"\n\n#NBA {B.HASH.get(slug, '')} #Basketball #NBAHistory")
print(mp4)
