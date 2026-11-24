"""Check every player ID in specs/*.json against ESPN's name for it. usage: python3 gen/verify_ids.py"""
import json, glob, re, urllib.request
seen = {}
for f in sorted(glob.glob("specs/*.json")):
    s = open(f).read(); d = json.loads(s)
    ids = set(re.findall(r'"p:(\d+)', s)) | {c["id"] for c in d.get("cands", [])}
    for i in sorted(ids):
        if i not in seen:
            try: seen[i] = json.load(urllib.request.urlopen(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{i}", timeout=20))["athlete"]["displayName"]
            except Exception as e: seen[i] = f"?? {e}"
        expect = next((c["full"] for c in d.get("cands", []) if c["id"] == i), None) or ", ".join(sorted(({b.get("name", "") for b in d.get("beats", []) if f"p:{i}" in json.dumps(b)} | {b.get("oname", "") for b in d.get("beats", []) if f"p:{i}" in json.dumps(b)}) - {""}))
        print(f"{f:28} {i:>8} ESPN={seen[i]:<22} spec={expect}")
