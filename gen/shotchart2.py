"""Two-game shot chart + "3 things to fix" (copy of @8bitwolves Df5dkpDg76T "WE SWEPT PORTLAND. BY 9 POINTS TOTAL.").

usage: python3 gen/shotchart2.py <raptors|warriors> [--out specs/x.json] [--no-fit]
   -> specs/<r|w>_sc2_<opp1><opp2>.json for gen/fmt_sc2.html (a copy of fmt_shotchart.html with the two-game scenes):
      python3 gen/factcheck.py specs/r_sc2_nykwas.json && zsh gen/batch.sh specs/r_sc2_nykwas.json

Their reel: hall title card (two faces, two scores), 2-game zones (theirs, then ours), game-1 team stat card,
game-2 star's shot dots, game-2 late moment (three faces + clock chip), "now the fixes" x3 (cluster + bar card,
made/tried card, big number card), next-opponent hall, standings card, next-game date chip. 53.7 s, 14 voice lines.

Every number comes from ESPN (summary box score + play-by-play shot log, standings, schedule). The story picks
(which game stat, which fixes, which late moment) are per team in STORY below, chosen by reading the two games;
the numbers are computed here, and each pick is asserted against the play-by-play so a wrong pick stops the build.
"""
import sys, json, pathlib, argparse, collections, os, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import espn
import shotchart as S
from shotchart import w, ws, ABC

ROOT = pathlib.Path(__file__).resolve().parent.parent
STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
def ordn(n): return f"{n}" + ({1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH") if n % 100 not in (11, 12, 13) else "TH")
ORDW = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth", 15: "fifteenth"}

# Per-team story picks (2026-11-19 build). Event ids: our last two games and the next one (espn.schedule).
STORY = {
    "raptors": {"g": ["401910002", "401910012"], "next": "401909308",
                "g1stat": "reb",                       # Tuesday: the Knicks won the glass
                "star2": "4431893", "star2_stat": "tp",   # Jamison Battle, 5 threes
                # late moment: Walter layup to make it 3, Dybantsa turnover with 21.9 left, Battle misses a three to tie
                "moment": {"plays": ["Ja'Kobe Walter makes driving layup", "AJ Dybantsa out of bounds lost ball turnover", "Jamison Battle misses 27-foot three point jumper"],
                           "faces": [("4684272", "WALTER", ""), ("5142718", "DYBANTSA", "TURNOVER"), ("4431893", "BATTLE", "")]},
                "fixes": ["ft2", "rim_g2", "q4"], "split_n": True, "tts_speed": 1.3, "minp": .38, "music": "sc134",
                "absent": {"ids": ["4433134", "4395625"], "games": [1], "line": "NO BARNES OR BARRETT."}},   # fix 3's portrait (theirs: the player who sat)
    "warriors": {"g": ["401910000", "401910016"], "next": "401910019",
                 "g1stat": "ft",                       # Monday: we won the line and still lost by 21
                 "star2": "4897262", "star2_stat": "fg",  # Will Richard 9 of 13
                 # Dallas' 12-0 run after 6-6 in the first
                 "run": {"game": 1, "from": [6, 6], "n": 12, "scorers": ["Kyrie Irving", "P.J. Washington", "Cooper Flagg", "Caleb Martin"],
                         "faces": [("6442", "IRVING", ""), ("4278078", "WASHINGTON", ""), ("5041939", "FLAGG", "DUNK")]},
                 "fixes": ["tp2", "ft_g2", "to_g1"], "split_n": True, "split_z": True,
                 "absent": {"ids": ["3975"], "games": [0, 1], "line": "NO CURRY, BOTH GAMES."}},   # "Two." / "Three." as their own lines (whisper line count)
}
SHORT_SAY = {"NY": "the Knicks", "WSH": "the Wizards", "NO": "the Pelicans", "DAL": "the Mavericks"}


def game(slug, ev):
    s, url = S.load(ev); my = str(espn.TEAMS[slug]); hdr = s["header"]["competitions"][0]
    comp = {str(c["team"]["id"]): c for c in hdr["competitors"]}; op = next(k for k in comp if k != my)
    st = {str(t["team"]["id"]): {x["name"]: x.get("displayValue") for x in t["statistics"]} for t in s["boxscore"]["teams"]}
    SH, FT = S.parse(s, comp)
    day, _ = espn.when(hdr["date"])
    return {"s": s, "url": url, "my": my, "op": op, "abbr": {k: comp[k]["team"]["abbreviation"] for k in comp}, "sc": {k: int(comp[k]["score"]) for k in comp},
            "lines": {k: [int(l.get("displayValue")) for l in comp[k].get("linescores", [])] for k in comp}, "TB": S.team_box(s), "BX": S.box_rows(s), "SH": SH, "st": st,
            "day": day.split()[0].upper(), "date": day.split()[1], "dayw": {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday"}[day.split()[0].upper()],
            "loc": S.team_meta(op)["loc"], "short": S.team_meta(op)["short"], "home": comp[my]["homeAway"] == "home"}


def standings():
    d = espn.get(STANDINGS); out = {}
    for conf in d["children"]:
        rows = []
        for e in conf["standings"]["entries"]:
            stt = {x["name"]: x for x in e["stats"]}
            rows.append({"abbr": e["team"]["abbreviation"], "id": str(e["team"]["id"]), "w": int(stt["wins"]["value"]), "l": int(stt["losses"]["value"]),
                         "pct": float(stt["winPercent"]["value"]), "seed": int(stt["playoffSeed"]["value"]), "diff": stt["pointDifferential"]["displayValue"], "conf": conf["abbreviation"]})
        rows.sort(key=lambda r: r["seed"])
        for r in rows: out[r["id"]] = dict(r, table=rows)
    return out


def build(slug):
    P = STORY[slug]; G = [game(slug, e) for e in P["g"]]; my = G[0]["my"]
    US = S.team_meta(my); UA = US["abbr"]; claims = []
    usc, themc = S.pick_colors(US, S.team_meta(G[0]["op"]))
    if S.dist(usc, "#9d3431") > 160: themc = "#9d3431"   # two different opponents: their Blazers red stands for "them" unless it's too close to ours
    OL = ["l:" + g_["abbr"][g_["op"]] for g_ in G]; UL = "l:" + UA
    res = [(g_["sc"][my], g_["sc"][g_["op"]]) for g_ in G]
    wins = sum(a > b for a, b in res); losses = 2 - wins; tot = sum(a - b for a, b in res)
    for g_ in G:
        o = g_["op"]; m = g_["my"]
        claims.append(f"{g_['day']} {g_['date']}: {UA} {g_['sc'][m]}, {g_['abbr'][o]} {g_['sc'][o]} ({g_['url']}). Box: {UA} FG {'-'.join(map(str, g_['TB'][m]['fg']))}, 3PT {'-'.join(map(str, g_['TB'][m]['tp']))}, FT {'-'.join(map(str, g_['TB'][m]['ft']))}, REB {g_['TB'][m]['reb']}, TO {g_['st'][m]['totalTurnovers']}, points conceded off turnovers {g_['st'][m]['turnoverPoints']}; "
                      f"{g_['abbr'][o]} FG {'-'.join(map(str, g_['TB'][o]['fg']))}, 3PT {'-'.join(map(str, g_['TB'][o]['tp']))}, FT {'-'.join(map(str, g_['TB'][o]['ft']))}, REB {g_['TB'][o]['reb']}. Linescore {UA} {' '.join(map(str, g_['lines'][m]))}, {g_['abbr'][o]} {' '.join(map(str, g_['lines'][o]))}.")
    n_say = w(abs(tot))
    # ---- combined zones
    uz = collections.OrderedDict((k, [0, 0]) for k in S.ZORDER); tz = collections.OrderedDict((k, [0, 0]) for k in S.ZORDER)
    for g_ in G:
        for k, m_, a_ in S.zones_of(g_["SH"][g_["my"]]): uz[k][0] += m_; uz[k][1] += a_
        for k, m_, a_ in S.zones_of(g_["SH"][g_["op"]]): tz[k][0] += m_; tz[k][1] += a_
    ufg = [sum(g_["TB"][my]["fg"][i] for g_ in G) for i in (0, 1)]; tfg = [sum(g_["TB"][g_["op"]]["fg"][i] for g_ in G) for i in (0, 1)]
    for nm, z, fg in (("us", uz, ufg), ("opp", tz, tfg)):
        if (sum(v[0] for v in z.values()), sum(v[1] for v in z.values())) != tuple(fg): sys.exit(f"{nm}: zone tiles don't add up to the box-score FG {fg}")
    claims.append(f"Two games combined (box score): {UA} FG {ufg[0]}-{ufg[1]}, opponents FG {tfg[0]}-{tfg[1]}. Zones from the play-by-play shot logs, both games: {UA} " + ", ".join(f"{k} {m_}/{a_}" for k, (m_, a_) in uz.items()) + "; opponents " + ", ".join(f"{k} {m_}/{a_}" for k, (m_, a_) in tz.items()) + ".")
    # ---- next opponent + standings
    nxt = next(e for e in espn.schedule(my) if e["id"] == P["next"]); nday, ntime = espn.when(nxt["date"])
    ST = standings(); me = ST[my]; no = ST[str(nxt["opp_id"])]; NA = no["abbr"]; NSHORT = S.team_meta(nxt["opp_id"])["short"]
    allt = sorted(ST.values(), key=lambda r: -float(r["diff"].replace("+", "")))
    met = [e for e in espn.schedule(my) if str(e["opp_id"]) == str(nxt["opp_id"]) and e["state"] == "post"]
    claims.append(f"ESPN standings ({STANDINGS}): {UA} {me['w']}-{me['l']}, {me['seed']} in the {me['conf']}; {NA} {no['w']}-{no['l']}, {no['seed']} in the {no['conf']}, point differential {no['diff']}. "
                  + f"{me['conf']} seeds {me['seed'] - 1}-{me['seed'] + 1}: " + ", ".join(f"{r['seed']}. {r['abbr']} {r['w']}-{r['l']}" for r in me["table"] if abs(r["seed"] - me["seed"]) <= 1) + ".")
    claims.append(f"ESPN schedule: next game {UA} {'vs' if nxt['home'] else 'at'} {NA}, {nday} {ntime} ET (event {nxt['id']})." + (f" Earlier meeting {met[-1]['id']}: {UA} {met[-1]['my']}, {NA} {met[-1]['their']} on {espn.when(met[-1]['date'])[0]}." if met else f" No earlier meeting this season."))
    neigh = [r for r in me["table"] if abs(r["seed"] - me["seed"]) <= 1]

    B = []
    cfg = {"us": UL, "them": OL, "usc": usc, "themc": themc}
    # 1 hook hall
    star1 = max((r for r in G[0]["BX"].values() if r["tid"] == my), key=lambda r: r["pts"]); star2 = G[1]["BX"][P["star2"]]
    head = ("SWEPT BOTH. " if wins == 2 else "LOST BOTH. " if losses == 2 else "SPLIT. ") + f"BY {abs(tot)} TOTAL."
    vo1 = ("We swept both games this week" if wins == 2 else "We lost both games this week" if losses == 2 else "We split two games this week") + (f", by {n_say} points total." if abs(tot) < 20 else f", by {n_say} total.")
    d1 = ("WE WON BOTH GAMES." if wins == 2 else "WE LOST BOTH GAMES." if losses == 2 else "WE SPLIT TWO GAMES.") + f"|BY {abs(tot)} POINTS. TOTAL."
    B.append({"kind": "sc2_hall", "cfg": cfg, "full": True, "pal": "pink", "ban": OL[0], "plate": head, "faces": [{"pk": "p:" + star1["id"], "nm": star1["last"]}, {"pk": "p:" + star2["id"], "nm": star2["last"]}], "wm": OL[1],
              "scores": [f"{g_['day']} {g_['sc'][my]}-{g_['sc'][g_['op']]}" for g_ in G], "dlg": d1, "vo": vo1})
    # 2 title
    B.append({"kind": "sc2_title", "sb": [wins, losses], "sbl": OL, "head2": "2-GAME SHOT CHART", "chip": "3 THINGS TO FIX", "dlg": "THE 2-GAME SHOT CHART|+ 3 THINGS TO FIX.",
              "vo": f"Here's the two game shot chart, and the three things we have to fix before the {NSHORT}." if len(NSHORT) < 8 else f"Here's the two game shot chart, and three things to fix before the {NSHORT}."})
    # 3 zones
    B.append({"kind": "sc2_zones", "sb": [wins, losses], "sbl": OL, "tz": [{"z": k, "v": f"{m_}/{a_}"} for k, (m_, a_) in tz.items() if a_], "uz": [{"z": k, "v": f"{m_}/{a_}"} for k, (m_, a_) in uz.items() if a_],
              "tfoot": f"OPP: {tfg[0]}/{tfg[1]} FG", "ufoot": f"{UA}: {ufg[0]}/{ufg[1]} FG", "dlg": f"OPPONENTS: {tfg[0]} MADE.", "dlg2": f"OPPONENTS: {tfg[0]} MADE.|US: {ufg[0]} MADE.",
              "vo": f"Our opponents made {w(tfg[0])} shots" + (". / We" if P.get("split_z") else ", we") + f" made {w(ufg[0])}."})
    # 4 game-1 team stat
    g1 = G[0]; m, o = g1["my"], g1["op"]; oa = g1["abbr"][o]
    if P["g1stat"] == "reb":
        ur, orr = g1["TB"][m]["reb"], g1["TB"][o]["reb"]; assert orr > ur
        card = {"title": "REBOUNDS", "rows": [{"l": "l:" + oa, "v": orr}, {"l": UL, "v": ur, "us": True}]}
        vo4 = f"{g1['dayw']}, {SHORT_SAY.get(oa, g1['short'])} won the glass, {w(orr)} rebounds to {w(ur)}."; d4 = f"{g1['day']}: THE GLASS.|{orr} REBOUNDS TO {ur}."
    else:
        uf, of = g1["TB"][m]["ft"], g1["TB"][o]["ft"]; assert uf[0] > of[0]
        card = {"title": "FREE THROWS: MADE / TRIED", "mode": "ma", "rows": [{"l": UL, "m": uf[0], "a": uf[1], "us": True}, {"l": "l:" + oa, "m": of[0], "a": of[1]}]}
        vo4 = f"{g1['dayw']}, we won the line, {w(uf[0])} free throws to {w(of[0])}."; d4 = f"{g1['day']}: WE WON THE LINE.|{uf[0]} FREE THROWS TO {of[0]}."
    B.append({"kind": "sc2_bars", "sb": [g1["sc"][m], g1["sc"][o]], "sbl": "l:" + oa, "head2": f"{g1['day']} {g1['date']}: {g1['sc'][m]}-{g1['sc'][o]}", "card": card, "dlg": d4, "vo": vo4})
    # 5 game-2 star
    g2 = G[1]; m2, o2 = g2["my"], g2["op"]; oa2 = g2["abbr"][o2]
    shots = [p for p in g2["SH"][m2] if p["pid"] == star2["id"]]
    if (sum(p["made"] for p in shots), len(shots)) != star2["fg"]: sys.exit(f"{star2['name']}: shot log doesn't match the box score")
    if P["star2_stat"] == "tp":   # theirs plots only the threes behind "3PT: 7/11"
        shots = [p for p in shots if p["three"]]
        if (sum(p["made"] for p in shots), len(shots)) != star2["tp"]: sys.exit(f"{star2['name']}: three-point shot log doesn't match the box score")
    shots = [p for p in shots if p["y"] >= -1]   # a few logged spots sit behind the baseline
    if P["star2_stat"] == "tp":
        vo5 = f"{g2['dayw']}, {star2['name']} hit {w(star2['tp'][0])} threes and scored {w(star2['pts'])}."; d5 = f"{g2['day']}: {star2['name'].upper()}.|{star2['tp'][0]} THREES. {star2['pts']} POINTS."; chip = f"3PT: {star2['tp'][0]}/{star2['tp'][1]}"
    else:
        vo5 = f"{g2['dayw']}, {star2['name']} made {w(star2['fg'][0])} of {w(star2['fg'][1])} and scored {w(star2['pts'])}."; d5 = f"{g2['day']}: {star2['name'].upper()}.|{star2['fg'][0]} OF {star2['fg'][1]}. {star2['pts']} POINTS."; chip = f"FG: {star2['fg'][0]}/{star2['fg'][1]}"
    B.append({"kind": "sc2_dots", "sb": [g2["sc"][m2], g2["sc"][o2]], "sbl": "l:" + oa2, "shots": S.enc_shots(shots), "chips": [chip], "pk": "p:" + star2["id"], "dlg": d5, "vo": vo5})
    # 6 the late moment / the run
    pl = g2["s"]["plays"]; away_is_us = g2["s"]["header"]["competitions"][0]["competitors"][0]["homeAway"] == "away" and str(g2["s"]["header"]["competitions"][0]["competitors"][0]["team"]["id"]) == my
    def sc_of(p): a, h = p["awayScore"], p["homeScore"]; return (a, h) if not g2["home"] else (h, a)   # (us, them)
    if "moment" in P:
        M = P["moment"]; idx = []
        k_to = next(i for i, p in enumerate(pl) if p["text"].startswith(M["plays"][1]) and p["period"]["number"] == 4)
        k_lay = max(i for i, p in enumerate(pl[:k_to]) if p["text"].startswith(M["plays"][0]))
        k_miss = next(i for i, p in enumerate(pl) if i > k_to and p["text"].startswith(M["plays"][2]))
        assert all(not pl[i].get("scoringPlay") for i in range(k_lay + 1, k_miss)), "someone scored between the layup and the miss"
        p_lay, p_to, p_miss = pl[k_lay], pl[k_to], pl[k_miss]
        u, t_ = sc_of(p_to); assert t_ - u == 3, (u, t_)
        clk = p_to["clock"]["displayValue"]; secs = round(float(clk)) if ":" not in clk else None; assert secs is not None
        claims.append(f"Play-by-play, 4th quarter: {p_lay['clock']['displayValue']} {p_lay['text']} (score {UA} {sc_of(p_lay)[0]}, {oa2} {sc_of(p_lay)[1]}); {clk} {p_to['text']}; {p_miss['clock']['displayValue']} {p_miss['text']}. Down {t_ - u} with {secs} seconds left; final {g2['sc'][m2]}-{g2['sc'][o2]}.")
        vo6 = f"Down {w(t_ - u)}, {w(secs)} seconds left. / Dybantsa lost it out of bounds, and Battle missed a three to tie."
        d6 = f"DOWN {t_ - u}, 0:{secs:02d} LEFT.|TURNOVER. MISSED 3."
        B.append({"kind": "sc2_moment", "sb": [u, t_], "sbl": "l:" + oa2, "chip": f"0:{secs:02d} TURNOVER", "faces": [{"pk": "p:" + a, "nm": n, "tg": tg} for a, n, tg in M["faces"]], "dlg": d6, "vo": vo6})
    else:
        R = P["run"]; sc_pl = [p for p in pl if p.get("scoringPlay")]
        i0 = next(i for i, p in enumerate(sc_pl) if list(sc_of(p)) == R["from"] and p["period"]["number"] == 1)
        run = []; base = sc_of(sc_pl[i0])
        for p in sc_pl[i0 + 1:]:
            u, t_ = sc_of(p)
            if u != base[0]: break
            run.append(p)
        assert sc_of(run[-1])[1] - base[1] == R["n"], (sc_of(run[-1]), base)
        BXn = {r["id"]: r["name"] for r in g2["BX"].values()}; names = sorted({BXn.get(str(p["participants"][0]["athlete"]["id"]), "?") for p in run if p.get("participants")})
        assert set(names) == set(R["scorers"]), names
        claims.append(f"Play-by-play, 1st quarter: tied {base[0]}-{base[1]} at {sc_pl[i0]['clock']['displayValue']}, then " + "; ".join(f"{p['clock']['displayValue']} {p['text']}" for p in run) + f". A {R['n']}-0 {oa2} run to {sc_of(run[-1])[1]}-{sc_of(run[-1])[0]}.")
        vo6 = f"Tied at {w(base[0])} in the first, {g2['loc']} ran off {w(R['n'])} straight. / Irving, Washington, Flagg and Martin all scored."
        d6 = f"TIED {base[0]}-{base[1]} IN THE 1ST.|THEN {R['n']}-0 {g2['loc'].upper()}."
        B.append({"kind": "sc2_moment", "sb": list(base), "sbl": "l:" + oa2, "chip": f"1ST Q: {R['n']}-0 RUN", "faces": [{"pk": "p:" + a, "nm": n, "tg": tg} for a, n, tg in R["faces"]], "dlg": d6, "vo": vo6})
    # 7 fixes
    FX = []
    for j, fx in enumerate(P["fixes"], 1):
        if fx == "ft2":
            um = sum(g_["TB"][my]["ft"][0] for g_ in G); ua_ = sum(g_["TB"][my]["ft"][1] for g_ in G); om = sum(g_["TB"][g_["op"]]["ft"][0] for g_ in G); oa_ = sum(g_["TB"][g_["op"]]["ft"][1] for g_ in G)
            claims.append(f"Free throws, both games (box score): {UA} {um}-{ua_}, opponents {om}-{oa_}.")
            # their FTs drawn at the line: made dots and missed rings in a tight jittered cluster (free throws have no shot location)
            import random; rnd = random.Random(7); clu = ""
            for k in range(oa_):
                x = 25 + rnd.choice([-2, -1, -1, 0, 0, 0, 1, 1, 2]); y = 14 + rnd.choice([-1, 0, 0, 1]); clu += ABC[x] + ABC[y + 5] + ("+" if k < om else ".")
            FX.append(dict(name="FREE THROWS", say="Free throws", lg="them", head=f"FIX {j} OF 3: FREE THROWS", d1=f"{j}: FREE THROWS.|THEM {om} MADE, US {um}.",
                           vo2=f"Our opponents hit {w(om)}, we hit {w(um)}.", clu=clu, card={"title": "FREE THROWS MADE, 2 GAMES", "rows": [{"l": OL, "v": om}, {"l": UL, "v": um, "us": True}]}))
        elif fx == "tp2":
            um = sum(g_["TB"][my]["tp"][0] for g_ in G); om = sum(g_["TB"][g_["op"]]["tp"][0] for g_ in G)
            clu = "".join(S.enc_shots([p for p in g_["SH"][g_["op"]] if p["three"]]) for g_ in G)
            mk = sum(1 for k in range(2, len(clu), 3) if clu[k] == "+"); assert mk == om, (mk, om)
            claims.append(f"Threes made, both games (box score): {UA} {um}, opponents {om}.")
            FX.append(dict(name="THE THREE", say="The three", lg="them", head=f"FIX {j} OF 3: THE THREE", d1=f"{j}: THE THREE.|THEM {om} MADE, US {um}.",
                           vo2=f"Our opponents hit {w(om)}, we hit {w(um)}.", clu=clu, card={"title": "THREES MADE, 2 GAMES", "rows": [{"l": OL, "v": om}, {"l": UL, "v": um, "us": True}]}))
        elif fx == "rim_g2":
            zu = dict((k, (m_, a_)) for k, m_, a_ in S.zones_of(g2["SH"][m2])); zo = dict((k, (m_, a_)) for k, m_, a_ in S.zones_of(g2["SH"][o2]))
            claims.append(f"{g2['day']} {g2['date']} play-by-play shot log, within 5 ft of the rim: {UA} {zu['RIM'][0]}/{zu['RIM'][1]}, {oa2} {zo['RIM'][0]}/{zo['RIM'][1]}.")
            FX.append(dict(name="THE RIM", say="The rim", lg="us", head=f"FIX {j} OF 3: THE RIM", d1=f"{j}: THE RIM.|{g2['day']}: {zu['RIM'][0]} OF {zu['RIM'][1]}.",
                           vo2=f"The rim. / {g2['dayw']}, we went {w(zu['RIM'][0])} for {w(zu['RIM'][1])}.", card={"title": f"{g2['day']} {g2['date']} AT THE RIM: MADE / TRIED", "mode": "ma",
                           "rows": [{"l": UL, "m": zu['RIM'][0], "a": zu['RIM'][1], "us": True}, {"l": "l:" + oa2, "m": zo['RIM'][0], "a": zo['RIM'][1]}]}, two=True))
        elif fx == "ft_g2":
            uf, of = g2["TB"][m2]["ft"], g2["TB"][o2]["ft"]
            FX.append(dict(name="FREE THROWS", say="Free throws", lg="us", head=f"FIX {j} OF 3: FREE THROWS", d1=f"{j}: FREE THROWS.|{g2['day']}: {uf[0]} OF {uf[1]}.",
                           vo2=f"Free throws. / {g2['dayw']}, we went {w(uf[0])} for {w(uf[1])}.", card={"title": f"{g2['day']} {g2['date']}: MADE / TRIED", "mode": "ma",
                           "rows": [{"l": UL, "m": uf[0], "a": uf[1], "us": True}, {"l": "l:" + oa2, "m": of[0], "a": of[1]}]}, two=True))
        elif fx == "q4":
            u4 = sum(g_["lines"][my][3] for g_ in G); o4 = sum(g_["lines"][g_["op"]][3] for g_ in G)
            led = all(sum(g_["lines"][my][:3]) > sum(g_["lines"][g_["op"]][:3]) for g_ in G); assert led
            claims.append(f"Linescores: after three quarters {UA} led both games (" + ", ".join(f"{sum(g_['lines'][my][:3])}-{sum(g_['lines'][g_['op']][:3])}" for g_ in G) + f"); 4th quarters {UA} " + " + ".join(str(g_['lines'][my][3]) for g_ in G) + f" = {u4}, opponents {o4}.")
            FX.append(dict(name="4TH QUARTERS", say="", lg="us", head=f"FIX {j} OF 3: 4TH QUARTERS", d1=f"{j}: {u4} PTS IN TWO 4THS.|WE LED BOTH AFTER 3.",
                           vo2=f"{w(u4).capitalize()} fourth quarter points, after leading both through three.", big={"title": "OUR 4TH QUARTER POINTS, 2 GAMES", "v": u4}, three=True))
        elif fx == "to_g1":
            to = int(g1["st"][m]["totalTurnovers"]); tp_ = int(g1["st"][m]["turnoverPoints"])
            FX.append(dict(name="TURNOVERS", say="", lg="us", head=f"FIX {j} OF 3: TURNOVERS", d1=f"{j}: {to} TURNOVERS {g1['day']}.|{tp_} POINTS OFF THEM.",
                           vo2=f"{w(to).capitalize()} turnovers {g1['dayw']}, {w(tp_)} points off them.", big={"title": f"OUR TURNOVERS, {g1['day']} {g1['date']}", "v": to}, three=True))
    say_n = {1: "One", 2: "Two", 3: "Three"}
    for j, f in enumerate(FX, 1):
        if j == 1:   # "Now the fixes. One. Free throws." -> banner flips to FIX 1 at 0.7 s (theirs: 26.0 -> 26.7)
            B.append({"kind": "sc2_fix", "head": "NOW THE FIXES", "headB": f["head"], "lg": f["lg"], "dlg": "NOW THE FIXES.", "dlg2": f["d1"], "vo": f"Now the fixes. / One, {f['say'].lower()}."})
            B.append({"kind": "sc2_fix", "head": f["head"], "lg": f["lg"], "clu": {"shots": f["clu"], "side": "them"}, "card": f["card"], "dlg": f["d1"], "dcont": True, "vo": f["vo2"]})
        else:        # "Two. <line>": banner first, the card 0.55 s in (theirs: 32.1 -> 32.6, 36.4 -> 37.0)
            b = {"kind": "sc2_fix", "head": f["head"], "lg": f["lg"], "late": True, "dlg": f["d1"], "vo": f"{say_n[j]}. " + ("/ " if P.get("split_n") else "") + f["vo2"]}
            if f.get("card"): b["card"] = f["card"]
            if f.get("big"): b["big"] = f["big"]
            if j == 3 and P.get("absent"):
                A = P["absent"]
                for gi in A["games"]:
                    for aid in A["ids"]: assert aid not in G[gi]["BX"], f"{aid} has a box-score line in game {gi}"
                claims.append("Did not play (no line in the ESPN box score): " + ", ".join(f"athlete {aid}" for aid in A["ids"]) + " in " + " and ".join(f"{G[gi]['day']} {G[gi]['date']}" for gi in A["games"]) + ".")
                b["face"] = "p:" + A["ids"][0]; b["dlg"] = b["dlg"].split("|")[0] + "|" + A["line"]
            B.append(b)
    # 8 next opponent hall, standings, date
    rec_w = lambda a, b: f"{w(a)} and {w(b)}"
    vo_n = f"The {NSHORT} are {rec_w(no['w'], no['l'])}, plus {ws(no['diff'].lstrip('+'))}"
    if met:
        mm = met[-1]; wl = int(mm["my"]) > int(mm["their"])
        vo_n += f". / {'We beat them' if wl else 'We lost to them'} by {w(abs(int(mm['my']) - int(mm['their'])))} in {['January','February','March','April','May','June','July','August','September','October','November','December'][int(mm['date'][5:7]) - 1]}."
        d_n = f"{NSHORT.upper()}: {no['w']}-{no['l']}.|LOST {mm['my']}-{mm['their']} IN OCT." if not wl else f"{NSHORT.upper()}: {no['w']}-{no['l']}.|WE BEAT THEM {mm['my']}-{mm['their']}."
    else:
        vo_n += ". / We haven't played them yet."; d_n = f"{NSHORT.upper()}: {no['w']}-{no['l']}.|{ordn(no['seed'])} IN THE {no['conf'].upper()}, {no['diff']}."
    B.append({"kind": "sc2_hall", "pal": "blue", "ban": "l:" + NA, "pills": [f"{NA} {no['w']}-{no['l']}", f"{no['diff']} DIFF"], "ped": "l:" + NA, "ul": True, "dlg": d_n, "vo": vo_n})
    today = __import__("datetime").datetime.now(espn.ET).strftime("%a %-m/%-d")
    when_say = "tonight" if nday == today else {"Mon": "on Monday", "Tue": "on Tuesday", "Wed": "on Wednesday", "Thu": "on Thursday", "Fri": "on Friday", "Sat": "on Saturday", "Sun": "on Sunday"}[nday.split()[0]]
    stand = {"title": f"{me['conf'].upper()} STANDINGS", "rows": [[f"{r['seed']}. {r['abbr']} {r['w']}-{r['l']}", r["id"] == my] for r in neigh]}
    confw = "East" if me["conf"] == "East" else "West"
    B.append({"kind": "sc2_hall", "pal": "blue", "ban": "l:" + NA, "ped": "l:" + NA, "ul": True, "stand": stand, "dlg": f"WE'RE {me['w']}-{me['l']}, {ordn(me['seed'])} {me['conf'].upper()}.|{NSHORT.upper()} {when_say.upper()}.", "vo": f"We're {rec_w(me['w'], me['l'])}, {ORDW[me['seed']]} in the {confw}."})
    rw = ("wins" if wins == 2 else "losses" if losses == 2 else "games")
    B.append({"kind": "sc2_hall", "pal": "blue", "ban": "l:" + NA, "ped": "l:" + NA, "ul": True, "stand": stand, "cont": True, "dcont": True, "date": {"txt": f"{nday.upper()}, {ntime} ET"},
              "dlg": f"WE'RE {me['w']}-{me['l']}, {ordn(me['seed'])} {me['conf'].upper()}.|{NSHORT.upper()} {when_say.upper()}.", "vo": f"Two {rw}, plenty of tape, {NSHORT} {when_say}."})
    # ---- caption (theirs: title + emoji, 5 bullets, "The 3 fixes:" + 3 numbered, closing, question; no merch)
    gl = " · ".join(f"{g_['day']} {g_['date']}: {S.team_meta(g_['op'])['short']} {g_['sc'][g_['op']]}, {US['short']} {g_['sc'][my]}" if g_["sc"][g_["op"]] > g_["sc"][my] else f"{g_['day']} {g_['date']}: {US['short']} {g_['sc'][my]}, {S.team_meta(g_['op'])['short']} {g_['sc'][g_['op']]}" for g_ in G)
    bl = [f"🗓️ {gl}", f"🎯 2 games: our opponents made {tfg[0]} shots, we made {ufg[0]}"]
    if P["g1stat"] == "reb": bl.append(f"🧾 {g1['dayw']} was lost on the glass: {card['rows'][0]['v']} rebounds to {card['rows'][1]['v']}")
    else: bl.append(f"🧾 {g1['dayw']} we won the line, {card['rows'][0]['m']} free throws to {card['rows'][1]['m']}, and still lost by {g1['sc'][o] - g1['sc'][m]}")
    bl.append(f"🔥 {star2['name']} {g2['dayw']}: {star2['pts']} PTS, " + (f"{star2['tp'][0]} of {star2['tp'][1]} from three" if P["star2_stat"] == "tp" else f"{star2['fg'][0]} of {star2['fg'][1]} from the floor"))
    if "moment" in P: bl.append(f"⏱️ Down {t_ - u} with {secs} seconds left: Ja'Kobe Walter had just scored, AJ Dybantsa lost it out of bounds, Jamison Battle's three to tie missed")
    else: bl.append(f"⏱️ Tied {base[0]}-{base[1]} in the 1st, then {R['n']} straight for {g2['loc']}: Irving, Washington, Flagg, Martin")
    caps = []
    for j, f in enumerate(FX, 1):
        e = ["1️⃣", "2️⃣", "3️⃣"][j - 1]
        if f["name"] == "FREE THROWS" and "clu" in f: caps.append(f"{e} Free throws: they made {f['card']['rows'][0]['v']} in 2 games, we made {f['card']['rows'][1]['v']}")
        elif f["name"] == "THE THREE": caps.append(f"{e} The three: they made {f['card']['rows'][0]['v']} in 2 games, we made {f['card']['rows'][1]['v']}")
        elif f["name"] == "THE RIM": r0 = f["card"]["rows"][0]; caps.append(f"{e} The rim: {r0['m']} of {r0['a']} on {g2['dayw']}")
        elif f["name"] == "FREE THROWS": r0 = f["card"]["rows"][0]; caps.append(f"{e} Free throws: {r0['m']} of {r0['a']} on {g2['dayw']}")
        elif f["name"] == "4TH QUARTERS": caps.append(f"{e} 4th quarters: {f['big']['v']} points in 2, after leading both games through 3")
        elif f["name"] == "TURNOVERS": caps.append(f"{e} Turnovers: {f['big']['v']} on {g1['dayw']}, and {g1['loc']} scored {g1['st'][m]['turnoverPoints']} off them")
    head_cap = ("WE SWEPT BOTH. " if wins == 2 else "WE LOST BOTH. " if losses == 2 else "WE SPLIT TWO. ") + f"BY {abs(tot)} POINTS TOTAL. {S.EMO.get(slug, '🏀')} The shot chart says we've got work to do before the {NSHORT}."
    close = f"The {NSHORT} are {no['w']}-{no['l']}, {ordn(no['seed']).lower()} in the {no['conf']} at {no['diff']}" + (f", and we lost to them {mm['my']}-{mm['their']} on {espn.when(mm['date'])[0].split()[1]}." if met and not wl else ", and we haven't played them yet.") + f" We're {me['w']}-{me['l']}, {ordn(me['seed']).lower()} in the {me['conf']}. Next: {NSHORT}, {nday.upper()} · {ntime} ET."
    cap = f"{head_cap}\n\n" + "\n".join(bl) + "\n\nThe 3 fixes:\n" + "\n".join(caps) + f"\n\n{close}\n\nWhich fix matters most against {no_loc(nxt)}?"
    facts = [{"game": g_["s"]["header"]["id"], "score": f"{max(g_['sc'].values())}-{min(g_['sc'].values())}"} for g_ in G]
    for pid, stl in ((star2["id"], ("PTS", "FG", "3PT")),):
        for st_ in stl: facts.append({"game": G[1]["s"]["header"]["id"], "player": pid, "stat": st_, "value": G[1]["BX"][pid]["box"][st_]})
    ids = {}
    for b in B:
        for f in b.get("faces", []): ids[f["pk"][2:]] = f["nm"]
        for k in ("pk",):
            if b.get(k): ids[b[k][2:]] = b.get("nm", "")
    claims.append(f"Two-game record {wins}-{losses}, total margin {' + '.join(str(abs(a - b)) for a, b in res)} = {abs(tot)}. The fixes are numbered 1 of 3 to 3 of 3 on screen. "
                  "Portraits are ESPN athlete ids from the box scores: " + ", ".join(f"{G[0]['BX'].get(k, G[1]['BX'].get(k, {})).get('name', k)} {k}" for k in ids) + ".")
    facts.append({"claim": " ".join(claims), "source": G[0]["url"]})
    spec = {"team": slug, "name": "sc2_" + "".join(S.ABBR3.get(g_["abbr"][g_["op"]], g_["abbr"][g_["op"]].lower()) for g_ in G), "template": "fmt_sc2.html", "music": P.get("music", "sc130"), "duck_bridge": True, "duck_depth": 0.9, "cps": 40, "voice_eq": "bright",
            "pace": "wolves", "tts_speed": P.get("tts_speed", 1.3), "minp": P.get("minp", MINP), "record": f"{me['w']}-{me['l']}", "caption": cap, "beats": B, "facts": facts}
    for b in B:
        for k in ("dlg", "dlg2"):
            for ln in str(b.get(k) or "").split("|"):
                if len(ln) > 22: print(f"REVIEW: dialog line over 22 chars (the box would shrink the font): {ln}")
    out = []
    for b in B:
        parts = [x.strip() for x in b.get("vo", "").split(" / ")]
        b["vo"] = S.say(parts[0]); out.append(b)
        for x in parts[1:]: out.append({"kind": b["kind"], "more": True, "vo": S.say(x)})   # same scene, its own voice line (their whisper splits here)
    spec["beats"] = out
    return spec


def no_loc(nxt): return S.team_meta(nxt["opp_id"])["loc"]


# Their scene starts (research/mirror/2026-11-18/Df5dkpDg76T_trace/trace.md) = where each of our lines must end.
THEIR_ENDS = [3.10, 7.50, 11.50, 15.30, 19.30, 26.00, 28.90, 32.10, 36.40, 41.70, 47.60, 50.10, 53.10]
GAP = .12   # history.py's gap in wolves pace
MINP = .46  # whisper (the copy check's line count) only splits lines reliably with >= 0.5 s of quiet between them (pad + GAP)


def fit(spec):
    """Voice every line as history.py will (Kokoro, wolves pace, spec tts_speed) and add silent pads so each scene's
    last line ends on their beat. "more" beats (the same scene's next sentence) get a 0.15 s pad before them so the
    pause is audible like theirs. In wolves pace a line followed by a pad has no gap; the pad is followed by GAP."""
    MINP = float(os.environ.get("SC2_MINP", spec.get("minp", globals()["MINP"])))   # search knob (cache/_sc2_sim.py); per team in STORY
    if os.environ.get("SC2_SPEED"): spec["tts_speed"] = float(os.environ["SC2_SPEED"])
    spec["minp"] = MINP
    B = spec["beats"]; ends = list(THEIR_ENDS); heads = [i for i, b in enumerate(B) if not b.get("more")]
    if len(heads) == len(ends) - 1: del ends[11]
    if len(heads) != len(ends): print(f"REVIEW: {len(heads)} scenes, expected {len(ends)}"); return spec
    d = ROOT / "cache" / f"scfit_{spec['team']}_{spec['name']}"; d.mkdir(parents=True, exist_ok=True)
    lj = d / "lines.json"; lj.write_text(json.dumps([{"id": f"b{i}", "text": b["vo"]} for i, b in enumerate(B)]))
    env = dict(os.environ, KOKORO_SPEED=str(spec.get("tts_speed", 1.25)), KOKORO_TRIM="1")
    durs = json.loads(subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts.py"), str(lj), str(d)], capture_output=True, text=True, check=True, env=env).stdout.strip().splitlines()[-1])
    out, t = [], 0.0
    for hi, e in zip(range(len(heads)), ends):
        i0 = heads[hi]; i1 = heads[hi + 1] if hi + 1 < len(heads) else len(B)
        for i in range(i0, i1):
            b = B[i]; dv = durs[f"b{i}"]; out.append(b)
            if i < i1 - 1: out.append({"kind": b["kind"], "pad": True, "hold": MINP, "vo": ""}); t += dv + MINP + GAP; continue
            hold = max(MINP, e - (t + dv) - GAP) if i < len(B) - 1 else e - (t + dv) - GAP   # every line gets >= 0.5 s of quiet after it
            if hold >= .1: out.append({"kind": b["kind"], "pad": True, "hold": round(hold, 3), "vo": ""}); t += dv + hold + GAP
            else: t += dv + GAP
            if t - e > .3: print(f"REVIEW: scene {hi} ends at {t:.2f} s, theirs at {e:.2f} s (shorten it): {b['vo']}")
    spec["beats"] = out
    print(f"fitted: last line ends {t:.2f} s (theirs {ends[-1]}), reel about {t + .6:.1f} s")
    return spec


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("team"); ap.add_argument("--out"); ap.add_argument("--no-fit", action="store_true")
    a = ap.parse_args(); spec = build(a.team)
    if not a.no_fit: spec = fit(spec)
    out = pathlib.Path(a.out) if a.out else ROOT / "specs" / f"{a.team[0]}_{spec['name']}.json"
    out.write_text(json.dumps(spec, indent=1, ensure_ascii=False)); print(out)
    print("\n".join(f"  {i:2d} {b['kind']:10s} {('pad ' + str(b['hold'])) if b.get('pad') else b.get('vo', '')}" for i, b in enumerate(spec["beats"])))
