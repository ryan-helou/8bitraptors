#!/usr/bin/env python3
"""Daily self-test: prove every generator still produces a post that passes QA, BEFORE a live post depends on it.
Runs from launchd each afternoon (com.8bitraptors.selftest). Quiet when everything passes; alerts Ryan when anything fails.

Checks:
  1. recap for each account's last game, 9 Games In, and a narrated story reel build and pass QA with 0 issues
     (QA includes layout, logos, fan voice, and voice-over-music level)
  2. the torture specs still score exactly their baseline (data/regress_baseline.json), so a template change
     that breaks or "fixes" an edge case is noticed
  3. every player ID in specs/ matches ESPN's name
  4. both Instagram tokens still work and belong to the right account
usage: python3 bin/selftest.py        (writes data/logs/selftest.log)
"""
import os, sys, json, re, subprocess, pathlib, datetime as dt
os.environ["PATH"] = os.path.dirname(sys.executable) + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"   # our python (has playwright) first
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "bin"))
from notify import notify
PY = sys.executable
log = open(ROOT / "data/logs/selftest.log", "a")
P = lambda *a: print(dt.datetime.now().isoformat(timespec="seconds"), *a, file=log, flush=True)
fails = []


def run(args, timeout=1800):
    try: return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired: return subprocess.CompletedProcess(args, 1, "", "timed out")


def build_and_qa(name, build_args, base):
    b = run([PY, "-I", *build_args])
    if b.returncode != 0: fails.append(f"{name}: build failed: {b.stderr.strip()[-150:]}"); P(name, "BUILD FAIL", b.stderr[-600:]); return
    q = run([PY, "-I", str(ROOT / "gen/qa.py"), str(ROOT / base)])
    st = json.loads((ROOT / f"{base}.qa.json").read_text()) if (ROOT / f"{base}.qa.json").exists() else {"issues": "?"}
    P(name, "QA", st.get("issues"), q.stdout[-800:])
    if st.get("issues") != 0: fails.append(f"{name}: QA found {st.get('issues')} issue(s): " + "; ".join(x.strip() for x in st.get("detail", [])[:2]))


P("=== self-test start")
build_and_qa("Raptors recap", [str(ROOT / "gen/build.py"), "recap", "raptors"], "out/raptors_recap")
build_and_qa("Warriors recap", [str(ROOT / "gen/build.py"), "recap", "warriors"], "out/warriors_recap")
build_and_qa("Raptors 9 Games In", [str(ROOT / "gen/build.py"), "gamesin", "raptors"], "out/raptors_gamesin")
build_and_qa("Story reel (Lowry)", [str(ROOT / "gen/history.py"), str(ROOT / "specs/r_lowry.json")], "out/raptors_lowry")

# 2. torture specs must score their recorded baseline
r = run(["zsh", str(ROOT / "gen/regress.sh")])
got = {m.group(1): int(m.group(2)) for m in re.finditer(r"== (\S+): (\d+) text issue", r.stdout)}
bf = ROOT / "data/regress_baseline.json"; base = json.loads(bf.read_text()) if bf.exists() else {}
P("torture", got, "baseline", base)
if not got: fails.append("torture tests did not run: " + r.stderr.strip()[-120:])
elif base and got != base: fails.append(f"torture tests changed: {got} vs baseline {base} (a template change moved an edge case)")

# 3. player IDs
v = run([PY, "-I", str(ROOT / "gen/verify_ids.py")], 600)
bad = []
for line in v.stdout.splitlines():
    m = re.search(r"ESPN=(.+?)\s+spec=(.*)$", line)
    if not m: continue
    espn_name, spec = m.group(1).strip(), m.group(2).strip()
    if espn_name.startswith("??"): bad.append(line.split()[0] + ": ESPN lookup failed"); continue
    en = set(re.findall(r"[a-z]+", espn_name.lower())); sn = set(re.findall(r"[a-z]+", spec.lower())) - {"jr", "iii", "ii"}
    if spec and not any(a_[:4] == b_[:4] for a_ in en for b_ in sn if len(a_) >= 3 and len(b_) >= 3):   # STEPH ~ Stephen
        bad.append(f"{line.split()[0]}: ID is {espn_name}, spec says {spec}")
P("ids", len(v.stdout.splitlines()), "checked;", bad)
if bad: fails.append("player ID mismatch: " + "; ".join(bad[:3]))

# 4. tokens
for acc in ("raptors", "warriors"):
    t = subprocess.run([PY, "-I", str(ROOT / "bin/ig_publish.py"), str(ROOT / "out/raptors_lowry.mp4"), "token check"], cwd=str(ROOT), env={**os.environ, "IG_ACCOUNT": acc}, capture_output=True, text=True, timeout=120)
    ok = f"Token belongs to: @8bit{acc}" in t.stdout
    P("token", acc, ok)
    if not ok: fails.append(f"@8bit{acc} token check failed: " + (t.stderr.strip() or t.stdout.strip())[-120:])

P("=== self-test done:", "PASS" if not fails else f"{len(fails)} FAIL", fails)
if fails: notify("self-test FAILED", f"{len(fails)} problem(s) before tonight's posts: " + " | ".join(fails)[:600])
print("PASS" if not fails else "\n".join(fails))
