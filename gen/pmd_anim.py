"""Idle-animation strips from the PMD Sprite Collab (same source and licence as gen/pmd.py, credit in the caption).
usage: python3 gen/pmd_anim.py hariyama kingdra ...  -> assets/monsters/pmdanim_<name>_<frames>_<ticks>.png and prints the
spec value "m:pmdanim_<name>_<frames>_<ticks>" (frames side by side, equal cells; ticks = mean frame length in 1/60 s)."""
import sys, re, pathlib
from PIL import Image
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pmd
OUT = pmd.ROOT / "assets/monsters"; OUT.mkdir(parents=True, exist_ok=True)


def strip(name, row=7):
    d = f"{pmd.dex(name):04d}"; xml = pmd.fetch(pmd.RAW.format(d=d, f="AnimData.xml")).decode()
    blk = re.search(r"<Name>Idle</Name>(.*?)</Anim>", xml, re.S).group(1)
    if "<CopyOf>" in blk: src = re.search(r"<CopyOf>(\w+)</CopyOf>", blk).group(1); blk = re.search(rf"<Name>{src}</Name>(.*?)</Anim>", xml, re.S).group(1)
    fw, fh = int(re.search(r"<FrameWidth>(\d+)", blk).group(1)), int(re.search(r"<FrameHeight>(\d+)", blk).group(1))
    durs = [int(x) for x in re.findall(r"<Duration>(\d+)</Duration>", blk)]
    p = pmd.C / f"_{d}_idle.png"
    if not p.exists(): p.write_bytes(pmd.fetch(pmd.RAW.format(d=d, f="Idle-Anim.png")))
    sh = Image.open(p).convert("RGBA"); r = row if sh.height // fh > row else 0; n = sh.width // fw
    fr = [sh.crop((k * fw, r * fh, (k + 1) * fw, (r + 1) * fh)) for k in range(n)]
    bb = [f.getbbox() for f in fr if f.getbbox()]; x0, y0, x1, y1 = min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb)
    fr = [f.crop((x0, y0, x1, y1)) for f in fr]; w, h = x1 - x0, y1 - y0
    out = Image.new("RGBA", (w * n, h)); [out.paste(f, (k * w, 0)) for k, f in enumerate(fr)]
    ticks = round(sum(durs[:n]) / max(1, len(durs[:n]))) if durs else 10
    key = f"pmdanim_{name.lower()}_{n}_{ticks}"; out.save(OUT / f"{key}.png"); return key


if __name__ == "__main__":
    for n in sys.argv[1:]: print(n, "m:" + strip(n))
