"""Build specs/r_sim_era.json and specs/w_sim_era.json (copy of @8bitwolves Df2-F5XgcNC) from data/sim/<team>_<date>.json.

Every number on screen / in the caption is read from the sim file and listed as a {"sim": ...} fact (gen/factcheck.py).
Silent hold beats are inserted so each beat starts where theirs does (WANT, from copy_check trace) and the narrator
pauses at their sentence breaks (PAUSE). Hold lengths use our Kokoro line durations in data/sim/<team>_sim_era_vo_durs.json;
re-measure them after changing any "vo" text:  python3 gen/sim_spec.py --tts
usage: python3 gen/sim_spec.py [--tts]   then  python3 gen/history.py specs/r_sim_era.json (and w_)
"""
import json, pathlib
ROOT = pathlib.Path("/Users/ryanhelou/Developer/8bitraptors")
DATE = "2026-11-18"
ESPN_ST = "https://www.espn.com/nba/standings"


def load(team):
    rel = f"data/sim/{team}_{DATE}.json"
    return rel, json.loads((ROOT / rel).read_text())


def F(rel, d, path, said=""):
    v = d
    for k in path.split("."): v = v[int(k)] if isinstance(v, list) else v[k]
    return {"sim": rel, "path": path, "value": v, "said": said}, v


def raptors():
    rel, d = load("raptors"); o = d["outputs"]; facts = []
    def f(path, said=""):
        x, v = F(rel, d, path, said); facts.append(x); return v
    runs = f("runs", "10,000 sims, ten thousand"); yrs = f("seasons", "10 seasons, 10 years, 10 for 10")
    lab = d["season_labels"]; f("season_labels.0", "2026-27"); f("season_labels.9", "2035-36 -> the sign 2026-36")
    rec = f("outputs.record_now", "our 5-8 start")
    sc, kw = "Scottie Barnes", "Kawhi Leonard"
    as_s = f(f"outputs.allstars.{sc}.mean_added", "about 4 more All-Star games (+4)")
    as_k = f(f"outputs.allstars.{kw}.mean_added", "about 2 (+2)")
    ten = f(f"outputs.allstars.{sc}.at_least.10", "1 run in 250 (0.4% = 1/250)")
    mv_s = f(f"outputs.mvp.ours_at_least_one_pct.{sc}", "about 1% of runs (1.0%)")
    top = o["mvp"]["share_of_all_mvps_pct"][0]; f("outputs.mvp.share_of_all_mvps_pct.0.player"); luka = f("outputs.mvp.share_of_all_mvps_pct.0.pct", "34%, about 1 in 3")
    e1 = o["season_enders_pct_of_sim_seasons"][0]; e2 = o["season_enders_pct_of_sim_seasons"][1]
    f("outputs.season_enders_pct_of_sim_seasons.0.0"); f("outputs.season_enders_pct_of_sim_seasons.0.1", "8%")
    f("outputs.season_enders_pct_of_sim_seasons.1.0"); f("outputs.season_enders_pct_of_sim_seasons.1.1", "6%")
    R = o["rings"]
    one = f("outputs.rings.at_least_one_pct", "24%, about 1 in 4"); ex = f("outputs.rings.exactly_one_pct", "EXACTLY 1: 19% (18.5)")
    per = [f(f"outputs.rings.per_season_pct.{l}", "bar") for l in lab]
    f("outputs.rings.per_season_pct.2026-27", "THIS SEASON: 6%, about 6%")
    f("outputs.rings.after_year3_avg_pct", "after year 3 (seasons 4-10, 2.8 down to 1.9 percent) around 2 or 3")
    none = f("outputs.rings.none_pct", "RUNS, NO RING 76%"); win = f("outputs.rings.window", "THE WINDOW 2026-29, the next 3 years"); f("outputs.rings.window_seasons", "3 years")
    run = o["run_we_hoped_for"]
    f("outputs.run_we_hoped_for.season", "2026-27 this season"); f("outputs.run_we_hoped_for.record", "59-23, a 59-win season")
    f("outputs.run_we_hoped_for.finals_mvp", "FINALS MVP KAWHI"); f("outputs.run_we_hoped_for.mvp_seasons.0.season", "KAWHI MVP 2026-27"); f("outputs.run_we_hoped_for.mvp_seasons.0.player")
    f("outputs.run_we_hoped_for.ring_seasons.0", "RING 1 (the run's first ring)")
    facts.append({"claim": "Toronto Raptors 5-8 in the ESPN standings on Nov 18, 2026", "source": ESPN_ST})
    facts.append({"claim": "Scottie Barnes: 2x NBA All-Star (2024, 2026); about 4 more in the sim -> around 6 for his career", "source": "https://en.wikipedia.org/wiki/Scottie_Barnes"})
    hi = R["window_seasons"]
    cfg = {"players": ["sb", "kl"], "tags": ["BARNES", "LEONARD"], "title": "SCOTTIE + KAWHI: 10,000 SIMS", "sign": "2026-36", "count": runs}
    simbox = lambda n, t=None: {"head": "THE SIM", "n": 2, "rows": [["SIMS", "10,000", None, t if n == 1 else None], ["SEASONS", "10", None, t]][:n]}
    asbox = lambda n, tt: {"head": "ALL-STAR GAMES, 10 YEARS", "n": 3, "t": tt[0] if n == 0 else None, "rows": [["SCOTTIE ALL-STARS", "+4", None, tt[1] if n == 1 else None], ["KAWHI ALL-STARS", "+2", None, tt[1] if n == 2 else None], ["SCOTTIE 10 FOR 10", "1 IN 250", None, tt[1] if n == 3 else None]][:max(1, n)] if n else []}
    gymL = {"logo": "l:LAL", "roof": "auto:LAL", "name": "LAKERS GYM", "sub": "MVP RACE"}
    gymB = {"logo": "l:BOS", "roof": "auto:BOS", "name": "CELTICS GYM", "sub": "SERIES WE LOST"}
    card = {"q": True}
    big = {"v": "24%", "lab": "AT LEAST|ONE RING"}
    bars = {"v": per, "hi": hi}
    hall = lambda rows, t=None: {"head": "THE RUN WE HOPED FOR", "n": 4, "t": t, "rows": rows}
    B = lambda rows: [[r[0], r[1]] for r in rows]
    beats = [
        {"kind": "sim_arena", "cfg": cfg, "count": True, "full": True, "dlg": "WE SIMULATED THE|SCOTTIE + KAWHI ERA", "vo": "We simulated the Scottie and Kawhi era"},
        {"kind": "sim_arena", "count": True, "stat": {"box": 0, "rows": [.25]}, "box": {"head": "THE SIM", "rows": B([["SIMS", "10,000"]])}, "dlg": "10,000 TIMES.", "vo": "ten thousand times."},
        {"kind": "sim_arena", "box": {"head": "THE SIM", "rows": B([["SIMS", "10,000"], ["SEASONS", "10"]])}, "dlg": "10 SEASONS FROM|OUR 5-8 START.", "vo": "Ten seasons from our five and eight start."},
        {"kind": "sim_map", "flash": True, "stat": {"box": .25, "rows": [.9]}, "box": {"head": "ALL-STAR GAMES, 10 YEARS", "rows": B([["SCOTTIE ALL-STARS", "+4"]])}, "dlg": "SCOTTIE: ABOUT 4 MORE|ALL-STAR GAMES.", "vo": "Scottie makes about four more All-Star games,"},
        {"kind": "sim_map", "box": {"head": "ALL-STAR GAMES, 10 YEARS", "rows": B([["SCOTTIE ALL-STARS", "+4"]])}, "dlg": "THAT'S AROUND 6|FOR HIS CAREER.", "vo": "that's around six for his career."},
        {"kind": "sim_map", "box": {"head": "ALL-STAR GAMES, 10 YEARS", "rows": B([["SCOTTIE ALL-STARS", "+4"], ["KAWHI ALL-STARS", "+2"]])}, "dlg": "KAWHI ADDS|ABOUT 2.", "vo": "Kawhi adds about two,"},
        {"kind": "sim_map", "stat": {"rows": [1.2]}, "box": {"head": "ALL-STAR GAMES, 10 YEARS", "rows": B([["SCOTTIE ALL-STARS", "+4"], ["KAWHI ALL-STARS", "+2"], ["SCOTTIE 10 FOR 10", "1 IN 250"]])}, "dlg": "1 RUN IN 250: SCOTTIE|GOES 10 FOR 10.", "vo": "and in one run in two fifty, Scottie goes ten for ten."},
        {"kind": "sim_gym", "flash": True, "gym": gymL, "players": ["sb", "ld"], "tags": ["BARNES", "DONCIC"], "stat": {"sign": 1.3}, "dlg": "MVP IS HARDER.", "vo": "MVP is harder."},
        {"kind": "sim_gym", "gym": gymL, "players": ["sb", "ld"], "tags": ["BARNES", "DONCIC"], "stat": {"box": .9, "rows": [1.4]}, "box": {"head": "MVP RACE (10,000 RUNS)", "rows": B([["SCOTTIE WINS ONE", "1.0%"]])}, "dlg": "SCOTTIE WINS ONE IN|1% OF RUNS.", "vo": "Scottie wins one in one percent of runs,"},
        {"kind": "sim_gym", "gym": gymL, "players": ["sb", "ld"], "tags": ["BARNES", "DONCIC"], "stat": {"rows": [.9]}, "box": {"head": "MVP RACE (10,000 RUNS)", "rows": B([["SCOTTIE WINS ONE", "1.0%"], ["LUKA'S SHARE", "34%"]])}, "dlg": "LUKA TAKES|ABOUT 1 IN 3.", "vo": "Luka takes about one in three,"},
        {"kind": "sim_gym", "flash": True, "gym": gymB, "stat": {"sign": 1.1}, "dlg": "WHO ENDS OUR|SEASONS?", "vo": "and the teams that end our seasons?"},
        {"kind": "sim_gym", "gym": gymB, "stat": {"box": .1, "rows": [.4, 1.1]}, "box": {"head": "WHO ENDS OUR SEASON (% OF SIM YEARS)", "rows": B([["BOSTON", "8%"], ["NEW YORK", "6%"]])}, "dlg": "MOST OFTEN BOSTON|AND NEW YORK.", "vo": "Most often Boston and New York."},
        {"kind": "sim_ring", "card": {"q": True}, "dlg": "SO, DO WE GET|A RING?", "vo": "So, do we get a ring?"},
        {"kind": "sim_ring", "stat": {"big": .5, "ex": 1.0}, "card": {"q": True, "big": big, "ex": {"v": "EXACTLY 1: 19%"}}, "dlg": "IN 24% OF RUNS,|YES.", "vo": "In twenty four percent of runs, yes,"},
        {"kind": "sim_ring", "card": {"big": big, "ex": {"v": "EXACTLY 1: 19%"}, "odds": {"v": "1 IN 4"}}, "dlg": "ABOUT 1 IN 4.", "vo": "that's about one in four."},
        {"kind": "sim_ring", "stat": {"bars": .2, "season": 1.4}, "card": {"big": big, "ex": {"v": "EXACTLY 1: 19%"}, "odds": {"v": "1 IN 4"}, "bars": bars, "season": {"v": "THIS SEASON: 6%"}}, "dlg": "BEST SHOT: THIS|SEASON, ABOUT 6%.", "vo": "Our best shot is this season, about six percent."},
        {"kind": "sim_ring", "card": {"big": big, "ex": {"v": "EXACTLY 1: 19%"}, "odds": {"v": "1 IN 4"}, "bars": bars, "season": {"v": "THIS SEASON: 6%"}}, "dlg": "AFTER YEAR 3, IT'S|AROUND 2 OR 3%.", "vo": "After year three, it's around two or three."},
        {"kind": "sim_hall", "flash": True, "dlg": "THE RUN WE WERE|HOPING FOR?", "vo": "The run we were hoping for?"},
        {"kind": "sim_hall", "stat": {"box": 0, "rows": [.3, 1.4]}, "box": {"head": "THE RUN WE HOPED FOR", "rows": [["2026-27", "59-23"], ["RING", "1"]]}, "dlg": "59 WINS AND A|RING THIS SEASON.", "vo": "Fifty nine wins and a ring this season,"},
        {"kind": "sim_hall", "trophy": True, "box": {"head": "THE RUN WE HOPED FOR", "rows": [["2026-27", "59-23"], ["RING", "1"], ["FINALS MVP", "KAWHI"]]}, "dlg": "KAWHI IS FINALS MVP.", "vo": "with Kawhi as Finals MVP."},
        {"kind": "sim_hall", "trophy": True, "stat": {"rows": [.6]}, "box": {"head": "THE RUN WE HOPED FOR", "rows": [["2026-27", "59-23"], ["RING", "1"], ["FINALS MVP", "KAWHI"], ["KAWHI MVP", "2026-27"]]}, "dlg": "AND REGULAR SEASON|MVP, THE SAME YEAR.", "vo": "And regular season MVP, the same year."},
        {"kind": "sim_hall", "trophy": True, "box": {"head": "THE BIG PICTURE", "rows": [["RUNS, NO RING", "76%"]]}, "dlg": "MOST RUNS NEVER|GET THERE.", "vo": "Most runs never get there,"},
        {"kind": "sim_hall", "trophy": True, "box": {"head": "THE BIG PICTURE", "rows": [["RUNS, NO RING", "76%"], ["THE WINDOW", "2026-29"]]}, "dlg": "THE WINDOW IS THE|NEXT 3 YEARS.", "vo": "the window is the next three years."},
    ]
    assert run["record"] == "59-23" and run["finals_mvp"] == kw and run["mvp_seasons"][0]["player"] == kw and run["season"] == "2026-27", run
    assert round(as_s) == 4 and round(as_k) == 2 and ten == 0.4 and mv_s == 1.0 and round(luka) == 34 and one == 24.2 and int(ex + .5) == 19 and round(per[0]) == 6 and round(none) == 76 and win == "2026-29"
    assert e1 == ["BOS", 8.2] and e2 == ["NY", 5.9] and top["player"] == "Luka Doncic" and rec == "5-8"
    caption = """WE SIMMED THE SCOTTIE + KAWHI ERA 10,000 TIMES 🦖💍

10 seasons from our 5-8 start. Here's what came out:

💍 At least one ring: 24% of runs (about 1 in 4)
📅 Best shot: THIS season at 6%. After year 3 it's around 2 to 3% a year
⭐ Scottie: about 4 more All-Star games (around 6 for his career). Kawhi: about 2 more
🏆 MVP: Scottie wins one in 1% of runs. Luka takes 34% of all the MVPs
🚧 Who ends our season most: Boston (8% of sim seasons) and New York (6%)
✨ The run we were hoping for: 59-23 and a ring THIS season with Kawhi as Finals MVP, and Kawhi MVP the same year

It's a fan simulation, not a prediction. Do we get one in the next three years?"""
    party = [{"id": "sb", "key": "p:4433134"}, {"id": "kl", "key": "p:6450"}, {"id": "ld", "key": "p:3945274"}]
    return {"team": "raptors", "name": "sim_era", "template": "fmt_sim.html", "pace": "wolves", "music": "calm", "cps": 40, "voice_eq": "bright", "record": rec, "caption": caption, "party": party, "beats": beats, "facts": facts}


# their beat map (copy_check trace of Df2-F5XgcNC): where each of our beats must start, and their length
WANT = {2: 4.5, 3: 6.7, 5: 11.1, 7: 16.1, 8: 17.6, 10: 22.4, 11: 24.4, 12: 26.9, 13: 28.9, 15: 32.5, 16: 36.2, 17: 38.9, 18: 40.2, 20: 45.3, 21: 47.9}
TOTAL = 52.7


PAUSE = {}   # no extra pauses: holding to their beat map (WANT) already puts our pauses where theirs are


def holds(spec, durs_file, extra=None):
    """Insert silent hold beats (the previous beat, finished) so each beat starts where theirs does; durations = our Kokoro lines."""
    D = json.loads(pathlib.Path(durs_file).read_text()); out = []; t = 0.0
    for i, b in enumerate(spec["beats"]):
        need = max(WANT.get(i, 0) - t, {**PAUSE, **(extra or {})}.get(i, 0))
        if need > .15:
            h = {k: v for k, v in out[-1].items() if k not in ("vo", "stat", "flash", "count", "cfg")}; h["full"] = True; h["vo"] = ""; h["hold"] = round(need, 2)
            out.append(h); t += need
        out.append(b); t += D[f"b{i}"] + .12
    h = {k: v for k, v in out[-1].items() if k not in ("vo", "stat", "flash", "count", "cfg")}; h["full"] = True; h["vo"] = ""; h["hold"] = max(.15, round(TOTAL - .6 - t, 2)); out.append(h)
    spec["beats"] = out; print("  total", round(t + .12 + h["hold"] + .6, 2)); return spec


def tts(team, spec):
    """Voice every line once (same settings as history.py's wolves pace) and store the durations."""
    import subprocess, os
    L = [{"id": f"b{i}", "text": b["vo"]} for i, b in enumerate(spec["beats"]) if b.get("vo")]
    lj = pathlib.Path(f"/tmp/_simspec_{team}.json"); lj.write_text(json.dumps(L))
    out = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts.py"), str(lj), f"/tmp/_simspec_{team}_vo"], capture_output=True, text=True, check=True,
                         env={**os.environ, "KOKORO_SPEED": "1.25", "KOKORO_TRIM": "1"}).stdout.strip().splitlines()[-1]
    (ROOT / f"data/sim/{team}_sim_era_vo_durs.json").write_text(out)


def warriors():
    rel, d = load("warriors"); o = d["outputs"]; facts = []
    def f(path, said=""):
        x, v = F(rel, d, path, said); facts.append(x); return v
    runs = f("runs", "10,000 sims, ten thousand, 2 of 10,000 runs"); f("seasons", "10 seasons, 10 years")
    lab = d["season_labels"]; f("season_labels.0", "2026-27"); f("season_labels.9", "2035-36 -> the sign 2026-36")
    rec = f("outputs.record_now", "our 8-6 start")
    sc, jb = "Stephen Curry", "Jimmy Butler III"
    as_s = f(f"outputs.allstars.{sc}.mean_added", "about 1 more All-Star game (+1)")
    as_j = f(f"outputs.allstars.{jb}.mean_added", "+0.4")
    j1 = f(f"outputs.allstars.{jb}.at_least.1", "one more in 2 of 5 runs (40%)")
    s2 = f(f"outputs.allstars.{sc}.at_least.2", "2 more in 1 run out of 5 (20.5% = about 1 in 5)")
    mvn = f(f"outputs.mvp.ours_runs_with_one.{sc}", "2 runs, 2 of 10,000")
    f("outputs.mvp.share_of_all_mvps_pct.0.player"); luka = f("outputs.mvp.share_of_all_mvps_pct.0.pct", "34.5%, about 1 in 3")
    E = o["season_enders_pct_of_sim_seasons"]
    for i, s_ in ((0, "7%"), (1, "6%")): f(f"outputs.season_enders_pct_of_sim_seasons.{i}.0"); f(f"outputs.season_enders_pct_of_sim_seasons.{i}.1", s_)
    R = o["rings"]
    one = f("outputs.rings.at_least_one_pct", "17%, about 1 in 6"); ex = f("outputs.rings.exactly_one_pct", "EXACTLY 1: 14%")
    per = [f(f"outputs.rings.per_season_pct.{l}", "bar") for l in lab]
    f("outputs.rings.per_season_pct.2026-27", "THIS SEASON: 1%, about 1 percent")
    aft = f("outputs.rings.after_both_stars_retired.share_of_all_rings_pct", "84% of them come after they retire")
    none = f("outputs.rings.none_pct", "RUNS, NO RING 83%")
    era = f("outputs.rings.with_a_star_still_playing.at_least_one_pct", "WITH STEPH OR JIMMY 3.4%, about 1 in 30")
    run = o["run_we_hoped_for"]
    f("outputs.run_we_hoped_for.season", "2026-27 this season"); f("outputs.run_we_hoped_for.record", "59-23, a 59-win season")
    f("outputs.run_we_hoped_for.finals_mvp", "FINALS MVP STEPH"); f("outputs.run_we_hoped_for.ring_seasons.0", "RING 1")
    f(f"outputs.run_we_hoped_for.allstar_seasons.{sc}.0", "BOTH ALL-STARS 2026-27"); f(f"outputs.run_we_hoped_for.allstar_seasons.{jb}.0", "2026-27")
    facts.append({"claim": "Golden State Warriors 8-6 in the ESPN standings on Nov 18, 2026", "source": ESPN_ST})
    facts.append({"claim": "Stephen Curry: 12x NBA All-Star (2014-2019, 2021-2026); about 1 more in the sim -> 13 for his career", "source": "https://en.wikipedia.org/wiki/Stephen_Curry"})
    assert rec == "8-6" and round(as_s) == 1 and round(as_j, 1) == 0.4 and j1 == 40.0 and s2 == 20.5 and mvn == 2 and luka == 34.5
    assert E[0] == ["SA", 6.6] and E[1] == ["MIN", 5.9] and round(one) == 17 and int(ex + .5) == 14 and round(per[0]) == 1 and round(aft) == 84 and round(none) == 83 and era == 3.4
    assert run["record"] == "59-23" and run["finals_mvp"] == sc and run["season"] == "2026-27" and run["allstar_seasons"][jb] == ["2026-27"]
    cfg = {"players": ["sc", "jb"], "tags": ["CURRY", "BUTLER"], "title": "STEPH + JIMMY: 10,000 SIMS", "sign": "2026-36", "count": runs}
    B = lambda rows: [[r[0], r[1]] for r in rows]
    gymL = {"logo": "l:LAL", "roof": "auto:LAL", "name": "LAKERS GYM", "sub": "MVP RACE"}
    gymS = {"logo": "l:SA", "roof": "auto:SA", "name": "SPURS GYM", "sub": "SERIES WE LOST"}
    big = {"v": "17%", "lab": "AT LEAST|ONE RING"}; bars = {"v": per, "hi": 1}
    AS = "ALL-STAR GAMES, 10 YEARS"; MV = "MVP RACE (10,000 RUNS)"; RN = "THE RUN WE HOPED FOR"; BP = "THE BIG PICTURE"
    c3 = {"big": big, "ex": {"v": "EXACTLY 1: 14%"}, "odds": {"v": "1 IN 6"}}
    beats = [
        {"kind": "sim_arena", "cfg": cfg, "count": True, "full": True, "dlg": "WE SIMULATED THE|STEPH + JIMMY ERA", "vo": "We simulated the Steph and Jimmy era"},
        {"kind": "sim_arena", "count": True, "stat": {"box": 0, "rows": [.25]}, "box": {"head": "THE SIM", "rows": [["SIMS", "10,000"]]}, "dlg": "10,000 TIMES.", "vo": "ten thousand times."},
        {"kind": "sim_arena", "box": {"head": "THE SIM", "rows": [["SIMS", "10,000"], ["SEASONS", "10"]]}, "dlg": "10 SEASONS FROM|OUR 8-6 START.", "vo": "Ten seasons from our eight and six start."},
        {"kind": "sim_map", "flash": True, "stat": {"box": .25, "rows": [.9]}, "box": {"head": AS, "rows": [["STEPH ALL-STARS", "+1"]]}, "dlg": "STEPH: ABOUT 1 MORE|ALL-STAR GAME.", "vo": "Steph makes about one more All-Star game,"},
        {"kind": "sim_map", "box": {"head": AS, "rows": [["STEPH ALL-STARS", "+1"]]}, "dlg": "THAT'S 13|FOR HIS CAREER.", "vo": "that's thirteen for his career."},
        {"kind": "sim_map", "box": {"head": AS, "rows": [["STEPH ALL-STARS", "+1"], ["JIMMY ALL-STARS", "+0.4"]]}, "dlg": "JIMMY ADDS ONE|IN 2 OF 5 RUNS.", "vo": "Jimmy adds one in two of five runs,"},
        {"kind": "sim_map", "stat": {"rows": [1.2]}, "box": {"head": AS, "rows": [["STEPH ALL-STARS", "+1"], ["JIMMY ALL-STARS", "+0.4"], ["STEPH 2 MORE", "1 IN 5"]]}, "dlg": "1 RUN IN 5: STEPH|MAKES 2 MORE.", "vo": "and in one run in five, Steph makes two more."},
        {"kind": "sim_gym", "flash": True, "gym": gymL, "players": ["sc", "ld"], "tags": ["CURRY", "DONCIC"], "stat": {"sign": 1.3}, "dlg": "MVP IS HARDER.", "vo": "MVP is harder."},
        {"kind": "sim_gym", "gym": gymL, "players": ["sc", "ld"], "tags": ["CURRY", "DONCIC"], "stat": {"box": .9, "rows": [1.4]}, "box": {"head": MV, "rows": [["STEPH WINS ONE", "2 RUNS"]]}, "dlg": "STEPH WINS ONE IN|2 OF 10,000 RUNS.", "vo": "Steph wins one in two of ten thousand runs,"},
        {"kind": "sim_gym", "gym": gymL, "players": ["sc", "ld"], "tags": ["CURRY", "DONCIC"], "stat": {"rows": [.9]}, "box": {"head": MV, "rows": [["STEPH WINS ONE", "2 RUNS"], ["LUKA'S SHARE", "34.5%"]]}, "dlg": "LUKA TAKES|ABOUT 1 IN 3.", "vo": "Luka takes about one in three,"},
        {"kind": "sim_gym", "flash": True, "gym": gymS, "stat": {"sign": 1.1}, "dlg": "WHO ENDS OUR|SEASONS?", "vo": "and the teams that end our seasons?"},
        {"kind": "sim_gym", "gym": gymS, "stat": {"box": .1, "rows": [.4, 1.1]}, "box": {"head": "WHO ENDS OUR SEASON (% OF SIM YEARS)", "rows": [["SAN ANTONIO", "7%"], ["MINNESOTA", "6%"]]}, "dlg": "MOST OFTEN SAN ANTONIO|AND MINNESOTA.", "vo": "Most often San Antonio and Minnesota."},
        {"kind": "sim_ring", "card": {"q": True}, "dlg": "SO, DO WE GET|A RING?", "vo": "So, do we get a ring?"},
        {"kind": "sim_ring", "stat": {"big": .5, "ex": 1.0}, "card": {"q": True, "big": big, "ex": {"v": "EXACTLY 1: 14%"}}, "dlg": "IN 17% OF RUNS,|YES.", "vo": "In seventeen percent of runs, yes,"},
        {"kind": "sim_ring", "card": dict(c3), "dlg": "ABOUT 1 IN 6.", "vo": "that's about one in six."},
        {"kind": "sim_ring", "stat": {"bars": .2, "season": 1.4}, "card": {**c3, "bars": bars, "season": {"v": "THIS SEASON: 1%"}}, "dlg": "THIS SEASON? ONLY|ABOUT 1%.", "vo": "But this season? Only about one percent."},
        {"kind": "sim_ring", "card": {**c3, "bars": bars, "season": {"v": "THIS SEASON: 1%"}}, "dlg": "84% OF THEM COME|AFTER THEY RETIRE.", "vo": "Eighty four percent come after they retire."},
        {"kind": "sim_hall", "flash": True, "dlg": "THE RUN WE WERE|HOPING FOR?", "vo": "The run we were hoping for?"},
        {"kind": "sim_hall", "stat": {"box": 0, "rows": [.3, 1.4]}, "box": {"head": RN, "rows": [["2026-27", "59-23"], ["RING", "1"]]}, "dlg": "59 WINS AND A|RING THIS SEASON.", "vo": "Fifty nine wins and a ring this season,"},
        {"kind": "sim_hall", "trophy": True, "box": {"head": RN, "rows": [["2026-27", "59-23"], ["RING", "1"], ["FINALS MVP", "STEPH"]]}, "dlg": "STEPH IS FINALS MVP.", "vo": "with Steph as Finals MVP."},
        {"kind": "sim_hall", "trophy": True, "stat": {"rows": [.6]}, "box": {"head": RN, "rows": [["2026-27", "59-23"], ["RING", "1"], ["FINALS MVP", "STEPH"], ["BOTH ALL-STARS", "2026-27"]]}, "dlg": "AND BOTH OF THEM|ARE ALL-STARS.", "vo": "And both are All-Stars."},
        {"kind": "sim_hall", "trophy": True, "box": {"head": BP, "rows": [["RUNS, NO RING", "83%"]]}, "dlg": "MOST RUNS NEVER|GET THERE.", "vo": "Most runs never get there,"},
        {"kind": "sim_hall", "trophy": True, "box": {"head": BP, "rows": [["RUNS, NO RING", "83%"], ["WITH STEPH OR JIMMY", "3.4%"]]}, "dlg": "WITH STEPH OR JIMMY:|ABOUT 1 IN 30.", "vo": "with Steph or Jimmy, about one in thirty."},
    ]
    caption = """WE SIMMED THE STEPH + JIMMY ERA 10,000 TIMES 💛💍

10 seasons from our 8-6 start. Here's what came out:

💍 At least one ring: 17% of runs (about 1 in 6)
📅 This season: about 1%. 84% of our sim rings come after Steph and Jimmy retire
⭐ Steph: about 1 more All-Star game (13 for his career). Jimmy makes one more in 40% of runs
🏆 MVP: Steph wins one in 2 of 10,000 runs. Luka takes 34.5% of all the MVPs
🚧 Who ends our season most: San Antonio (7% of sim seasons) and Minnesota (6%)
✨ The run we were hoping for: 59-23 and a ring THIS season with Steph as Finals MVP, both of them All-Stars

It's a fan simulation, not a prediction. Do we get one while Steph is still here?"""
    party = [{"id": "sc", "key": "p:3975"}, {"id": "jb", "key": "p:6430"}, {"id": "ld", "key": "p:3945274"}]
    return {"team": "warriors", "name": "sim_era", "template": "fmt_sim.html", "pace": "wolves", "music": "calm", "cps": 40, "voice_eq": "bright", "record": rec, "caption": caption, "party": party, "beats": beats, "facts": facts}


RW_EXTRA = {}


if __name__ == "__main__":
    import sys
    if "--tts" in sys.argv: tts("raptors", raptors()); tts("warriors", warriors())
    s = holds(raptors(), str(ROOT / "data/sim/raptors_sim_era_vo_durs.json")); (ROOT / "specs/r_sim_era.json").write_text(json.dumps(s, indent=1, ensure_ascii=False)); print("ok raptors", len(s["beats"]))
    s = holds(warriors(), str(ROOT / "data/sim/warriors_sim_era_vo_durs.json"), RW_EXTRA); (ROOT / "specs/w_sim_era.json").write_text(json.dumps(s, indent=1, ensure_ascii=False)); print("ok warriors", len(s["beats"]))
