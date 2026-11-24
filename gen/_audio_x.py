"""Chiptune soundtrack + sound effects for a reel, matched to its scene timeline.

usage: audio.py TIMELINE.json OUT.wav
TIMELINE has spans [{scene,start,end}], total, events [{t,type}] (events come from the template's EVENTS()).

Modelled on @8bitwolves' audio: a bright pulse-wave melody over arpeggios, triangle bass and noise drums,
held at a steady level (no pumping), with a dip under the battle transition and small game SFX on cursor
moves, card reveals and attacks. Output is stereo; build.py normalises it to -14 LUFS.
"""
import json, sys, wave, os
import numpy as np

SR = 44100
tl = json.load(open(sys.argv[1])); OUT = sys.argv[2]
DUR = tl["total"]; N = int(SR * DUR)
ML, MR, SL, SR_ = (np.zeros(N) for _ in range(4))
rng = np.random.default_rng(7)


def hz(m): return 440 * 2 ** ((m - 69) / 12)


def osc(kind, f, n, duty=.5):
    t = np.arange(n) / SR
    if kind == "sq": return np.where(((f * t) % 1) < duty, 1., -1.)
    if kind == "tri": return 2 * np.abs(2 * ((f * t) % 1) - 1) - 1
    x = rng.uniform(-1, 1, n)
    return np.diff(x, prepend=0) * .6 if kind == "hiss" else x


def sweep(f0, f1, n, kind="sq", duty=.5):
    f = np.linspace(f0, f1, n); ph = np.cumsum(f) / SR
    return np.where((ph % 1) < duty, 1., -1.) if kind == "sq" else 2 * np.abs(2 * (ph % 1) - 1) - 1


def env(n, a=.004, d=.08, s=.6, r=.03):
    t = np.arange(n) / SR; e = np.minimum(1, t / a)
    e = e * np.where(t < a + d, 1 - (1 - s) * np.clip((t - a) / d, 0, 1), s)
    k = min(n, int(r * SR))
    if k: e[-k:] *= np.linspace(1, 0, k)
    return e


def put(L, R, t, x, vol, pan=0.):
    i = int(t * SR); m = min(len(x), N - i)
    if m <= 0 or i < 0: return
    L[i:i + m] += x[:m] * vol * (1 - max(0, pan)); R[i:i + m] += x[:m] * vol * (1 + min(0, pan))


def tone(L, R, t, m, dur, vol, kind="sq", duty=.5, pan=0., a=.004, d=.08, s=.6):
    n = int(dur * SR)
    if n > 0: put(L, R, t, osc(kind, hz(m), n, duty) * env(n, a, d, s), vol, pan)


THEMES = {
    "calm": dict(bpm=124, chords=[(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)], bass=[48, 45, 41, 43],
                 mel=[[72, 76, 79, 76, 74, 76, 72, None], [69, 72, 76, 72, 74, 72, 69, 67],
                      [65, 69, 72, 74, 76, 74, 72, 69], [67, 71, 74, 79, 77, 74, 71, None]], drive=0),
    "battle": dict(bpm=152, chords=[(57, 60, 64), (53, 57, 60), (55, 59, 62), (52, 56, 59)], bass=[45, 41, 43, 40],
                   mel=[[81, 79, 76, 79, 81, 84, 83, 81], [77, 76, 72, 76, 77, 81, 79, 77],
                        [79, 77, 74, 77, 79, 83, 81, 79], [76, 75, 71, 75, 76, 80, 83, 80]], drive=1),
    # copy skill 2026-11-18: @8bitwolves' bench-as-a-Pokemon-team reel (Df3mQljgFqD) measures 89 BPM in the copy check; under our
    # narration a 92 BPM bed (calm's harmony) is what measures in range (sweep on both final timelines: 92 -> 92.3 detected)
    "bench92": dict(bpm=92, chords=[(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)], bass=[48, 45, 41, 43],
                    mel=[[72, 76, 79, 76, 74, 76, 72, None], [69, 72, 76, 72, 74, 72, 69, 67],
                         [65, 69, 72, 74, 76, 74, 72, 69], [67, 71, 74, 79, 77, 74, 71, None]], drive=0),
    # copy skill 2026-11-19: @8bitwolves' "IF X HAD A POKEMON TEAM" reel (Df490ITCVCg) measures 108 BPM; same harmony as bench92
    # copy skill 2026-11-19: @8bitwolves' "best Wolves team ever" sim reel (Df5806FgG18) measures 136 BPM; same harmony as calm
    "best136": dict(bpm=136, chords=[(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)], bass=[48, 45, 41, 43],
                    mel=[[72, 76, 79, 76, 74, 76, 72, None], [69, 72, 76, 72, 74, 72, 69, 67],
                         [65, 69, 72, 74, 76, 74, 72, 69], [67, 71, 74, 79, 77, 74, 71, None]], drive=0, gain=0.8),
    # copy skill 2026-11-19: @8bitwolves' two-game shot chart (Df5dkpDg76T) measures 129 BPM; battle's harmony at 130 measures 129.2
    "sc130": dict(bpm=130, chords=[(57, 60, 64), (53, 57, 60), (55, 59, 62), (52, 56, 59)], bass=[45, 41, 43, 40],
                  mel=[[81, 79, 76, 79, 81, 84, 83, 81], [77, 76, 72, 76, 77, 81, 79, 77],
                       [79, 77, 74, 77, 79, 83, 81, 79], [76, 75, 71, 75, 76, 80, 83, 80]], drive=1),
    "pkt108": dict(bpm=108, chords=[(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)], bass=[48, 45, 41, 43],
                   mel=[[72, 76, 79, 76, 74, 76, 72, None], [69, 72, 76, 72, 74, 72, 69, 67],
                        [65, 69, 72, 74, 76, 74, 72, 69], [67, 71, 74, 79, 77, 74, 71, None]], drive=0),
    # same bed at 112 BPM: on our mix the copy check's detector reads 112 as ~112 (108 itself reads 83, sweep 2026-11-19)
    "pkt112": dict(bpm=112, chords=[(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)], bass=[48, 45, 41, 43],
                   mel=[[72, 76, 79, 76, 74, 76, 72, None], [69, 72, 76, 72, 74, 72, 69, 67],
                        [65, 69, 72, 74, 76, 74, 72, 69], [67, 71, 74, 79, 77, 74, 71, None]], drive=0),
}
THEME_OF = {"hook": "hook", "battle": "battle", "final": "battle", "pog": "battle", "cast": "battle", "bars": "battle", "next": "battle"}


def theme_section(name, t0, t1):
    T = THEMES[name]; G = T.get("gain", 1.0); beat = 60 / T["bpm"]; bar = 4 * beat; e8, e16 = beat / 2, beat / 4
    b = 0
    while t0 + b * bar < t1:
        s = t0 + b * bar; k = b % 4; ch = T["chords"][k]
        for j, m in enumerate(T["mel"][k]):                       # lead: 25% pulse, slightly left
            if m and s + j * e8 < t1: tone(ML, MR, s + j * e8, m, e8 * .92, .20 * G, "sq", .25, -.18, d=.06, s=.7)
        for j in range(16):                                       # arpeggio: thin 12.5% pulse, right
            if s + j * e16 < t1: tone(ML, MR, s + j * e16, ch[j % 3] + 12, e16 * .8, .055 * G, "sq", .125, .35, d=.03, s=.5)
        for j in range(8):                                        # bass: triangle eighths, root/octave
            if s + j * e8 < t1: tone(ML, MR, s + j * e8, T["bass"][k] + (12 if j % 2 else 0), e8 * .9, .30 * G, "tri", d=.05, s=.8)
        for j in range(16 if T["drive"] else 8):                  # hats
            step = e16 if T["drive"] else e8; tt = s + j * step
            if tt < t1 and (T["drive"] or j % 2): n = int(.03 * SR); put(ML, MR, tt, osc("hiss", 0, n) * env(n, .001, .02, .2, .005), .05 * G, .2)
        for j in range(4):                                        # kick + snare
            tt = s + j * beat
            if tt >= t1: continue
            if T["drive"] or j % 2 == 0:
                n = int(.09 * SR); put(ML, MR, tt, sweep(140, 45, n, "tri") * env(n, .002, .06, .2, .02), .26 * G)
            if j % 2:
                n = int(.12 * SR); put(ML, MR, tt, osc("noise", 0, n) * env(n, .001, .05, .25, .04), (.10 if T["drive"] else .06) * G)
        b += 1


def hook_section(t0, t1):
    for m in (57, 60, 64, 69): tone(ML, MR, t0, m + 12, .42, .09, "sq", .5, 0, d=.3, s=.3)
    n = int(.6 * SR); put(ML, MR, t0, osc("noise", 0, n) * env(n, .001, .5, .05, .05), .12)
    n = int((t1 - t0) * SR); put(ML, MR, t0, sweep(220, 880, n, "sq", .5) * np.linspace(0, 1, n) ** 2, .05, .1)
    for j in range(int((t1 - t0) / .125)): tone(ML, MR, t0 + j * .125, 45 + (12 if j % 2 else 0), .11, .26, "tri", d=.05, s=.8)


# --- music: merge runs of spans that share a theme so the tune doesn't restart every card
runs = []
for sp in tl["spans"]:
    th = THEME_OF.get(sp["scene"], __import__("os").environ.get("MUSIC_THEME", "calm"))   # copy skill: spec "music" picks the bed (their reels run ~152 BPM = battle)
    if runs and runs[-1][0] == th: runs[-1][2] = sp["end"]
    else: runs.append([th, sp["start"], sp["end"]])
for th, a, b in runs:
    hook_section(a, b) if th == "hook" else theme_section(th, a, b)


# --- sound effects
def sfx(kind, t):
    if kind == "blip": tone(SL, SR_, t, 91, .045, .16, "sq", .5)
    elif kind == "confirm": tone(SL, SR_, t, 84, .06, .16, "sq", .5); tone(SL, SR_, t + .06, 91, .08, .16, "sq", .5)
    elif kind == "alert": tone(SL, SR_, t, 96, .04, .12, "sq", .5); tone(SL, SR_, t + .07, 96, .05, .12, "sq", .5)
    elif kind == "appear":
        for j, m in enumerate((88, 91, 96)): tone(SL, SR_, t + j * .05, m, .05, .12, "sq", .25)
    elif kind == "chime":
        for j, m in enumerate((84, 88, 91, 96)): tone(SL, SR_, t + j * .055, m, .09, .10, "sq", .5, d=.05, s=.4); tone(SL, SR_, t + j * .055, m - 12, .09, .08, "tri")
    elif kind == "step": n = int(.018 * SR); put(SL, SR_, t, osc("hiss", 0, n) * env(n, .001, .01, .3, .004), .07)
    elif kind == "whoosh":
        n = int(.5 * SR); put(SL, SR_, t, osc("noise", 0, n) * np.sin(np.linspace(0, np.pi, n)), .14)
        put(SL, SR_, t, sweep(1400, 200, n, "sq", .5) * np.linspace(1, 0, n), .07)
    elif kind == "attack":
        n = int(.32 * SR); put(SL, SR_, t, osc("noise", 0, n) * env(n, .002, .25, .1, .05), .2)
        n = int(.26 * SR); put(SL, SR_, t, sweep(700, 140, n, "sq", .5) * env(n, .002, .2, .2, .03), .12)
    elif kind == "hit":
        n = int(.16 * SR); put(SL, SR_, t, sweep(130, 50, n, "tri") * env(n, .001, .12, .2, .03), .34)
        n = int(.08 * SR); put(SL, SR_, t, osc("noise", 0, n) * env(n, .001, .06, .1, .02), .15)


duck = np.ones(N)
for ev in tl.get("events", []):
    sfx(ev["type"], ev["t"])
    if ev["type"] == "whoosh":                                    # music dips under the transition, like Wolves
        i, m = int(ev["t"] * SR), int(.55 * SR); seg = 1 - .65 * np.sin(np.linspace(0, np.pi, m))
        duck[i:i + m] = np.minimum(duck[i:i + m], seg[:max(0, min(m, N - i))])

def bright(x, sr):
    """Presence lift for a deep narrator: 2nd-order high-pass at 200 Hz + RBJ high shelf +9 dB at 2 kHz.
    Only used when a spec asks for it (2026-11-18, shot-chart copy: their mix centroid 2269 Hz vs ours 1484 Hz)."""
    import scipy.signal as ss
    b, a = ss.butter(2, 200 / (sr / 2), "high"); x = ss.lfilter(b, a, x)
    A = 10 ** (9 / 40); w0 = 2 * np.pi * 2000 / sr; al = np.sin(w0) / 2 * np.sqrt(2); c = np.cos(w0); r = 2 * np.sqrt(A) * al
    b = [A * ((A + 1) + (A - 1) * c + r), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - r)]
    a = [(A + 1) - (A - 1) * c + r, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - r]
    return ss.lfilter(b, a, x)


VO = np.zeros(N)
for v in tl.get("vo", []):                                        # narration (Kokoro), music ducks under it
    w = wave.open(v["wav"]); sr0 = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768; w.close()
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(1)
    if sr0 != SR: x = np.interp(np.arange(int(len(x) * SR / sr0)) * sr0 / SR, np.arange(len(x)), x)
    i = int(v["t"] * SR); m = min(len(x), N - i)
    if m > 0:
        if v.get("eq") == "bright": x = bright(x, SR)              # copy skill: spec "voice_eq": "bright" (mix brightness like the reference)
        sp = x[np.abs(x) > .01]; rms = np.sqrt(np.mean(sp ** 2)) if len(sp) else 1e-6
        VO[i:i + m] += x[:m] / max(rms, 1e-6) * .16          # level by loudness (RMS), not peak: soft voices get as loud as bright ones
VO = np.tanh(VO * 1.4) / 1.4                                   # gentle limiter so loud syllables don't clip
if tl.get("vo"):
    talk = np.zeros(N)                                         # hold the duck for each whole line (no music swell between words)
    for v in tl.get("vo", []):
        w = wave.open(v["wav"]); d = w.getnframes() / w.getframerate(); w.close()
        a0, a1 = max(0, int((v["t"] - .08) * SR)), min(N, int((v["t"] + d + .12) * SR)); talk[a0:a1] = 1
        if v.get("bridge"):                                    # copy skill (spec "duck_bridge"): no music swell in a short pause between two lines
            nx = [u["t"] for u in tl["vo"] if u["t"] > v["t"]]
            if nx and min(nx) - (v["t"] + d) < 9: talk[a0:min(N, int(min(nx) * SR))] = 1
    k = int(.12 * SR); talk = np.convolve(talk, np.ones(k) / k, "same")      # 120 ms ramps in and out
    vduck = 1 - max([.85] + [float(v.get("duck", .85)) for v in tl["vo"]]) * talk   # music drops ~16 dB under the narration (copy skill: spec "duck_depth" deepens it)
    ML, MR = ML * .55 * vduck, MR * .55 * vduck
L = ML * duck + SL * (.5 if tl.get("vo") else 1); R = MR * duck + SR_ * (.5 if tl.get("vo") else 1)
mx = max(np.max(np.abs(L)), np.max(np.abs(R)), 1e-6); L, R = L / mx, R / mx
L, R = np.tanh(L * 1.6) / np.tanh(1.6), np.tanh(R * 1.6) / np.tanh(1.6)
fade = np.minimum(1, (DUR - np.arange(N) / SR) / .35)
if tl.get("vo"):                                                  # narration on top (gen/vo_check.py verifies >= 15 dB gap)
    if os.environ.get("AUDIO_STEMS"):
        for nm, sig in (("music", (L * .16) * fade * .9), ("voice", (VO * .9) * fade * .9)):
            ww = wave.open(OUT + f".{nm}.wav", "w"); ww.setnchannels(1); ww.setsampwidth(2); ww.setframerate(SR); ww.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes()); ww.close()
    L, R = L * .16 + VO * .9, R * .16 + VO * .9    # gentle saturation = steady level
L *= fade * .9; R *= fade * .9
w = wave.open(OUT, "w"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
print("audio ok", round(DUR, 2), len(tl.get("events", [])), "events")
