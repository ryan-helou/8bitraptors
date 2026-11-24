"""Monster sprites from the PMD Sprite Collab (https://sprites.pmdcollab.org, CC BY-NC 4.0; credit in every caption).
get("hawlucha") -> PIL RGBA image: first Idle frame facing down-left, trimmed. Cached in assets/pmd/.
usage: python3 gen/pmd.py hawlucha decidueye ...   (writes assets/pmd/_sheet.png for a look)"""
import sys, json, re, pathlib, urllib.request
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent; C = ROOT / "assets/pmd"; C.mkdir(parents=True, exist_ok=True)
RAW = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite/{d}/{f}"
UA = {"User-Agent": "8bit-reels"}
CREDIT = "Monster sprites: PMD Sprite Collab (sprites.pmdcollab.org), CC BY-NC 4.0"


def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()


def dex(name):
    f = C / "_dex.json"; m = json.loads(f.read_text()) if f.exists() else {}
    k = name.lower().strip()
    if k not in m:
        m[k] = json.loads(fetch(f"https://pokeapi.co/api/v2/pokemon-species/{k}"))["id"]; f.write_text(json.dumps(m))
    return m[k]


def get(name, row=7, shiny=False):
    """shiny=True uses the collab's shiny palette (sprite/<dex>/0000/0001/), added 2026-11-15 for the shiny countdown."""
    out = C / f"{name.lower()}{'_shiny' if shiny else ''}.png"
    if out.exists(): return Image.open(out).convert("RGBA")
    d = f"{dex(name):04d}"; xml = fetch(RAW.format(d=d, f="AnimData.xml")).decode()
    blk = re.search(r"<Name>Idle</Name>(.*?)</Anim>", xml, re.S).group(1)
    if "<CopyOf>" in blk: src = re.search(r"<CopyOf>(\w+)</CopyOf>", blk).group(1); blk = re.search(rf"<Name>{src}</Name>(.*?)</Anim>", xml, re.S).group(1)
    fw, fh = int(re.search(r"<FrameWidth>(\d+)", blk).group(1)), int(re.search(r"<FrameHeight>(\d+)", blk).group(1))
    p = C / f"_{d}_idle{'_shiny' if shiny else ''}.png"
    if not p.exists(): p.write_bytes(fetch(RAW.format(d=d, f=("0000/0001/" if shiny else "") + "Idle-Anim.png")))
    sh = Image.open(p).convert("RGBA"); rows = sh.height // fh; r = row if rows > row else 0
    im = sh.crop((0, r * fh, fw, (r + 1) * fh)); im = im.crop(im.getbbox()); im.save(out); return im


if __name__ == "__main__":
    ims = [get(n) for n in sys.argv[1:]]; s = 4
    sh = Image.new("RGBA", (sum(i.width * s + 20 for i in ims), max(i.height * s for i in ims) + 20), (220, 235, 245, 255)); x = 10
    for i in ims: sh.alpha_composite(i.resize((i.width * s, i.height * s), Image.NEAREST), (x, 10)); x += i.width * s + 20
    sh.save(C / "_sheet.png"); print(C / "_sheet.png")
