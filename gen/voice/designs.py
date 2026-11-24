"""Generate the designed-voice candidates through VoiceStudio (Qwen3-TTS VoiceDesign) -> review/voices/q*.wav"""
import json, urllib.request, uuid, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; VS = "http://localhost:3900"
T = (ROOT / "review/voices/script.txt").read_text().strip()
B = ("A normal American guy, about 27 years old, with a medium-pitched voice, neither deep nor high. Natural and human, steady and even, "
     "with gentle, natural ups and downs. Not breathy, not whispery, not husky, not intimate, not an announcer.")
V = {"q01_everyday": "Talking like he's telling a friend about last night's game.",
     "q02_clear": "Clear, clean diction, relaxed confidence, moderate pace.",
     "q03_warm": "A little warmth and a slight smile in his voice.",
     "q04_calm": "Calm and grounded, unhurried but never sleepy.",
     "q05_podcast": "Like a young sports podcast co-host: easygoing and engaged.",
     "q06_canadian": "Slight Canadian accent, friendly and down-to-earth.",
     "q07_crisp": "Crisp and articulate, like a good audiobook narrator, but casual.",
     "q08_youtube": "Like a laid-back basketball YouTuber explaining a story, interested but not hyped.",
     "q09_bright": "Slightly brighter tone, upbeat but controlled, no shouting.",
     "q10_grainy": "A tiny bit of natural grain in his voice, relaxed and steady.",
     "q11_reporter": "Like a young local sports reporter reading a recap: clear, even, matter-of-fact.",
     "q12_friendly": "Friendly and approachable, smooth pacing, very natural rhythm."}
def post(path, fields=None, js=None):
    if js is not None: req = urllib.request.Request(VS + path, json.dumps(js).encode(), {"content-type": "application/json"})
    else:
        b = uuid.uuid4().hex; body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items()) + f"--{b}--\r\n".encode()
        req = urllib.request.Request(VS + path, body, {"content-type": f"multipart/form-data; boundary={b}"})
    return urllib.request.urlopen(req, timeout=600).read()
post("/engines/select", js={"family": "tts", "backend_id": "mlx-audio", "model_id": "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit"})
(ROOT / "review/voices/designs.json").write_text(json.dumps({k: B + " " + v for k, v in V.items()}, indent=1))
for k, v in V.items():
    (ROOT / f"review/voices/{k}.wav").write_bytes(post("/generate", {"text": T, "language": "en", "instruct": B + " " + v, "seed": 42})); print(k, flush=True)
