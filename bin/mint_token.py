#!/usr/bin/env python3
"""Turn a fresh Graph API Explorer user token into a long-lived Page token for @8bitraptors.

Reuses the Meta app already set up for RyanTalks (META_APP_ID / META_APP_SECRET read from its .env).
Reads NEW_USER_TOKEN from ./.env, finds the Page whose linked IG account is EXPECTED_IG_USERNAME,
and writes IG_USER_ID and IG_TOKEN into ./.env. Prints names and ids only, never tokens.
"""
import json, pathlib, sys, urllib.parse, urllib.request
SLUG = (sys.argv[1] if len(sys.argv) > 1 else "raptors").lower()
SUF = "" if SLUG == "raptors" else "_" + SLUG.upper()
ROOT = pathlib.Path(__file__).resolve().parent.parent
G = "https://graph.facebook.com/v23.0"

def read_env(p):
    return dict(l.split("=", 1) for l in pathlib.Path(p).read_text().splitlines() if "=" in l and not l.lstrip().startswith("#"))

def get(path, **q):
    try:
        return json.load(urllib.request.urlopen(f"{G}/{path}?" + urllib.parse.urlencode(q), timeout=30))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {path}: {e.read().decode()[:300]}")

mine = read_env(ROOT / ".env")
app = read_env(mine.get("APP_ENV", "/Users/ryanhelou/Developer/RyanTalks/.env"))
want = "8bit" + SLUG
short = mine.get("NEW_USER_TOKEN", "").split("#")[0].strip()
if not short: sys.exit("Put the Graph API Explorer user token in .env as NEW_USER_TOKEN first.")
long_ = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app["META_APP_ID"].strip(),
            client_secret=app["META_APP_SECRET"].strip(), fb_exchange_token=short)["access_token"]
pages = get("me/accounts", fields="name,id,access_token,instagram_business_account{username,id}", access_token=long_).get("data", [])
print("Pages visible:", [(p["name"], (p.get("instagram_business_account") or {}).get("username")) for p in pages])
hit = [p for p in pages if (p.get("instagram_business_account") or {}).get("username") == want]
if not hit: sys.exit(f"No Page with linked Instagram @{want}. Re-run login and tick the new Page + Instagram account.")
p = hit[0]
lines = [l for l in (ROOT / ".env").read_text().splitlines() if not l.startswith(("IG_USER_ID"+SUF+"=", "IG_TOKEN"+SUF+"=", "NEW_USER_TOKEN="))]
lines += [f"IG_USER_ID{SUF}={p['instagram_business_account']['id']}", f"IG_TOKEN{SUF}={p['access_token']}"]
(ROOT / ".env").write_text("\n".join(lines) + "\n")
print(f"OK: wrote IG_USER_ID and IG_TOKEN for @{want} (Page '{p['name']}'). NEW_USER_TOKEN removed.")
