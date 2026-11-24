"""Shot-chart game recap (copy of @8bitwolves Df2aW0Zg3nZ "Wolves vs Blazers by the shot chart").

usage: python3 gen/shotchart.py <raptors|warriors> <espn event id> [--out specs/x.json]
   -> specs/<r|w>_sc_<opp>.json, a ready-to-build spec for gen/fmt_shotchart.html:
      python3 gen/factcheck.py specs/r_sc_nyk.json && zsh gen/batch.sh specs/r_sc_nyk.json

Everything comes from ESPN's summary for the event (box score + play-by-play shot log with x/y).
The script finds the game's story the way Wolves does (a paradox in the numbers first: "Portland made 4 more shots
than us and still lost by 8"), writes the narration in fan voice (we/us/our), the on-screen text, the caption and
the "facts" list that gen/factcheck.py checks. Refuses to write a spec for a game that isn't final.

Court coordinates: ESPN gives x 0-50 ft across the court and y in ft from the rim (baseline about -5). Zones:
RIM within 5 ft of the rim, PAINT the rest of the lane (16 ft wide, to the free-throw line), MIDRANGE other twos,
CORNER 3 threes taken below 9 ft, 3 PT other threes. End-of-quarter heaves are dropped (ESPN's box score drops them too).
Shot dots are passed to the template letter-encoded (no digits) so the fact check only sees numbers a viewer reads.
"""
import sys, json, math, re, pathlib, argparse, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import espn

ROOT = pathlib.Path(__file__).resolve().parent.parent
ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
EMO = {"raptors": "🦖", "warriors": "💛"}
ABBR3 = {"NY": "nyk", "GS": "gsw", "NO": "nop", "SA": "sas", "UTAH": "uta", "WSH": "was", "BKN": "bkn", "LAL": "lal", "LAC": "lac"}
ORD = {1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH"}
ORDW = {1: "first", 2: "second", 3: "third", 4: "fourth"}
ZORDER = ["RIM", "PAINT", "MIDRANGE", "CORNER 3", "3 PT"]


# ---------------------------------------------------------------- words for the narrator
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
def w(n):
    n = int(n)
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000: h, r = divmod(n, 100); return ONES[h] + " hundred" + ("" if r == 0 else " " + w(r))
    return str(n)
def ws(n):
    """A score the way a broadcaster says it: 106 -> one oh six, 115 -> one fifteen."""
    n = int(n)
    if 100 <= n < 200: r = n - 100; return "one " + ("hundred" if r == 0 else "oh " + ONES[r] if r < 10 else w(r))
    return w(n)
SAY = {"Saddiq": "Sah-deek", "Yaxel": "Yak-sel"}   # narration-only respellings (gen/tts.py has the shared list)
def say(t):
    for k, v in SAY.items(): t = t.replace(k, v)
    return t
def rec_w(rec):
    a, b = rec.split("-"); return f"{w(a)} and {w(b)}"


# ---------------------------------------------------------------- data
def zone(x, y, three):
    if three: return "CORNER 3" if y <= 9 else "3 PT"
    if math.hypot(x - 25, y) <= 5: return "RIM"
    if abs(x - 25) <= 8 and y <= 14: return "PAINT"
    return "MIDRANGE"


def enc_shots(shots):
    s = ""
    for p in shots:
        x = max(0, min(51, round(p["x"]))); y = max(0, min(51, round(p["y"]) + 5))
        s += ABC[x] + ABC[y] + ("+" if p["made"] else ".")
    return s


def frac(m, a): return f"{m}/{a}"


def load(event):
    url = f"{espn.SITE}/summary?event={event}"; s = espn.get(url)
    hdr = s["header"]["competitions"][0]
    if hdr["status"]["type"]["state"] != "post":
        sys.exit(f"game {event} is not final yet ({hdr['status']['type'].get('detail', '')}); run again when it is")
    return s, url


def team_meta(tid):
    t = espn.get(f"{espn.SITE}/teams/{tid}")["team"]
    return {"id": str(tid), "abbr": t["abbreviation"], "loc": t["location"], "short": t["name"], "color": "#" + t.get("color", "333333"),
            "alt": "#" + t.get("alternateColor", "777777"), "arena": ((t.get("franchise") or {}).get("venue") or {}).get("fullName", "")}


def lum(h): n = int(h[1:], 16); return .299 * (n >> 16) + .587 * ((n >> 8) & 255) + .114 * (n & 255)
def dist(a, b): A, B = int(a[1:], 16), int(b[1:], 16); return sum(abs(((A >> k) & 255) - ((B >> k) & 255)) for k in (16, 8, 0))
def mute(h, f=.82):
    """Wolves' bars are muted team colours (#4377a2, #9d3431): pull toward slate a little."""
    n = int(h[1:], 16); c = [(n >> 16) & 255, (n >> 8) & 255, n & 255]; gy = (90, 98, 112)
    return "#" + "".join(f"{round(v * f + g * (1 - f)):02x}" for v, g in zip(c, gy))
def pick_colors(us, op):
    ok = lambda h: 45 < lum(h) < 190
    uc = min([h for h in (us["color"], us["alt"]) if ok(h)] or ["#4377a2"], key=lum)   # the deeper colour, like their blue
    cands = [h for h in (op["color"], op["alt"]) if ok(h) and dist(h, uc) > 160]
    oc = cands[0] if cands else ("#9d3431" if dist("#9d3431", uc) > 160 else "#7a8a9a")
    return mute(uc), mute(oc)


def parse(s, tids):
    plays = s["plays"]; shots = collections.defaultdict(list); ft = collections.defaultdict(list)
    for p in plays:
        if not p.get("shootingPlay"): continue
        tid = str(p["team"]["id"]); pid = str(p["participants"][0]["athlete"]["id"]) if p.get("participants") else ""
        per = p["period"]["number"]
        if "Free Throw" in p["type"]["text"]: ft[tid].append({"pid": pid, "made": bool(p["scoringPlay"]), "per": per}); continue
        c = p.get("coordinate") or {}
        x, y = c.get("x", -1), c.get("y", -1)
        if "Heave" in p["type"]["text"] or not (-1 <= x <= 51 and -6 <= y <= 40): continue   # heaves / bad coordinates
        three = p.get("pointsAttempted") == 3 or "three point" in p.get("text", "")
        shots[tid].append({"pid": pid, "x": x, "y": y, "made": bool(p["scoringPlay"]), "three": three, "per": per, "z": zone(x, y, three)})
    return shots, ft


def box_rows(s):
    out = {}
    for t in s["boxscore"]["players"]:
        lab = t["statistics"][0]["labels"]
        for a in t["statistics"][0]["athletes"]:
            if not a.get("stats"): continue
            d = dict(zip(lab, a["stats"])); at = a["athlete"]
            last = at.get("lastName") or at["displayName"].split()[-1]
            last = " ".join(x for x in last.split() if x.strip(".").lower() not in ("jr", "sr", "ii", "iii", "iv")) or last
            r = {"id": str(at["id"]), "tid": str(t["team"]["id"]), "name": at["displayName"], "last": last.upper(), "box": d}
            mk = lambda k: tuple(int(v) for v in d[k].split("-")) if d.get(k) and "-" in d[k] else (0, 0)
            r.update(pts=int(d.get("PTS") or 0), reb=int(d.get("REB") or 0), ast=int(d.get("AST") or 0), fg=mk("FG"), tp=mk("3PT"), ftl=mk("FT"))
            out[r["id"]] = r
    return out


def team_box(s):
    ts = {}
    for t in s["boxscore"]["teams"]:
        st = {x["name"]: x.get("displayValue") for x in t["statistics"]}
        mk = lambda k: tuple(int(v) for v in st[k].split("-"))
        ts[str(t["team"]["id"])] = {"fg": mk("fieldGoalsMade-fieldGoalsAttempted"), "tp": mk("threePointFieldGoalsMade-threePointFieldGoalsAttempted"),
                                    "ft": mk("freeThrowsMade-freeThrowsAttempted"), "reb": int(st.get("totalRebounds") or 0)}
    return ts


def zones_of(shots):
    z = collections.OrderedDict((k, [0, 0]) for k in ZORDER)
    for p in shots: z[p["z"]][1] += 1; z[p["z"]][0] += p["made"]
    return [(k, m, a) for k, (m, a) in z.items() if a]


# ---------------------------------------------------------------- story
def build(slug, event):
    s, url = load(event); my = str(espn.TEAMS[slug]); hdr = s["header"]["competitions"][0]
    comp = {str(c["team"]["id"]): c for c in hdr["competitors"]}; op = next(k for k in comp if k != my)
    US, OP = team_meta(my), team_meta(op); home = comp[my]["homeAway"] == "home"
    try:
        hv = [e["venue"] for e in espn.schedule(my) if e["home"] and e["state"] == "post" and e.get("venue")]
        if hv: US["arena"] = hv[-1]
    except Exception: pass
    sc = {k: int(comp[k]["score"]) for k in comp}; won = sc[my] > sc[op]; M = abs(sc[my] - sc[op])
    rec = next((r["summary"] for r in comp[my].get("record", []) if r.get("type") == "total"), "")
    lines = {k: [int(l.get("displayValue")) for l in comp[k].get("linescores", [])] for k in comp}
    TB = team_box(s); BX = box_rows(s); SH, FT = parse(s, comp)
    usc, opc = pick_colors(US, OP)
    review = []
    for k in (my, op):
        pm, pa = sum(p["made"] for p in SH[k]), len(SH[k])
        if (pm, pa) != TB[k]["fg"]: review.append(f"play-by-play has {comp[k]['team']['abbreviation']} {pm}/{pa} FG, box score {TB[k]['fg'][0]}/{TB[k]['fg'][1]}: zone tiles won't add up to the FG line")
    city = s.get("gameInfo", {}).get("venue", {}).get("address", {}).get("city", "") or (US["loc"] if home else OP["loc"])
    W_, L_ = (my, op) if won else (op, my)
    Opp, OPP = OP["loc"], OP["loc"].upper()
    nper = len(lines[my]); P = lambda per: ORD.get(per, "OT")
    claims = []   # numbers from the summary that aren't box-score lines, stated plainly for the fact check
    fg = {k: TB[k]["fg"] for k in comp}; tp = {k: TB[k]["tp"] for k in comp}; ftt = {k: TB[k]["ft"] for k in comp}
    claims.append(f"Matchup: {US['loc']} {US['short']} vs {OP['loc']} {OP['short']}.")
    claims.append(f"ESPN box score, final {US['abbr']} {sc[my]} {OP['abbr']} {sc[op]}: {US['abbr']} FG {fg[my][0]}-{fg[my][1]}, 3PT {tp[my][0]}-{tp[my][1]}, FT {ftt[my][0]}-{ftt[my][1]}; "
                  f"{OP['abbr']} FG {fg[op][0]}-{fg[op][1]}, 3PT {tp[op][0]}-{tp[op][1]}, FT {ftt[op][0]}-{ftt[op][1]}. Linescore {US['abbr']} {' '.join(map(str, lines[my]))}, "
                  f"{OP['abbr']} {' '.join(map(str, lines[op]))}. {US['abbr']} record after the game {rec}. Margin {M}.")

    # ---- hook angle: a paradox in the numbers, like Wolves
    rest = {k: sum(lines[k][1:]) for k in comp}; half2 = {k: sum(lines[k][2:]) for k in comp}
    ang = None
    if fg[L_][0] > fg[W_][0]: ang = ("shots", fg[L_][0] - fg[W_][0])
    elif rest[L_] > rest[W_] and lines[W_][0] - lines[L_][0] >= max(15, M): ang = ("rest", rest[L_] - rest[W_])   # one awful quarter beats "won the 2nd half"
    elif nper >= 4 and half2[L_] > half2[W_]: ang = ("half2", half2[L_] - half2[W_])
    elif rest[L_] > rest[W_]: ang = ("rest", rest[L_] - rest[W_])
    elif tp[L_][0] > tp[W_][0]: ang = ("threes", tp[L_][0] - tp[W_][0])
    elif ftt[L_][0] - ftt[W_][0] >= 5: ang = ("ft", ftt[L_][0] - ftt[W_][0])
    else: ang = ("plain", abs(fg[my][0] - fg[op][0]))
    kind, n = ang
    usW = (L_ != my)                     # we're the winner
    res = (f"WE WON {sc[my]}-{sc[op]}" if won else f"WE LOST {sc[my]}-{sc[op]}")
    def bars(title, vals): rows = sorted([{"l": "l:" + US["abbr"], "v": vals[my], "us": True}, {"l": "l:" + OP["abbr"], "v": vals[op]}], key=lambda r: -r["v"]); return {"title": title, "rows": rows}
    LS = "us" if L_ == my else "them"
    if kind == "shots":
        head = "WE MADE MORE SHOTS" if L_ == my else "THEY MADE MORE SHOTS"; card = bars("MADE SHOTS", {k: fg[k][0] for k in comp})
        vo0 = (f"We made {w(n)} more {'shot' if n == 1 else 'shots'} than {Opp} and still lost by {w(M)}." if L_ == my else f"{Opp} made {w(n)} more {'shot' if n == 1 else 'shots'} than us and still lost by {w(M)}.")
        d0 = (f"WE MADE {n} MORE|SHOTS. WE LOST BY {M}." if L_ == my else f"{OPP} MADE {n} MORE|SHOTS. WE WON BY {M}.")
        tail = "the chart doesn't tell it all"; story = (f"We made more shots. {Opp} won by {M}." if L_ == my else f"{Opp} made more shots. We won by {M}.")
    elif kind in ("half2", "rest"):
        v = half2 if kind == "half2" else rest; lab = "2ND HALF POINTS" if kind == "half2" else "POINTS AFTER THE 1ST"
        claims.append(f"{'Second-half' if kind == 'half2' else 'Points over the last ' + str(nper - 1) + ' quarters (after the 1st)'}: {US['abbr']} {v[my]}, {OP['abbr']} {v[op]}.")
        card = bars(lab, v)
        if kind == "half2":
            head = "WE WON THE 2ND HALF" if L_ == my else "THEY WON THE 2ND HALF"
            vo0 = (f"We won the second half by {w(n)} and still lost by {w(M)}." if L_ == my else f"{Opp} won the second half by {w(n)}, and we still won by {w(M)}.")
            d0 = (f"WE WON THE 2ND HALF.|WE LOST BY {M}." if L_ == my else f"THEY WON THE 2ND HALF.|WE WON BY {M}.")
            tail = "the first half tells it"; story = (f"We won the second half. We lost by {M}." if L_ == my else f"{Opp} won the second half. We won by {M}.")
        else:
            head = "WE OUTSCORED THEM" if L_ == my else "THEY OUTSCORED US"
            vo0 = (f"We outscored {Opp} after the first and still lost by {w(M)}." if L_ == my else f"{Opp} outscored us after the first, and we still won by {w(M)}.")
            d0 = (f"WE WON THE LAST {nper - 1} QUARTERS|BY {n}. WE LOST BY {M}." if L_ == my else f"THEY WON THE LAST {nper - 1}|QUARTERS BY {n}. WE WON BY {M}.")
            tail = "watch the first quarter"; story = (f"We outscored {Opp} after the 1st quarter. We lost by {M}." if L_ == my else f"{Opp} outscored us after the 1st quarter. We won by {M}.")
            if L_ == my: d0 = f"WE OUTSCORED THEM BY {n}|AFTER THE 1ST. LOST BY {M}."
            else: d0 = f"THEY OUTSCORED US BY {n}|AFTER THE 1ST. WE WON BY {M}."
    elif kind == "threes":
        head = "WE MADE MORE THREES" if L_ == my else "THEY MADE MORE THREES"; card = bars("THREES MADE", {k: tp[k][0] for k in comp})
        vo0 = (f"We made {w(n)} more {'three' if n == 1 else 'threes'} than {Opp} and still lost by {w(M)}." if L_ == my else f"{Opp} made {w(n)} more {'three' if n == 1 else 'threes'} than us and still lost by {w(M)}.")
        d0 = (f"WE MADE {n} MORE|THREES. LOST BY {M}." if L_ == my else f"{OPP} MADE {n} MORE|THREES. WE WON BY {M}.")
        tail = "the threes don't tell it all"; story = (f"We made more threes. {Opp} won by {M}." if L_ == my else f"{Opp} made more threes. We won by {M}.")
    elif kind == "ft":
        head = "WE MADE MORE FREE THROWS" if L_ == my else "THEY MADE MORE FREE THROWS"; card = bars("FREE THROWS MADE", {k: ftt[k][0] for k in comp})
        vo0 = (f"We made {w(n)} more {'free throw' if n == 1 else 'free throws'} than {Opp} and still lost by {w(M)}." if L_ == my else f"{Opp} made {w(n)} more {'free throw' if n == 1 else 'free throws'} than us and still lost by {w(M)}.")
        d0 = (f"WE MADE {n} MORE FREE|THROWS. LOST BY {M}." if L_ == my else f"{OPP} MADE {n} MORE|FREE THROWS. WE WON BY {M}.")
        tail = "the line doesn't tell it all"; story = (f"We won the free throw line. {Opp} won by {M}." if L_ == my else f"{Opp} won the free throw line. We won by {M}.")
    else:
        more = max(comp, key=lambda k: fg[k][0])
        head = "WE MADE MORE SHOTS" if more == my else "THEY MADE MORE SHOTS"; card = bars("MADE SHOTS", {k: fg[k][0] for k in comp})
        if won: vo0 = f"We made {w(n)} more {'shot' if n == 1 else 'shots'} than {Opp} and won by {w(M)}."; d0 = f"WE MADE {n} MORE|SHOTS. WE WON BY {M}."
        else: vo0 = f"{Opp} made {w(n)} more {'shot' if n == 1 else 'shots'} than us and won by {w(M)}."; d0 = f"{OPP} MADE {n} MORE|SHOTS. WE LOST BY {M}."
        tail = "the chart tells it all"; story = (f"We won by {M}." if won else f"{Opp} won by {M}.")
    if n == 0 and kind == "plain": vo0 = vo0.replace(f"{w(0)} more shots than {Opp} and", "as many shots as " + Opp + " and")

    # ---- the difference: the stat that explains the winner's margin best
    q = [(lines[W_][i] - lines[L_][i], i + 1) for i in range(nper)]; qm, qn = max(q)
    rimm = {k: sum(p["made"] for p in SH[k] if p["z"] == "RIM") for k in comp}; rima = {k: sum(1 for p in SH[k] if p["z"] == "RIM") for k in comp}
    qfg = lambda k, per: (sum(p["made"] for p in SH[k] if p["per"] == per), sum(1 for p in SH[k] if p["per"] == per))
    qtp = lambda k, per: (sum(p["made"] for p in SH[k] if p["per"] == per and p["three"]), sum(1 for p in SH[k] if p["per"] == per and p["three"]))
    cand = []
    if kind not in ("ft",): cand.append(("ft", ftt[W_][0] - ftt[L_][0]))
    if kind not in ("threes",): cand.append(("threes", 3 * (tp[W_][0] - tp[L_][0])))
    cand.append(("rim", 2 * (rimm[W_] - rimm[L_])))
    if qn <= 4 and qm >= 10 and kind not in ("half2",): cand.append(("quarter", qm + (6 if kind == "rest" and qn == 1 else 0)))
    dk, dv = max(cand, key=lambda c: c[1])
    if dk == "ft": dlab, dname, dsay = "FREE THROWS", "THE LINE", "the line"; dvals = {k: ftt[k] for k in comp}
    elif dk == "threes": dlab, dname, dsay = "THREES", "THE 3 BALL", "the three ball"; dvals = {k: tp[k] for k in comp}
    elif dk == "rim": dlab, dname, dsay = "AT THE RIM", "THE RIM", "the rim"; dvals = {k: (rimm[k], rima[k]) for k in comp}
    else: dlab, dname, dsay = f"{P(qn)} QUARTER", f"THE {P(qn)} QUARTER", f"the {ORDW[qn]} quarter"; dvals = {k: qfg(k, qn) for k in comp}
    if dk == "rim": claims.append(f"Play-by-play shot log, shots within 5 ft of the rim: {US['abbr']} {rimm[my]}/{rima[my]}, {OP['abbr']} {rimm[op]}/{rima[op]}.")
    if dk == "quarter": claims.append(f"Play-by-play, {P(qn).lower()} quarter: {US['abbr']} FG {dvals[my][0]}/{dvals[my][1]}, 3PT {qtp(my, qn)[0]}/{qtp(my, qn)[1]}; {OP['abbr']} FG {dvals[op][0]}/{dvals[op][1]}, 3PT {qtp(op, qn)[0]}/{qtp(op, qn)[1]}. Score after the {P(qn).lower()}: {US['abbr']} {sum(lines[my][:qn])}, {OP['abbr']} {sum(lines[op][:qn])}.")
    dm, da, om, oa = dvals[my][0], dvals[my][1], dvals[op][0], dvals[op][1]
    if dk == "ft" and abs(da - oa) >= 8: vo5 = f"The difference was {dsay}. We shot {w(da)} free throws, {Opp} shot {w(oa)}."; d5 = f"FREE THROWS:|{da} TO {oa}."
    else:
        unit = {"ft": "at the line", "threes": "from three", "rim": "at the rim", "quarter": f"in the {ORDW.get(qn, '')}"}[dk]
        vo5 = f"The difference: {dsay}. {w(dm).capitalize()} of {w(da)}, to {w(om)} of {w(oa)}."; d5 = f"{dlab}:|{dm} OF {da} VS {om} OF {oa}."
    fcard = {"title": f"{dlab}: MADE / TRIED", "rows": [{"l": "l:" + US["abbr"], "m": dm, "a": da, "us": True}, {"l": "l:" + OP["abbr"], "m": om, "a": oa}]}

    # ---- players
    def rim_of(pid, tid): sh = [p for p in SH[tid] if p["pid"] == pid]; return sum(p["made"] for p in sh if p["z"] == "RIM"), sum(1 for p in sh if p["z"] == "RIM")
    def pbp_ok(r): sh = [p for p in SH[r["tid"]] if p["pid"] == r["id"]]; return (sum(p["made"] for p in sh), len(sh)) == r["fg"]
    def shots_of(r): return [p for p in SH[r["tid"]] if p["pid"] == r["id"]]
    mine = sorted([r for r in BX.values() if r["tid"] == my], key=lambda r: (-r["pts"], r["fg"][1])); theirs = sorted([r for r in BX.values() if r["tid"] == op], key=lambda r: (-r["pts"], r["fg"][1]))
    star = next((r for r in mine if pbp_ok(r)), mine[0])
    second = max([r for r in mine if r is not star], key=lambda r: r["pts"] + .8 * r["reb"] + .9 * r["ast"] + (4 if r["reb"] >= 10 or r["ast"] >= 10 else 0))
    pfacts = collections.defaultdict(set)
    def use(r, *stats): pfacts[r["id"]].update(stats)
    sr = rim_of(star["id"], my)
    hi = []
    if star["ftl"][0] >= 6 and star["ftl"][0] >= .85 * star["ftl"][1]: hi.append(("ft", f"FT: {star['ftl'][0]}/{star['ftl'][1]}", f"{w(star['ftl'][0])} of {w(star['ftl'][1])} at the line", f"{star['ftl'][0]} OF {star['ftl'][1]} AT THE LINE"))
    if star["tp"][0] >= 4: hi.append(("tp", f"3PT: {star['tp'][0]}/{star['tp'][1]}", f"{w(star['tp'][0])} of {w(star['tp'][1])} from three", f"{star['tp'][0]} OF {star['tp'][1]} FROM 3"))
    if sr[0] >= 4: hi.append(("rim", f"RIM: {sr[0]}/{sr[1]}", f"{w(sr[0])} of {w(sr[1])} at the rim", f"{sr[0]} OF {sr[1]} AT THE RIM"))
    use(star, "PTS", "FG")
    if not hi: hi.append(("fg", f"FG: {star['fg'][0]}/{star['fg'][1]}", f"{w(star['fg'][0])} of {w(star['fg'][1])} from the floor", f"{star['fg'][0]} OF {star['fg'][1]} FROM THE FLOOR"))
    for h in hi[:2]:
        if h[0] == "ft": use(star, "FT")
        if h[0] == "tp": use(star, "3PT")
    if sr[1] and any(h[0] == "rim" for h in hi[:2]): claims.append(f"Play-by-play shot log: {star['name']} {sr[0]}/{sr[1]} within 5 ft of the rim.")
    h1 = hi[0]; h2 = hi[1] if len(hi) > 1 else None
    vo_s1 = f"{star['last'].title()} had {w(star['pts'])}, {h1[2]}."
    d_s1 = f"{star['last']}: {star['pts']} PTS,|{h1[3]}."
    eff = star["pts"] >= 1.5 * max(1, star["fg"][1])
    if h2 and eff: vo_s2 = f"Add {h2[2]}, and that's {w(star['pts'])} points on {w(star['fg'][1])} shots."; d_s2 = f"{h2[3]}.|{star['pts']} PTS ON {star['fg'][1]} SHOTS."
    elif h2: vo_s2 = f"Add {h2[2]}, but {w(star['fg'][0])} of {w(star['fg'][1])} overall."; d_s2 = f"{h2[3]}.|{star['fg'][0]} OF {star['fg'][1]} OVERALL."
    else: vo_s2 = f"That's {w(star['pts'])} points on {w(star['fg'][0])} of {w(star['fg'][1])} shooting."; d_s2 = f"{star['pts']} PTS ON|{star['fg'][0]} OF {star['fg'][1]} SHOOTING."
    chip2 = h2[1] if h2 else f"{star['fg'][1]} FGA"
    if not h2: chip2 = f"FG: {star['fg'][0]}/{star['fg'][1]}"
    # second guy
    s2 = second
    if s2["reb"] >= 10: vo_2 = f"{s2['last'].title()} did the dirty work, {w(s2['pts'])} points and {w(s2['reb'])} boards."; d_2 = f"{s2['last']}: {s2['pts']} PTS,|{s2['reb']} REB."; c2 = [f"{s2['pts']} PTS", f"{s2['reb']} REB"]; use(s2, "PTS", "REB")
    elif s2["ast"] >= 8: vo_2 = f"{s2['last'].title()} ran the show, {w(s2['pts'])} points and {w(s2['ast'])} assists."; d_2 = f"{s2['last']}: {s2['pts']} PTS,|{s2['ast']} AST."; c2 = [f"{s2['pts']} PTS", f"{s2['ast']} AST"]; use(s2, "PTS", "AST")
    elif s2["tp"][0] >= 3: vo_2 = f"{s2['last'].title()} hit {w(s2['tp'][0])} of {w(s2['tp'][1])} from deep for {w(s2['pts'])}."; d_2 = f"{s2['last']}: {s2['pts']} PTS,|{s2['tp'][0]} OF {s2['tp'][1]} FROM 3."; c2 = [f"{s2['pts']} PTS", f"3PT: {s2['tp'][0]}/{s2['tp'][1]}"]; use(s2, "PTS", "3PT")
    else: vo_2 = f"{s2['last'].title()} added {w(s2['pts'])} on {w(s2['fg'][0])} of {w(s2['fg'][1])}."; d_2 = f"{s2['last']}: {s2['pts']} PTS,|{s2['fg'][0]} OF {s2['fg'][1]}."; c2 = [f"{s2['pts']} PTS", f"FG: {s2['fg'][0]}/{s2['fg'][1]}"]; use(s2, "PTS", "FG")
    # opponent: a cold star (Lillard 2 of 15) or a triple-double, then their top scorer
    cold = next((r for r in sorted(theirs, key=lambda r: r["fg"][0] / max(1, r["fg"][1])) if r["fg"][1] >= 10 and r["fg"][0] <= .3 * r["fg"][1] and pbp_ok(r)), None)
    trip = next((r for r in theirs if sum(v >= 10 for v in (r["pts"], r["reb"], r["ast"])) >= 3), None)
    top = next((r for r in theirs if r is not cold and r is not trip), theirs[0])
    if trip and trip is theirs[0]: top = next(r for r in theirs if r is not trip)
    obeats = []
    if trip: cold = None   # a triple-double is the bigger story than a cold shooter
    if cold:
        cr = rim_of(cold["id"], op); use(cold, "PTS", "FG")
        if cr[1] >= 4 and cr[0] <= .3 * cr[1]:
            claims.append(f"Play-by-play shot log: {cold['name']} {cr[0]}/{cr[1]} within 5 ft of the rim.")
            vo_c = f"{cold['name']} had the opposite night, {w(cold['fg'][0])} of {w(cold['fg'][1])}, {w(cr[0])} for {w(cr[1])} at the rim."; d_c = f"{cold['last']}: {cold['fg'][0]} OF {cold['fg'][1]},|{cr[0]} OF {cr[1]} AT THE RIM."; cc = [f"{cold['fg'][0]}/{cold['fg'][1]} FG", f"RIM: {cr[0]}/{cr[1]}"]
        else:
            vo_c = f"{cold['name']} had the opposite night, {w(cold['fg'][0])} of {w(cold['fg'][1])}."; d_c = f"{cold['last']}: {cold['fg'][0]} OF {cold['fg'][1]}."; cc = [f"{cold['fg'][0]}/{cold['fg'][1]} FG"]
        obeats.append(("dots", cold, vo_c, d_c, cc, f"{cold['pts']} PTS"))
    elif trip:
        use(trip, "PTS", "REB", "AST")
        vo_c = f"{trip['name']} had a triple double, {w(trip['pts'])}, {w(trip['reb'])} and {w(trip['ast'])}."; d_c = f"{trip['last']}: {trip['pts']} PTS,|{trip['reb']} REB, {trip['ast']} AST."
        obeats.append(("dots", trip, vo_c, d_c, [f"{trip['pts']} PTS", f"{trip['reb']} REB", f"{trip['ast']} AST"], f"{trip['pts']} PTS"))
    if not obeats:   # no cold star, no triple-double: their next guy, so the scene count still matches theirs
        o2 = next((r for r in theirs if r is not top and pbp_ok(r)), None)
        if o2:
            if o2["reb"] >= 10: use(o2, "PTS", "REB"); vo_c = f"{o2['name']} did the dirty work for them, {w(o2['pts'])} and {w(o2['reb'])}."; d_c = f"{o2['last']}: {o2['pts']} PTS,|{o2['reb']} REB."; cc = [f"{o2['pts']} PTS", f"{o2['reb']} REB"]
            elif o2["ast"] >= 8: use(o2, "PTS", "AST"); vo_c = f"{o2['name']} ran their offense, {w(o2['pts'])} and {w(o2['ast'])} assists."; d_c = f"{o2['last']}: {o2['pts']} PTS,|{o2['ast']} AST."; cc = [f"{o2['pts']} PTS", f"{o2['ast']} AST"]
            else: use(o2, "PTS", "FG"); vo_c = f"{o2['name']} chipped in {w(o2['pts'])} on {w(o2['fg'][0])} of {w(o2['fg'][1])}."; d_c = f"{o2['last']}: {o2['pts']} PTS,|{o2['fg'][0]} OF {o2['fg'][1]}."; cc = [f"{o2['pts']} PTS", f"{o2['fg'][0]}/{o2['fg'][1]} FG"]
            obeats.append(("dots", o2, vo_c, d_c, cc, f"{o2['pts']} PTS"))
    use(top, "PTS", "FG")
    if won: vo_t = f"{top['name']} kept them close with {w(top['pts'])}."
    else: vo_t = f"{top['name'] if len(top['name']) <= 11 else top['last'].title()} added {w(top['pts'])}."
    if top["tp"][0] >= 4: use(top, "3PT")   # caption line
    d_t = f"{top['last']}: {top['pts']} PTS."
    tz = zones_of(shots_of(top))
    if tz: claims.append(f"Play-by-play shot log, {top['name']} by zone: " + ", ".join(f"{k} {m}/{a}" for k, m, a in tz) + ".")

    # ---- the lead: the biggest lead that matters (a blown lead beats the winner's cushion), then how it ended
    pl = [p for p in s["plays"] if "awayScore" in p]; awayk = next(k for k in comp if comp[k]["homeAway"] == "away")
    def scores(p): a, h = p["awayScore"], p["homeScore"]; return (a, h) if awayk == my else (h, a)   # (us, them)
    lead_of = lambda side: (lambda p: (scores(p)[0] - scores(p)[1]) * (1 if side == my else -1))
    lmax = max(lead_of(L_)(p) for p in pl); F = L_ if lmax >= 6 else W_; lead = lead_of(F)
    mi = max(range(len(pl)), key=lambda i: (lead(pl[i]), -i)); ml = lead(pl[mi]); mper = pl[mi]["period"]["number"]
    after = pl[mi:]; ni = min(range(len(after)), key=lambda i: (lead(after[i]), i)); nl = lead(after[ni])
    sc_pl = [p for p in after if p.get("scoringPlay")]
    picks = [pl[mi]] + [sc_pl[round(i * (len(sc_pl) - 1) / 5)] for i in range(1, 6)] if len(sc_pl) >= 6 else [pl[mi]] + sc_pl
    cut = F == W_ and F == op and 1 <= nl <= M - 4      # we cut their lead down late
    if cut and after[ni] not in picks: picks.append(after[ni]); picks.sort(key=lambda p: pl.index(p))
    ticks = []
    for p in picks:
        u, t = scores(p)
        if not ticks or ticks[-1] != [u, t]: ticks.append([u, t])
    if ticks[-1] != [sc[my], sc[op]]: ticks.append([sc[my], sc[op]])
    perw = ORDW.get(mper, "overtime"); fin = f"{ws(max(sc.values()))} to {ws(min(sc.values()))}"
    claims.append(f"Play-by-play score: {US['abbr'] if F == my else OP['abbr']} biggest lead {ml} in the {P(mper).lower()} quarter" + (f", cut to {nl} later" if cut else "") + ". Score checkpoints (" + US['abbr'] + "-" + OP['abbr'] + "): " + ", ".join(f"{u}-{t}" for u, t in ticks) + ".")
    ltitle = f"{'OUR' if F == my else 'THEIR'} LEAD IN THE {P(mper)}"; d_l = f"{'UP' if F == my else 'DOWN'} {ml} IN THE {P(mper)}..."
    if F == my and won:
        chipped = ml - M >= 8
        vo_l = f"We led by {w(ml)} in the {perw} before {Opp} chipped it down, {fin}." if chipped else f"We led by {w(ml)} in the {perw}, and won it {fin}."
        lead_c = f"We led by {ml} in the {P(mper).lower()}" + (f" before {Opp} chipped it down." if chipped else ".")
    elif F == my:
        vo_l = f"We led by {w(ml)} in the {perw}. It ended {fin}."; lead_c = f"We led by {ml} in the {P(mper).lower()} and lost it."
    elif won:
        vo_l = f"{Opp} led by {w(ml)} in the {perw}. We came back and won it {fin}."; lead_c = f"{Opp} led by {ml} in the {P(mper).lower()}. We came back."
    elif cut:
        vo_l = f"{Opp} led by {w(ml)}. We cut it to {w(nl)}, but it ended {fin}."; lead_c = f"{Opp} led by {ml}. We cut it to {nl}, but it ended {max(sc.values())}-{min(sc.values())}."
    else:
        vo_l = f"{Opp} led by {w(ml)} in the {perw}. Final, {fin}."; lead_c = f"{Opp} led by {ml} in the {P(mper).lower()}."
    # ---- close: the town, the record, one opinion
    close_cap = None
    if won: close_vo, close_d = f"{star['last'].title()} is playing like a star.", f"{star['last']}'S PLAYING|LIKE A STAR."
    elif dk == "quarter": close_vo, close_d, close_cap = f"fix the {ORDW[qn]} quarter.", f"FIX THE {P(qn)}|QUARTER.", f"fix the {P(qn).lower()} quarter."
    elif dk == "ft": close_vo, close_d = "we have to get to the line.", "WE HAVE TO GET|TO THE LINE."
    elif dk == "threes": close_vo, close_d = "we need the threes to fall.", "WE NEED THE|THREES TO FALL."
    else: close_vo, close_d = "we have to own the paint.", "WE HAVE TO|OWN THE PAINT."
    if close_d.count("|") == 0: close_d = close_d

    # ---- beats (mirrors their 13 lines: hook, title, us, them, difference x2, star x2, second, opp x2, lead, town)
    UL, OL = "l:" + US["abbr"], "l:" + OP["abbr"]
    cfg = {"us": UL, "them": OL, "usc": usc, "themc": opc, "score": [sc[my], sc[op]], "won": won}
    B = []
    B.append({"kind": "sc_hook", "cfg": cfg, "head": head, "card": card, "chip": res, "dlg": d0, "pk": "p:" + star["id"], "tag": f"{star['pts']} PTS", "nm": star["last"], "vo": vo0})
    B.append({"kind": "sc_hook", "cont": True, "head": head, "card": card, "chip": res, "city": city.upper(), "cl": "l:" + (US if home else OP)["abbr"], "final": f"{sc[my]}-{sc[op]} FINAL", "dlg": f"{US['short'].upper()} {'VS' if home else 'AT'} {OP['short'].upper()},|SHOT BY SHOT.",
              "pk": "p:" + star["id"], "tag": f"{star['pts']} PTS", "nm": star["last"], "vo": f"This is {US['short']} {'versus' if home else 'at'} {OP['short']} by the shot chart."})
    B.append({"kind": "sc_zones", "side": "us", "zones": [{"z": k, "v": frac(m, a)} for k, m, a in zones_of(SH[my])], "foot": f"{US['abbr']}: {fg[my][0]}/{fg[my][1]} FG", "dlg": f"US: {fg[my][0]} OF {fg[my][1]}.", "vo": f"We went {w(fg[my][0])} of {w(fg[my][1])}."})
    B.append({"kind": "sc_zones", "side": "them", "zones": [{"z": k, "v": frac(m, a)} for k, m, a in zones_of(SH[op])], "foot": f"{OP['abbr']}: {fg[op][0]}/{fg[op][1]} FG", "dlg": f"{OPP}: {fg[op][0]} MADE.", "vo": f"{Opp} made {w(fg[op][0])}."})
    B.append({"kind": "sc_bars", "card": fcard, "n": 2, "intro": True, "dlg": f"THE DIFFERENCE:|{dname}.", "dlg2": d5, "vo": vo5})
    B.append({"kind": "sc_dots", "side": "us", "shots": enc_shots(shots_of(star)), "chips": [h1[1]], "pk": "p:" + star["id"], "tag": f"{star['pts']} PTS", "nm": star["last"], "dlg": d_s1, "vo": vo_s1})
    B.append({"kind": "sc_dots", "side": "us", "cont": True, "shots": enc_shots(shots_of(star)), "chips": [h1[1], chip2], "pk": "p:" + star["id"], "tag": f"{star['pts']} PTS", "nm": star["last"], "dlg": d_s2, "vo": vo_s2})
    B.append({"kind": "sc_dots", "side": "us", "shots": enc_shots(shots_of(s2)), "chips": c2, "pk": "p:" + s2["id"], "tag": f"{s2['pts']} PTS", "nm": s2["last"], "dlg": d_2, "vo": vo_2})
    for _, r, vo_c, d_c, cc, tg in obeats:
        B.append({"kind": "sc_dots", "side": "them", "shots": enc_shots(shots_of(r)), "chips": cc, "pk": "p:" + r["id"], "tag": f"{r['fg'][0]}/{r['fg'][1]} FG" if r is cold else tg, "nm": r["last"], "dlg": d_c, "vo": vo_c})
    B.append({"kind": "sc_zones", "side": "them", "player": True, "zones": [{"z": k, "v": frac(m, a)} for k, m, a in tz], "foot": f"{top['pts']} PTS", "pk": "p:" + top["id"], "tag": f"{top['fg'][0]}/{top['fg'][1]} FG", "nm": top["last"], "dlg": d_t, "vo": vo_t})
    B.append({"kind": "sc_lead", "title": ltitle, "ticks": ticks, "wside": "us" if F == my else "them", "dlg": d_l, "dlg2": f"FINAL: {sc[my]}-{sc[op]}.", "vo": vo_l})
    town = {"kind": "sc_town", "town": f"{US['short'].upper()} TOWN", "sub": f"{US['abbr']} {rec}", "arena": US["arena"].upper(), "rec": rec,
            "p1": "p:" + star["id"], "n1": star["last"], "p2": "p:" + s2["id"], "n2": s2["last"], "cont": True, "dlg": f"{rec}. {close_d}", "vo": f"That's {rec_w(rec)}. {close_vo[0].upper() + close_vo[1:]}"}
    B.append(town)

    # ---- caption (mirrors theirs: score line + story, emoji bullets, closing line, one question)
    def ln(r, extra): return f"{r['name']}: {extra}"
    bl = [f"🎯 FG: us {fg[my][0]} of {fg[my][1]}, {Opp} {fg[op][0]} of {fg[op][1]}"]
    if dk == "quarter": bl.append(f"🧊 {P(qn).lower()} quarter: us {dm} of {da}, {Opp} {om} of {oa}. {'Down' if lines[my][qn - 1] < lines[op][qn - 1] else 'Up'} {max(sum(lines[my][:qn]), sum(lines[op][:qn]))}-{min(sum(lines[my][:qn]), sum(lines[op][:qn]))} after it")
    elif dk == "ft": bl.append(f"🧾 Free throws: {da} attempts for us, {oa} for them ({dm}/{da} vs {om}/{oa})")
    elif dk == "threes": bl.append(f"🏹 Threes: us {dm} of {da}, {Opp} {om} of {oa}")
    else: bl.append(f"🧱 At the rim: us {dm} of {da}, {Opp} {om} of {oa}")
    bl.append("🔥 " + ln(star, f"{star['pts']} PTS on {star['fg'][1]} shots" + "".join(", " + h[3].lower().replace(" from 3", " from three") for h in hi[:2])))
    bl.append(("💪 " if s2["reb"] >= 10 else "🎯 " if s2["tp"][0] >= 3 else "🧠 ") + ln(s2, d_2.split(":", 1)[1].replace("|", " ").strip().rstrip(".").replace(" FROM 3", " from three").replace(" OF ", " of ")))
    for _, r, vo_c, d_c, cc, tg in obeats:
        bl.append(("🧊 " if r is cold else "🎩 " if r is trip else "💥 ") + ln(r, d_c.split(":", 1)[1].replace("|", " ").strip().rstrip(".").replace(" OF ", " of ").replace(" AT THE RIM", " at the rim")) + (" (triple-double)" if r is trip and r is not cold else ""))
    bl.append(f"😤 {top['name']} " + (f"kept them close with {top['pts']}" if won else f"led them with {top['pts']}" + (f", {top['tp'][0]} of {top['tp'][1]} from three" if top['tp'][0] >= 4 else "")))
    cc_ = close_cap or close_vo
    closing = f"{lead_c} That's {rec}, and {cc_}" if won else f"{lead_c} That's {rec}. {cc_[0].upper() + cc_[1:]}"
    q = (f"Is {star['name']} our best player right now?" if won else "Who needs to step up next game?")
    cap = f"{US['short'].upper()} {sc[my]}, {OP['short'].upper()} {sc[op]} {EMO.get(slug, '🏀')} {story}\n\n" + "\n".join(bl) + f"\n\n{closing}\n\n{q}"

    # ---- facts for gen/factcheck.py
    facts = [{"game": str(event), "score": f"{max(sc.values())}-{min(sc.values())}"}]
    for pid, stats in pfacts.items():
        for st_ in sorted(stats): facts.append({"game": str(event), "player": pid, "stat": st_, "value": BX[pid]["box"][st_]})
    facts.append({"claim": " ".join(claims) + f" Zones (play-by-play shot log): {US['abbr']} " + ", ".join(f"{k} {m}/{a}" for k, m, a in zones_of(SH[my])) + f"; {OP['abbr']} " + ", ".join(f"{k} {m}/{a}" for k, m, a in zones_of(SH[op])) + ".", "source": url})
    for r in (star, s2) + tuple(x[1] for x in obeats) + (top,):
        facts.append({"game": str(event), "player": r["id"], "stat": "FG", "value": BX[r["id"]]["box"]["FG"]}) if "FG" not in pfacts[r["id"]] else None
    for b in B: b["vo"] = say(b.get("vo", ""))
    spec = {"team": slug, "name": f"sc_{ABBR3.get(OP['abbr'], OP['abbr'].lower())}", "template": "fmt_shotchart.html", "music": "battle", "cps": 40, "voice_eq": "bright", "record": rec,
            "caption": cap, "beats": B, "facts": facts}
    if review: spec["_review"] = review
    return spec


# Their reel's line ends (Df2aW0Zg3nZ trace, research/mirror/wolves/Df2aW0Zg3nZ_trace/trace.md): hook, title, us, them,
# difference (+ its bars, one scene), star x2, second, opp cold/triple-double, opp scorer, lead (+ final, town cut), close.
THEIR_ENDS = [4.1, 8.7, 11.2, 13.4, 18.5, 21.9, 26.3, 30.1, 34.8, 37.25, 42.5, 45.6]   # town cuts in 3.25 s into the lead line (40.5)
# Voice: history.py's default Kokoro speed (1.05, no "pace": "wolves") speaks about 2.85 words/s, their narrator 2.86;
# wolves pace (1.25) measured 3.37 words/s on this format and fails the copy check's pace test.
GAP = .35   # history.py's gap after every beat outside wolves pace


def fit(spec):
    """Voice every line exactly as history.py will (Kokoro, wolves pace) and add silent 'pad' beats so each line
    ends where theirs ends; the template keeps the previous scene animating through a pad."""
    import os, subprocess
    B = spec["beats"]; ends = list(THEIR_ENDS)
    if len(B) == len(ends) - 1: del ends[8]          # no cold shooter / triple-double beat
    if len(B) != len(ends): print(f"REVIEW: {len(B)} beats, expected {len(ends)}: timing not fitted"); return spec
    d = ROOT / "cache" / f"scfit_{spec['team']}_{spec['name']}"; d.mkdir(parents=True, exist_ok=True)
    lj = d / "lines.json"; lj.write_text(json.dumps([{"id": f"b{i}", "text": b["vo"]} for i, b in enumerate(B)]))
    env = {k: v for k, v in os.environ.items() if k not in ("KOKORO_SPEED", "KOKORO_TRIM")}
    durs = json.loads(subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts.py"), str(lj), str(d)], capture_output=True, text=True, check=True, env=env).stdout.strip().splitlines()[-1])
    out, t = [], 0.0
    for i, (b, e) in enumerate(zip(B, ends)):
        dv = durs[f"b{i}"]; out.append(b); hold = e - (t + dv) - 2 * GAP
        if hold >= .1: out.append({"kind": b["kind"], "pad": True, "hold": round(hold, 3), "vo": ""}); t = e
        else:
            t += dv + GAP
            if t - e > .35: print(f"REVIEW: line {i} ends at {t:.2f} s, theirs at {e:.2f} s (shorten it): {b['vo']}")
    spec["beats"] = out
    print(f"fitted: last line ends {t:.2f} s (theirs {ends[-1]}), reel about {t + .6:.1f} s")
    return spec


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("team"); ap.add_argument("event"); ap.add_argument("--out"); ap.add_argument("--no-fit", action="store_true")
    a = ap.parse_args(); spec = build(a.team, a.event)
    if not a.no_fit: spec = fit(spec)
    out = pathlib.Path(a.out) if a.out else ROOT / "specs" / f"{a.team[0]}_{spec['name']}.json"
    out.write_text(json.dumps(spec, indent=1, ensure_ascii=False)); print(out)
    for r in spec.get("_review", []): print("REVIEW:", r)
    print("\n".join(f"  {i:2d} {b['kind']:9s} {('pad ' + str(b['hold'])) if b.get('pad') else b.get('vo', '')}" for i, b in enumerate(spec["beats"])))
