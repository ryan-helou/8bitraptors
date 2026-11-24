"""Automated reel QA. usage: qa.py out/<slug>_<kind>   (uses the .data.json, .timeline.json and .mp4 next to it)
Checks every 1/3 s: text overlapping other text, text too small to read on a phone, text outside Instagram's
safe zone; then audio loudness and (for narrated reels) that the transcript matches the script."""
import sys, json, os, re, subprocess, pathlib
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent; base = sys.argv[1]
data = json.loads(pathlib.Path(base + ".data.json").read_text()); tl = json.loads(pathlib.Path(base + ".timeline.json").read_text())
data.setdefault("spans", tl["spans"]); data.setdefault("total", tl["total"]); data.setdefault("handle", "8bit" + pathlib.Path(base).name.split("_")[0])
issues = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
    pg = b.new_page(viewport={"width": 540, "height": 960}); pg.goto("file://" + str(ROOT / "gen/reel_t.html")); pg.evaluate("d=>setData(d)", data)
    t = 0.0
    while t < data["total"]:
        res = pg.evaluate(f"(()=>{{window.__QA=[];window.__QP=[];render({t});const r=[window.__QA,window.__QP];window.__QA=null;window.__QP=null;return r}})()"); boxes, panels = res
        sc = next((s["scene"] for s in data["spans"] if s["start"] <= t < s["end"]), "?")
        for x in boxes:
            if x[0].startswith("__CUT__"): issues.append((round(t, 2), sc, f"text cut short: {x[0][7:]!r}"))
        boxes = [x for x in boxes if not x[0].startswith("__CUT__")]
        vis = [x for x in boxes if x[6] > .6 and x[0].strip()]
        for x in vis:
            s_, x0, y0, w, h, px = x[:6]
            if px < 40 and not (px >= 32): issues.append((round(t, 2), sc, f"tiny text ({px}px): {s_!r}"))
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
    b.close()
seen = set(); out = []
for t, sc, m in issues:
    k = (sc, m)
    if k not in seen: seen.add(k); out.append(f"  {t:6.2f}s [{sc}] {m}")
mp4 = base + ".mp4"
lufs = subprocess.run(["ffmpeg", "-v", "info", "-i", mp4, "-af", "loudnorm=print_format=summary", "-f", "null", "-"], capture_output=True, text=True).stderr
I = re.search(r"Input Integrated:\s+(-?[\d.]+)", lufs); TP = re.search(r"Input True Peak:\s+(-?[\d.]+)", lufs)
print(f"== {pathlib.Path(base).name}: {len(out)} text issue(s); loudness {I.group(1) if I else '?'} LUFS, peak {TP.group(1) if TP else '?'} dBTP")
print("\n".join(out[:40]))
if tl.get("vo"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-ar", "16000", "-ac", "1", "/tmp/_qa.wav"])
    tx = subprocess.run(["whisper-cli", "-m", os.path.expanduser("~/.whisper-models/ggml-small.en.bin"), "-f", "/tmp/_qa.wav", "-nt", "-np"], capture_output=True, text=True).stdout
    script = " ".join(b["vo"] for b in data.get("story", {}).get("beats", []))
    norm = lambda s: re.findall(r"[a-z]+", s.lower()); sw, tw = set(norm(script)), set(norm(tx))
    miss = [w for w in norm(script) if w not in tw and len(w) > 3]
    print(f"  narration: {100 * len(sw & tw) // max(1, len(sw))}% of script words heard; not heard: {sorted(set(miss))[:15]}")
    print("  transcript:", tx.strip()[:400])
