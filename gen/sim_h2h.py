"""Fan Monte Carlo: TODAY's team vs the franchise's best team ever, best-of-7, 10,000 series. A fan simulation, not a prediction.

usage: python3 gen/sim_h2h.py raptors|warriors [--runs 10000] [--seed 7]
  -> data/sim/<team>_h2h_<YYYY-MM-DD>.json  (every input, every assumption below, every output number)
Copy of @8bitwolves Df5806FgG18 ("Today's Wolves vs KG's 2004 Wolves, best-of-7, simulated 10,000 times").

THE MODEL (deliberately simple; every constant is in ASSUMPTIONS and saved with the output)
Inputs
  * The great team: its regular season from Basketball-Reference (saved page in research/sim_h2h/): record, points scored and
    allowed per game, and every player's per-game line (G, MP, PTS, TRB, AST, STL, BLK, 3P).
  * Today's team: ESPN public JSON pulled when the script runs: this season's completed games (points for / against) and every
    rostered player's 2026-27 per-game line (athletes/<id>/stats). Today's team is taken at full strength: players who are
    out right now still count if they have played this season.
1. Graded against its own era: a team's strength = its point margin per game in its own season (points scored minus allowed
   per game). The league average margin is 0 in every season, so +6 means "6 points a game better than an average team
   OF ITS OWN YEAR", whatever the scoring level was. The margin is shrunk toward 0 by its sample size like a normal-normal model
   (team talent SD TEAM_SD, single-game margin SD GAME_SD): 15 games get shrunk a lot, 82 games very little.
2. Games: margin of the home team ~ Normal(strength_home - strength_away + HOME, GAME_SD); home team wins if margin > 0.
   Home court (games 1, 2, 5, 7) goes to the better regular-season winning percentage. Series ends at 4 wins.
3. Rotation: the 8 players with the most minutes per game (at least MIN_GP games for that team that season).
   Playoff minutes: the top 5 play PO_TOP times their minutes (capped at PO_CAP), players 6-8 play PO_BENCH times theirs.
   Per-minute production is the player's own season rate. Each game a player's PTS / REB / AST are Gamma draws around his
   mean (coefficient of variation CV_*), STL / BLK / 3PM are Poisson draws. Stats do not depend on the game result.
4. Series MVP = the player on the series winner with the highest series total of
   PTS + .4 REB + .7 AST + STL + .7 BLK (a box-score Game Score without shooting misses).
"""
import sys, json, re, html, pathlib, argparse, datetime as dt
import numpy as np
from scipy.stats import norm
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import espn

ROOT = pathlib.Path(__file__).resolve().parent.parent
GREAT = {"raptors": dict(season="2018-19", label="2019", bbref="TOR/2019", file="research/sim_h2h/bbref_TOR_2019.html"),
         "warriors": dict(season="2015-16", label="2016", bbref="GSW/2016", file="research/sim_h2h/bbref_GSW_2016.html")}
ASSUMPTIONS = dict(TEAM_SD=4.5, GAME_SD=13.0, HOME=2.5, MIN_GP=20, MIN_GP_NOW=5, ROT=8, PO_TOP=1.06, PO_CAP=40.0, PO_BENCH=0.95,
                   CV_PTS=0.35, CV_REB=0.40, CV_AST=0.45)
A = ASSUMPTIONS


def bbref(path):
    s = open(ROOT / path).read()
    summ = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.search(r'data-template="Partials/Teams/Summary">(.*?)NBA \d{4} Playoffs', s, re.S).group(1))))
    rec = re.search(r"Record:\s*(\d+)-(\d+)", summ); pf = float(re.search(r"PTS/G:\s*([\d.]+)", summ).group(1)); pa = float(re.search(r"Opp PTS/G:\s*([\d.]+)", summ).group(1))
    s2 = s.replace("<!--", "").replace("-->", "")
    tb = re.search(r'<table[^>]*id="per_game_stats".*?</table>', s2, re.S).group(0)
    P = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        c = {k: re.sub(r"<[^>]+>", "", v) for k, v in re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</t[dh]>', row, re.S)}
        nm = html.unescape(c.get("name_display") or c.get("player") or "")
        if not nm or nm.startswith("Team") or not c.get("games", "").isdigit(): continue
        f = lambda k: float(c.get(k) or 0)
        P.append(dict(name=nm, gp=int(c["games"]), min=f("mp_per_g"), pts=f("pts_per_g"), reb=f("trb_per_g"), ast=f("ast_per_g"),
                      stl=f("stl_per_g"), blk=f("blk_per_g"), fg3=f("fg3_per_g")))
    return dict(w=int(rec.group(1)), l=int(rec.group(2)), pf=pf, pa=pa, players=P, summary=summ[:400])


def today(slug):
    tid = espn.TEAMS[slug]
    games = [g for g in espn.schedule(tid) if g["state"] == "post" and g["my"] is not None]
    pf = sum(float(g["my"]) for g in games); pa = sum(float(g["their"]) for g in games); n = len(games)
    w = sum(1 for g in games if float(g["my"]) > float(g["their"]))
    P = []
    for a in espn.get(f"{espn.SITE}/teams/{tid}/roster")["athletes"]:
        d = espn.get(f"{espn.WEB}/athletes/{a['id']}/stats?seasontype=2")
        cat = next((c for c in d.get("categories", []) if c.get("name") == "averages"), None)
        if not cat: continue
        row = next((s for s in cat["statistics"] if s.get("season", {}).get("displayName") == "2026-27"), None)
        if not row: continue
        v = dict(zip(cat["labels"], row["stats"])); f = lambda k: float(str(v.get(k) or 0).split("-")[0] or 0)
        P.append(dict(id=a["id"], name=a["fullName"], gp=int(f("GP")), min=f("MIN"), pts=f("PTS"), reb=f("REB"), ast=f("AST"),
                      stl=f("STL"), blk=f("BLK"), fg3=f("3PT"), out=any(i.get("status") == "Out" for i in a.get("injuries", []))))
    return dict(w=w, l=n - w, pf=round(pf / n, 2), pa=round(pa / n, 2), gp=n, players=P,
                games=[dict(id=g["id"], date=g["date"][:10], opp=g["opp_abbr"], my=g["my"], their=g["their"]) for g in games])


def rotation(players, min_gp):
    R = sorted([p for p in players if p["gp"] >= min_gp], key=lambda p: -p["min"])[:A["ROT"]]
    for i, p in enumerate(R):
        p["po_min"] = round(min(A["PO_CAP"], p["min"] * A["PO_TOP"]) if i < 5 else p["min"] * A["PO_BENCH"], 2)
        k = p["po_min"] / p["min"]
        p["mean"] = {s: p[s] * k for s in ("pts", "reb", "ast", "stl", "blk", "fg3")}
    return R


def strength(margin, gp):
    k = (A["GAME_SD"] / A["TEAM_SD"]) ** 2
    return margin * gp / (gp + k)


def gamma(rng, mean, cv, shape):
    k = 1 / cv ** 2
    return rng.gamma(k, np.maximum(mean, 1e-9) / k, size=shape)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("team"); ap.add_argument("--runs", type=int, default=10000); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--date", default=dt.date.today().isoformat()); arg = ap.parse_args()
    slug, R = arg.team, arg.runs; rng = np.random.default_rng(arg.seed); G = GREAT[slug]
    old = bbref(G["file"]); now = today(slug)
    old["margin"] = round(old["pf"] - old["pa"], 2); now["margin"] = round(now["pf"] - now["pa"], 2)
    old_gp = old["w"] + old["l"]
    s_old, s_now = strength(old["margin"], old_gp), strength(now["margin"], now["gp"])
    old_home = old["w"] / old_gp >= now["w"] / max(1, now["gp"])
    rot_old, rot_now = rotation(old["players"], A["MIN_GP"]), rotation(now["players"], A["MIN_GP_NOW"])

    # ---- games: 7 per series drawn (games after the clinch are ignored)
    home_old = np.array([1, 1, 0, 0, 1, 0, 1], bool) if old_home else np.array([0, 0, 1, 1, 0, 1, 0], bool)
    mu = np.where(home_old, s_old - s_now + A["HOME"], s_old - s_now - A["HOME"])   # old team's expected margin per game
    marg = rng.normal(mu, A["GAME_SD"], size=(R, 7)); old_w = marg > 0
    cw_old, cw_now = np.cumsum(old_w, 1), np.cumsum(~old_w, 1)
    end = np.argmax((cw_old == 4) | (cw_now == 4), axis=1)          # index of the clinching game
    length = end + 1; old_series = cw_old[np.arange(R), end] == 4
    played = np.arange(7)[None, :] <= end[:, None]                    # (R,7)

    # ---- box scores for every player in every game
    def lines(rot):
        out = []
        for p in rot:
            m = p["mean"]
            st = dict(pts=gamma(rng, m["pts"], A["CV_PTS"], (R, 7)), reb=gamma(rng, m["reb"], A["CV_REB"], (R, 7)), ast=gamma(rng, m["ast"], A["CV_AST"], (R, 7)),
                      stl=rng.poisson(m["stl"], (R, 7)).astype(float), blk=rng.poisson(m["blk"], (R, 7)).astype(float), fg3=rng.poisson(m["fg3"], (R, 7)).astype(float))
            st = {k: np.round(v) for k, v in st.items()}
            out.append(st)
        return out
    L_old, L_now = lines(rot_old), lines(rot_now)
    gs = lambda s: s["pts"] + .4 * s["reb"] + .7 * s["ast"] + s["stl"] + .7 * s["blk"]
    tot = lambda s: np.where(played, gs(s), 0).sum(1)
    T_old = np.stack([tot(s) for s in L_old], 1); T_now = np.stack([tot(s) for s in L_now], 1)
    mvp_old = np.argmax(T_old, 1); mvp_now = np.argmax(T_now, 1)
    ng = played.sum()

    def avg(rot, L):
        out = []
        for p, s in zip(rot, L):
            a = {k: round(float(np.where(played, v, 0).sum() / ng), 2) for k, v in s.items()}
            a["pts30_pct"] = round(float(((s["pts"] >= 30) & played).sum() / ng * 100), 1)
            a["pts20_reb10_pct"] = round(float(((s["pts"] >= 20) & (s["reb"] >= 10) & played).sum() / ng * 100), 1)
            a["pts30_reb10_pct"] = round(float(((s["pts"] >= 30) & (s["reb"] >= 10) & played).sum() / ng * 100), 1)
            a["fg3_5_pct"] = round(float(((s["fg3"] >= 5) & played).sum() / ng * 100), 1)
            out.append(dict(name=p["name"], id=p.get("id"), gp=p["gp"], min=p["min"], po_min=p["po_min"],
                            season=dict(pts=p["pts"], reb=p["reb"], ast=p["ast"], stl=p["stl"], blk=p["blk"], fg3=p["fg3"]), sim=a))
        return out
    A_old, A_now = avg(rot_old, L_old), avg(rot_now, L_now)
    for i, a in enumerate(A_old):
        a["mvp_pct_of_old_wins"] = round(float((mvp_old[old_series] == i).mean() * 100), 1)
        a["mvp_pct_all"] = round(float(((mvp_old == i) & old_series).mean() * 100), 1)
    for i, a in enumerate(A_now):
        a["mvp_pct_of_now_wins"] = round(float((mvp_now[~old_series] == i).mean() * 100), 1) if (~old_series).any() else 0.0
        a["mvp_pct_all"] = round(float(((mvp_now == i) & ~old_series).mean() * 100), 1)

    dist = {f"old_in_{k}": round(float(((length == k) & old_series).mean() * 100), 1) for k in (4, 5, 6, 7)}
    dist.update({f"now_in_{k}": round(float(((length == k) & ~old_series).mean() * 100), 1) for k in (4, 5, 6, 7)})
    mode = max(dist, key=dist.get)
    g7 = length == 7
    out = dict(
        what=f"{slug}: today's team (2026-27) vs the {G['season']} team, best-of-7, {R} series. Fan simulation, not a prediction.",
        date=arg.date, runs=R, seed=arg.seed, assumptions=A,
        sources=dict(great=f"https://www.basketball-reference.com/teams/{G['bbref']}.html", today="ESPN public JSON (team schedule, roster, athletes/<id>/stats), pulled " + arg.date),
        inputs=dict(
            great=dict(season=G["season"], label=G["label"], w=old["w"], l=old["l"], pf=old["pf"], pa=old["pa"], margin=old["margin"], strength=round(s_old, 2),
                       rotation=[{k: p[k] for k in ("name", "gp", "min", "po_min", "pts", "reb", "ast", "stl", "blk", "fg3")} for p in rot_old]),
            today=dict(season="2026-27", w=now["w"], l=now["l"], gp=now["gp"], pf=now["pf"], pa=now["pa"], margin=now["margin"], strength=round(s_now, 2), games=now["games"],
                       rotation=[{k: p[k] for k in ("id", "name", "gp", "min", "po_min", "pts", "reb", "ast", "stl", "blk", "fg3", "out")} for p in rot_now]),
            home_court="great" if old_home else "today", p_game_old_home=round(float(norm.cdf((s_old - s_now + A["HOME"]) / A["GAME_SD"])), 3),
            p_game_old_away=round(float(norm.cdf((s_old - s_now - A["HOME"]) / A["GAME_SD"])), 3)),
        outputs=dict(
            great_wins_pct=round(float(old_series.mean() * 100), 1), today_wins_pct=round(float((~old_series).mean() * 100), 1),
            dist=dist, most_common=mode, most_common_pct=dist[mode],
            great_most_common_len=max((4, 5, 6, 7), key=lambda k: dist[f"old_in_{k}"]),
            game7_pct=round(float(g7.mean() * 100), 1), today_wins_game7_pct=round(float((~old_series[g7]).mean() * 100), 1) if g7.any() else 0.0,
            avg_length=round(float(length.mean()), 2),
            great_players=A_old, today_players=A_now))
    p = ROOT / "data/sim" / f"{slug}_h2h_{arg.date}.json"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(out, indent=1))
    o = out["outputs"]
    print(p); print(f"great {o['great_wins_pct']}%  mode {o['most_common']} {o['most_common_pct']}%  g7 {o['game7_pct']}% (today wins {o['today_wins_game7_pct']}%)  strength old {s_old:.2f} now {s_now:.2f}")
    for a in A_old[:4] + A_now[:4]: print(" ", a["name"], a["sim"]["pts"], a["sim"]["reb"], a["sim"]["ast"], a["sim"]["blk"], a["sim"]["fg3"], a.get("mvp_pct_of_old_wins", a.get("mvp_pct_of_now_wins")), a["sim"]["pts30_pct"])


if __name__ == "__main__":
    main()
