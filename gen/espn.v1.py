"""ESPN data layer: everything a reel needs for any NBA team, from ESPN's public JSON."""
import json, urllib.request, concurrent.futures as cf, datetime as dt
from zoneinfo import ZoneInfo
SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
ET = ZoneInfo("America/New_York")
TEAMS = {"raptors": 28, "warriors": 9}   # add more: ESPN team ids

def get(url, tries=3):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25))
        except Exception as e:
            if i == tries - 1: raise

def team_info(tid):
    t = get(f"{SITE}/teams/{tid}")["team"]
    return {"id": tid, "abbr": t["abbreviation"], "name": t["displayName"], "short": t["name"],
            "record": t["record"]["items"][0]["summary"], "color": "#" + t.get("color", "000000"), "alt": "#" + t.get("alternateColor", "ffffff")}

def player_stats(aid):
    try:
        s = get(f"{WEB}/athletes/{aid}/overview")["statistics"]
        lab = s["labels"]; row = next(sp for sp in s["splits"] if sp["displayName"] == "Regular Season")["stats"]
        d = dict(zip(lab, row)); f = lambda k: float(d.get(k, 0) or 0)
        return {"gp": int(f("GP")), "min": f("MIN"), "ppg": f("PTS"), "rpg": f("REB"), "apg": f("AST"), "p3": f("3P%"), "spg": f("STL")}
    except Exception:
        return {"gp": 0, "min": 0, "ppg": 0, "rpg": 0, "apg": 0, "p3": 0, "spg": 0}

def roster(tid):
    r = get(f"{SITE}/teams/{tid}/roster")["athletes"]
    with cf.ThreadPoolExecutor(8) as ex: stats = list(ex.map(lambda a: player_stats(a["id"]), r))
    out = []
    for a, s in zip(r, stats):
        inj = [i.get("status") for i in a.get("injuries", [])]
        out.append({"id": a["id"], "name": a["fullName"], "last": " ".join(w for w in (a.get("lastName") or a["fullName"].split()[-1]).split() if w.strip(".").lower() not in ("jr","sr","ii","iii","iv")) or a["fullName"].split()[-1], "jersey": a.get("jersey"),
                    "pos": a.get("position", {}).get("abbreviation", ""), "out": any(x in ("Out", "Out For Season") for x in inj),
                    "doubtful": any(x in ("Doubtful", "Day-To-Day", "Questionable") for x in inj), "inj": inj, **s})
    return out

def schedule(tid):
    ev = get(f"{SITE}/teams/{tid}/schedule")["events"]; out = []
    for e in ev:
        c = e["competitions"][0]; me = next(x for x in c["competitors"] if str(x["team"]["id"]) == str(tid)); op = next(x for x in c["competitors"] if x is not me)
        sc = lambda x: (x.get("score") or {}).get("displayValue") if isinstance(x.get("score"), dict) else x.get("score")
        out.append({"id": e["id"], "date": e["date"], "state": c["status"]["type"]["state"], "home": me["homeAway"] == "home",
                    "opp_id": op["team"]["id"], "opp_abbr": op["team"]["abbreviation"], "opp_name": op["team"]["displayName"], "opp_short": op["team"].get("shortDisplayName", op["team"]["displayName"]),
                    "my": sc(me), "their": sc(op), "win": me.get("winner")})
    return out

def when(iso):
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    return d.strftime("%a %-m/%-d"), d.strftime("%-I:%M %p").replace(":00", "")

def boxscore(event_id):
    s = get(f"{SITE}/summary?event={event_id}")
    teams = {}
    for t in s["boxscore"]["players"]:
        lab = t["statistics"][0]["labels"]; rows = []
        for a in t["statistics"][0]["athletes"]:
            if not a.get("stats"): continue
            d = dict(zip(lab, a["stats"])); rows.append({"id": a["athlete"]["id"], "name": a["athlete"]["displayName"], "last": a["athlete"].get("shortName", "").split()[-1], **{k: d.get(k) for k in lab}})
        teams[t["team"]["id"]] = {"abbr": t["team"]["abbreviation"], "rows": rows}
    ts = {t["team"]["id"]: {x["name"]: x.get("displayValue") for x in t["statistics"]} for t in s["boxscore"]["teams"]}
    hdr = s["header"]["competitions"][0]; line = {c["team"]["id"]: [l.get("displayValue") for l in c.get("linescores", [])] for c in hdr["competitors"]}
    return {"teams": teams, "team_stats": ts, "linescore": line, "status": hdr["status"]["type"]["state"], "competitors": {c["team"]["id"]: {"abbr": c["team"]["abbreviation"], "score": c.get("score"), "winner": c.get("winner"), "record": (c.get("record") or [{}])[0].get("summary")} for c in hdr["competitors"]}}

def standings_rank(tid):
    d = get("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings")
    for conf in d["children"]:
        ents = sorted(conf["standings"]["entries"], key=lambda e: -next(float(s["value"]) for s in e["stats"] if s["name"] == "winPercent"))
        for i, e in enumerate(ents, 1):
            if str(e["team"]["id"]) == str(tid): return i, conf["abbreviation"]
    return None, None
