"""Page timings for multi-page voice lines (gen/fmt_bench.html "pages"): word times from whisper on each built clip.
usage: python3 gen/timepages.py specs/<x>.json   (after one build; writes stat.pt and the PC monsters' stat.pg[k].st.pct, then rebuild)
A page starts just before its anchor word "w"; "pa" anchors list words whose monsters pop in on that page."""
import sys, json, re, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
VOFF, LEAD = .15, .12   # history.py starts a clip VOFF after its scene; a page turns LEAD before its word


def words(wav):
    tmp = "/tmp/_tp16.wav"; subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ar", "16000", "-ac", "1", tmp], check=True)
    out = subprocess.run(["whisper-cli", "-m", str(pathlib.Path.home() / ".whisper-models/ggml-small.en.bin"), "-f", tmp, "-ml", "1", "-sow", "-np"], capture_output=True, text=True).stdout
    W = []
    for ln in out.splitlines():
        m = re.match(r"\[(\d+):(\d+):([\d.]+) --> [^\]]+\]\s*(.*)", ln)
        if m and m.group(4).strip(): W.append((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), re.sub(r"[^a-z0-9]", "", m.group(4).lower())))
    return W


NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "sixteen": "16", "thirtyfour": "34"}


def find(W, w, after):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    if w in NUM:
        for t, x in W:
            if t >= after and x.startswith(NUM[w]): return t
    for k, (t, x) in enumerate(W):
        if t >= after and x and (x.startswith(w[:4]) or w.startswith(x[:4]) and len(x) >= 3 or len(x) >= 4 and __import__("difflib").SequenceMatcher(None, x, w).ratio() >= .7): return t
    return None


spec_p = pathlib.Path(sys.argv[1]); spec = json.loads(spec_p.read_text()); vod = ROOT / "out" / f"{spec['team']}_{spec['name']}_vo"
GAP = .12   # history.py (wolves pace): a clip followed by a silent hold gets no gap, a silent hold gets GAP after it
dur = lambda f: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)
# 1) silent holds ("cont") sized so the next clip starts on the reference's cut (stat.pg[0].cut), never under .05 s
B = spec["beats"]; t = 0.0; starts = {}
for i, b in enumerate(B):
    starts[i] = t
    if b.get("vo"): t += dur(vod / f"b{i}.wav") + (0 if i + 1 < len(B) and not B[i + 1].get("vo") else GAP)
    else:
        nxt = B[i + 1] if i + 1 < len(B) else None; cut = ((nxt or {}).get("stat", {}).get("pg") or [{}])[0].get("cut") if nxt else None
        if b.get("cont") and cut is not None: b["hold"] = round(max(.05, cut - t - GAP), 2)
        t += float(b.get("hold", 1.1)) + GAP
print("length", round(t + .6, 2))
for i, b in enumerate(spec["beats"]):
    if not b.get("pages"): continue
    W = words(vod / f"b{i}.wav"); pt, last = [0], 0.0
    st = b.setdefault("stat", {}); pg = st.setdefault("pg", [{} for _ in b["pages"]])
    for k, p in enumerate(b["pages"]):
        if k == 0: continue
        t = find(W, p["w"], last)
        if t is None: print(f"beat {i} page {k}: anchor {p['w']!r} not heard in {[x for _, x in W]}"); t = last + .8
        last = t; at = VOFF + t - LEAD; cut = (pg[k] if k < len(pg) else {}).get("cut")
        if cut is not None: at = min(at + .9, max(at - .6, cut - starts[i]))   # the Wolves' text often leads the voice   # turn on the reference's cut, within the words' reach
        pt.append(round(max(pt[-1] + .3, at), 2))
    st["pt"] = pt
    for k, p in enumerate(b["pages"]):
        if p.get("pa"):
            ts = []; aft = (pt[k - 1] - VOFF) if k else 0
            for w in p["pa"]:
                t = find(W, w, aft) or (aft + .5); aft = t; ts.append(round(max(0, VOFF + t - pt[k] + .05), 2))
            pg[k].setdefault("st", {})["pct"] = ts
    print(i, pt, [pg[k].get("st", {}).get("pct") for k in range(len(b["pages"])) if pg[k].get("st", {}).get("pct")])
spec_p.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
