#!/usr/bin/env python3
"""Mirror @8bitwolves one day behind (Ryan, 2026-11-18: "every day we watch what videos he posted, and we post the
same videos, same times, the next day").

usage: python3 bin/wolves_watch.py [YYYY-MM-DD]     (a Toronto "posting day"; default: yesterday)

A posting day runs 04:00 -> 04:00 Toronto, so a 01:32 post belongs to the evening before.
For every Wolves reel of that day it saves, under research/mirror/<day>/:
  <code>.mp4 (for study only, never re-posted), .caption.txt, .transcript.txt, _strip.png (1 frame / 2 s)
and writes plan.json + plan.md: each reel's time, length, voice or music-only, format tag, views/likes at pull time,
and the mirror slot (same clock time, next day) for @8bitraptors and @8bitwarriors.
Building and queueing our versions is done by hand (or by the daily mirror session) from plan.md.
"""
import sys, json, re, pathlib, subprocess, urllib.request, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo
ROOT = pathlib.Path(__file__).resolve().parent.parent
TOR = ZoneInfo("America/Toronto")
YTDLP = "/opt/homebrew/bin/yt-dlp"; WHISPER_MODEL = str(pathlib.Path.home() / ".whisper-models/ggml-small.en.bin")
env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))

# format tags: first match wins. Each maps to the generator we use for our version.
FORMATS = [
    (r"SHOT CHART|SHOT BY SHOT|EVERY SHOT", "shotchart", "gen/shotchart.py <team> <event>  (fmt_shotchart.html)"),
    (r"^\s*(?:[A-Z]+ \d+, [A-Z]+ \d+|FINAL)", "recap", "gen/shotchart.py or build.py recap (score-line recap)"),
    (r"SIM", "sim", "gen/sim_era.py + fmt_sim.html"),
    (r"POK[EÉ]MON TEAM|POK[EÉ]MON TRAINER", "pokemon_team", "trainer spec (specs/r_tr_*.json, p_* beats)"),
    (r"WAS A POK[EÉ]MON|IF EVERY", "pokemon_starters", "team/mon beats (specs/r_tr_*.json)"),
    (r"GAME DAY|GAMEDAY|CARD DUEL", "gameday", "game-day card for our NEXT game"),
    (r"\d+ GAMES IN|WEEKS IN|WHERE THE .* STAND", "games_in", "build.py gamesin"),
    (r"STARTING FIVE|PC\b|IN THE BOX", "starting5", "build.py starting5"),
    (r"EVOLVING|HIGH SCORE|MILESTONE", "milestone", "build.py milestone"),
    (r"TRAINER CARD", "trainer_card", "new format"),
    (r"THEN VS NOW", "then_now", "new format"),
    (r"STAT CHECK|VS .*:", "stat_check", "new format"),
    (r"GYM", "gym", "fmt_region_map / gym beats"),
    (r"MUSEUM|SEASON HIGHS", "museum", "new format"),
    (r"HOW .* BECAME|HOW .* GOT TO|FROM .* TO", "journey", "fmt_journey_map.html"),
    (r"WHO WON THE .* TRADE|TRADE", "trade", "fmt_trade_review.html"),
    (r"HOW THE .* WERE BUILT|HOW WE BUILT", "team_builder", "fmt_team_builder.html"),
    (r"WHO.?S OUR|WHO STEPS UP|NO\. ?\d|\?", "question", "choose-your-starter style poll"),
]


def fetch_media(limit=40):
    f = f"business_discovery.username(8bitwolves){{followers_count,media_count,media.limit({limit}){{id,timestamp,caption,like_count,comments_count,permalink,view_count,media_product_type}}}}"
    u = f"https://graph.facebook.com/v23.0/{env['IG_USER_ID'].strip()}?fields={urllib.parse.quote(f)}&access_token={env['IG_TOKEN'].strip()}"
    return json.load(urllib.request.urlopen(u, timeout=60))["business_discovery"]


def post_day(ts):   # Toronto posting day, 04:00 -> 04:00
    t = dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").astimezone(TOR)
    return (t - dt.timedelta(hours=4)).date(), t


def tag(cap):
    title = (cap or "").split("\n")[0].upper()
    for rx, name, how in FORMATS:
        if re.search(rx, title): return name, how
    return "new", "new format: study the video and build a template"


def main():
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else (dt.datetime.now(TOR) - dt.timedelta(hours=4)).date() - dt.timedelta(days=1)
    out = ROOT / "research/mirror" / day.isoformat(); out.mkdir(parents=True, exist_ok=True)
    b = fetch_media(); plan = []
    for m in sorted(b["media"]["data"], key=lambda m: m["timestamp"]):
        d, t = post_day(m["timestamp"])
        if d != day: continue
        code = m["permalink"].rstrip("/").split("/")[-1]; mp4 = out / f"{code}.mp4"
        (out / f"{code}.caption.txt").write_text(m.get("caption") or "")
        if not mp4.exists():
            subprocess.run([YTDLP, "-q", "--no-warnings", "-f", "b[ext=mp4]/b", "-o", str(mp4), f"https://www.instagram.com/reel/{code}/"], timeout=300)
        dur, words = None, ""
        if mp4.exists():
            dur = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout or 0), 1)
            wav = out / f"{code}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-ar", "16000", "-ac", "1", str(wav)])
            tx = subprocess.run(["whisper-cli", "-m", WHISPER_MODEL, "-f", str(wav), "-np"], capture_output=True, text=True).stdout
            (out / f"{code}.transcript.txt").write_text(tx); wav.unlink(missing_ok=True)
            words = " ".join(re.sub(r"\[[^\]]*\]", "", tx).split())
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", "fps=1/2,scale=180:-1,tile=8x4", "-frames:v", "1", str(out / f"{code}_strip.png")])
        voiced = len(re.sub(r"\(.*?\)|\[.*?\]|music", "", words, flags=re.I).split()) > 12
        fmt, how = tag(m.get("caption"))
        nxt = (t + dt.timedelta(days=1))
        plan.append(dict(code=code, url=m["permalink"], posted=t.strftime("%a %Y-%m-%d %H:%M"), mirror_date=nxt.date().isoformat(), mirror_time=t.strftime("%H:%M"),
                         seconds=dur, voice=voiced, format=fmt, build_with=how, title=(m.get("caption") or "").split("\n")[0],
                         views_at_pull=m.get("view_count"), likes_at_pull=m.get("like_count"), comments_at_pull=m.get("comments_count"), hook=words[:160]))
    (out / "plan.json").write_text(json.dumps(dict(day=day.isoformat(), followers=b.get("followers_count"), pulled=dt.datetime.now(TOR).isoformat(timespec="minutes"), reels=plan), indent=1, ensure_ascii=False))
    md = [f"# Mirror plan: @8bitwolves on {day:%a %b %d} -> ours on {(day + dt.timedelta(days=1)):%a %b %d}", f"Wolves followers at pull: {b.get('followers_count')}. {len(plan)} reels.", ""]
    for p in plan:
        md += [f"## {p['mirror_time']}  {p['title']}", f"- theirs: {p['url']} posted {p['posted']}, {p['seconds']} s, {'narrated' if p['voice'] else 'music only'}, {p['views_at_pull']} views / {p['likes_at_pull']} likes at pull",
               f"- format: **{p['format']}** -> {p['build_with']}", f"- hook: \"{p['hook']}\"", f"- ours: @8bitraptors and @8bitwarriors at {p['mirror_date']} {p['mirror_time']} Toronto, same length", ""]
    (out / "plan.md").write_text("\n".join(md)); print("\n".join(md))


if __name__ == "__main__":
    main()
