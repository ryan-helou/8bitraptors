"""Voice-over-music check: how far the narration sits above the music while someone is talking.
usage: python3 gen/vo_check.py out/<slug_kind>   (re-mixes from the timeline with stems) -> prints dB gap; exit 1 if < 14 dB"""
import sys, json, subprocess, os, wave, numpy as np
base = sys.argv[1]; tmp = "/tmp/_vo_mix.wav"
subprocess.run([sys.executable, "gen/audio.py", base + ".timeline.json", tmp], env={**os.environ, "AUDIO_STEMS": "1"}, capture_output=True, check=True)
rd = lambda f: (lambda w: (np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768))(wave.open(f))
v, m = rd(tmp + ".voice.wav"), rd(tmp + ".music.wav")
win = 4410; n = len(v) // win; vr = np.sqrt((v[:n * win].reshape(n, win) ** 2).mean(1)); mr = np.sqrt((m[:n * win].reshape(n, win) ** 2).mean(1))
talk = vr > 10 ** (-40 / 20)
gap = 20 * np.log10(vr[talk] + 1e-9) - 20 * np.log10(mr[talk] + 1e-9)
print(f"{os.path.basename(base)}: voice is {np.median(gap):.1f} dB above the music while talking (worst 10%: {np.percentile(gap, 10):.1f} dB)")
sys.exit(0 if np.percentile(gap, 10) >= 6 and np.median(gap) >= 16 else 1)
