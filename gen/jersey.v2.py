"""Repaint a headshot's jersey in a team's colours (ESPN headshots show a player's latest team).
Pixels in the lower part of the image that are far from the player's skin tone get mapped by brightness onto the
team palette (dark trim / main colour / light trim)."""
import numpy as np
from PIL import Image
PAL = {"BKN": ((0, 0, 0), (28, 28, 30), (245, 245, 245)), "TOR": ((24, 24, 28), (206, 17, 65), (235, 235, 240)), "GSW": ((20, 40, 110), (29, 66, 138), (255, 199, 44)), "NYK": ((0, 45, 98), (0, 107, 182), (245, 132, 38))}

def repaint(im, team, top=.7):
    a = np.asarray(im.convert("RGBA")).astype(float); h, w = a.shape[:2]
    rgb, al = a[..., :3], a[..., 3]
    face = rgb[int(h * .25):int(h * .55), int(w * .38):int(w * .62)].reshape(-1, 3); fa = al[int(h * .25):int(h * .55), int(w * .38):int(w * .62)].reshape(-1)
    skin = np.median(face[fa > 128], 0)
    y0 = int(h * top); reg = rgb[y0:]; d = np.sqrt(((reg - skin) ** 2).sum(-1))
    lum = reg @ np.array([.299, .587, .114]); dark, main, light = (np.array(c, float) for c in PAL[team])
    t = np.clip((lum - 40) / 150, 0, 1)[..., None]
    col = np.where(lum[..., None] < 45, dark, np.where(lum[..., None] > 205, light, main * (0.55 + 0.6 * t)))
    import colorsys
    hsv = np.array([colorsys.rgb_to_hsv(*(px / 255)) for px in reg.reshape(-1, 3)]).reshape(reg.shape)
    sh = colorsys.rgb_to_hsv(*(skin / 255))[0]; hd = np.minimum(abs(hsv[..., 0] - sh), 1 - abs(hsv[..., 0] - sh)) * 360
    jersey = ((hsv[..., 1] > .28) & (hd > 18)) | (lum > 200)          # coloured cloth or white trim; never greys/beards or skin hues
    m = jersey & (d > 70) & (al[y0:] > 128)
    reg[m] = np.clip(col[m], 0, 255); rgb[y0:] = reg
    # Wipe sponsor patches, numbers and logos from the other team (Nov 8: "ibotta", "crypto.com", a Suns "6" showed through):
    # inside the jersey, any small detail that differs strongly from the surrounding cloth is replaced by that cloth.
    from PIL import ImageFilter
    y1 = int(h * (top + .06)); k = max(9, (int(w * .09) // 2) * 2 + 1)
    for thr in (60, 38):                                              # two passes: bold marks, then faint leftovers
        base = Image.fromarray(np.clip(rgb[y1:], 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(k)); med = np.asarray(base).astype(float)
        sub = rgb[y1:]; dd = np.sqrt(((sub - skin) ** 2).sum(-1)); dm = np.sqrt(((sub - med) ** 2).sum(-1))
        cloth = (dd > 70) & (al[y1:] > 200) & (np.sqrt(((med - skin) ** 2).sum(-1)) > 70)
        fix = cloth & (dm > thr)
        sub[fix] = med[fix]; rgb[y1:] = sub
    return Image.fromarray(np.dstack([rgb, al]).astype(np.uint8), "RGBA")
