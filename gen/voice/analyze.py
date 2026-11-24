"""Measure every candidate in review/voices: pitch (Hz), pitch movement (semitones), speed, speech-to-text accuracy; write mp3s + stats.json"""
import glob, json, subprocess, re, pathlib, sys
import numpy as np, librosa
R = pathlib.Path("review/voices"); out = R / "mp3"; out.mkdir(exist_ok=True)
script = (R / "script.txt").read_text().strip()
W = lambda x: [w for w in re.findall(r"[a-z']+", x.lower().replace("-", " ")) if w not in set("a an the and in on".split())]
want = W(script); stats = json.loads((R / "stats.json").read_text()) if (R / "stats.json").exists() else {}
for f in sorted(glob.glob(str(R / "*.wav"))):
    k = pathlib.Path(f).stem
    if k in stats and "--all" not in sys.argv: continue
    t = f"/tmp/_vt_{k}.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f, "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-40dB,loudnorm=I=-16:TP=-1.5", "-ar", "24000", "-ac", "1", t], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", t, "-b:a", "64k", str(out / f"{k}.mp3")], check=True)
    y, sr = librosa.load(t, sr=16000); f0, v, _ = librosa.pyin(y, fmin=60, fmax=300, sr=sr); f0 = f0[v]
    st = 12 * np.log2(f0 / np.median(f0))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", t, "-ar", "16000", "/tmp/_vt16.wav"], check=True)
    tx = subprocess.run(["whisper-cli", "-m", str(pathlib.Path.home() / ".whisper-models/ggml-small.en.bin"), "-f", "/tmp/_vt16.wav", "-nt", "-np"], capture_output=True, text=True).stdout.strip()
    NUM = {"24": "twenty four", "27": "twenty seven", "5": "five", "4": "four", "9": "nine"}
    tx2 = re.sub(r"\d+", lambda m: NUM.get(m.group(0), m.group(0)), tx).replace("Scotty", "Scottie")
    got = set(W(tx2))
    stats[k] = {"hz": round(float(np.median(f0))), "move": round(float(np.percentile(st, 90) - np.percentile(st, 10)), 1),
                "secs": round(len(y) / sr, 1), "acc": round(sum(w in got for w in want) / len(want) * 100), "heard": tx}
    print(k, stats[k]["hz"], "Hz", stats[k]["move"], "st", stats[k]["secs"], "s", stats[k]["acc"], "%", flush=True)
(R / "stats.json").write_text(json.dumps(stats, indent=1))
