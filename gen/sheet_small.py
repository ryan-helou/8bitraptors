"""Eye-check contact sheet: one settled frame per scene. usage: python3 gen/sheet.py out/<slug_kind> OUT.png"""
import json, sys, subprocess, pathlib, tempfile
from PIL import Image
base = sys.argv[1]; tl = json.load(open(base + ".timeline.json")); tmp = pathlib.Path(tempfile.mkdtemp()); ims = []
for i, s in enumerate(tl["spans"]):
    t = max(s["start"] + .2, s["end"] - .45); f = tmp / f"{i}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", base + ".mp4", "-frames:v", "1", str(f)], check=True)
    ims.append(Image.open(f).crop((0, 180, 1080, 1620)).resize((360, 480)))
cols = min(6, len(ims)); rows = (len(ims) + cols - 1) // cols; sh = Image.new("RGB", (360 * cols, 480 * rows))
for i, im in enumerate(ims): sh.paste(im, ((i % cols) * 360, (i // cols) * 480))
sh.save(sys.argv[2]); print(sys.argv[2])
