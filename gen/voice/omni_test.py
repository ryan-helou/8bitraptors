"""A/B voices for the narrated reels with OmniVoice (VoiceStudio's engine). Writes review/voice_ab/<name>.wav"""
import torch, soundfile as sf, numpy as np, time, sys
from omnivoice import OmniVoice
m = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="mps", dtype=torch.float32)
SR = getattr(m, "sampling_rate", 24000)
TEXT = ("Denver came in three and three! Vegas had the Raptors as 4.5-point underdogs... and no Kawhi Leonard! "
        "Denver ran away with it, up by as many as 27! Nikola Jokic dropped a triple-double! "
        "The Raptors forced 15 turnovers, turned them into 24 points... but it wasn't enough! "
        "RJ Barrett led the Raptors with 22! Raptors fall, 128 to 109! Who was your MVP? Comment below!")
x, sr = sf.read("review/voice_ab/0_current_kokoro.wav"); sf.write("review/voice_ab/_ref.wav", x[:int(sr * 6.2)], sr)
REFT = "Denver came in three and three. Vegas had the Raptors as 4.5-point underdogs. And no Kawhi Leonard."
V = {"C_hype_young": dict(instruct="male, young adult, high pitch, american accent", speed=1.3),
     "D_hype_clone": dict(ref_audio="review/voice_ab/_ref.wav", ref_text=REFT, speed=1.15),
     "E_hype_fast": dict(instruct="male, young adult, moderate pitch, american accent", speed=1.45)}
for name in (sys.argv[1:] or V):
    torch.manual_seed(7); t = time.time()
    a = np.asarray(m.generate(text=TEXT, **V[name])[0]).squeeze()
    sf.write(f"review/voice_ab/{name}.wav", a, SR); print(name, round(time.time() - t), "s", flush=True)
