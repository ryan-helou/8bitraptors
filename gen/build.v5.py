#!/usr/bin/env python3
"""python3 gen/build.py <party|starter|recap> <team> [event_id]  -> out/<team>_<kind>.mp4 + .caption.txt  (music-only reels, safe-zone layout)"""
import sys, os, io, json, base64, subprocess, urllib.request, pathlib, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
import espn
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"; OUT = ROOT / "out"; CACHE.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
HANDLE = {"raptors": "8bitraptors", "warriors": "8bitwarriors"}
MOVE = {"raptors": "ROAR", "warriors": "SPLASH"}
HASH = {"raptors": "#Raptors #WeTheNorth #Toronto", "warriors": "#Warriors #DubNation #GoldBloodedFamily"}

def fetch(url, path):
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
    return path

def enc(im):
    b = io.BytesIO(); im.save(b, "PNG"); return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

def pix(im, n, colors):
    im = im.convert("RGBA"); a = im.getchannel("A").resize((n, n), Image.LANCZOS).point(lambda v: 255 if v > 110 else 0)
    q = im.resize((n, n), Image.LANCZOS).convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE).convert("RGBA"); q.putalpha(a); return q

def sprite_player(aid):
    p = CACHE / f"p64_{aid}.json"
    if p.exists(): return json.loads(p.read_text())
    raw = fetch(f"https://a.espncdn.com/i/headshots/nba/players/full/{aid}.png", CACHE / f"raw_p_{aid}.png")
    im = Image.open(raw).convert("RGBA"); im = im.crop(im.getchannel("A").getbbox()); w, h = im.size; s = min(w, h); l = (w - s) // 2
    d = enc(pix(im.crop((l, 0, l + s, s)), 56, 64)); p.write_text(json.dumps(d)); return d

def sprite_hi(aid):
    """Sharper headshot for big slots (cards, hook, player of the game): 96 px, 64 colours."""
    p = CACHE / f"h112_{aid}.json"
    if p.exists(): return json.loads(p.read_text())
    sprite_player(aid); raw = CACHE / f"raw_p_{aid}.png"
    im = Image.open(raw).convert("RGBA"); im = im.crop(im.getchannel("A").getbbox()); w, h = im.size; s = min(w, h); l = (w - s) // 2
    d = enc(pix(im.crop((l, 0, l + s, s)), 112, 200)); p.write_text(json.dumps(d)); return d

NICK = json.loads((ROOT / "gen/names.json").read_text())

def nick(p):
    """What fans call the player (Wolves uses ANT, MELO, JK, AYO); first name if we have no nickname."""
    if p["name"] in NICK: return NICK[p["name"]]
    first = p["name"].split()[0].upper()
    return first if len(first) <= 9 else p["last"].upper()

def best_stat(p):
    """The stat that makes the player look best, like Wolves (6.3 APG for a passer, 14.3 RPG for a big)."""
    opts = [(p["ppg"] / 15, f"{p['ppg']:.1f} PPG"), (p["rpg"] / 7, f"{p['rpg']:.1f} RPG"), (p["apg"] / 5, f"{p['apg']:.1f} APG")]
    return max(opts)[1]

def card_type(cands):
    """Give each candidate a distinct Wolves-style type and the three stats that fit it."""
    def scores(p):
        ok3 = p["min"] >= 18 and 25 <= p["p3"] <= 55
        return {"SCORER": p["ppg"] / 18, "PLAYMAKER": p["apg"] / 6, "DEFENDER": (p["spg"] + p["bpg"]) / 2.2,
                "SLASHER": (p["fg"] - 44) / 8 if p["fg"] >= 47 and p["ppg"] >= 8 else 0,
                "SHOOTER": (p["p3"] - 33) / 6 if ok3 else 0, "REBOUNDER": p["rpg"] / 9}
    out, taken = {}, set()
    for p in sorted(cands, key=lambda p: -max(scores(p).values())):
        t = next(k for k, _ in sorted(scores(p).items(), key=lambda kv: -kv[1]) if k not in taken); taken.add(t); out[p["id"]] = t
    f1 = lambda v: f"{v:.1f}"
    stats = {"SCORER": lambda p: [[f1(p["ppg"]), "PPG"], [f1(p["fg"]), "FG%"], [f1(p["min"]), "MIN"]],
             "SLASHER": lambda p: [[f1(p["ppg"]), "PPG"], [f1(p["fg"]), "FG%"], [f1(p["rpg"]), "REB"]],
             "PLAYMAKER": lambda p: [[f1(p["ppg"]), "PPG"], [f1(p["apg"]), "AST"], [f1(p["min"]), "MIN"]],
             "DEFENDER": lambda p: [[str(p["gp"]), "GAMES"], [f1(p["spg"]), "STL"], [f1(p["min"]), "MIN"]],
             "SHOOTER": lambda p: [[f1(p["ppg"]), "PPG"], [f1(p["p3"]), "3P%"], [f1(p["min"]), "MIN"]],
             "REBOUNDER": lambda p: [[f1(p["ppg"]), "PPG"], [f1(p["rpg"]), "REB"], [f1(p["min"]), "MIN"]]}
    return {pid: (t, stats[t](next(p for p in cands if p["id"] == pid))) for pid, t in out.items()}

def season_label():
    n = dt.datetime.now(); y = n.year if n.month >= 9 else n.year - 1
    return f"{y}-{(y + 1) % 100:02d}"

def sprite_logo_hi(abbr):
    p = CACHE / f"l128_{abbr}.json"
    if p.exists(): return json.loads(p.read_text())
    sprite_logo(abbr); im = Image.open(CACHE / f"raw_l_{abbr}.png").convert("RGBA"); im = im.crop(im.getchannel("A").getbbox()); w, h = im.size; s = max(w, h)
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0)); sq.paste(im, ((s - w) // 2, (s - h) // 2))
    d = enc(pix(sq, 128, 96)); p.write_text(json.dumps(d)); return d

def sprite_logo(abbr):
    p = CACHE / f"l64_{abbr}.json"
    if p.exists(): return json.loads(p.read_text())
    raw = fetch(f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr.lower()}.png", CACHE / f"raw_l_{abbr}.png")
    im = Image.open(raw).convert("RGBA"); im = im.crop(im.getchannel("A").getbbox()); w, h = im.size; s = max(w, h)
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0)); sq.paste(im, ((s - w) // 2, (s - h) // 2))
    d = enc(pix(sq, 64, 40)); p.write_text(json.dumps(d)); return d

def common(slug):
    tid = espn.TEAMS[slug]; team = espn.team_info(tid); team["logo"] = "l_" + team["abbr"]; assets = {"l_" + team["abbr"]: sprite_logo(team["abbr"])}
    return tid, team, assets

def opp_color(abbr):
    try:
        t = espn.get(f"{espn.SITE}/teams/{abbr.lower()}")["team"]; c, a = "#" + t.get("color", "2a4a8a"), "#" + t.get("alternateColor", "2a4a8a")
        lum = lambda h: .299 * int(h[1:3], 16) + .587 * int(h[3:5], 16) + .114 * int(h[5:7], 16)
        return c if lum(c) > 30 else a
    except Exception: return "#2a4a8a"

def next_game(tid, team, slug):
    nxt = next(e for e in espn.schedule(tid) if e["state"] == "pre"); day, tm = espn.when(nxt["date"])
    today = dt.datetime.now(espn.ET).strftime("%a %-m/%-d")
    when = ("TONIGHT " if day == today else day.upper() + " * ") + tm + " ET"; when_c = ("Tonight " if day == today else day + " ") + tm + " ET"
    opp = {"abbr": nxt["opp_abbr"], "name": nxt["opp_name"], "short": nxt["opp_short"], "logo": "l_" + nxt["opp_abbr"]}
    opp["color"] = opp_color(opp["abbr"])
    try: opp["record"] = espn.get(f"{espn.SITE}/teams/{opp['abbr'].lower()}")["team"]["record"]["items"][0]["summary"]
    except Exception: opp["record"] = ""
    return nxt, opp, {"venue": (nxt.get("venue") or "").upper(), "when": when, "when_c": when_c, "vs": ("VS " if nxt["home"] else "@ ") + opp["short"].upper(), "home": nxt["home"], "day": day, "tm": tm}

def spans(items):
    t = 0; out = []
    for name, d in items: out.append({"scene": name, "start": t, "end": t + d}); t += d
    return out, t

def render(slug, kind, data, sp, total):
    data["spans"] = sp; data["total"] = total; data["handle"] = HANDLE[slug]
    for k in [k for k in data["assets"] if k.startswith("l_")]: data["assets"]["H" + k] = sprite_logo_hi(k[2:])
    tl = OUT / f"{slug}_{kind}.timeline.json"; tl.write_text(json.dumps({"lines": [], "spans": sp, "total": total}))
    dj = OUT / f"{slug}_{kind}.data.json"; dj.write_text(json.dumps(data))
    wav = OUT / f"{slug}_{kind}.wav"
    frames = ROOT / "cache" / f"frames_{slug}_{kind}"; subprocess.run(["rm", "-rf", str(frames)]); frames.mkdir(parents=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
        pg = b.new_page(viewport={"width": 540, "height": 960}); pg.goto("file://" + str(ROOT / "gen/reel_t.html")); pg.evaluate("d=>setData(d)", data)
        tl.write_text(json.dumps({"spans": sp, "total": total, "events": pg.evaluate("EVENTS()")}))
        subprocess.run([sys.executable, "-I", str(ROOT / "gen/audio.py"), str(tl), str(wav)], check=True, stdout=subprocess.DEVNULL)
        for i in range(int(total * 30)):
            u = pg.evaluate(f'render({i/30});document.getElementById("c").toDataURL("image/png")'); (frames / f"f{i:05d}.png").write_bytes(base64.b64decode(u.split(",")[1]))
        b.close()
    mp4 = OUT / f"{slug}_{kind}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", str(frames / "f%05d.png"), "-i", str(wav), "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "44100", "-c:a", "aac", "-b:a", "160k", "-shortest", str(mp4)], check=True)
    subprocess.run(["rm", "-rf", str(frames)]); return mp4

def party(slug):
    tid, team, assets = common(slug); R = espn.roster(tid); nxt, opp, game = next_game(tid, team, slug); assets[opp["logo"]] = sprite_logo(opp["abbr"])
    R = [p for p in R if p["gp"] > 0 or p["out"]]; outs = sorted([p for p in R if p["out"] and p["ppg"] > 0], key=lambda p: -p["ppg"])[:2]; ins = sorted([p for p in R if not p["out"]], key=lambda p: -p["ppg"])
    pick = (outs + ins)[:6]; party = []
    for p in pick: assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"]); party.append({"key": "p_" + p["id"], "name": nick(p)[:13], "full": p["name"], "lv": p.get("jersey") or "", "stat": best_stat(p), "out": p["out"]})
    rest = nick(outs[0]) if outs else "EVERYBODY"
    star = outs[0] if outs else ins[0]; assets["p_" + star["id"]] = sprite_player(star["id"]); assets["h_" + star["id"]] = sprite_hi(star["id"])
    hook = {"key": "p_" + star["id"], "stamp": "OUT" if outs else "HOT", "color": "red" if outs else "gold", "line1": (star["last"].upper() + (" IS OUT" if outs else " IS HOT")), "line2": "WHO'S READY?" if outs else "WHO'S NEXT?"}
    data = {"team": team, "opp": opp, "game": game, "party": party, "restName": rest, "move": MOVE.get(slug, "ATTACK"), "assets": assets, "hook": hook}
    sp, tot = spans([("party", 4.6), ("battle", 6.6), ("end", 2.4)]); mp4 = render(slug, "party", data, sp, tot)
    lines = "\n".join(f"{'😴' if p['out'] else '🟢'} {p['full']}: {p['stat']}{' (resting)' if p['out'] else ''}" for p in party)
    cap = f"PARTY CHECK 🎮🏀 {outs[0]['name'] if outs else 'Everybody'} is resting up. The rest of the pack is READY.\n\n{lines}\n\nA wild {opp['short'].upper()} appeared!\n\n🆚 {team['short']} {'vs' if game['home'] else '@'} {opp['short']}\n⏰ {game['when_c']}\n{team['short']} {team['record']}\n\nWho steps up? 👇\n\n#NBA {HASH.get(slug,'')} #Basketball"
    (OUT / f"{slug}_party.caption.txt").write_text(cap); return mp4

def starter(slug):
    tid, team, assets = common(slug); R = espn.roster(tid); nxt, opp, game = next_game(tid, team, slug)
    R = [p for p in R if p["gp"] > 0]; outs = sorted([p for p in R if p["out"]], key=lambda p: -p["ppg"]); ins = sorted([p for p in R if not p["out"]], key=lambda p: -p["ppg"])
    grp = lambda p: "CENTER" if p.get("pos") == "C" else "GUARD" if "G" in (p.get("pos") or "") else "FORWARD"
    same = [p for p in ins if outs and grp(p) == grp(outs[0])]
    c3 = same[:3] if len(same) >= 3 else ins[1:4]; q = f"WHICH {grp(outs[0])} STEPS UP?" if outs and len(same) >= 3 else "WHO STEPS UP?"
    TS = card_type(c3)
    colors = ["#b3283f", "#2a5ab3", "#2a8a4a"]; cands = []
    for i, p in enumerate(c3):
        assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"])
        cands.append({"key": "p_" + p["id"], "name": nick(p), "full": p["name"].upper(), "first": nick(p), "jersey": p["jersey"], "type": TS[p["id"]][0], "color": colors[i],
                      "stats": TS[p["id"]][1], "fullc": p["name"]})
    out = nick(outs[0]) if outs else "THE STAR"
    star = outs[0] if outs else ins[0]; assets["p_" + star["id"]] = sprite_player(star["id"]); assets["h_" + star["id"]] = sprite_hi(star["id"])
    hook = {"key": "p_" + star["id"], "stamp": "OUT" if outs else "HOT", "color": "red" if outs else "gold", "line1": star["last"].upper() + (" IS OUT" if outs else " IS HOT"), "line2": "WHO STEPS UP?"}
    assets[opp["logo"]] = sprite_logo(opp["abbr"]); data = {"team": team, "opp": opp, "game": game, "restName": out, "assets": assets, "hook": hook, "starter": {"season": season_label(), "out": out, "q": q, "cands": cands}}
    sp, tot = spans([("lab", 2.4), ("pk0", 1.0), ("cq", 2.6), ("pk1", 1.0), ("cw", 2.6), ("pk2", 1.0), ("ch", 2.6), ("pick", 3.4), ("end", 2.2)]); mp4 = render(slug, "starter", data, sp, tot)
    L = "\n".join(f"{n}️⃣ {c['fullc']}, {c['type'].lower()}: " + ", ".join(f"{v} {k}" for v, k in c["stats"]) for n, c in zip((1, 2, 3), cands))
    cap = f"CHOOSE YOUR STARTER 🎮🏀 {outs[0]['name'] if outs else 'The star'} is resting. Who steps up {'tonight' if game['when'].startswith('TONIGHT') else 'next game'}?\n\n{L}\n\nComment 1, 2 or 3 👇\n\n⏰ {game['when_c']} {game['vs'].title().replace('Vs','vs')}\n\n#NBA {HASH.get(slug,'')} #Basketball"
    (OUT / f"{slug}_starter.caption.txt").write_text(cap); return mp4

def recap(slug, event_id=None):
    tid, team, assets = common(slug); sched = espn.schedule(tid)
    done = [e for e in sched if e["state"] == "post"]; ev = next((e for e in done if e["id"] == str(event_id)), done[-1]); b = espn.boxscore(ev["id"])
    me, op = str(tid), str(ev["opp_id"]); my, th = int(b["competitors"][me]["score"]), int(b["competitors"][op]["score"]); win = my > th
    opp = {"abbr": ev["opp_abbr"], "name": ev["opp_name"], "short": ev["opp_short"], "logo": "l_" + ev["opp_abbr"]}; assets[opp["logo"]] = sprite_logo(opp["abbr"])
    rows = sorted(b["teams"][me]["rows"], key=lambda r: -int(r["PTS"] or 0)); pg = rows[0]; num = {p["id"]: p.get("jersey") for p in espn.roster(tid)}
    assets["p_" + pg["id"]] = sprite_player(pg["id"]); assets["h_" + pg["id"]] = sprite_hi(pg["id"]); fg, t3 = pg["FG"], pg["3PT"]
    pog = {"key": "p_" + pg["id"], "name": pg["last"].upper(), "jersey": num.get(pg["id"]), "stats": [[int(pg["PTS"]), "PTS"], [int(pg["REB"]), "REB"], [int(pg["AST"]), "AST"]], "line": f"{fg} FG * {t3.split('-')[0]} 3PM", "line2": f"{pg['MIN']} MIN * {pg['+/-']} +/-"}
    cast = []
    for r in rows[1:4]:
        assets["p_" + r["id"]] = sprite_player(r["id"]); assets["h_" + r["id"]] = sprite_hi(r["id"]); cast.append({"key": "p_" + r["id"], "name": r["last"].upper(), "line": f"{r['PTS']} PTS", "line2": f"{r['REB']} REB * {r['AST']} AST"})
    ts, to = b["team_stats"][me], b["team_stats"][op]; f = lambda d, k: float(d.get(k) or 0)
    bars = [{"label": "FIELD GOAL %", "mine": f(ts, "fieldGoalPct"), "theirs": f(to, "fieldGoalPct"), "mineT": f"{ts['fieldGoalPct']}%", "theirT": f"{to['fieldGoalPct']}%"},
            {"label": "THREE POINT %", "mine": f(ts, "threePointFieldGoalPct"), "theirs": f(to, "threePointFieldGoalPct"), "mineT": f"{ts['threePointFieldGoalPct']}%", "theirT": f"{to['threePointFieldGoalPct']}%"},
            {"label": "REBOUNDS", "mine": f(ts, "totalRebounds"), "theirs": f(to, "totalRebounds"), "mineT": ts["totalRebounds"], "theirT": to["totalRebounds"]},
            {"label": "TURNOVERS", "mine": f(ts, "turnovers"), "theirs": f(to, "turnovers"), "mineT": ts["turnovers"], "theirT": to["turnovers"]}]
    team2 = espn.team_info(tid); rec = b["competitors"][me].get("record") or team2["record"]
    nxt = next((e for e in sched if e["state"] == "pre"), None); nd = espn.when(nxt["date"]) if nxt else ("", ""); nx = {"opp": (("vs " if nxt["home"] else "@ ") + nxt["opp_short"]) if nxt else "TBD", "when": (nd[0] + " " + nd[1] + " ET").upper(), "cta1": f"RATE {pg['last'].upper()}: 1-10", "cta2": "COMMENT BELOW"}
    if nxt: assets[("l_" + nxt["opp_abbr"])] = sprite_logo(nxt["opp_abbr"])
    nextopp = {"abbr": nxt["opp_abbr"], "logo": "l_" + nxt["opp_abbr"]} if nxt else opp
    q = b["linescore"]; data = {"team": team, "opp": nextopp, "game": {}, "assets": assets, "handle": HANDLE[slug],
        "recap": {"win": win, "my": my, "their": th, "record_line": rec, "linescore": {"my": q[me]}, "headline": f"{team['short'].upper()} {'BEAT' if win else 'FALL TO'} {opp['short'].upper()}", "pog": pog, "cast": cast, "bars": bars, "next": nx}}
    opp["color"] = opp_color(opp["abbr"]); data["recap"]["gopp"] = opp; data["recap"]["next"]["color"] = opp_color(nextopp["abbr"]); data["recap"]["next"]["logo"] = nextopp["logo"]
    data["hook"] = {"key": pog["key"], "stamp": f"{pog['stats'][0][0]} PTS", "color": "gold", "line1": f"{pg['last'].upper()} {'WENT OFF' if int(pg['PTS']) >= 30 else 'LED THE WAY'}", "line2": f"{team['abbr']} {my}, {opp['abbr']} {th}"}
    sp, tot = spans([("final", 4.5), ("pog", 5.5), ("cast", 4.5), ("bars", 4.0), ("next", 4.0)]); mp4 = render(slug, "recap", data, sp, tot)
    res = "VICTORY" if win else "FINAL"
    cap = f"{res} {'🏆' if win else '📉'}🎮 {team['short']} {my}, {opp['short']} {th}\n\n⭐ PLAYER OF THE GAME: {pg['name']}: {pg['PTS']} PTS, {pg['REB']} REB, {pg['AST']} AST ({fg} FG)\n" + "\n".join(f"🔹 {r['name']}: {r['PTS']} PTS, {r['REB']} REB, {r['AST']} AST" for r in rows[1:4]) + f"\n\n📊 Record: {rec}\n⏭️ Next: {nx['opp']}, {nx['when'].title().replace('Et','ET')}\n\nRate {pg['last']}'s night 1-10 👇\n\n#NBA {HASH.get(slug,'')} #Basketball"
    (OUT / f"{slug}_recap.caption.txt").write_text(cap); return mp4

if __name__ == "__main__":
    kind, slug = sys.argv[1], sys.argv[2]
    print(party(slug) if kind == "party" else starter(slug) if kind == "starter" else recap(slug, sys.argv[3] if len(sys.argv) > 3 else None))
