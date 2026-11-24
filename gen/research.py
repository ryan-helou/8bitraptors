"""Research helpers for writing specs (facts first, script second).
  python3 gen/research.py id "Terrence Ross"                -> ESPN athlete id(s) + names
  python3 gen/research.py wiki Terrence_Ross "dunk" "2013"  -> sentences on the Wikipedia page containing each key
  python3 gen/research.py games 20140504 Raptors            -> ESPN event ids/scores that day for a team
  python3 gen/research.py season 3978 2012-13               -> ESPN regular-season averages row for a player
"""
import sys, re, json, html, urllib.request, urllib.parse
sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.as_posix())
import espn

UA = {"User-Agent": "Mozilla/5.0"}


def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "replace")


def wiki_text(page):
    t = html.unescape(re.sub(r"<[^>]+>", " ", fetch("https://en.wikipedia.org/wiki/" + urllib.parse.quote(page))))
    return re.sub(r"\s+", " ", t)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "id":
        q = urllib.parse.quote(sys.argv[2])
        d = json.loads(fetch(f"https://site.web.api.espn.com/apis/common/v3/search?query={q}&limit=5&type=player"))
        for it in d.get("items", []):
            if "basketball" in json.dumps(it).lower(): print(it.get("id"), it.get("displayName"), it.get("description", ""))
    elif cmd == "wiki":
        t = wiki_text(sys.argv[2])
        for k in sys.argv[3:]:
            hits = [m.start() for m in re.finditer(re.escape(k), t)][:3]
            if not hits: print(f"[{k}] NOT FOUND")
            for i in hits: print(f"[{k}] ...{t[max(0, i - 160):i + 160]}...")
    elif cmd == "games":
        d = espn.get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={sys.argv[2]}")
        for e in d["events"]:
            if sys.argv[3].lower() in e["name"].lower():
                print(e["id"], e["name"], [(c["team"]["abbreviation"], c["score"]) for c in e["competitions"][0]["competitors"]])
    elif cmd == "season":
        typ = sys.argv[4] if len(sys.argv) > 4 else "2"
        d = espn.get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{sys.argv[2]}/stats?seasontype={typ}")
        for c in d.get("categories", []):
            if c["name"] == "averages":
                for s in c["statistics"]:
                    if s["season"]["displayName"] == sys.argv[3] or sys.argv[3] == "all": print(s["season"]["displayName"], s.get("teamSlug"), dict(zip(c["labels"], s["stats"])))
