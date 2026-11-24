"""Build specs/r_best_ever.json and specs/w_best_ever.json (copy of @8bitwolves Df5806FgG18, "Is this the best Wolves team ever?")
from data/sim/<team>_h2h_<DATE>.json (gen/sim_h2h.py).

Every number on screen / in the caption is read from the sim file and listed as a {"sim": ...} fact, or cited as a claim.
Silent hold beats are inserted so each beat starts where theirs does (WANT = their scene/page times from the copy_check trace).
Hold lengths use our Kokoro line durations in data/sim/<team>_best_ever_vo_durs.json; re-measure after changing any "vo":
  python3 gen/sim_h2h_spec.py --tts
"""
import json, pathlib, subprocess, os, sys, re
ROOT = pathlib.Path("/Users/ryanhelou/Developer/8bitraptors")
DATE = "2026-11-19"
NAME = "best_ever"
TOTAL = 48.3
PAUSE = 0.55

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def wd(n):
    """0-99 as words for the narrator (Kokoro reads spelled numbers most naturally)."""
    n = int(round(n))
    if n < 20: return ONES[n]
    return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])


def vo_nums(s):
    s = s.replace("2019", "twenty nineteen").replace("2016", "twenty sixteen").replace("10,000", "ten thousand")
    return re.sub(r"\b(\d{1,2})\b", lambda m: wd(int(m.group(1))), s)


def load(team):
    rel = f"data/sim/{team}_h2h_{DATE}.json"
    return rel, json.loads((ROOT / rel).read_text())


def getp(d, path):
    v = d
    for k in path.split("."): v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def pl(o, side, name):
    L = o["great_players" if side == "old" else "today_players"]
    return next(i for i, p in enumerate(L) if p["name"] == name)


# their scene / page starts (s), from research/mirror/2026-11-18/Df5806FgG18_trace + frame study
#   town 0 | p2 6.0 | room 9.4 | p2 13.3 | lab 15.4 | results 18.4 | p2 20.6 | gym 25.8 | p2 30.2 | today 33.5 | game 7 38.1 | route 42.3 | p2 44.5 | last line 46.3
WANT = [0, 2.55, 6.0, 9.4, 13.45, 15.32, 18.4, 20.6, 25.8, 29.6, 33.5, 38.1, 42.25, 44.5, 46.3]


def build(team):
    rel, d = load(team); o = d["outputs"]; I = d["inputs"]; facts = []
    def f(path, said=""):
        v = getp(d, path)
        if isinstance(v, (int, float)) and not isinstance(v, bool): said = (said + f" | shown as {round(v)} / {v:.1f}").strip(" |")
        facts.append({"sim": rel, "path": path, "value": v, "said": said}); return v
    R = team == "raptors"
    yr = I["great"]["label"]; ssn = I["great"]["season"]
    runs = f("runs", "10,000 sims / series, ten thousand")
    f("inputs.great.season", f"{ssn} ({yr})")
    gw, gl = f("inputs.great.w", "58-24 / 73-9"), f("inputs.great.l", "58-24 / 73-9")
    gm = f("inputs.great.margin", "+X.X a game vs its own league"); nm = f("inputs.today.margin", "NOW +X.X")
    pct = f("outputs.great_wins_pct", "great team wins X% of the series")
    mlen = f("outputs.great_most_common_len", "most often in N")
    g7 = f("outputs.game7_pct", "X% go to Game 7"); g7w = f("outputs.today_wins_game7_pct", "we win X% of those (about 1 in N)")
    modek = o["most_common"]; f(f"outputs.dist.{modek}", "the highlighted bar")
    dist = o["dist"]
    for k in dist: f(f"outputs.dist.{k}", "bar height")
    if R:
        star_o, star_n, ast_n, third_n = "Kawhi Leonard", "Scottie Barnes", "Immanuel Quickley", "RJ Barrett"
        old_ids, old_tags = ["3012", "3149673", "6450"], ["KYLE", "PASCAL", "KAWHI"]
        new_ids, new_tags = ["4433134", "4395724", "4395625"], ["SCOTTIE", "IQ", "RJ"]
    else:
        star_o, star_n, ast_n, third_n = "Stephen Curry", "Stephen Curry", "Draymond Green", "Yaxel Lendeborg"
        old_ids, old_tags = ["6589", "6475", "3975"], ["DRAY", "KLAY", "STEPH"]
        new_ids, new_tags = ["3975", "6589", "5175737"], ["STEPH", "DRAY", "YAXEL"]
    io = pl(o, "old", star_o); so = f"outputs.great_players.{io}"
    in_, ia, i3 = pl(o, "new", star_n), pl(o, "new", ast_n), pl(o, "new", third_n)
    sn, sa, s3 = f"outputs.today_players.{in_}", f"outputs.today_players.{ia}", f"outputs.today_players.{i3}"
    o_pts = f(so + ".sim.pts", "28 / 28.2 points"); o_reb = f(so + ".sim.reb", "8 / 7.7 rebounds")
    o_stl = f(so + ".sim.stl", "STL 1.9"); o_fg3 = f(so + ".sim.fg3", "3PM 5.4 / 5 threes"); o_30 = f(so + ".sim.pts30_pct", "30-PT GMS X%")
    o_mvp = f(so + ".mvp_pct_of_old_wins", "series MVP in X% of their wins")
    n_pts = f(sn + ".sim.pts", "PTS 25.2 / 25 a game"); a_ast = f(sa + ".sim.ast", "AST 6.2 / 6 assists")
    t3 = f(s3 + (".sim.pts" if R else ".sim.reb"), "third row")
    P = lambda x: f"{x:.0f}%"          # whole percent on screen, like theirs
    sg = lambda x: f"{x:+.1f}"
    one_in = round(100 / g7w) if g7w else 0
    W = lambda x: x
    party = [{"id": "o" + "abc"[i], "key": f"p:{k}"} for i, k in enumerate(old_ids)] + [{"id": "n" + "abc"[i], "key": f"p:{k}"} for i, k in enumerate(new_ids)]
    TN = "RAPTORS" if R else "WARRIORS"
    star_tag_o = old_tags[2]; star_tag_n = new_tags[0]; ast_tag = new_tags[1]
    cfg = {"old": ["oa", "ob", "oc"], "new": ["na", "nb", "nc"], "otags": old_tags, "ntags": new_tags, "count": runs,
           "title": f"BEST {TN} TEAM EVER?", "title2": f"{yr} VS NOW", "rec": f"{yr}: {gw}-{gl}", "bo7": "BEST OF 7", "today": "TODAY"}
    t1 = "TODAY'S RAPTORS VS THE|2019 CHAMPS: 10,000 SIMS" if R else "TODAY'S WARRIORS VS THE|73-9 TEAM: 10,000 SIMS"
    t2 = "A 7-GAME SERIES,|PLAYED 10,000 TIMES."
    roomA = {"name": f"THE {yr} ROOM", "sub": "NBA CHAMPIONS" if R else "73 WINS", "top": "green"}
    boxA = {"head": f"{ssn} {TN}"}
    rowsA = [["RECORD", f"{gw}-{gl}"], ["FMVP", "KAWHI"] if R else ["MVP", "STEPH"], ["WON", "TITLE"] if R else ["MADE", "FINALS"]]
    pillA = "ONLY TITLE" if R else "NBA RECORD"
    mvp_tagA = "FMVP" if R else "MVP"
    lab = {"name": "SIM LAB", "sub": "GRADED BY ERA"}
    boxes = [{"head": f"VS {yr} LEAGUE", "k": yr, "v": sg(gm)}, {"head": "VS TODAY'S NBA", "k": "NOW", "v": sg(nm)}]
    labP = {"players": ["oc", "na"], "tags": [star_tag_o, star_tag_n]}
    res = {"name": "10,000 SERIES", "sub": "SIM RESULTS"}
    chart = {"big": P(pct), "lab": f"{yr} WINS|THE SERIES", "now": [dist[f"now_in_{k}"] for k in (4, 5, 6, 7)], "old": [dist[f"old_in_{k}"] for k in (7, 6, 5, 4)],
             "nowlab": "NOW WINS IN", "oldlab": f"{yr} WINS IN", "hi": ("old", [7, 6, 5, 4].index(int(modek[-1]))) if modek.startswith("old") else ("now", [4, 5, 6, 7].index(int(modek[-1]))),
             "hipill": f"{dist[modek]:.1f}%"}
    gymname = "KAWHI'S GYM" if R else "STEPH'S GYM"
    gymsub = "SIM AVERAGES" if R else "2016 SIM AVERAGES"
    gymhead = "KAWHI: SIM AVERAGES" if R else "2016 STEPH: SIM AVERAGES"
    gymrows = [["PTS", f"{o_pts:.1f}"], ["REB", f"{o_reb:.1f}"], ["STL", f"{o_stl:.1f}"] if R else ["3PM", f"{o_fg3:.1f}"], ["30-PT GMS", P(o_30)]]
    mvppill = f"SERIES MVP:|{P(o_mvp)} OF {yr} WINS"
    todrows = [[f"{star_tag_n} PTS", f"{n_pts:.1f}"], [f"{ast_tag} AST", f"{a_ast:.1f}"], ["RJ PTS", f"{t3:.1f}"] if R else ["YAXEL REB", f"{t3:.1f}"]]
    place = "TORONTO" if R else "THE BAY"
    goal = "TITLE"
    B = []
    gC = {"kind": "h2h_town", "cfg": cfg}
    # ---- 0 town (hook): voice from frame 1, first page already on screen
    B.append({**gC, "full": True, "dlg": t1, "vo": f"Is this the best {'Raptors' if R else 'Warriors'} team ever?"})
    B.append({"kind": "h2h_town", "full": True, "dlg": t1,
              "vo": "We put Scottie and Quickley against the 2019 champions" if R else "We put today's Steph and Draymond against the 73 win team"})
    B.append({"kind": "h2h_town", "dlg": t2, "vo": "in a seven game series, and ran it ten thousand times."})
    # ---- 3 the great team's room
    rA = {"kind": "h2h_room", "irisIn": True, "room": roomA, "players": ["oc"], "tags": [star_tag_o], "box": {**boxA, "rows": rowsA}, "pill": pillA, "mvp": mvp_tagA,
          "stat": {"ph": [1.4, 2.2, 4.5, 4.6, 5.0]}}   # box, pill, row 2 + MVP tag + trophy, row 3 (group seconds)
    B.append({**rA, "dlg": (f"{gw}-{gl} AND THE FRANCHISE'S|ONLY TITLE." if R else f"{gw}-{gl}: STILL THE BEST|RECORD IN NBA HISTORY."),
              "vo": "That team won 58 games and the franchise's only title," if R else "That team won 73 games, still the NBA record,"})
    B.append({**rA, "irisIn": False, "dlg": ("AND KAWHI WAS|FINALS MVP." if R else "AND STEPH WAS THE|UNANIMOUS MVP."),
              "vo": "and Kawhi was Finals MVP." if R else "and Steph was unanimous MVP."})
    # ---- 5 sim lab
    B.append({"kind": "h2h_lab", "irisIn": True, "lab": lab, "boxes": boxes, **labP, "dlg": "EACH TEAM GRADED VS|ITS OWN ERA.", "vo": "Each team is graded against its own era."})
    # ---- 6 results
    rs = {"kind": "h2h_res", "res": res, "chart": chart, "q": "BEST TEAM EVER?", "a": "NOT YET"}
    B.append({**rs, "irisIn": True, "dlg": "SO IS IT THE BEST?|NOT YET.", "vo": "The answer is, not yet."})
    B.append({**rs, "dlg": f"{yr} WINS {P(pct)}.|MOST LIKELY: {yr} IN {mlen}",
              "vo": f"The {yr} team wins {round(pct)} percent of the series, most often in {mlen}."})
    # ---- 8 the star's gym
    gy = {"kind": "h2h_room", "irisIn": True, "room": {"name": gymname, "sub": gymsub, "top": "green"}, "players": ["oc"], "tags": [star_tag_o],
          "box": {"head": gymhead, "rows": gymrows, "count": True}, "ppg": f"{o_pts:.0f} PPG", "mvppill": mvppill, "gym": True, "stat": {"ph": [0, 99, 2.2, 4.8, 4.9]}}
    B.append({**gy, "dlg": (f"KAWHI: {o_pts:.0f} PTS, {o_reb:.0f} REB|A GAME." if R else f"2016 STEPH: {o_pts:.0f} PTS,|{o_fg3:.0f} THREES A GAME."),
              "vo": (f"Kawhi is the reason, {o_pts:.0f} points and {o_reb:.0f} rebounds a game," if R else f"2016 Steph is the reason, {o_pts:.0f} points and {o_fg3:.0f} threes a game,")})
    B.append({**gy, "irisIn": False, "dlg": f"SERIES MVP IN {P(o_mvp)}|OF {yr} WINS.", "vo": f"and he's series MVP in {round(o_mvp)} percent of their wins."})
    # ---- 10 today's room
    B.append({"kind": "h2h_room", "irisIn": True, "today": True, "room": {"name": "TODAY'S ROOM", "sub": "SIM AVERAGES", "top": "navy"}, "players": ["na", "nb"], "tags": [star_tag_n, ast_tag],
              "box": {"head": "NOW: SIM AVERAGES", "rows": todrows, "count": True}, "pp": [f"{n_pts:.0f} PPG", f"{a_ast:.0f} AST"], "stat": {"ph": [0, 99, 1.0 if R else 0.6, 2.9, 3.3]},
              "dlg": (f"SCOTTIE: {n_pts:.0f} A GAME.|IQ: {a_ast:.0f} ASSISTS." if R else f"STEPH NOW: {n_pts:.0f} A GAME.|DRAY: {a_ast:.0f} ASSISTS."),
              "vo": (f"Scottie answers with {n_pts:.0f} a game, and Quickley runs it with {a_ast:.0f} assists." if R else f"Today's Steph answers with {n_pts:.0f} a game, and Draymond runs it with {a_ast:.0f} assists.")})
    # ---- 11 game 7 town
    B.append({"kind": "h2h_town", "irisIn": True, "stat": {"irisT": .12}, "g7": {"place": place, "sub": "GAME 7", "pill": f"{P(g7)} GO TO 7", "pill2": f"WE WIN {P(g7w)}"}, "cfg2": cfg,
              "dlg": f"{P(g7)} GO TO GAME 7.|WE WIN {P(g7w)} OF THOSE.", "vo": f"{round(g7)} percent go to Game 7, and we win about 1 in {one_in}."})
    # ---- 12 route
    rt = {"kind": "h2h_route", "route": {"name": f"ROUTE TO THE {goal}", "sub": "NOT YET", "bar": f"NBA {goal}: NOT YET", "sign": goal}, "walk": ["na", "nb"], "wtags": [star_tag_n, ast_tag]}
    B.append({**rt, "irisIn": True, "dlg": "TO PASS THEM:|WIN THE NBA TITLE.", "vo": "To pass them for real, we have to do"})
    B.append({**rt, "dlg": ("ONLY ONE RAPTORS TEAM|HAS DONE IT." if R else "THE 73-9 TEAM|NEVER DID IT."), "vo": "what only one Raptors team has done." if R else "what that seventy three win team couldn't."})
    B.append({**rt, "full": True, "dlg": ("ONLY ONE RAPTORS TEAM|HAS DONE IT." if R else "THE 73-9 TEAM|NEVER DID IT."), "vo": "Win the title.", "dissolve": True})

    if R:
        cap = (f"Today's Raptors vs Kawhi's 2019 Raptors, best-of-7, simulated 10,000 times 🦖 The 2019 team wins {pct}% of the series, most often in {mlen}. "
               f"Kawhi averages {o_pts:.1f} points and {o_reb:.1f} rebounds and is series MVP in {o_mvp}% of the 2019 wins. "
               f"Scottie answers with {n_pts:.1f} a game, Quickley runs it with {a_ast:.1f} assists, and {g7}% of the series go to Game 7, where we win {g7w}%. "
               f"Both teams graded against their own era. To pass them for real: win a title. Who are you taking in a Game 7? 👇")
        claims = [
            {"claim": "2018-19 Raptors went 58-24, scored 114.4 and allowed 108.4 per game (+6.0), won the 2019 NBA title over Golden State", "source": "https://www.basketball-reference.com/teams/TOR/2019.html"},
            {"claim": "Kawhi Leonard was the 2019 NBA Finals MVP", "source": "https://www.basketball-reference.com/playoffs/NBA_2019.html"},
            {"claim": "The 2019 title is the Raptors' only NBA championship (franchise: 1 championship)", "source": "https://www.basketball-reference.com/teams/TOR/"},
            {"claim": "Raptors 2026-27: 5-10, 112.0 scored and allowed per game (ESPN schedule, 15 completed games)", "source": "https://www.espn.com/nba/team/schedule/_/name/tor"},
        ]
    else:
        cap = (f"Today's Warriors vs the 73-9 Warriors, best-of-7, simulated 10,000 times 💛 The 2016 team wins {pct}% of the series, most often in {mlen}. "
               f"2016 Steph averages {o_pts:.1f} points and {o_fg3:.1f} threes and is series MVP in {o_mvp}% of the 2016 wins. "
               f"Today's Steph answers with {n_pts:.1f} a game, Draymond runs it with {a_ast:.1f} assists, and {g7}% of the series go to Game 7, where we win {g7w}%. "
               f"Both teams graded against their own era. To pass them for real: win the title they couldn't. Who are you taking in a Game 7? 👇")
        claims = [
            {"claim": "2015-16 Warriors went 73-9 (still the NBA record), scored 114.9 and allowed 104.1 per game (+10.8), lost the 2016 Finals", "source": "https://www.basketball-reference.com/teams/GSW/2016.html"},
            {"claim": "Stephen Curry was the unanimous 2015-16 MVP", "source": "https://www.basketball-reference.com/awards/awards_2016.html"},
            {"claim": "73-9 is the best regular-season record in NBA history", "source": "https://en.wikipedia.org/wiki/2015%E2%80%9316_Golden_State_Warriors_season"},
            {"claim": "Warriors 2026-27: 8-7, 113.7 scored and 112.8 allowed per game (ESPN schedule, 15 completed games)", "source": "https://www.espn.com/nba/team/schedule/_/name/gs"},
        ]
    claims.append({"claim": "Method: gen/sim_h2h.py (point margin per game vs its own league, shrunk by sample size; best-of-7 2-2-1-1-1, home court to the better record; 8-man playoff rotations; Gamma/Poisson box scores; series MVP = best series Game Score on the winner). Fan simulation, not a prediction.",
                   "source": "https://www.basketball-reference.com/about/glossary.html"})
    for b in B:
        if b.get("vo"): b["vo"] = vo_nums(b["vo"]); b["vo"] = b["vo"][0].upper() + b["vo"][1:]
    spec = {"team": team, "name": NAME, "template": "fmt_sim.html", "pace": "wolves", "tts_speed": 1.3, "music": "best136", "cps": 42, "voice_eq": "bright",
            "caption": cap, "party": party, "beats": B, "facts": facts + claims}
    return spec


def tts(team, spec):
    L = [{"id": f"b{i}", "text": b["vo"]} for i, b in enumerate(spec["beats"]) if b.get("vo")]
    lj = pathlib.Path(f"/tmp/_h2hspec_{team}.json"); lj.write_text(json.dumps(L))
    out = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts.py"), str(lj), f"/tmp/_h2hspec_{team}_vo"], capture_output=True, text=True, check=True,
                         env={**os.environ, "KOKORO_SPEED": str(spec.get("tts_speed", 1.25)), "KOKORO_TRIM": "1"}).stdout.strip().splitlines()[-1]
    (ROOT / f"data/sim/{team}_{NAME}_vo_durs.json").write_text(out)


def holds(spec, team):
    D = json.loads((ROOT / f"data/sim/{team}_{NAME}_vo_durs.json").read_text()); out = []; t = 0.0
    for i, b in enumerate(spec["beats"]):
        need = WANT[i] - t if i < len(WANT) else 0
        if i and spec["beats"][i - 1].get("vo", "").rstrip()[-1:] in ".?" and not b.get("irisIn") and b["kind"] == spec["beats"][i - 1]["kind"]: need = max(need, PAUSE if i < len(spec["beats"]) - 1 else .2)   # whisper splits lines at sentence pauses like theirs
        if need > .02:
            h = {k: v for k, v in out[-1].items() if k not in ("vo", "stat", "flash", "cfg", "irisIn")}; h["full"] = True; h["vo"] = ""; h["hold"] = round(need, 2)
            out.append(h); t += need
        elif need < -.3: print(f"  {team} beat {i} late by {-need:.2f} s")
        out.append(b); t += D[f"b{i}"] + .12
    h = {k: v for k, v in out[-1].items() if k not in ("vo", "stat", "flash", "cfg", "irisIn")}; h["full"] = True; h["vo"] = ""; h["hold"] = max(.15, round(TOTAL - .6 - t, 2)); out.append(h)
    spec["beats"] = out; print(f"  {team} total", round(t + h["hold"] + .6, 2)); return spec


if __name__ == "__main__":
    for team, pre in (("raptors", "r"), ("warriors", "w")):
        s = build(team)
        if "--tts" in sys.argv or not (ROOT / f"data/sim/{team}_{NAME}_vo_durs.json").exists(): tts(team, s)
        s = holds(s, team)
        (ROOT / f"specs/{pre}_{NAME}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False)); print("ok", team, len(s["beats"]))
