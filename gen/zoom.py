"""Zoom sheet for the eye check: every text box, circle and logo badge from every scene, cropped at full resolution
with centre crosshairs, so a few-pixel offset is obvious. usage: python3 gen/zoom.py out/<slug_kind>  -> /tmp/zoom_<name>_<n>.png"""
import sys, json, os, io, base64, pathlib
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parent.parent; base = sys.argv[1]; name = pathlib.Path(base).name
data = json.loads(pathlib.Path(base + ".data.json").read_text()); tl = json.loads(pathlib.Path(base + ".timeline.json").read_text())
data.setdefault("spans", tl["spans"]); data.setdefault("total", tl["total"])
crops = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
    pg = b.new_page(viewport={"width": 540, "height": 960}); pg.goto("file://" + str(ROOT / "gen/reel_t.html")); pg.evaluate("d=>setData(d)", data)
    for sp in data["spans"]:
        t = max(sp["start"] + .2, sp["end"] - .45)
        qa, qr, qb, qc, url = pg.evaluate(f"(()=>{{window.__QA=[];window.__QR=[];window.__QB=[];window.__QC=[];render({t});const r=[window.__QA,window.__QR,window.__QB,window.__QC,document.getElementById('c').toDataURL('image/png')];window.__QA=null;window.__QR=null;window.__QB=null;window.__QC=null;return r}})()")
        fr = Image.open(io.BytesIO(base64.b64decode(url.split(",")[1]))).convert("RGB"); seen = set()
        for x in qa:
            if len(x) < 11 or x[0].startswith("__CUT__") or x[6] < .6 or not x[0].strip(): continue
            L, R, it, ib, ti = x[1], x[1] + x[3], x[7], x[8], x[9]; cx, cy = (L + R) / 2, (it + ib) / 2
            circ = [c for c in qc if c[3] <= ti and (cx - c[0]) ** 2 + (cy - c[1]) ** 2 <= c[2] ** 2 and c[2] < 2.2 * max(ib - it, x[3] / 2) and x[3] < 1.9 * c[2]]
            if circ: c = circ[-1]; box = (c[0] - c[2], c[1] - c[2], c[0] + c[2], c[1] + c[2])
            else:
                under = [r for r in qr[:ti] if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]]
                if not under: continue
                box = tuple(under[-1])
                if box[2] - box[0] > 1000: box = (L - 20, it - 20, R + 20, ib + 20)
            key = tuple(round(v) for v in box)
            if key in seen: continue
            seen.add(key); crops.append((sp["scene"], box, fr))
        for bx, by, br, col, k in qb:
            box = (bx - br - 10, by - br - 10, bx + br + 10, by + br + 10); crops.append((sp["scene"], box, fr))
    b.close()
cells = []
for scene, (x0, y0, x1, y1), fr in crops:
    pad = 10; c = fr.crop((int(x0 - pad), int(y0 - pad), int(x1 + pad), int(y1 + pad)))
    s = min(2.0, 520 / max(1, c.width), 300 / max(1, c.height)); c = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.NEAREST)
    d = ImageDraw.Draw(c); mx, my = c.width / 2, c.height / 2
    d.line((mx, 0, mx, c.height), fill=(0, 255, 255)); d.line((0, my, c.width, my), fill=(0, 255, 255))
    cell = Image.new("RGB", (540, max(60, c.height + 22)), (30, 30, 30)); cell.paste(c, ((540 - c.width) // 2, 20)); ImageDraw.Draw(cell).text((4, 4), scene, fill=(255, 255, 0)); cells.append(cell)
n = 0
for i in range(0, len(cells), 16):
    grp = cells[i:i + 16]; cols = 4; rows = (len(grp) + cols - 1) // cols; hmax = [max(c.height for c in grp[r * cols:(r + 1) * cols]) for r in range(rows)]
    sh = Image.new("RGB", (540 * cols, sum(hmax)), (0, 0, 0)); y = 0
    for r in range(rows):
        for j, c in enumerate(grp[r * cols:(r + 1) * cols]): sh.paste(c, (j * 540, y))
        y += hmax[r]
    sh.save(f"/tmp/zoom_{name}_{n}.png"); print(f"/tmp/zoom_{name}_{n}.png"); n += 1
