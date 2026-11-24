"""Automated reel QA. usage: qa.py out/<slug>_<kind>   (uses the .data.json, .timeline.json and .mp4 next to it)
Checks every 1/3 s: text overlapping other text, text too small to read on a phone, text outside Instagram's
safe zone; then audio loudness and (for narrated reels) that the transcript matches the script."""
import sys, json, os, re, subprocess, pathlib
# 2026-11-18 Ryan: "forget your old rule" on minimum text size for copies. In mirror mode text may be as small as the reference's.
COPY_MODE = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("data/mirror_mode").exists()
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent; base = sys.argv[1]
data = json.loads(pathlib.Path(base + ".data.json").read_text()); tl = json.loads(pathlib.Path(base + ".timeline.json").read_text())
data.setdefault("spans", tl["spans"]); data.setdefault("total", tl["total"]); data.setdefault("handle", "8bit" + pathlib.Path(base).name.split("_")[0])
issues = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
    pg = b.new_page(viewport={"width": 540, "height": 960}); pg.goto("file://" + os.environ.get("QA_TEMPLATE", str(ROOT / "gen/reel_t.html"))); pg.evaluate("d=>setData(d)", data)
    t = 0.0
    while t < data["total"]:
        res = pg.evaluate(f"(()=>{{window.__QA=[];window.__QP=[];window.__QR=[];window.__QB=[];window.__QC=[];render({t});const r=[window.__QA,window.__QP,window.__QR,window.__QB,window.__QC];window.__QA=null;window.__QP=null;window.__QR=null;window.__QB=null;window.__QC=null;return r}})()"); boxes, panels, rects, qb, qc = res
        sc = next((s["scene"] for s in data["spans"] if s["start"] <= t < s["end"]), "?")
        for x in boxes:
            if x[0].startswith("__CUT__"): issues.append((round(t, 2), sc, f"text cut short: {x[0][7:]!r}"))
        boxes = [x for x in boxes if not x[0].startswith("__CUT__")]
        vis = [x for x in boxes if x[6] > .6 and x[0].strip()]
        cur = next((s2 for s2 in data["spans"] if s2["start"] <= t < s2["end"]), {"start": 0, "end": 1e9}); settle = min(1.4, .45 * (cur["end"] - cur["start"]))
        for x in vis:
            s_, x0, y0, w, h, px = x[:6]
            if px < 40 and not (px >= 32) and not COPY_MODE: issues.append((round(t, 2), sc, f"tiny text ({px}px): {s_!r}"))
            st = next((s2["start"] for s2 in data["spans"] if s2["start"] <= t < s2["end"]), 0)
            if (x0 < 20 or x0 + w > 1060) and t - st > settle: issues.append((round(t, 2), sc, f"text off the side: {s_!r}"))
            if y0 < 200 or y0 + h > 1600: issues.append((round(t, 2), sc, f"text outside safe zone (y {y0}-{y0+h}): {s_!r}"))
        cur = next((s2 for s2 in data["spans"] if s2["start"] <= t < s2["end"]), {"start": 0, "end": 1e9})
        settle = min(1.4, .45 * (cur["end"] - cur["start"]))
        if t - cur["start"] > settle:
            for x in vis:
                s_, x0, y0, w, h = x[:5]; cx, cy = x0 + w / 2, y0 + h * .55
                inside = [p_ for p_ in panels if p_[4] > .6 and p_[0] <= cx <= p_[2] and p_[1] <= cy <= p_[3]]
                if inside:
                    p_ = min(inside, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
                    if x0 < p_[0] - 6 or x0 + w > p_[2] + 6 or y0 + h * .2 < p_[1] - 6 or y0 + h * .85 > p_[3] + 8:
                        issues.append((round(t, 2), sc, f"text spills out of its panel: {s_!r}"))
            for x in vis:                                   # pixel-geometry check: every text against the box it is drawn on
                if len(x) < 11: continue
                s_, x0, y0, w = x[:4]; it, ib, ti, al = x[7], x[8], x[9], x[10]; L, Rr = x0, x0 + w; cx, cy = (L + Rr) / 2, (it + ib) / 2; ih = ib - it + 1
                circ = [c for c in qc if c[3] <= ti and (cx - c[0]) ** 2 + (cy - c[1]) ** 2 <= c[2] ** 2 and c[2] < 2.2 * max(ih, w / 2) and w < 1.9 * c[2]]
                if circ:                                       # text inside a small circle (e.g. the VS bubble): centre on the circle
                    c = circ[-1]
                    if max(abs(cx - c[0]), abs(cy - c[1])) > 3: issues.append((round(t, 2), sc, f"text off-centre in its circle ({cx - c[0]:+.0f}px, {cy - c[1]:+.0f}px): {s_!r}"))
                    continue
                under = [(i, r) for i, r in enumerate(rects[:ti]) if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]]
                if not under: continue
                pi, r = under[-1]; bw, bh = r[2] - r[0], r[3] - r[1]
                if r[0] <= L and r[2] >= Rr and r[1] <= it and r[3] >= ib and bw < 1000:
                    gl, gr, gt, gb = L - r[0], r[2] - Rr, it - r[1], r[3] - ib
                    if min(gl, gr, gt, gb) < 4: issues.append((round(t, 2), sc, f"text too close to its box edge ({min(gl, gr, gt, gb):.0f}px): {s_!r}"))
                    others = [o for o in vis if o is not x and len(o) > 10 and o[1] < r[2] and o[1] + o[3] > r[0] and o[7] < r[3] and o[8] > r[1] and o[1] < Rr and o[1] + o[3] > L]
                    later = [q for q in rects[pi + 1:] if q[0] >= r[0] - 1 and q[2] <= r[2] + 1 and q[1] >= r[1] - 1 and q[3] <= r[3] + 1 and (q[2] - q[0]) >= 20 and (q[3] - q[1]) >= 6 and q[0] < Rr and q[2] > L and not any(((q[0] + q[2]) / 2 - c[0]) ** 2 + ((q[1] + q[3]) / 2 - c[1]) ** 2 <= (c[2] + 2) ** 2 for c in qc)]
                    badges_in = [bd for bd in qb if r[0] <= bd[0] <= r[2] and r[1] <= bd[1] <= r[3]]
                    stacked = any(o[8] < it or o[7] > ib for o in others) or any(q[3] <= it or q[1] >= ib for q in later)
                    beside = any(not (o[8] < it or o[7] > ib) for o in others) or any(not (q[3] <= it or q[1] >= ib) for q in later) or badges_in
                    # vertical cell: the band of the box between the nearest stacked items above and below this text
                    above = [o[8] for o in others if o[8] < it] + [q[3] for q in later if q[3] <= it]
                    below = [o[7] for o in others if o[7] > ib] + [q[1] for q in later if q[1] >= ib]
                    ct, cb = max([r[1]] + above), min([r[3]] + below); ut, ub = it - ct, cb - ib
                    if (cb - ct) < 2.6 * max(8, ih) and abs(ut - ub) > max(3, .15 * ih) and (not stacked or (above and below) or (above and cb == r[3]) or (below and ct == r[1])):
                        issues.append((round(t, 2), sc, f"text not vertically centred (top {ut:.0f}px vs bottom {ub:.0f}px): {s_!r}"))
                    if al == "center" and not beside and bw < w + 160 and abs(gl - gr) > 3:
                        issues.append((round(t, 2), sc, f"text not horizontally centred (left {gl:.0f}px vs right {gr:.0f}px): {s_!r}"))
                elif bw >= 12 and bh >= 12 and bw < 1000 and (L < r[0] - 1 or Rr > r[2] + 1 or it < r[1] - 1 or ib > r[3] + 1):
                    issues.append((round(t, 2), sc, f"text crosses its box edge: {s_!r}"))
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, c = vis[i], vis[j]
                ix = max(0, min(a[1] + a[3], c[1] + c[3]) - max(a[1], c[1])); iy = max(0, min(a[2] + a[4], c[2] + c[4]) - max(a[2], c[2]))
                st0 = next((s2["start"] for s2 in data["spans"] if s2["start"] <= t < s2["end"]), 0)
                gap = max(a[1], c[1]) - min(a[1] + a[3], c[1] + c[3])
                if t - st0 > settle and iy > .5 * min(a[4], c[4]) and gap < 10 and a[0] != c[0]:
                    issues.append((round(t, 2), sc, f"texts touching: {a[0]!r} / {c[0]!r}"))
                if ix * iy > .15 * min(a[3] * a[4], c[3] * c[4]) and not (a[0] == c[0]) and t - st0 > settle:
                    issues.append((round(t, 2), sc, f"text overlaps: {a[0]!r} / {c[0]!r}"))
        t += 1 / 3
    # logos: measure each badge's logo from the finished frame's pixels (settled frame of every scene)
    import base64, io
    import numpy as np
    from PIL import Image
    for sp in data["spans"]:
        tt = max(sp["start"] + .2, sp["end"] - .45)
        qb, url = pg.evaluate(f"(()=>{{window.__QB=[];render({tt});const r=window.__QB;window.__QB=null;return [r,document.getElementById('c').toDataURL('image/png')]}})()")
        if not qb: continue
        fr = np.asarray(Image.open(io.BytesIO(base64.b64decode(url.split(",")[1]))).convert("RGB")).astype(int)
        for bx, by, br, col, key in qb:
            if not key or br < 10: continue
            fill = np.array([int(col[i:i + 2], 16) for i in (1, 3, 5)]); rr = br - 2
            y0, y1, x0, x1 = int(by - rr), int(by + rr) + 1, int(bx - rr), int(bx + rr) + 1
            if y0 < 0 or x0 < 0 or y1 > fr.shape[0] or x1 > fr.shape[1]: continue
            yy, xx = np.mgrid[y0:y1, x0:x1]; inside = (yy - by) ** 2 + (xx - bx) ** 2 <= rr * rr
            m = inside & (np.abs(fr[y0:y1, x0:x1] - fill).sum(-1) > 60)
            if m.sum() < 30: continue
            ys, xs = np.nonzero(m); ys = ys + y0; xs = xs + x0
            ox = ((xs.min() + xs.max()) / 2 + xs.mean()) / 2 - bx; oy = ((ys.min() + ys.max()) / 2 + ys.mean()) / 2 - by
            if max(abs(ox), abs(oy)) > max(3, .06 * br):
                issues.append((round(tt, 2), sp["scene"], f"logo off-centre in its badge ({ox:+.0f}px, {oy:+.0f}px): {key}"))
    b.close()
if tl.get("vo"):                                                   # narration must sit clearly above the music
    vc = subprocess.run([sys.executable, str(ROOT / "gen/vo_check.py"), base], cwd=str(ROOT), capture_output=True, text=True)
    if vc.returncode != 0: issues.append((0.0, "audio", "voice not clearly above the music: " + vc.stdout.strip()))
sys.path.insert(0, str(ROOT / "gen")); import voicecheck            # fan voice: we/our/us about our own team
for m in voicecheck.check_reel(base): issues.append((0.0, "voice", m))
seen = set(); out = []
for t, sc, m in issues:
    k = (sc, m)
    if k not in seen: seen.add(k); out.append(f"  {t:6.2f}s [{sc}] {m}")
mp4 = base + ".mp4"
lufs = subprocess.run(["ffmpeg", "-v", "info", "-i", mp4, "-af", "loudnorm=print_format=summary", "-f", "null", "-"], capture_output=True, text=True).stderr
I = re.search(r"Input Integrated:\s+(-?[\d.]+)", lufs); TP = re.search(r"Input True Peak:\s+(-?[\d.]+)", lufs)
print(f"== {pathlib.Path(base).name}: {len(out)} text issue(s); loudness {I.group(1) if I else '?'} LUFS, peak {TP.group(1) if TP else '?'} dBTP")
print("\n".join(out[:40]))
import hashlib
pathlib.Path(base + ".qa.json").write_text(json.dumps({"mp4_md5": hashlib.md5(open(mp4, "rb").read()).hexdigest(), "issues": len(out), "detail": out[:40]}))
if tl.get("vo"):
    QW = f"/tmp/_qa_{os.getpid()}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-ar", "16000", "-ac", "1", QW])
    tx = subprocess.run(["whisper-cli", "-m", os.path.expanduser("~/.whisper-models/ggml-small.en.bin"), "-f", QW, "-nt", "-np"], capture_output=True, text=True).stdout
    script = " ".join(b["vo"] for b in data.get("story", {}).get("beats", []))
    norm = lambda s: re.findall(r"[a-z]+", s.lower()); sw, tw = set(norm(script)), set(norm(tx))
    miss = [w for w in norm(script) if w not in tw and len(w) > 3]
    print(f"  narration: {100 * len(sw & tw) // max(1, len(sw))}% of script words heard; not heard: {sorted(set(miss))[:15]}")
    print("  transcript:", tx.strip()[:400])
