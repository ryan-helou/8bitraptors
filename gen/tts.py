"""Narration lines. usage (run with .venv/bin/python): tts.py LINES.json OUTDIR  -> prints JSON durations.
LINES: [{"id": "...", "text": "..."}].
Voice: Ryan's pick (2026-11-07) = the "chill podcast host" designed in VoiceStudio (Qwen3-TTS VoiceDesign, Apache-2.0),
driven through VoiceStudio's local API on :3900 with a fixed seed so every line and every reel sounds like the same guy.
Falls back to Kokoro am_michael (gen/tts_kokoro.py) if VoiceStudio isn't running, so overnight recaps never fail."""
import json, sys, pathlib, subprocess, urllib.request, uuid
ROOT = pathlib.Path(__file__).resolve().parent.parent
VS = "http://localhost:3900"
MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit"
VOICE = ("An upbeat, clear American male sports broadcaster in his thirties, like a TV highlights narrator. Bright, confident, energetic and friendly. "
         "Crisp, punchy delivery at a brisk pace. Natural, conversational. Not breathy, not whispery, not slow, not intimate.")
SEED, TEMPO = 42, 1.05          # TEMPO: gentle speed-up (pitch kept) so reels don't drag
UNSAY = {"Kuh-why": "Kawhi", "Bare-ett": "Barrett", "Emmanuel": "Immanuel"}   # Kokoro respellings this voice doesn't need


def post(path, fields=None, js=None, timeout=300):
    if js is not None:
        req = urllib.request.Request(VS + path, json.dumps(js).encode(), {"content-type": "application/json"})
    else:
        b = uuid.uuid4().hex; body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items()) + f"--{b}--\r\n".encode()
        req = urllib.request.Request(VS + path, body, {"content-type": f"multipart/form-data; boundary={b}"})
    return urllib.request.urlopen(req, timeout=timeout).read()


NUMW = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand and oh a an the".split())
def heard(wav, text):
    """Share of the script's (non-number) words that whisper hears in the take."""
    import re, tempfile
    try:
        tmp = tempfile.mktemp(suffix=".wav"); subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ar", "16000", "-ac", "1", tmp], check=True)
        tx = subprocess.run(["whisper-cli", "-m", str(pathlib.Path.home() / ".whisper-models/ggml-small.en.bin"), "-f", tmp, "-nt", "-np"], capture_output=True, text=True, timeout=120).stdout
    except Exception: return 1.0
    W = lambda x: [w for w in re.findall(r"[a-z']+", x.lower().replace("-", " ")) if w not in NUMW and len(w) > 1]
    want, got = W(text), set(W(tx))
    return sum(w in got for w in want) / max(1, len(want))


def dur(f): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)


def studio(lines, out):
    json.loads(urllib.request.urlopen(VS + "/health", timeout=3).read())["status"] == "ok" or 1 / 0
    post("/engines/select", js={"family": "tts", "backend_id": "mlx-audio", "model_id": MODEL})
    res = {}
    for L in lines:
        t = L["text"]
        for k, v in UNSAY.items(): t = t.replace(k, v)
        import hashlib, shutil
        ck = ROOT / "cache/tts" / (hashlib.sha1(f"{MODEL}|{VOICE}|{SEED}|{TEMPO}|{t}".encode()).hexdigest() + ".wav"); ck.parent.mkdir(parents=True, exist_ok=True)
        f = out / f"{L['id']}.wav"
        if ck.exists(): shutil.copy(ck, f); res[L["id"]] = round(dur(f), 3); continue
        raw = out / f"{L['id']}.raw.wav"
        for attempt, seed in enumerate((SEED, SEED + 1, SEED + 2)):      # re-take a line the model garbles (checked by speech-to-text)
            raw.write_bytes(post("/generate", {"text": t, "language": "en", "instruct": VOICE, "seed": seed}))
            sc = heard(raw, t)
            if sc >= .85: break
            print(f"{L['id']}: only {sc:.0%} of words heard with seed {seed}, re-taking", file=sys.stderr)
        f = out / f"{L['id']}.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-af",
                        f"silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        f"silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-40dB,atempo={TEMPO}", str(f)], check=True)
        raw.unlink(); shutil.copy(f, ck); res[L["id"]] = round(dur(f), 3)
    return res


lines = json.load(open(sys.argv[1])); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
USE_STUDIO = False   # 2026-11-07: Ryan picked Kokoro "Echo +25% deep" (gen/tts_kokoro.py) after auditioning 43 voices
try:
    if not USE_STUDIO: raise RuntimeError("studio voice paused")
    res = studio(lines, out)
except Exception as e:
    print(f"VoiceStudio unavailable ({e}); falling back to Kokoro", file=sys.stderr)
    SAY = {"Kawhi": "Kuh-why", "Barrett": "Bare-ett", "Immanuel": "Emmanuel", "Siakam": "Seeahkam", "Poeltl": "Pertle", "Podziemski": "Pod-zem-ski", "Porzingis": "Por-zing-is", "Sengun": "Shen-goon"}
    for L in lines:
        for k, v in SAY.items(): L["text"] = L["text"].replace(k, v)
    kj = out / "_kokoro_lines.json"; kj.write_text(json.dumps(lines))
    res = json.loads(subprocess.run([sys.executable, str(ROOT / "gen/tts_kokoro.py"), str(kj), sys.argv[2]], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
print(json.dumps(res))
