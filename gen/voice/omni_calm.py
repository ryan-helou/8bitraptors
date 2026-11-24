"""Soothing-but-not-monotone voice candidates (OmniVoice). Writes review/voice_ab/<name>.wav"""
import torch, soundfile as sf, numpy as np, time, sys
from omnivoice import OmniVoice
from omnivoice.models.omnivoice import OmniVoiceGenerationConfig as GC
m = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="mps", dtype=torch.float32)
SR = getattr(m, "sampling_rate", 24000)
TEXT = ("Denver came in three and three. Vegas had the Raptors as four-and-a-half-point underdogs, and no Kawhi Leonard. "
        "Denver ran away with it, up by as many as twenty-seven. Nikola Jokic dropped a triple-double. "
        "The Raptors forced fifteen turnovers, and turned them into twenty-four points... but it wasn't enough. "
        "RJ Barrett led the Raptors with twenty-two. Raptors fall, one twenty-eight to one-oh-nine. Who was your MVP? Comment below.")
cfg = GC(class_temperature=0.6)
V = {"F_calm_warm": dict(instruct="male, middle-aged, moderate pitch, american accent", speed=1.1),
     "G_calm_low": dict(instruct="male, young adult, low pitch, american accent", speed=1.12),
     "H_calm_female": dict(instruct="female, young adult, moderate pitch, american accent", speed=1.1)}
for name in (sys.argv[1:] or V):
    torch.manual_seed(11); t = time.time()
    a = np.asarray(m.generate(text=TEXT, generation_config=cfg, **V[name])[0]).squeeze()
    sf.write(f"review/voice_ab/{name}.wav", a, SR); print(name, round(time.time() - t), "s", flush=True)
