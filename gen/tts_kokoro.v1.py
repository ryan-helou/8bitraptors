"""Kokoro voiceover lines. usage (run with .venv/bin/python): tts_kokoro.py LINES.json OUTDIR  -> prints JSON durations.
LINES: [{"id": "...", "text": "..."}].
Voice: Ryan's pick 2026-11-07 = "Echo +25% deep" (75% am_echo + 25% am_onyx style blend) at speed 1.05,
chosen from 43 auditioned voices: a normal ~27-year-old guy, medium-low pitch (~102 Hz), steady but not flat."""
import json, sys, pathlib, soundfile as sf
from kokoro_onnx import Kokoro
ROOT = pathlib.Path(__file__).resolve().parent.parent
k = Kokoro(str(ROOT / "assets/tts/kokoro-v1.0.onnx"), str(ROOT / "assets/tts/voices-v1.0.bin"))
VOICE = k.get_voice_style("am_echo") * .75 + k.get_voice_style("am_onyx") * .25; SPEED = 1.05
lines = json.load(open(sys.argv[1])); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True); res = {}
for L in lines:
    a, sr = k.create(L["text"], voice=VOICE, speed=SPEED, lang="en-us"); f = out / f"{L['id']}.wav"; sf.write(f, a, sr); res[L["id"]] = round(len(a) / sr, 3)
print(json.dumps(res))
