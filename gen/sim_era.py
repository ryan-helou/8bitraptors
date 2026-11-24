"""Fan Monte Carlo of an "era": 10,000 runs x 10 seasons for one team's two stars. A fan simulation, not a prediction.

usage: python3 gen/sim_era.py raptors|warriors [--runs 10000] [--seed 7]
  -> data/sim/<team>_<YYYY-MM-DD>.json  (ESPN inputs, every assumption below, every output number)

THE MODEL (deliberately simple; every constant is in ASSUMPTIONS and saved with the output)
Data (ESPN public JSON, pulled when the script runs):
  * standings for all 30 teams: W, L, games played, points for/against per game -> point differential per game
  * every player's per-game box score this season and last season (statistics/byathlete), age, team
  * the league injury report (return dates for players who are out right now)
1. Player rating = Hollinger Game Score per game (GmSc: PTS + .4 FGM - .7 FGA - .4 (FTA-FTM) + .4 REB + STL + .7 AST
   + .7 BLK - .4 PF - TOV; .4 REB because ESPN gives total rebounds, not offensive/defensive).
   This season's GmSc is blended with last season's as if last season were PRIOR_GP games (small samples get pulled to
   last season). A player with 0 games this season keeps last season's rating minus one year of age decline.
2. Age curve: each year a player's rating changes by AGE_STEP[age band] + Normal(0, RATING_NOISE).
   Retirement before each season: probability RETIRE_SLOPE * (age - RETIRE_AGE), capped at .9 (0 below that age).
   Availability: each season a player is healthy with probability 1 - (INJ_BASE + INJ_AGE * years over 30), then plays
   80-100% of games; otherwise he plays 10-60%. A player out right now only plays the part of this season after his
   ESPN return date.
3. Team strength = net rating (points per game vs an average team).
   This season: the observed point differential is shrunk toward 0 like a normal-normal model
   (team talent SD TEAM_SD, single-game margin SD GAME_SD). Every season after: net' = .7 net + Normal(0, YEAR_SD)
   (keeps the league spread stable). OUR team is split into "the rest" (same AR(1), centred on the league-average
   non-star level) plus our two stars, each worth STAR_K * (rating - REPLACEMENT) * share of games played, so the stars'
   ageing, injuries and retirements move our team. A retired star's slot is refilled gradually: it is worth
   league-average-top-2-player * (1 - .7^years since he retired). Other teams' players do not move their team (simplification).
4. Games: P(win vs average) = Phi(net / GAME_SD); a playoff game between A (home) and B = Phi((netA - netB + HOME) / GAME_SD).
   Season 1 keeps the real record so far and only simulates the games left.
5. Postseason: seeds by wins inside each conference (random tiebreak); play-in 7v8, 9v10, loser 7/8 vs winner 9/10;
   best-of-7 series 2-2-1-1-1 with home court to the better seed (Finals: more wins). Players stay on their current
   team for all 10 years (no trades or free agency in the model).
6. All-Stars: 12 per conference among players who play >= 50% of games: score = rating + .08 (team wins - 41) + Normal(0, 1.5).
   MVP: among players who play >= 65 of 82 (79%): score = rating + .12 (team wins - 41) + Normal(0, 1.5).
   Each year ROOKIES players (age 20, rating Normal(ROOKIE_MEAN, ROOKIE_SD)) join random teams, so new stars can appear.
   Finals MVP when we win: our healthy stars and "someone else" (rating FMVP_OTHER), highest rating + Normal(0, 2.5).
7. "The run we hoped for": among runs where we win a ring with one of our stars as Finals MVP, prefer runs where one of
   them also wins MVP; pick the title season whose win total is closest to the median wins of all our title seasons
   (a typical title team, not a freak 75-win outlier). Only a run's FIRST ring counts as its title season. The MVP
   condition is only used when one of our stars wins MVP in at least 0.5% of runs. Ties: earliest season, lowest run.
   "The window": the seasons, counting from this one, until the yearly title odds first fall below half of the best year.
"""
import sys, json, pathlib, argparse, datetime as dt
import numpy as np
from scipy.stats import norm
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import espn

ROOT = pathlib.Path(__file__).resolve().parent.parent
STARS = {"raptors": ["4433134", "6450"], "warriors": ["3975", "6430"]}   # Scottie Barnes + Kawhi Leonard / Stephen Curry + Jimmy Butler III (ESPN rosters 2026-11-18)
ASSUMPTIONS = dict(
    SEASONS=10, PRIOR_GP=20, TEAM_SD=4.5, GAME_SD=13.0, YEAR_SD=3.2, AR=0.7, HOME=2.5,
    STAR_K=0.35, REPLACEMENT=8.0, RATING_NOISE=1.2,
    AGE_STEP={"<=22": 1.2, "23-25": 0.6, "26-28": 0.0, "29-31": -0.5, "32-34": -1.0, "35+": -1.5},
    RETIRE_AGE=34, RETIRE_SLOPE=0.10, INJ_BASE=0.15, INJ_AGE=0.03,
    ALLSTAR_PER_CONF=12, ALLSTAR_MIN_SHARE=0.5, MVP_MIN_SHARE=65 / 82, WIN_W_AS=0.08, WIN_W_MVP=0.12, VOTE_SD=1.5,
    ROOKIES=30, ROOKIE_MEAN=7.0, ROOKIE_SD=3.0, FMVP_OTHER=15.0, FMVP_SD=2.5, INJURED_RETURN_SHARE=0.85,
)
A = ASSUMPTIONS
BYATH = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?region=us&lang=en&contentorigin=espn&isqualified=false&limit=500&sort=offensive.avgPoints:desc"


def age_step(age):
    a = np.asarray(age)
    return np.select([a <= 22, a <= 25, a <= 28, a <= 31, a <= 34], [1.2, 0.6, 0.0, -0.5, -1.0], -1.5)


def players(season=None):
    out, page = [], 1
    while True:
        d = espn.get(BYATH + (f"&season={season}&seasontype=2" if season else "") + f"&page={page}")
        for x in d["athletes"]:
            v = {}
            for c in x["categories"]:
                cat = next(k for k in d["categories"] if k["name"] == c["name"])
                v.update({n: float(t) for n, t in zip(cat["names"], c["totals"]) if t not in ("", "-", None)})
            gp = v.get("gamesPlayed", 0)
            if not gp: continue
            reb = v.get("avgRebounds", 0); pf = v.get("avgFouls", 0)
            gm = (v["avgPoints"] + .4 * v["avgFieldGoalsMade"] - .7 * v["avgFieldGoalsAttempted"] - .4 * (v["avgFreeThrowsAttempted"] - v["avgFreeThrowsMade"])
                  + .4 * reb + v.get("avgSteals", 0) + .7 * v["avgAssists"] + .7 * v.get("avgBlocks", 0) - .4 * pf - v["avgTurnovers"])
            a = x["athlete"]
            out.append({"id": a["id"], "name": a["displayName"], "last": a.get("lastName", ""), "age": a.get("age"), "team": a.get("teamShortName"),
                        "gp": int(gp), "ppg": v["avgPoints"], "gmsc": round(gm, 2)})
        if page >= d["pagination"]["pages"]: break
        page += 1
    return out


def fetch(slug):
    st = espn.get("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings")
    teams = []
    for conf in st["children"]:
        for e in conf["standings"]["entries"]:
            s = {x["name"]: x.get("value") for x in e["stats"]}
            w, l = int(s["wins"]), int(s["losses"])
            teams.append({"id": e["team"]["id"], "abbr": e["team"]["abbreviation"], "name": e["team"]["displayName"], "conf": conf["abbreviation"],
                          "w": w, "l": l, "ppg": round(s["avgPointsFor"], 1), "oppg": round(s["avgPointsAgainst"], 1),
                          "diff": round(s["avgPointsFor"] - s["avgPointsAgainst"], 1)})
    now, prev = players(), players(2026)
    inj = {}
    for t in espn.get(f"{espn.SITE}/injuries").get("injuries", []):
        for i in t.get("injuries", []):
            if i.get("status") == "Out":
                inj[str(i["athlete"].get("id") or i["athlete"]["links"][0]["href"].split("/id/")[1].split("/")[0])] = {
                    "status": i["status"], "return": (i.get("details") or {}).get("returnDate"), "comment": i.get("shortComment", "")}
    roster = {str(a["id"]): a for a in espn.get(f"{espn.SITE}/teams/{espn.TEAMS[slug]}/roster")["athletes"]}
    return teams, now, prev, inj, roster


def series(pA, rng, n_games):
    """pA: (runs, n_games) prob A wins each game. A wins the series if A wins the majority of all games (same winner as stopping at 4)."""
    return (rng.random(pA.shape) < pA).sum(1) > n_games // 2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("team"); ap.add_argument("--runs", type=int, default=10000); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--date", default=dt.date.today().isoformat()); arg = ap.parse_args()
    slug, R, Y = arg.team, arg.runs, A["SEASONS"]; rng = np.random.default_rng(arg.seed)
    teams, now, prev, inj, roster = fetch(slug)
    T = len(teams); ab = [t["abbr"] for t in teams]; tix = {a: i for i, a in enumerate(ab)}
    me = next(i for i, t in enumerate(teams) if str(t["id"]) == str(espn.TEAMS[slug]))
    conf = np.array([0 if t["conf"] == "East" else 1 for t in teams])

    # ---- player pool: everyone who has played this season, plus our stars (whatever their games played)
    pv = {p["id"]: p for p in prev}; pool = {p["id"]: dict(p) for p in now}
    for sid in STARS[slug]:
        if sid not in pool:
            a = roster[sid]; q = pv[sid]
            pool[sid] = {"id": sid, "name": a["fullName"], "last": a.get("lastName", ""), "age": a.get("age"), "team": ab[me], "gp": 0, "ppg": 0.0, "gmsc": 0.0}
        pool[sid]["team"] = ab[me]
    P = list(pool.values())
    for p in P:
        q = pv.get(p["id"])
        if q and p["gp"]: p["rating"] = round((p["gp"] * p["gmsc"] + A["PRIOR_GP"] * q["gmsc"]) / (p["gp"] + A["PRIOR_GP"]), 2)
        elif q: p["rating"] = round(q["gmsc"] + float(age_step(p["age"])), 2)
        else: p["rating"] = round((p["gp"] * p["gmsc"] + A["PRIOR_GP"] * A["ROOKIE_MEAN"]) / (p["gp"] + A["PRIOR_GP"]), 2)
        p["prev_gp"], p["prev_gmsc"] = (q["gp"], q["gmsc"]) if q else (0, None)
    P = [p for p in P if p["team"] in tix]
    NP0 = len(P); NP = NP0 + A["ROOKIES"] * Y
    sidx = [next(i for i, p in enumerate(P) if p["id"] == s) for s in STARS[slug]]

    # ---- team strength now: shrink the observed differential (normal-normal)
    gp = np.array([t["w"] + t["l"] for t in teams]); diff = np.array([t["diff"] for t in teams])
    k = (A["GAME_SD"] / A["TEAM_SD"]) ** 2
    post_mean = diff * gp / (gp + k); post_sd = np.sqrt(1 / (1 / A["TEAM_SD"] ** 2 + gp / A["GAME_SD"] ** 2))
    val = lambda r: A["STAR_K"] * np.maximum(0, r - A["REPLACEMENT"])
    star_obs = sum(val(P[i]["rating"]) * P[i]["gp"] / gp[me] for i in sidx)
    # league-average value of a team's two best players -> the level "the rest" of our team regresses to
    top2 = [sorted((val(p["rating"]) for p in P if p["team"] == a), reverse=True)[:2] for a in ab]
    mu_rest = -float(np.mean([sum(x) for x in top2])); slot_avg = -mu_rest / 2

    # season-1 share of the remaining games for players who are out right now
    end = dt.date(2027, 4, 12); today = dt.date.fromisoformat(arg.date); left_days = (end - today).days
    out_share = {}
    for i, p in enumerate(P):
        j = inj.get(str(p["id"]))
        if j:
            rd = dt.date.fromisoformat(j["return"][:10]) if j.get("return") else end
            out_share[i] = max(0.0, (end - max(rd, today)).days / left_days) * A["INJURED_RETURN_SHARE"]

    # ---- state arrays (runs x players)
    rating = np.zeros((R, NP)); rating[:, :NP0] = [p["rating"] for p in P]
    age = np.zeros((R, NP)); age[:, :NP0] = [p["age"] for p in P]
    team = np.zeros((R, NP), int); team[:, :NP0] = [tix[p["team"]] for p in P]
    active = np.zeros((R, NP), bool); active[:, :NP0] = True
    net = rng.normal(post_mean, post_sd, (R, T))
    rest = net[:, me] - star_obs  # our non-star level, inferred from our differential so far
    W = np.zeros((R, Y, T), int)
    titles = np.zeros((R, Y), bool); fmvp = np.full((R, Y), -1); mvp = np.full((R, Y), -1, int); allstar = np.zeros((R, Y, len(sidx)), bool)
    ended_by = np.full((R, Y), -2, int)   # -2 missed play-in, -1 champion, else team index that knocked us out
    made_po = np.zeros((R, Y), bool); seed_me = np.zeros((R, Y), int); star_active = np.zeros((R, Y, len(sidx)), bool); star_share = np.zeros((R, Y, len(sidx)))
    ar = np.arange(R); yrs_gone = np.zeros((R, len(sidx)), int)

    def g(pa):  # prob home team wins, from net difference
        return norm.cdf(pa / A["GAME_SD"])

    for y in range(Y):
        if y:   # ageing, retirement, rookies, team drift
            rating += np.where(active, age_step(age) + rng.normal(0, A["RATING_NOISE"], (R, NP)), 0); age += 1
            pr = np.clip(A["RETIRE_SLOPE"] * (age - A["RETIRE_AGE"]), 0, .9); active &= ~(rng.random((R, NP)) < pr)
            s = NP0 + A["ROOKIES"] * (y - 1); e = s + A["ROOKIES"]
            rating[:, s:e] = rng.normal(A["ROOKIE_MEAN"], A["ROOKIE_SD"], (R, A["ROOKIES"])); age[:, s:e] = 20
            team[:, s:e] = rng.integers(0, T, (R, A["ROOKIES"])); active[:, s:e] = True
            net = A["AR"] * net + rng.normal(0, A["YEAR_SD"], (R, T))
            rest = mu_rest + A["AR"] * (rest - mu_rest) + rng.normal(0, A["YEAR_SD"], R)
        # availability (share of games played)
        hurt = rng.random((R, NP)) < (A["INJ_BASE"] + A["INJ_AGE"] * np.maximum(0, age - 30))
        share = np.where(hurt, rng.uniform(.1, .6, (R, NP)), rng.uniform(.8, 1.0, (R, NP))) * active
        if y == 0:
            for i, sh in out_share.items(): share[:, i] = np.minimum(share[:, i], sh)
        # our team: the rest + stars
        gone = np.stack([~active[:, i] for i in sidx], 1); yrs_gone = np.where(gone, yrs_gone + 1, 0)
        repl = slot_avg * (1 - A["AR"] ** yrs_gone) * gone   # a retired star's slot is refilled gradually, toward a league-average top-2 player
        sv = np.stack([val(rating[:, i]) * share[:, i] for i in sidx], 1) + repl
        net[:, me] = rest + sv.sum(1)
        po_net = net.copy(); po_net[:, me] = rest + sum(val(rating[:, i]) * (share[:, i] >= .6) for i in sidx) + repl.sum(1)
        star_active[:, y] = np.stack([active[:, i] for i in sidx], 1); star_share[:, y] = np.stack([share[:, i] for i in sidx], 1)
        # regular season
        if y == 0:
            left = 82 - gp; w0 = np.array([t["w"] for t in teams])
            W[:, y] = w0 + rng.binomial(left, g(net))
        else:
            W[:, y] = rng.binomial(82, g(net))
        wins = W[:, y]
        # seeds per conference
        seeds = []
        for c in (0, 1):
            ids = np.where(conf == c)[0]; key = wins[:, ids] + rng.random((R, len(ids))) * .5
            seeds.append(ids[np.argsort(-key, 1)])   # (R, 15) team index by seed
        champs = []
        for c in (0, 1):
            S = seeds[c]
            def game(h, a):  # single game, h at home -> winner, loser
                hw = rng.random(R) < g(po_net[ar, h] - po_net[ar, a] + A["HOME"]); return np.where(hw, h, a), np.where(hw, a, h)
            def bo7(h, a):
                d = po_net[ar, h] - po_net[ar, a]; home = np.array([1, 1, 0, 0, 1, 0, 1], bool)
                p = g(np.where(home, d[:, None] + A["HOME"], d[:, None] - A["HOME"])); hw = series(p, rng, 7)
                return np.where(hw, h, a), np.where(hw, a, h)
            w78, l78 = game(S[:, 6], S[:, 7]); w910, l910 = game(S[:, 8], S[:, 9]); s8, l8 = game(l78, w910)
            # who knocked us out in the play-in
            m = l910 == me; ended_by[m, y] = w910[m]
            m = l8 == me; ended_by[m, y] = s8[m]
            bracket = [S[:, 0], s8, S[:, 3], S[:, 4], S[:, 2], S[:, 5], S[:, 1], w78]   # 1v8, 4v5, 3v6, 2v7
            seed_of = np.zeros((R, T), int)
            for sd in range(10): seed_of[ar, S[:, sd]] = sd
            seed_of[ar, w78] = 6; seed_of[ar, s8] = 7
            pos = (S[:, :10] == me).any(1); made_po[pos, y] |= True
            if (conf[me] == c):
                hit = S == me; seed_me[:, y] = hit.argmax(1) + 1
            rnd = bracket
            while len(rnd) > 1:
                nxt = []
                for a_, b_ in zip(rnd[::2], rnd[1::2]):
                    hfirst = seed_of[ar, a_] <= seed_of[ar, b_]; h = np.where(hfirst, a_, b_); a2 = np.where(hfirst, b_, a_)
                    wn, ls = bo7(h, a2); m = ls == me; ended_by[m, y] = wn[m]; nxt.append(wn)
                rnd = nxt
            champs.append(rnd[0])
        e, w_ = champs
        hfirst = wins[ar, e] + rng.random(R) * .5 >= wins[ar, w_] + rng.random(R) * .5
        h = np.where(hfirst, e, w_); a2 = np.where(hfirst, w_, e)
        d = po_net[ar, h] - po_net[ar, a2]; home = np.array([1, 1, 0, 0, 1, 0, 1], bool)
        hw = series(g(np.where(home, d[:, None] + A["HOME"], d[:, None] - A["HOME"])), rng, 7)
        ch = np.where(hw, h, a2); ls = np.where(hw, a2, h); m = ls == me; ended_by[m, y] = ch[m]
        titles[:, y] = ch == me; ended_by[titles[:, y], y] = -1
        # Finals MVP among our healthy stars and "someone else"
        cand = np.stack([np.where(share[:, i] >= .6, rating[:, i], -99) for i in sidx] + [np.full(R, A["FMVP_OTHER"])], 1) + rng.normal(0, A["FMVP_SD"], (R, len(sidx) + 1))
        fm = cand.argmax(1); fmvp[titles[:, y], y] = fm[titles[:, y]]
        # All-Stars and MVP
        tw = wins[ar[:, None], team]
        sc = rating + A["WIN_W_AS"] * (tw - 41) + rng.normal(0, A["VOTE_SD"], (R, NP)); sc[share < A["ALLSTAR_MIN_SHARE"]] = -1e9
        pc = conf[team]
        for c in (0, 1):
            s2 = np.where(pc == c, sc, -1e9); thr = -np.sort(-s2, 1)[:, A["ALLSTAR_PER_CONF"] - 1]
            for j, i in enumerate(sidx):
                if conf[me] == c: allstar[:, y, j] = (s2[:, i] >= thr) & (s2[:, i] > -1e8)
        ms = rating + A["WIN_W_MVP"] * (tw - 41) + rng.normal(0, A["VOTE_SD"], (R, NP)); ms[share < A["MVP_MIN_SHARE"]] = -1e9
        mvp[:, y] = ms.argmax(1)
        print(f"season {y+1}/{Y} done", file=sys.stderr)

    # ---- outputs
    first = int(dt.date.fromisoformat(arg.date).year) if dt.date.fromisoformat(arg.date).month >= 9 else int(arg.date[:4]) - 1
    lab = [f"{first + y}-{str(first + y + 1)[2:]}" for y in range(Y)]
    pct = lambda x: round(100 * float(x), 1)
    nt = titles.sum(1)
    per_season = [pct(titles[:, y].mean()) for y in range(Y)]
    best = int(np.argmax(per_season))
    win_lo = next((y for y in range(best, Y) if per_season[y] < per_season[best] / 2), Y)
    names = [P[i]["name"] for i in sidx]
    as_add = allstar.sum(1)   # (R, stars)
    mv_names = {}
    for i in mvp.ravel():
        mv_names[int(i)] = mv_names.get(int(i), 0) + 1
    top_mvp = sorted(mv_names.items(), key=lambda kv: -kv[1])[:8]
    def pname(i): return P[i]["name"] if i < NP0 else "a future draft pick"
    eb = ended_by[ended_by >= 0]; tot = R * Y
    ends = sorted(((ab[t], pct((eb == t).sum() / tot)) for t in set(eb.tolist())), key=lambda kv: -kv[1])
    # the run we hoped for
    star_fm = titles & (fmvp >= 0) & (fmvp < len(sidx))
    star_mvp = np.isin(mvp, sidx)
    best_run = None
    if star_fm.any():
        med = int(np.median(W[:, :, me][titles]))   # wins in a typical title season of ours
        first_t = np.where(titles.any(1), titles.argmax(1), -1)
        dream_mvp = max((star_mvp[:, :] & (mvp == i)).any(1).mean() for i in sidx) >= .005
        for need_mvp in ((True, False) if dream_mvp else (False,)):
            cands = []
            for r in np.where(star_fm.any(1))[0]:
                y = int(first_t[r])
                if not star_fm[r, y] or (need_mvp and not star_mvp[r].any()): continue
                cands.append((abs(int(W[r, y, me]) - med), y, int(r)))
            if cands:
                _, y, r = min(cands); mv = [int(z) for z in np.where(star_mvp[r])[0]]
                best_run = {"run": int(r), "season": lab[y], "season_index": y, "record": f"{W[r, y, me]}-{82 - W[r, y, me]}", "median_title_wins": med, "rings_in_run": int(nt[r]),
                            "finals_mvp": names[fmvp[r, y]], "mvp_seasons": [{"season": lab[z], "player": pname(int(mvp[r, z]))} for z in mv],
                            "ring_seasons": [lab[z] for z in np.where(titles[r])[0]], "needed_mvp": need_mvp,
                            "allstar_seasons": {names[j]: [lab[z] for z in np.where(allstar[r, :, j])[0]] for j in range(len(sidx))},
                            "seasons": [{"season": lab[z], "record": f"{W[r, z, me]}-{82 - W[r, z, me]}", "title": bool(titles[r, z]),
                                         "ended_by": ("CHAMPION" if ended_by[r, z] == -1 else "MISSED PLAY-IN" if ended_by[r, z] == -2 else ab[ended_by[r, z]])} for z in range(Y)]}
                break
    era = titles & star_active.any(2)   # titles won while at least one of the two stars is still playing
    out = {
        "what": "Fan Monte Carlo simulation, not a prediction. See the docstring of gen/sim_era.py for the model.",
        "team": slug, "abbr": ab[me], "date": arg.date, "runs": R, "seasons": Y, "season_labels": lab, "seed": arg.seed,
        "assumptions": ASSUMPTIONS,
        "inputs": {"standings": teams, "stars": [P[i] for i in sidx], "star_injuries": {P[i]["name"]: inj.get(str(P[i]["id"])) for i in sidx},
                   "season1_out_share": {P[i]["name"]: round(out_share[i], 3) for i in out_share if i in sidx},
                   "posterior_net_now": {ab[t]: [round(float(post_mean[t]), 2), round(float(post_sd[t]), 2)] for t in range(T)},
                   "our_rest_level_now": round(float(post_mean[me] - star_obs), 2), "league_rest_level": round(mu_rest, 2),
                   "pool_size_now": NP0, "pool_top": sorted(({k: p[k] for k in ("name", "team", "age", "gp", "rating")} for p in P), key=lambda p: -p["rating"])[:30],
                   "sources": ["https://site.api.espn.com/apis/v2/sports/basketball/nba/standings", BYATH, BYATH + "&season=2026&seasontype=2",
                               f"{espn.SITE}/injuries", f"{espn.SITE}/teams/{espn.TEAMS[slug]}/roster"]},
        "outputs": {
            "record_now": f"{teams[me]['w']}-{teams[me]['l']}",
            "rings": {"at_least_one_pct": pct((nt >= 1).mean()), "exactly_one_pct": pct((nt == 1).mean()), "two_plus_pct": pct((nt >= 2).mean()),
                      "none_pct": pct((nt == 0).mean()), "mean_rings": round(float(nt.mean()), 2), "per_season_pct": dict(zip(lab, per_season)),
                      "best_season": lab[best], "best_season_pct": per_season[best], "after_year3_avg_pct": round(float(np.mean(per_season[3:])), 1),
                      "window": f"{lab[0][:4]}-{lab[win_lo - 1][-2:]}" if win_lo > 0 else lab[0], "window_seasons": win_lo,
                      "with_a_star_still_playing": {"at_least_one_pct": pct(era.any(1).mean()), "exactly_one_pct": pct((era.sum(1) == 1).mean()),
                                                    "share_of_all_rings_pct": pct(era.sum() / max(1, titles.sum()))},
                      "after_both_stars_retired": {"share_of_all_rings_pct": pct((titles & ~star_active.any(2)).sum() / max(1, titles.sum()))}},
            "allstars": {names[j]: {"mean_added": round(float(as_add[:, j].mean()), 2), "median_added": float(np.median(as_add[:, j])),
                                    "dist": {str(n): pct((as_add[:, j] == n).mean()) for n in range(Y + 1)},
                                    "at_least": {str(n): pct((as_add[:, j] >= n).mean()) for n in range(1, Y + 1)},
                                    "per_season_pct": dict(zip(lab, [pct(allstar[:, y, j].mean()) for y in range(Y)]))} for j in range(len(sidx))},
            "mvp": {"ours_at_least_one_pct": {names[j]: pct((mvp == sidx[j]).any(1).mean()) for j in range(len(sidx))},
                    "ours_runs_with_one": {names[j]: int((mvp == sidx[j]).any(1).sum()) for j in range(len(sidx))},
                    "ours_mean": {names[j]: round(float((mvp == sidx[j]).sum(1).mean()), 3) for j in range(len(sidx))},
                    "share_of_all_mvps_pct": [{"player": pname(i), "team": P[i]["team"] if i < NP0 else "", "pct": pct(n / tot)} for i, n in top_mvp]},
            "season_enders_pct_of_sim_seasons": ends[:10],
            "missed_playin_pct_of_sim_seasons": pct((ended_by == -2).mean()),
            "made_playoffs_pct": dict(zip(lab, [pct(made_po[:, y].mean()) for y in range(Y)])),
            "wins_mean": dict(zip(lab, [round(float(W[:, y, me].mean()), 1) for y in range(Y)])),
            "star_still_active_pct": {names[j]: dict(zip(lab, [pct(star_active[:, y, j].mean()) for y in range(Y)])) for j in range(len(sidx))},
            "finals_mvp_when_we_win_pct": {**{names[j]: pct((fmvp[titles] == j).mean()) if titles.any() else 0 for j in range(len(sidx))}, "someone else": pct((fmvp[titles] == len(sidx)).mean()) if titles.any() else 0},
            "run_we_hoped_for": best_run,
        },
    }
    f = ROOT / "data/sim" / f"{slug}_{arg.date}.json"; f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(f)


if __name__ == "__main__":
    main()
