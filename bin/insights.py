"""Per-reel performance for both accounts -> data/insights/<date>.json and a table on stdout. usage: python3 bin/insights.py"""
import json, urllib.request, pathlib, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
G = "https://graph.facebook.com/v23.0"
def get(u):
    try: return json.load(urllib.request.urlopen(u, timeout=30))
    except Exception as e: return {"err": str(e)[:80]}
now = dt.datetime.now(dt.timezone.utc); rows = []
for acc, suf in (("raptors", ""), ("warriors", "_WARRIORS")):
    T, I = env["IG_TOKEN" + suf].strip(), env["IG_USER_ID" + suf].strip()
    u = get(f"{G}/{I}?fields=username,followers_count,media_count&access_token={T}")
    print(f"\n## @{u.get('username')}  followers {u.get('followers_count')}  posts {u.get('media_count')}")
    m = get(f"{G}/{I}/media?fields=id,caption,timestamp,like_count,comments_count,permalink&limit=50&access_token={T}")
    for x in m.get("data", []):
        ins = get(f"{G}/{x['id']}/insights?metric=views,reach,saved,shares,ig_reels_avg_watch_time,ig_reels_video_view_total_time&access_token={T}")
        d = {i["name"]: i["values"][0]["value"] for i in ins.get("data", [])}
        ts = dt.datetime.strptime(x["timestamp"], "%Y-%m-%dT%H:%M:%S%z"); age = round((now - ts).total_seconds() / 3600, 1)
        r = dict(acc=acc, posted=ts.astimezone(dt.timezone(dt.timedelta(hours=-5))).strftime("%a %H:%M"), age_h=age, title=(x.get("caption") or "").split("\n")[0][:38],
                 views=d.get("views"), reach=d.get("reach"), likes=x.get("like_count"), comments=x.get("comments_count"), shares=d.get("shares"), saves=d.get("saved"),
                 avg_watch_s=round(d.get("ig_reels_avg_watch_time", 0) / 1000, 1), permalink=x.get("permalink"), followers=u.get("followers_count"))
        rows.append(r); print(f"{r['posted']:>9} {age:>5}h  {r['title']:<38} views {r['views']!s:>5}  reach {r['reach']!s:>5}  ♥{r['likes']!s:>3}  💬{r['comments']!s:>2}  ↗{r['shares']!s:>2}  watch {r['avg_watch_s']}s")
(ROOT / "data/insights").mkdir(parents=True, exist_ok=True)
(ROOT / f"data/insights/{now.astimezone().strftime('%Y-%m-%d_%H%M')}.json").write_text(json.dumps(rows, indent=1))
