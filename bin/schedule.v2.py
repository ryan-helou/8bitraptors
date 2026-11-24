"""Schedule a one-shot reel post via launchd. usage: schedule.py LABEL ACCOUNT VIDEO CAPTION_FILE HH:MM [THUMB_MS]
Copies VIDEO into scheduled/<LABEL>.mp4 and CAPTION into data/caption_<LABEL>.txt (so later rebuilds can't change a queued post
unless re-scheduled), writes ~/Library/LaunchAgents/com.8bitraptors.<LABEL>.plist for today at HH:MM and loads it."""
import sys, os, shutil, pathlib, plistlib, subprocess, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
label, account, video, cap, hm = sys.argv[1:6]; thumb = sys.argv[6] if len(sys.argv) > 6 else "1300"
import json, hashlib
stamp = ROOT / (str(video)[:-4] + ".qa.json"); md5 = hashlib.md5(open(ROOT / video, "rb").read()).hexdigest()
if not stamp.exists(): sys.exit(f"{label}: REFUSED - no QA stamp for {video}; run gen/qa.py first")
st = json.loads(stamp.read_text())
if st.get("mp4_md5") != md5: sys.exit(f"{label}: REFUSED - {video} changed after QA; re-run gen/qa.py")
if st.get("issues", 1) != 0: sys.exit(f"{label}: REFUSED - QA found {st.get('issues')} issue(s): {st.get('detail', [])[:3]}")
v = ROOT / "scheduled" / f"{label}.mp4"; shutil.copy(ROOT / video, v)
(ROOT / "data" / f"stamp_{label}.json").write_text(json.dumps({**st, "label": label}))
c = ROOT / "data" / f"caption_{label}.txt"; shutil.copy(ROOT / cap, c)
h, m = map(int, hm.split(":")); d = dt.date.today()
pl = pathlib.Path.home() / "Library/LaunchAgents" / f"com.8bitraptors.{label}.plist"
subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/com.8bitraptors.{label}"], capture_output=True)
plistlib.dump({"Label": f"com.8bitraptors.{label}", "WorkingDirectory": str(ROOT),
               "ProgramArguments": ["/Library/Frameworks/Python.framework/Versions/3.12/bin/python3", "-I", str(ROOT / "bin/scheduled_post.py"), label, account, account, str(v), str(c), thumb],
               "StartCalendarInterval": {"Month": d.month, "Day": d.day, "Hour": h, "Minute": m},
               "StandardOutPath": str(ROOT / f"data/logs/{label}.launchd.log"), "StandardErrorPath": str(ROOT / f"data/logs/{label}.launchd.log")}, open(pl, "wb"))
r = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(pl)], capture_output=True, text=True)
print(f"{label}: {account} at {hm} -> {'loaded' if r.returncode == 0 else r.stderr.strip()}")
