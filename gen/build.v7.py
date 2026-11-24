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

def render(slug, kind, data, sp, total, vo=None):
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
        tl.write_text(json.dumps({"spans": sp, "total": total, "events": pg.evaluate("EVENTS()"), "vo": vo or []}))
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

def starting5(slug):
    """Wolves' STARTING FIVE PC: both starting fives in PC boxes, five positional matchups, team data, who wins."""
    tid, team, assets = common(slug); nxt, opp, game = next_game(tid, team, slug); assets[opp["logo"]] = sprite_logo(opp["abbr"])
    oid = nxt["opp_id"]; R = {p["id"]: p for p in espn.roster(tid)}; OR = {p["id"]: p for p in espn.roster(oid)}
    def five(team_id, roster):
        last = [e for e in espn.schedule(team_id) if e["state"] == "post"][-1]; b = espn.boxscore(last["id"])
        rows = b["teams"][str(team_id)]["rows"]; day = espn.when(last["date"])[0].upper()
        picks = [roster[r["id"]] for r in rows if r["id"] in roster and not roster[r["id"]]["out"] and roster[r["id"]]["gp"] > 0]
        top = picks[:5] if len(picks) >= 5 else picks + sorted([p for p in roster.values() if p not in picks and not p["out"]], key=lambda p: -p["min"])[:5 - len(picks)]
        g = lambda p: 0 if "G" in (p.get("pos") or "") else (2 if p.get("pos") == "C" else 1)
        top = sorted(top, key=lambda p: (g(p), -p["ppg"]))
        lastpts = {r["id"]: int(r["PTS"] or 0) for r in rows}
        return top, lastpts, day
    mine, mpts, mday = five(tid, R); theirs, tpts, tday = five(int(oid), OR)
    def card(p, pts, day):
        assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"])
        return {"key": "p_" + p["id"], "name": nick(p) if p["name"] in NICK else p["last"].upper(), "box": p["last"].upper(), "full": p["name"],
                "v": [p["ppg"], p["rpg"], p["apg"], p["fg"], p["p3"]], "last": pts.get(p["id"], 0), "day": day}
    M = [card(p, mpts, mday) for p in mine]; O = [card(p, tpts, tday) for p in theirs]
    labels = ["GUARDS", "GUARDS", "FORWARDS", "FORWARDS", "CENTERS"]
    def note(a, b):
        best = max((a, b), key=lambda c: c["last"])
        if best["last"] >= 25: return f"{best['box']} HAD {best['last']} PTS {best['day'].split()[0]} {best['day'].split()[1]}"
        sh = max((a, b), key=lambda c: c["v"][4])
        if sh["v"][4] >= 38: return f"{sh['box']}: {sh['v'][4]:.1f}% FROM THREE"
        sc = max((a, b), key=lambda c: c["v"][0]); return f"{sc['box']}: {sc['v'][0]:.1f} PPG"
    grp = lambda p: "CENTERS" if p.get("pos") == "C" else "GUARDS" if "G" in (p.get("pos") or "") else "FORWARDS"
    mus = [{"pos": grp(mine[i]), "a": M[i], "b": O[i], "note": note(M[i], O[i])} for i in range(5)]
    ti = lambda t_id: espn.get(f"{espn.SITE}/teams/{t_id}")["team"]["record"]["items"]
    def rec(items, kind): return next((i for i in items if i.get("type") == kind), {})
    mi, oi = ti(tid), ti(oid); st = lambda it, k: next((x["value"] for x in it.get("stats", []) if x["name"] == k), 0)
    ordn = lambda n: f"{int(n)}{'TH' if 10 <= int(n) % 100 <= 20 else {1: 'ST', 2: 'ND', 3: 'RD'}.get(int(n) % 10, 'TH')}"
    conf = "EAST" if team["abbr"] in ("TOR", "MIL", "BOS", "NY", "PHI", "BKN", "MIA", "ORL", "ATL", "CHA", "WSH", "CLE", "DET", "IND", "CHI") else "WEST"
    away = not game["home"]; ab = opp["abbr"]
    tdata = [[rec(mi, "total").get("summary", ""), "RECORD", rec(oi, "total").get("summary", "")],
             [ordn(st(rec(mi, "total"), "playoffSeed")), conf, ordn(st(rec(oi, "total"), "playoffSeed"))],
             [f"{st(rec(mi, 'total'), 'avgPointsFor'):.1f}", "PPG", f"{st(rec(oi, 'total'), 'avgPointsFor'):.1f}"],
             [f"{st(rec(mi, 'total'), 'avgPointsAgainst'):.1f}", "OPP PPG", f"{st(rec(oi, 'total'), 'avgPointsAgainst'):.1f}"],
             [rec(mi, "road" if away else "home").get("summary", ""), f"{'ROAD' if away else 'HOME'} / {'HOME' if away else 'ROAD'}", rec(oi, "home" if away else "road").get("summary", "")]]
    data = {"team": team, "opp": opp, "game": game, "assets": assets, "s5": {"mine": M, "theirs": O, "mus": mus, "tdata": tdata}}
    sp, tot = spans([("sfbox", 3.0), ("mu0", 3.4), ("mu1", 3.4), ("mu2", 3.4), ("mu3", 3.4), ("mu4", 3.4), ("tdata", 3.0), ("swap", 3.4)]); mp4 = render(slug, "starting5", data, sp, tot)
    L = "\n".join(f"{m['pos'][:-1].title()}: {m['a']['full']} vs {m['b']['full']}" for m in mus)
    cap = (f"STARTING FIVE PC 🎮🏀 Grab each matchup: {team['short']} vs {opp['short']}\n\n{L}\n\n"
           f"📊 {team['short']} {tdata[0][0]} ({tdata[1][0]} {conf}) | {opp['short']} {tdata[0][2]} ({tdata[1][2]})\n"
           f"⏰ {game['when_c']} {game['vs'].title().replace('Vs', 'vs')}\n\nWho wins the swap? Comment {team['abbr']} or {ab} 👇\n\n#NBA {HASH.get(slug, '')} #Basketball")
    (OUT / f"{slug}_starting5.caption.txt").write_text(cap); return mp4

WORDS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
def say(n): return WORDS[n] if 0 <= n < len(WORDS) else str(n)
def ordw(n): return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}.get(n, f"{n}th")

def spoken(p):
    """Name as the narrator says it: the nickname when it's a word (Steph, Jimmy), else the full name."""
    nk = NICK.get(p["name"], "")
    if nk in ("IQ", "KP", "CMB", "TJD"): return ".".join(nk) + "."
    return nk.title() if nk.isalpha() and len(nk) > 2 and nk != p["name"].split()[-1].upper() else p["name"].replace(" III", "").replace(" II", "").replace(" Jr.", "")

def games_in(slug):
    """Wolves' narrated 'N GAMES IN: the story so far' explainer, scripted from ESPN data and voiced by Kokoro."""
    tid, team, assets = common(slug); nxt, opp, game = next_game(tid, team, slug)
    played = [e for e in espn.schedule(tid) if e["state"] == "post"]; n = len(played)
    R = espn.roster(tid); byid = {p["id"]: p for p in R}; Tn = team["short"]
    games = []
    for e in played:
        b = espn.boxscore(e["id"]); rows = b["teams"][str(tid)]["rows"]; top = max(rows, key=lambda r: int(r["PTS"] or 0))
        assets["l_" + e["opp_abbr"]] = sprite_logo(e["opp_abbr"])
        city = e["opp_name"].replace(e["opp_short"], "").strip()
        games.append({"w": bool(e["win"]), "logo": "l_" + e["opp_abbr"], "opp": e["opp_short"], "city": city, "home": e["home"], "my": int(e["my"]), "their": int(e["their"]),
                      "top": top, "rows": rows, "day": espn.when(e["date"])[0]})
    W = sum(g["w"] for g in games); Lr = n - W
    first = games[0]["w"]; k0 = next((i for i, g in enumerate(games) if g["w"] != first), n)
    cur = games[-1]["w"]; k1 = next((i for i, g in enumerate(reversed(games)) if g["w"] != cur), n)
    beats = []
    B = lambda **kw: beats.append(kw)
    gl = [{"w": g["w"], "logo": g["logo"]} for g in games]
    B(kind="trainer", head="TRAINER CARD", tag=f"{n} GAMES IN", games=gl, reveal=False, vo=f"{say(n).capitalize()} games in, here's where the {Tn} stand.", dlg=f"{n} GAMES IN. HERE'S WHERE|THE {Tn.upper()} STAND...")
    if not first and k0 >= 2 and cur and k1 >= 3:
        B(kind="trainer", head="TRAINER CARD", tag=f"{n} GAMES IN", games=gl, reveal=True, chip=f"STARTED 0-{k0}", vo=f"They're {say(W)} and {say(Lr)}. But it started oh and {say(k0)}.", dlg=f"THEY'RE {W}-{Lr}.|BUT IT STARTED 0-{k0}!")
    elif first and k0 >= 2:
        B(kind="trainer", head="TRAINER CARD", tag=f"{n} GAMES IN", games=gl, reveal=True, chip=f"HOT START {k0}-0", vo=(f"They're {say(W)} and {say(Lr)}, and it started hot." if cur else f"They're {say(W)} and {say(Lr)}. It started {say(k0)} and oh."), dlg=(f"THEY'RE {W}-{Lr},|AND IT STARTED HOT!" if cur else f"THEY'RE {W}-{Lr}.|IT STARTED {k0}-0!"))
    else:
        B(kind="trainer", head="TRAINER CARD", tag=f"{n} GAMES IN", games=gl, reveal=True, vo=f"They're {say(W)} and {say(Lr)}.", dlg=f"THEY'RE {W}-{Lr}.")
    outs = sorted([p for p in R if p["out"] and (p["ppg"] > 8 or p["gp"] > 20)], key=lambda p: -p["ppg"])[:3]
    without = ""
    if outs:
        miss = [g for g in games if outs[0]["id"] not in {r["id"] for r in g["rows"]}]
        if 0 < len(miss) < n:
            mw = sum(g["w"] for g in miss); without = f" Without him, they're {say(mw)} and {say(len(miss) - mw)}."
        for p in outs: assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"])
        B(kind="center", head=f"{Tn.upper()} CENTER", players=[{"key": "p_" + p["id"], "name": nick(p), "tag": "OUT"} for p in outs],
          vo="No " + ", no ".join(p["name"].replace(" III", "").replace(" II", "").replace(" Jr.", "") for p in outs) + "." + without, dlg=("NO " + ". NO ".join(nick(p) for p in outs) + ".").replace(". NO ", ".|NO ", 1) if len(outs) > 2 else "NO " + ". NO ".join(nick(p) for p in outs) + ".")
    if cur and k1 >= 3:
        run = games[-k1:]; rows = [{"logo": g["logo"], "name": g["opp"].upper(), "sub": f"{g['my']}-{g['their']}", "val": f"+{g['my'] - g['their']}", "w": True} for g in run][-6:]
        B(kind="hot", head="THE STREAK", rows=rows, vo=f"Then they flipped the switch. {say(k1).capitalize()} straight wins.", dlg=f"THEN THEY FLIPPED THE SWITCH:|{k1} STRAIGHT WINS!")
    else:
        big = sorted([g for g in games if g["w"]], key=lambda g: -(g["my"] - g["their"]))[:4]
        if big: B(kind="hot", head="BIGGEST WINS", rows=[{"logo": g["logo"], "name": g["opp"].upper(), "sub": f"{g['my']}-{g['their']}", "val": f"+{g['my'] - g['their']}", "w": True} for g in big],
                  vo=f"Their best win? {big[0]['opp']}, by {big[0]['my'] - big[0]['their']}.", dlg=f"BEST WIN: {big[0]['opp'].upper()}|BY {big[0]['my'] - big[0]['their']}!")
    healthy = sorted([p for p in R if not p["out"] and p["gp"] > 0], key=lambda p: -p["ppg"])
    def best_game(pid):
        c = [(int(r["PTS"] or 0), g) for g in games for r in espn.boxscore.__dict__.get("_c", []) if False]
        return c
    tops = {}
    for g in games:
        b = None
    # career-high style lines from each game's top scorer
    pg = {}
    for g in games:
        for r in g["rows"]: pg.setdefault(r["id"], []).append((int(r["PTS"] or 0), g))
    for j, p in enumerate(healthy[:2]):
        assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"])
        bests = sorted(pg.get(p["id"], []), key=lambda x: -x[0]); nk = nick(p)
        rk = False
        try:
            dd = espn.get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{p['id']}/stats"); cc = next(c for c in dd["categories"] if c["name"] == "totals")
            rk = len(cc.get("statistics", [])) == 1
        except Exception: pass
        where = lambda g: (f"in {g['city']}" if not g["home"] else f"against the {g['opp']}")
        wshort = lambda g: (f"AT {g['city'].upper()}" if not g["home"] else f"VS {g['opp'].upper()}")
        if bests:
            pts, g = bests[0]
            if j == 0:
                B(kind="fire", head=f"{nk} WAS ON FIRE", key="p_" + p["id"], name=nk, lines=[[f"{pts} PTS", wshort(g)]] + ([[f"{bests[1][0]} PTS", wshort(bests[1][1])]] if len(bests) > 1 else []),
                  vo=(f"{spoken(p)} has been cooking. {round(p['ppg'])} a night, with {pts} {where(g)}." if p["ppg"] >= 25 else f"{spoken(p)} is putting up {round(p['ppg'])} a night, with {pts} {where(g)}."), dlg=f"{nk}: {p['ppg']:.1f} PPG.|{pts} {wshort(g)}!")
            else:
                B(kind="fire", head=("ROOKIE ON FIRE" if rk else "STEPPING UP"), key="p_" + p["id"], name=nk, badge=("ROOKIE" if rk else "STEPPING UP"), lines=[[f"{p['ppg']:.1f}", "PPG"], [f"{pts} PTS", wshort(g)]],
                  vo=f"And {'the rookie ' if rk else ''}{spoken(p)}? {round(p['ppg'])} a game, with {pts} {where(g)}.", rookie=rk, dlg=f"{nk}: {p['ppg']:.1f} PPG.|{pts} {wshort(g)}!")
    if len(healthy) >= 4:
        h4 = healthy[:4]; p3 = h4[2]
        for p in h4: assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"])
        B(kind="step", head="STEPPING UP", players=[{"key": "p_" + p["id"], "name": nick(p), "hi": p is p3} for p in h4], big=f"{p3['ppg']:.1f}", small=f"PPG ({nick(p3)})",
          vo=f"And {spoken(p3)} adds {round(p3['ppg'])} a night.", dlg=f"{nick(p3)} ADDS|{p3['ppg']:.1f} A NIGHT!")
    rank = int(next((x["value"] for x in espn.get(f"{espn.SITE}/teams/{tid}")["team"]["record"]["items"][0]["stats"] if x["name"] == "playoffSeed"), 0))
    conf = "EAST" if team["abbr"] in ("TOR", "MIL", "BOS", "NY", "PHI", "BKN", "MIA", "ORL", "ATL", "CHA", "WSH", "CLE", "DET", "IND", "CHI") else "WEST"
    if cur and k1 >= 3:
        B(kind="log", head=f"WIN STREAK: {k1}", games=gl, note=f"{ordw(rank).upper()} IN THE {conf}", vo=f"{say(k1).capitalize()} straight wins... and they're still only {ordw(rank)} in the {conf.title()}.", dlg=f"{k1} STRAIGHT...|BUT ONLY {rank}{['TH','ST','ND','RD'][rank if rank < 4 else 0]} IN THE {conf}.")
    else:
        B(kind="log", head=f"{n} GAMES: {W}-{Lr}", games=gl, note=f"{ordw(rank).upper()} IN THE {conf}", vo=f"That's good for {ordw(rank)} in the {conf.title()}.", dlg=f"{W}-{Lr}: {rank}{['TH','ST','ND','RD'][rank if rank < 4 else 0]} IN THE {conf}.")
    nday = game["day"].split()[0]; dayname = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}.get(nday, nday)
    ask = f"Can they make it {say(k1 + 1)}?" if cur and k1 >= 3 else ("Can they turn it around?" if not cur and k1 >= 2 else ("Can they keep it rolling?" if W > Lr else "Can they get back on track?"))
    when_s = "tonight" if game["when"].startswith("TONIGHT") else f"on {dayname}"
    gl2 = gl + [{"w": True, "logo": opp["logo"]}][:0]
    B(kind="log", head="NEXT BATTLE", games=gl, note=f"NEXT: {opp['short'].upper()} * {game['when']}", vo=f"Next up, the {opp['short']} {when_s}. {ask}", dlg=f"NEXT: {opp['short'].upper()}, {nday.upper()} {game['tm']}.|{ask.upper()}")
    assets[opp["logo"]] = sprite_logo(opp["abbr"])
    # voice
    SAYS = {"Immanuel": "Emmanuel", "Barrett": "Bare-ett", "Kawhi": "Kuh-why", "Porzingis": "Por-zing-is", "Lendeborg": "Len-deh-borg", "Podziemski": "Pod-zem-ski", "Poeltl": "Pertle"}
    pron = lambda x: [x := x.replace(k, v) for k, v in SAYS.items()][-1]
    vod = OUT / f"{slug}_vo"; lines = [{"id": f"b{i}", "text": pron(b["vo"])} for i, b in enumerate(beats)]
    lj = OUT / f"{slug}_vo_lines.json"; lj.write_text(json.dumps(lines))
    durs = json.loads(subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts.py"), str(lj), str(vod)], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    sp = []; t = 0.0; vo = []
    for i, b in enumerate(beats):
        d = durs[f"b{i}"]; b["dur"] = d; start = t; vo.append({"t": round(start + .15, 3), "wav": str(vod / f"b{i}.wav")}); t = start + d + .3
        sp.append({"scene": f"st{i}", "start": round(start, 3), "end": round(t, 3)})
    sp.append({"scene": "end", "start": round(t, 3), "end": round(t + 2.2, 3)}); total = round(t + 2.2, 3)
    data = {"team": team, "opp": opp, "game": game, "assets": assets, "story": {"beats": beats}}
    mp4 = render(slug, "gamesin", data, sp, total, vo)
    cap = (f"{n} GAMES IN 🎮🏀 The {Tn} are {W}-{Lr}. Here's the story so far:\n\n" + "\n".join("• " + b["dlg"].replace("|", " ").capitalize() for b in beats[1:-1]) +
           f"\n\nNext up: {game['vs'].title().replace('Vs', 'vs')}, {game['when_c']}\n\n{ask} 👇\n\n#NBA {HASH.get(slug, '')} #Basketball")
    (OUT / f"{slug}_gamesin.caption.txt").write_text(cap); return mp4

def milestone(slug):
    """Teaser for a round-number career milestone a healthy player is about to hit (Wolves' EVOLVING / NEW HIGH SCORE)."""
    tid, team, assets = common(slug); nxt, opp, game = next_game(tid, team, slug); assets[opp["logo"]] = sprite_logo(opp["abbr"])
    R = [p for p in espn.roster(tid) if not p["out"] and p["gp"] > 0]; best = None
    for p in R:
        try:
            d = espn.get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{p['id']}/stats")
            c = next(c for c in d["categories"] if c["name"] == "totals"); T = dict(zip(c["labels"], c["totals"]))
        except Exception: continue
        num = lambda v: int(str(v).split("-")[0].replace(",", ""))
        for lab, stat, step, per in (("PTS", "POINTS", 1000, p["ppg"]), ("REB", "REBOUNDS", 1000, p["rpg"]), ("AST", "ASSISTS", 1000, p["apg"]), ("3PT", "THREES", 100, 3)):
            if lab not in T: continue
            v = num(T[lab]); goal = (v // step + 1) * step; need = goal - v
            if per > 0 and need <= max(1, per * 1.2) and v >= step:
                score = need / max(per, .1)
                if not best or score < best[0]: best = (score, p, stat, v, goal, need)
    if not best: print("no milestone within reach"); return None
    _, p, stat, v, goal, need = best; nk = nick(p)
    assets["p_" + p["id"]] = sprite_player(p["id"]); assets["h_" + p["id"]] = sprite_hi(p["id"])
    last = [e for e in espn.schedule(tid) if e["state"] == "post"][-1]; b = espn.boxscore(last["id"]); row = next((r for r in b["teams"][str(tid)]["rows"] if r["id"] == p["id"]), None)
    key = {"POINTS": "PTS", "REBOUNDS": "REB", "ASSISTS": "AST", "THREES": "3PT"}[stat]
    lw = espn.when(last["date"])[0].upper().split()[0] + (" VS " if last["home"] else " AT ") + last["opp_short"].upper()
    line = [[row["PTS"], "PTS", key == "PTS"], [row["REB"], "REB", key == "REB"], [row["AST"], "AST", key == "AST"]] if row else []
    fmt = lambda x: f"{x:,}"; unit = stat[:-1] if need == 1 else stat
    ms = {"key": "p_" + p["id"], "name": nk, "jersey": p.get("jersey"), "stat": stat if stat != "THREES" else "3PM", "curTxt": fmt(v), "goalTxt": fmt(goal), "pct": max(.02, 1 - need / (goal * .02 if goal * .02 > need else need * 1.05)),
          "head": f"{fmt(goal)} CAREER {stat}", "h2": f"WHAT? {nk} IS EVOLVING...", "last": {"when": lw, "line": line},
          "d0": f"{nk} NEEDS {need} MORE|FOR {fmt(goal)} CAREER {stat}!", "d1": (f"LAST GAME: {row['PTS']} PTS...|BUT JUST {row[key.replace('3PT','3PT')]} {key}." if row and key != "3PT" else f"{fmt(v)} AND COUNTING..."),
          "d2": f"WHAT? {nk} IS|ABOUT TO EVOLVE...", "d3": f"{game['day'].split()[0].upper()} {game['vs'].replace('@ ','AT ')}:|WILL {nk} HIT {fmt(goal)}?", "ask": f"{need} {unit} TO GO"}
    data = {"team": team, "opp": opp, "game": game, "assets": assets, "ms": ms}
    sp, tot = spans([("ms0", 3.8), ("ms1", 3.8), ("ms2", 3.4), ("ms3", 3.8), ("end", 2.2)]); mp4 = render(slug, "milestone", data, sp, tot)
    cap = (f"WHAT? {nk} IS EVOLVING... 🎮🏀 {p['name']} is {need} {unit.lower()} away from {fmt(goal)} career {stat.lower()}.\n\n"
           f"📈 Career {stat.lower()}: {fmt(v)}\n" + (f"🕹️ Last game ({lw.title()}): {row['PTS']} PTS, {row['REB']} REB, {row['AST']} AST\n" if row else "") +
           f"\n⏰ Next: {game['vs'].title().replace('Vs', 'vs')}, {game['when_c']}\n\nWill he get it in the first quarter? 👇\n\n#NBA {HASH.get(slug, '')} #Basketball")
    (OUT / f"{slug}_milestone.caption.txt").write_text(cap); return mp4

def secs(clock):
    c = str(clock or "0")
    return int(c.split(":")[0]) * 60 + float(c.split(":")[1]) if ":" in c else float(c)

def shot_name(text):
    t = text.lower()
    if "three point" in t: return "3-POINTER"
    if "free throw" in t: return "FREE THROW"
    if "dunk" in t: return "DUNK"
    if "layup" in t: return "LAYUP"
    if "tip" in t: return "TIP-IN"
    return "JUMPER"

def gamestory(slug, event_id=None):
    """Wolves' narrated post-game story ('GYM BATTLE', 24K): who they faced, how it went, the 4th-quarter run, the dagger."""
    tid, team, assets = common(slug); Tn = team["short"]; sched = espn.schedule(tid)
    done = [e for e in sched if e["state"] == "post"]; ev = next((e for e in done if e["id"] == str(event_id)), done[-1])
    S = espn.get(f"{espn.SITE}/summary?event={ev['id']}"); b = espn.boxscore(ev["id"])
    me, op = str(tid), str(ev["opp_id"]); my, th = int(ev["my"]), int(ev["their"]); win = my > th
    oppn, opps, city = ev["opp_name"], ev["opp_short"], ev["opp_name"].replace(ev["opp_short"], "").strip()
    assets["l_" + ev["opp_abbr"]] = sprite_logo(ev["opp_abbr"]); OL = "l_" + ev["opp_abbr"]; ocol = opp_color(ev["opp_abbr"])
    ts = {t["team"]["id"]: {x["name"]: x.get("displayValue") for x in t["statistics"]} for t in S["boxscore"]["teams"]}
    num = lambda v: int(float(str(v or 0).split("-")[0]))
    home_id = next(c["team"]["id"] for c in S["header"]["competitions"][0]["competitors"] if c["homeAway"] == "home")
    plays = S.get("plays", [])
    def score_at(p): h, a = int(p.get("homeScore", 0)), int(p.get("awayScore", 0)); return (h, a) if home_id == me else (a, h)
    R = {p["id"]: p for p in espn.roster(tid)}
    # --- opponent context
    ot = espn.get(f"{espn.SITE}/teams/{ev['opp_abbr'].lower()}")["team"]; orec = ot["record"]["items"][0]["summary"]
    ow, ol = [int(x) for x in orec.split("-")]; ow_b, ol_b = (ow - (0 if win else 1), ol - (1 if win else 0))
    oseed = int(next((x["value"] for x in ot["record"]["items"][0]["stats"] if x["name"] == "playoffSeed"), 0))
    oconf = "EAST" if ev["opp_abbr"] in ("TOR", "MIL", "BOS", "NY", "PHI", "BKN", "MIA", "ORL", "ATL", "CHA", "WSH", "CLE", "DET", "IND", "CHI") else "WEST"
    osched = [e for e in espn.schedule(int(op)) if e["state"] == "post" and e["id"] != ev["id"]]
    ostreak = 0
    for e in reversed(osched):
        if ostreak == 0 or (ostreak > 0) == bool(e["win"]): ostreak += 1 if e["win"] else -1
        else: break
    beats = []; B = lambda **kw: beats.append(kw)
    lead = f"{oppn.split()[0] if city else opps}"
    if oseed == 1: ctx, cdlg = f"the best record in the {oconf.title()}", f"BEST RECORD IN THE {oconf}!"
    elif ostreak <= -3: ctx, cdlg = f"losers of {say(-ostreak)} straight", f"LOSERS OF {-ostreak} STRAIGHT."
    elif ostreak >= 3: ctx, cdlg = f"winners of {say(ostreak)} straight", f"WINNERS OF {ostreak} STRAIGHT!"
    else: ctx, cdlg = "", ""
    B(kind="gym", head=f"{'GYM LEADER' if ow_b >= ol_b else 'NEXT GYM'}: {city.upper() or opps.upper()}", rec=f"{ow_b}-{ol_b}", chip=cdlg.rstrip('!.') if cdlg else "", logo=OL, ocol=ocol,
      vo=f"{city or 'The ' + opps} came in {say(ow_b)} and {say(ol_b)}" + (f", {ctx}." if ctx else "."), dlg=f"{(city or opps).upper()}: {ow_b}-{ol_b}." + (f"|{cdlg}" if cdlg else ""))
    # --- challenger: line + injuries
    det = ((S.get("pickcenter") or [{}])[0].get("details") or "")
    line = ""
    try:
        ab, sp = det.split()[0], abs(float(det.split()[1]))
        fav = ab == team["abbr"]; line = f"{sp:g}-point {'favorites' if fav else 'underdogs'}"
    except Exception: fav = None
    outs = sorted([p for p in R.values() if p["out"] and p["ppg"] > 12], key=lambda p: -p["ppg"])[:1]
    vo2 = (f"Vegas had the {Tn} as {line}." if line else "") + (f" And no {outs[0]['name'].replace(' III','').replace(' Jr.','')}." if outs else "")
    if vo2:
        if outs: assets["p_" + outs[0]["id"]] = sprite_player(outs[0]["id"])
        B(kind="gym", head=f"CHALLENGER: {Tn.upper()}", rec=f"{ow_b}-{ol_b}", logo=OL, ocol=ocol, me=True, line=(line.upper().replace("-POINT ", " ") if line else ""), out=("p_" + outs[0]["id"]) if outs else None, outname=nick(outs[0]) if outs else "",
          vo=vo2.strip() + (f" Nobody told {team['name'].replace(Tn, '').strip()}." if (win and fav is False) else ""), dlg=(f"VEGAS: {line.upper().replace('-POINT', '-PT')}." if line else "") + (f"|...AND NO {nick(outs[0])}." if outs else ""))
    # --- battle: lead changes, opponent star, turnovers
    lc = num(ts.get(me, {}).get("leadChanges")); orows = b["teams"][op]["rows"]; star = max(orows, key=lambda r: int(r["PTS"] or 0))
    sv = [int(star["PTS"] or 0), int(star["REB"] or 0), int(star["AST"] or 0)]; td = sum(v >= 10 for v in sv) >= 3
    assets["p_" + star["id"]] = sprite_player(star["id"])
    mylead, oplead = num(ts.get(me, {}).get("largestLead")), num(ts.get(op, {}).get("largestLead"))
    if lc >= 10: flow = f"This one was a slugfest. {lc} lead changes."
    elif win and mylead >= 15: flow = f"{Tn} led by as many as {mylead}."
    elif not win and oplead >= 15: flow = f"{opps if not city else city} ran away with it, up by as many as {oplead}."
    elif abs(my - th) <= 6: flow = "This one went down to the wire."
    else: flow = f"{Tn} led by as many as {mylead}." if win else f"{opps if not city else city} led by as many as {oplead}."
    B(kind="bat", head="GYM BATTLE", logo=OL, ocol=ocol, oname=opps.upper(), score=None, chip=(f"LEAD CHANGES {lc}" if lc >= 10 else ""), vo=flow, dlg=flow.upper().replace(". ", ".|", 1))
    sl = f"a triple-double" if td else f"{sv[0]}"
    B(kind="bat", head="GYM BATTLE", logo=OL, ocol=ocol, oname=star["last"].upper(), star="p_" + star["id"], chip=(f"TRIPLE-DOUBLE" if td else f"{sv[0]} PTS"),
      vo=f"{star['name']} dropped {sl}.", dlg=f"FOE {star['last'].upper()} DROPPED|{('A TRIPLE-DOUBLE' if td else str(sv[0]) + ' PTS')}!")
    oto, tp = num(ts.get(op, {}).get("totalTurnovers")), num(ts.get(me, {}).get("turnoverPoints"))
    if oto >= 15 and tp >= 15:
        B(kind="bat", head="GYM BATTLE", logo=OL, ocol=ocol, oname=opps.upper(), chip=f"TURNOVERS {oto}|PTS OFF THEM {tp}",
          vo=(f"But {opps if not city else city} kept coughing it up. {oto} turnovers, and the {Tn} turned them into {tp} points." if win else f"The {Tn} forced {oto} turnovers and turned them into {tp} points, but it wasn't enough."),
          dlg=(f"{oto} TURNOVERS!|{Tn.upper()} TURNED THEM INTO {tp} PTS!" if win else f"{oto} TURNOVERS FORCED...|BUT NOT ENOUGH."))
    # --- 4th quarter: score midway, best run, hero
    q4 = [p for p in plays if p.get("period", {}).get("number") == 4]
    mid = next((p for p in q4 if secs(p.get("clock", {}).get("displayValue")) <= 360), q4[-1] if q4 else None)
    W = me if win else op
    sc = [(p, score_at(p)) for p in q4 if p.get("scoringPlay")]
    best = None
    for i in range(len(sc)):
        for j in range(i, len(sc)):
            a0 = score_at(q4[0]) if i == 0 else sc[i - 1][1]; a1 = sc[j][1]
            wpts = (a1[0] - a0[0]) if W == me else (a1[1] - a0[1]); lpts = (a1[1] - a0[1]) if W == me else (a1[0] - a0[0])
            if lpts <= 4 and wpts >= 8 and (not best or wpts - lpts > best[0]): best = (wpts - lpts, wpts, lpts, i, j)
    if mid and best:
        m0 = score_at(mid); diff = m0[0] - m0[1]; state = f"Down {abs(diff)}" if diff < 0 else (f"Up {diff}" if diff > 0 else "Tied")
        runp = {}
        for p, _ in sc[best[3]:best[4] + 1]:
            if str(p.get("team", {}).get("id")) == W and p.get("participants"):
                a = p["participants"][0]["athlete"]["id"]; runp[a] = runp.get(a, 0) + int(p.get("scoreValue") or 0)
        hero_id = max(runp, key=runp.get) if runp else None; hrow = next((r for g2 in b["teams"].values() for r in g2["rows"] if r["id"] == hero_id), None)
        close = abs(diff) <= 8
        if win and hrow and close:
            assets["p_" + hero_id] = sprite_player(hero_id); hn = nick(R[hero_id]) if hero_id in R else hrow["last"].upper(); hs = spoken(R[hero_id]) if hero_id in R else hrow["name"]
            B(kind="q4", head="4TH QUARTER", ocol=ocol, logo=OL, oname=opps.upper(), hero="p_" + hero_id, hname=hn, s0=list(m0), run=f"{best[1]}-{best[2]}", rp=runp[hero_id],
              vo=f"{state} midway through the fourth, {hs} took over. {(say(runp[hero_id]) if runp[hero_id] <= 20 else str(runp[hero_id])).capitalize()} points in {'an' if str(best[1]).startswith(('8','11','18')) else 'a'} {best[1]}-{best[2]} run.", dlg=f"{state.upper()} MIDWAY THROUGH THE 4TH...|{hn}: {runp[hero_id]} PTS IN A {best[1]}-{best[2]} RUN!")
        elif win and diff >= 10:
            B(kind="q4", head="4TH QUARTER", ocol=ocol, logo=OL, oname=opps.upper(), hero=None, s0=list(m0), run=f"{best[1]}-{best[2]}", rp=0,
              vo=f"Up {diff} midway through the fourth, they never looked back.", dlg=f"UP {diff} MIDWAY THROUGH THE 4TH...|NEVER LOOKED BACK!")
        elif not win and abs(diff) <= 8:
            B(kind="q4", head="4TH QUARTER", ocol=ocol, logo=OL, oname=opps.upper(), hero=None, s0=list(m0), run=f"{best[2]}-{best[1]}", rp=0,
              vo=f"{state} midway through the fourth, then the {opps} went on a {best[1]}-{best[2]} run.", dlg=f"{state.upper()} MIDWAY THROUGH THE 4TH...|{opps.upper()} WENT ON A {best[1]}-{best[2]} RUN.")
    # --- dagger: most points for the winner in the final 3:00
    if win:
        late = [p for p in q4 if p.get("scoringPlay") and secs(p.get("clock", {}).get("displayValue")) <= 180 and str(p.get("team", {}).get("id")) == me and p.get("participants")]
        lp = {}
        for p in late: a = p["participants"][0]["athlete"]["id"]; lp.setdefault(a, []).append(p)
        if lp:
            did = max(lp, key=lambda a: sum(int(p.get("scoreValue") or 0) for p in lp[a])); pts = sum(int(p.get("scoreValue") or 0) for p in lp[did])
            if pts >= 5 and did in R:
                shots = [shot_name(p["text"]) for p in lp[did]]; kinds = {}
                for x in shots: kinds[x] = kinds.get(x, 0) + 1
                assets["p_" + did] = sprite_player(did); dn = nick(R[did])
                say_shots = ", then ".join(("a " if x[0] not in "AEIOU3" else "an ") .replace("an 3","a 3") + x.lower().replace("-pointer", "-pointer") for x in shots[:3])
                B(kind="dagger", head="THE DAGGER", hero="p_" + did, hname=dn, shots=[[k, v] for k, v in kinds.items()][:3], pts=pts,
                  vo=f"Then the dagger. {spoken(R[did])} hit {say_shots}. {pts} points in the final three minutes.", dlg=f"THE DAGGER: {dn}!|{pts} PTS IN THE FINAL 3:00!")
    # --- team high + final + next
    mrows = b["teams"][me]["rows"]; top = max(mrows, key=lambda r: int(r["PTS"] or 0)); assets["p_" + top["id"]] = sprite_player(top["id"]); assets["h_" + top["id"]] = sprite_hi(top["id"])
    tn = nick(R[top["id"]]) if top["id"] in R else top["last"].upper(); tsay = spoken(R[top["id"]]) if top["id"] in R else top["name"]
    B(kind="fire", head="TEAM HIGH", key="p_" + top["id"], name=tn, badge="TEAM HIGH", lines=[[f"{top['PTS']} PTS", f"{top['REB']} REB * {top['AST']} AST"]],
      vo=f"{tsay} led the {Tn} with {top['PTS']}.", dlg=f"{tn} LED THE {Tn.upper()}|WITH {top['PTS']}!")
    B(kind="final", head="VICTORY!" if win else "DEFEAT", ocol=ocol, logo=OL, my=my, th=th, win=win, oname=opps.upper(),
      vo=(f"{Tn} win, {my} to {th}." if win else f"{Tn} fall, {th} to {my}."), dlg=(f"{Tn.upper()} WIN!|{my}-{th}" if win else f"{Tn.upper()} FALL.|{th}-{my}"))
    nxt = next((e for e in sched if e["state"] == "pre"), None)
    if nxt:
        day, tm = espn.when(nxt["date"]); assets["l_" + nxt["opp_abbr"]] = sprite_logo(nxt["opp_abbr"])
        team2 = espn.team_info(tid)
        B(kind="next", head=("BOSS DEFEATED!" if win else "NEXT BATTLE"), logo=OL, nlogo="l_" + nxt["opp_abbr"], rec=team2["record"], ntxt=f"NEXT: {'VS' if nxt['home'] else '@'} {nxt['opp_abbr']}", nday=f"{day.split()[0].upper()} {tm} ET", win=win,
          vo=f"Who was your MVP? Comment below.", dlg="WHO WAS YOUR MVP?|COMMENT BELOW!")
    # --- voice, timeline, render
    SAYS = {"Immanuel": "Emmanuel", "Barrett": "Bare-ett", "Kawhi": "Kuh-why", "Porzingis": "Por-zing-is", "Lendeborg": "Len-deh-borg", "Podziemski": "Pod-zem-ski", "Poeltl": "Pertle", "Sengun": "Shen-goon"}
    pron = lambda x: [x := x.replace(k, v) for k, v in SAYS.items()][-1]
    vod = OUT / f"{slug}_rvo"; lines = [{"id": f"b{i}", "text": pron(bt["vo"])} for i, bt in enumerate(beats)]
    lj = OUT / f"{slug}_rvo_lines.json"; lj.write_text(json.dumps(lines))
    durs = json.loads(subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts.py"), str(lj), str(vod)], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    sp, vo, t = [], [], 0.0
    for i, bt in enumerate(beats):
        d = durs[f"b{i}"]; bt["dur"] = d; vo.append({"t": round(t + .15, 3), "wav": str(vod / f"b{i}.wav")}); sp.append({"scene": f"st{i}", "start": round(t, 3), "end": round(t + d + .35, 3)}); t += d + .35
    total = round(t + .6, 3); sp[-1]["end"] = total
    data = {"team": team, "opp": {"abbr": ev["opp_abbr"], "short": opps, "logo": OL, "color": ocol}, "game": {}, "assets": assets, "story": {"beats": beats}}
    mp4 = render(slug, "recap", data, sp, total, vo)
    lines_c = "\n".join("• " + bt["dlg"].replace("|", " ").capitalize() for bt in beats[2:-2])
    cap = (f"{'VICTORY' if win else 'FINAL'} 🎮🏀 {Tn} {my}, {opps} {th}\n\n{lines_c}\n\n⭐ {top['name']}: {top['PTS']} PTS, {top['REB']} REB, {top['AST']} AST\n\n"
           + (f"Next: {'vs' if nxt['home'] else '@'} {nxt['opp_short']}, {espn.when(nxt['date'])[0]} {espn.when(nxt['date'])[1]} ET\n\n" if nxt else "") + f"Who was your MVP? 👇\n\n#NBA {HASH.get(slug, '')} #Basketball")
    (OUT / f"{slug}_recap.caption.txt").write_text(cap); return mp4

if __name__ == "__main__":
    kind, slug = sys.argv[1], sys.argv[2]
    print(party(slug) if kind == "party" else starter(slug) if kind == "starter" else starting5(slug) if kind == "starting5" else games_in(slug) if kind == "gamesin" else milestone(slug) if kind == "milestone" else recap(slug, sys.argv[3] if len(sys.argv) > 3 else None) if kind == "recap_music" else gamestory(slug, sys.argv[3] if len(sys.argv) > 3 else None))
