#!/usr/bin/env python3
"""Follow end card on every reel (Ryan 2026-11-25: "in the video too"). Appends a ~2.5 s 8-bit card to the END of a queued
reel (after its payoff), voiced in our narrator's voice: "Follow us for daily <team> news, trades and stories."
The card and its voice line are made once per account (cache/endcard/). Updates the QA stamp's md5 so the posters accept
the new file, and marks the queue entry endcard=true so it is never added twice.
usage: python3 bin/endcard.py LABEL            one queued post
       python3 bin/endcard.py --all            every queued post that doesn't have it yet"""
import sys, json, pathlib, subprocess, hashlib, shutil
from PIL import Image, ImageDraw, ImageFont
ROOT = pathlib.Path(__file__).resolve().parent.parent; C = ROOT / "cache/endcard"; C.mkdir(parents=True, exist_ok=True)
TEAM = {"raptors": ("RAPTORS", "@8BITRAPTORS", (206, 17, 65)), "warriors": ("WARRIORS", "@8BITWARRIORS", (255, 199, 44))}
F = lambda n, s: ImageFont.truetype(str(ROOT / "assets/fonts" / n), s)


def assets(acc):
    team, handle, col = TEAM[acc]; png, wav = C / f"{acc}.png", C / f"{acc}.wav"
    if not png.exists():
        im = Image.new("RGB", (1080, 1920), (10, 15, 38)); d = ImageDraw.Draw(im)
        for y in range(0, 1920, 8): d.line([(0, y), (1080, y)], fill=(14, 20, 48))           # scanlines
        d.text((540, 640), "FOLLOW", font=F("PressStart2P-Regular.ttf", 110), fill=(232, 184, 74), anchor="mm")
        d.text((540, 800), handle, font=F("PressStart2P-Regular.ttf", 62), fill=(255, 255, 255), anchor="mm")
        box = (90, 980, 990, 1300); d.rectangle(box, fill=(245, 245, 250), outline=col, width=10)    # dialog box
        for i, line in enumerate(["DAILY " + team + " NEWS,", "TRADES AND STORIES."]):   # centred; fits the box at 38 px
            d.text((540, 1085 + i * 100), line, font=F("PressStart2P-Regular.ttf", 38), fill=(40, 40, 52), anchor="mm")
        d.polygon([(930, 1255), (960, 1255), (945, 1278)], fill=col)                                  # "continue" arrow
        im.save(png)
    if not wav.exists():
        lines = C / f"{acc}_lines.json"; lines.write_text(json.dumps([{"id": acc, "text": f"Follow us for daily {team.title()} news, trades and stories."}]))
        subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "gen/tts_kokoro.py"), str(lines), str(C)], cwd=str(ROOT), check=True,
                       env={"KOKORO_SPEED": "1.15", "KOKORO_TRIM": "1", "PATH": "/usr/bin:/bin:/opt/homebrew/bin"}, capture_output=True)
    return png, wav


def add(it):
    if it.get("endcard"): return False
    png, wav = assets(it["account"]); v = pathlib.Path(it["video"]); tmp = v.with_suffix(".end.mp4")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout) + 0.7
    fc = (f"[1:v]scale=1080:1920,fps=30,format=yuv420p,setsar=1,fade=in:st=0:d=0.15[cv];"
          f"[2:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={dur:.2f}[ca];"
          f"[0:v]fps=30,format=yuv420p,setsar=1[v0];[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
          f"[v0][a0][cv][ca]concat=n=2:v=1:a=1[v][a]")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v), "-loop", "1", "-t", f"{dur:.2f}", "-i", str(png), "-i", str(wav),
                        "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)], capture_output=True, text=True)
    if r.returncode or not tmp.exists(): print(it["label"], "FAILED", r.stderr[-300:]); return False
    shutil.move(tmp, v)
    stp = ROOT / "data" / f"stamp_{it['label']}.json"
    if stp.exists(): s = json.loads(stp.read_text()); s["mp4_md5"] = hashlib.md5(v.read_bytes()).hexdigest(); s["endcard"] = True; stp.write_text(json.dumps(s, indent=1))
    it["endcard"] = True; return True


if __name__ == "__main__":
    qp = ROOT / "data/api_queue.json"; q = json.loads(qp.read_text())
    pick = [j for j in q if j["state"] == "queued" and (sys.argv[1] == "--all" or j["label"] == sys.argv[1])]
    n = 0
    for j in pick:
        if add(j): n += 1; qp.write_text(json.dumps(q, indent=1, ensure_ascii=False))
    print(f"end card added to {n} of {len(pick)}")
