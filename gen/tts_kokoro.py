"""Kokoro voiceover lines. usage (run with .venv/bin/python): tts_kokoro.py LINES.json OUTDIR  -> prints JSON durations.
LINES: [{"id": "...", "text": "..."}].
Voice: Ryan's pick 2026-11-07 = "Echo +25% deep" (75% am_echo + 25% am_onyx style blend) at speed 1.05,
chosen from 43 auditioned voices: a normal ~27-year-old guy, medium-low pitch (~102 Hz), steady but not flat."""
import json, sys, pathlib, soundfile as sf
from kokoro_onnx import Kokoro
ROOT = pathlib.Path(__file__).resolve().parent.parent
k = Kokoro(str(ROOT / "assets/tts/kokoro-v1.0.onnx"), str(ROOT / "assets/tts/voices-v1.0.bin"))
VOICE = k.get_voice_style("am_echo") * .75 + k.get_voice_style("am_onyx") * .25; SPEED = float(__import__("os").environ.get("KOKORO_SPEED", "1.05"))   # party reels use 1.25 to match @8bitwolves (~180 wpm)
TRIM = __import__("os").environ.get("KOKORO_TRIM") == "1"   # wolves/party pace (2026-11-12): Kokoro leaves ~0.3-0.5 s of silence after each line


def trim(a, sr, lead=.02, tail=.14, db=-40):
    """Cut leading/trailing silence (20 ms RMS below db dBFS), keeping `lead`/`tail` seconds, with a 30 ms fade-out so the cut never clicks."""
    import numpy as np
    w = int(sr * .02); n = len(a) // w
    if n < 3: return a
    r = 20 * np.log10(np.sqrt((a[:n * w].reshape(n, w) ** 2).mean(1)) + 1e-9); on = np.where(r > db)[0]
    if not len(on): return a
    s0 = max(0, on[0] * w - int(lead * sr)); s1 = min(len(a), (on[-1] + 1) * w + int(tail * sr)); a = a[s0:s1].copy()
    fo = min(len(a), int(.03 * sr)); a[-fo:] *= np.linspace(1, 0, fo); return a


lines = json.load(open(sys.argv[1])); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True); res = {}
for L in lines:
    a, sr = k.create(L["text"], voice=VOICE, speed=SPEED, lang="en-us"); f = out / f"{L['id']}.wav"
    if TRIM: a = trim(a, sr)
    sf.write(f, a, sr); res[L["id"]] = round(len(a) / sr, 3)
print(json.dumps(res))
