"""Up-close eye check for team logos: every NBA logo drawn in a round badge at large size -> /tmp/logo_sheet.png.
Run after any change to logo sprites (gen/build.py logo_square / sprite_logo*)."""
import sys, base64, io, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import build as B
from PIL import Image, ImageDraw
AB = "ATL BOS BKN CHA CHI CLE DAL DEN DET GS HOU IND LAC LAL MEM MIA MIL MIN NO NY OKC ORL PHI PHX POR SAC SA TOR UTAH WSH".split()
cells = []
for ab in AB:
    lg = Image.open(io.BytesIO(base64.b64decode(B.sprite_logo_hi(ab).split(",")[1]))).convert("RGBA")
    R = 110; c = Image.new("RGBA", (260, 260), (216, 240, 216, 255)); d = ImageDraw.Draw(c)
    for rr, col in ((R + 16, (10, 15, 38)), (R + 8, (244, 244, 244)), (R, (40, 60, 120)), (R - 16, (25, 35, 80))): d.ellipse((130 - rr, 130 - rr, 130 + rr, 130 + rr), fill=col)
    sz = int(R * 1.72); c.alpha_composite(lg.resize((sz, sz), Image.NEAREST), (130 - sz // 2, 130 - sz // 2)); d.text((6, 4), ab, fill=(0, 0, 0)); cells.append(c)
g = Image.new("RGB", (260 * 6, 260 * 5), (255, 255, 255))
for i, c in enumerate(cells): g.paste(c, ((i % 6) * 260, (i // 6) * 260))
g.save(sys.argv[1] if len(sys.argv) > 1 else "/tmp/logo_sheet.png")
