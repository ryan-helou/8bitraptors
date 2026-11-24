"""Original pixel monsters for the 'if every starter was a monster' reels (no third-party characters).
Each is drawn from simple shapes at 40x40, outlined, shaded, and saved as assets/monsters/<name>.png (upscaled 4x, transparent).
usage: python3 gen/monsters.py   (writes all, plus assets/monsters/_sheet.png)"""
from PIL import Image, ImageDraw, ImageFilter
import pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "assets/monsters"; N = 40


def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)


def finish(im):
    a = im.split()[3]; edge = a.filter(ImageFilter.MaxFilter(3))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); ol = Image.new("RGBA", im.size, (24, 20, 32, 255))
    out.paste(ol, mask=edge); out.alpha_composite(im); return out.resize((N * 4, N * 4), Image.NEAREST)


def eye(d, x, y, col=(255, 255, 255), pupil=(20, 20, 30), big=False):
    r = 3 if big else 2
    d.rectangle([x - r + 1, y - r + 1, x + r - 1, y + r - 1], fill=col); d.rectangle([x - 1, y - 1, x, y], fill=pupil); d.point((x - 1, y - 1), fill=(255, 255, 255))


def base(body, belly=None):
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)


def emberfox():
    im, d = base(0); B = (238, 120, 40); L = (255, 214, 140)
    for i, c in enumerate([(255, 80, 30), (255, 140, 40), (255, 200, 60)]):   # three flame tails
        d.polygon([(26, 26), (36 - i * 2, 8 + i * 5), (33 - i * 3, 24)], fill=c)
    d.ellipse([10, 20, 30, 34], fill=B); d.ellipse([14, 26, 26, 34], fill=L)
    d.ellipse([5, 8, 21, 22], fill=B); d.polygon([(6, 12), (5, 2), (11, 9)], fill=B); d.polygon([(19, 11), (21, 1), (15, 8)], fill=B)
    d.polygon([(7, 10), (6, 5), (10, 9)], fill=(255, 220, 160)); d.ellipse([4, 15, 12, 21], fill=L); d.point((5, 17), fill=(30, 20, 20))
    eye(d, 11, 13); eye(d, 17, 13)
    for x in (12, 18, 24): d.rectangle([x, 33, x + 3, 36], fill=shade(B, .8))
    return im


def zapmink():
    im, d = base(0); B = (44, 58, 92); Y = (255, 226, 70)
    d.line([(26, 28), (31, 22), (28, 20), (35, 12), (32, 11), (37, 4)], fill=Y, width=3)
    d.ellipse([8, 22, 30, 32], fill=B)
    for x in (13, 19, 25): d.polygon([(x, 22), (x + 3, 26), (x, 26), (x + 2, 31)], fill=Y)
    d.ellipse([4, 13, 18, 26], fill=B); d.polygon([(5, 15), (2, 9), (9, 13)], fill=B); d.polygon([(16, 14), (19, 9), (13, 12)], fill=B)
    d.rectangle([5, 21, 13, 25], fill=(120, 140, 190)); eye(d, 8, 18, col=(255, 240, 120)); eye(d, 14, 18, col=(255, 240, 120))
    for x in (10, 16, 22, 26): d.rectangle([x, 31, x + 2, 35], fill=(24, 30, 52))
    return im


def stonehorn():
    im, d = base(0); B = (130, 128, 140); D = (92, 90, 104)
    d.ellipse([6, 12, 36, 34], fill=B)
    for x, y in ((14, 16), (22, 14), (28, 20), (18, 24)): d.ellipse([x, y, x + 6, y + 4], fill=D)
    d.polygon([(6, 22), (0, 8), (11, 18)], fill=(225, 215, 190)); d.polygon([(8, 18), (5, 13), (11, 17)], fill=(200, 190, 165))
    eye(d, 10, 23, col=(255, 230, 120))
    for x in (9, 16, 25, 31): d.rectangle([x, 32, x + 4, 37], fill=D)
    return im


def galehawk():
    im, d = base(0); B = (60, 120, 220); W = (150, 200, 255)
    d.polygon([(18, 18), (2, 4), (6, 16), (1, 20), (16, 24)], fill=W); d.polygon([(22, 18), (39, 3), (34, 16), (39, 20), (24, 24)], fill=W)
    for p in ((4, 6), (8, 10), (35, 6), (31, 11)): d.point(p, fill=(255, 255, 255))
    d.ellipse([13, 14, 27, 32], fill=B); d.ellipse([16, 22, 24, 31], fill=(220, 235, 255))
    d.ellipse([13, 6, 27, 18], fill=B); d.polygon([(14, 12), (8, 14), (14, 15)], fill=(255, 190, 40))
    d.polygon([(18, 6), (20, 1), (22, 6)], fill=(30, 60, 140)); eye(d, 17, 11); eye(d, 23, 11)
    d.line([(17, 32), (16, 37)], fill=(255, 190, 40), width=2); d.line([(23, 32), (24, 37)], fill=(255, 190, 40), width=2)
    return im


def mossgolem():
    im, d = base(0); B = (120, 112, 96); M = (90, 160, 80)
    d.rectangle([11, 14, 29, 33], fill=B); d.ellipse([12, 3, 28, 17], fill=B)
    d.rectangle([4, 15, 10, 28], fill=B); d.rectangle([30, 15, 36, 28], fill=B)
    d.ellipse([10, 1, 30, 9], fill=M); d.rectangle([11, 14, 29, 17], fill=M); d.rectangle([4, 15, 10, 17], fill=M); d.rectangle([30, 15, 36, 17], fill=M)
    for p, c in (((14, 3), (255, 120, 160)), ((25, 4), (255, 230, 90)), ((32, 15), (255, 120, 160))): d.rectangle([p[0], p[1], p[0] + 1, p[1] + 1], fill=c)
    eye(d, 16, 10, big=True); eye(d, 24, 10, big=True); d.line([(18, 14), (22, 14)], fill=(70, 60, 50))
    d.rectangle([12, 33, 18, 38], fill=shade(B, .8)); d.rectangle([22, 33, 28, 38], fill=shade(B, .8))
    return im


def shadepaw():
    im, d = base(0); B = (80, 52, 128); D = (52, 32, 90)
    d.arc([22, 6, 40, 30], 200, 330, fill=B, width=3)
    d.ellipse([10, 18, 34, 32], fill=B); d.ellipse([3, 9, 19, 25], fill=B)
    d.polygon([(4, 12), (3, 4), (9, 10)], fill=B); d.polygon([(17, 11), (19, 3), (13, 9)], fill=B)
    eye(d, 8, 16, col=(200, 120, 255), pupil=(255, 255, 255)); eye(d, 14, 16, col=(200, 120, 255), pupil=(255, 255, 255))
    for x in (9, 16, 24, 30): d.ellipse([x - 1, 30, x + 5, 37], fill=D)
    return im


def frostram():
    im, d = base(0); B = (235, 240, 250); I = (140, 200, 240)
    d.ellipse([10, 16, 34, 32], fill=B)
    for x in (12, 18, 24, 30): d.ellipse([x - 3, 14, x + 3, 20], fill=B)
    d.ellipse([3, 10, 17, 24], fill=(200, 210, 230)); d.arc([0, 4, 14, 18], 90, 330, fill=I, width=3); d.arc([9, 3, 23, 17], 200, 80, fill=I, width=3)
    eye(d, 7, 16, col=(160, 230, 255)); eye(d, 12, 16, col=(160, 230, 255))
    for x in (12, 18, 25, 30): d.rectangle([x, 31, x + 2, 37], fill=(110, 120, 140))
    return im


def clawrex():
    im, d = base(0); B = (210, 40, 60); L = (255, 210, 190)
    d.polygon([(28, 22), (39, 30), (37, 33), (26, 28)], fill=B)
    d.ellipse([14, 16, 32, 32], fill=B); d.ellipse([18, 22, 28, 32], fill=L)
    d.polygon([(16, 18), (6, 6), (20, 4), (22, 16)], fill=B); d.ellipse([3, 4, 21, 14], fill=B)
    d.polygon([(10, 4), (12, -1), (14, 4), (17, 0), (18, 5)], fill=(255, 150, 40)); d.rectangle([3, 11, 13, 13], fill=L)
    for x in (5, 8, 11): d.polygon([(x, 11), (x + 1, 13), (x + 2, 11)], fill=(255, 255, 255))
    eye(d, 14, 8)
    d.line([(15, 22), (11, 25)], fill=B, width=2); d.line([(11, 25), (10, 27)], fill=(255, 255, 255))
    d.rectangle([17, 31, 20, 37], fill=shade(B, .8)); d.rectangle([25, 31, 28, 37], fill=shade(B, .8))
    return im


ALL = {"emberfox": emberfox, "zapmink": zapmink, "stonehorn": stonehorn, "galehawk": galehawk, "mossgolem": mossgolem, "shadepaw": shadepaw, "frostram": frostram, "clawrex": clawrex}
if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True); ims = []
    for k, f in ALL.items(): im = finish(f()); im.save(OUT / f"{k}.png"); ims.append(im)
    sh = Image.new("RGBA", (N * 4 * 4, N * 4 * 2), (200, 230, 200, 255))
    for i, im in enumerate(ims): sh.alpha_composite(im, ((i % 4) * N * 4, (i // 4) * N * 4))
    sh.save(OUT / "_sheet.png"); print(OUT / "_sheet.png")
