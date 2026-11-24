"""Fan-voice check: our accounts talk about their own team as "we / our / us" (Ryan, 2026-11-07).
Flags third-person lines about OUR team ("They're 5-4", "Raptors win", "led the Raptors", "Toronto takes...").
The opponent stays third person, so only our team's names are checked.

usage: python3 gen/voicecheck.py out/<slug>_<kind>      (checks narration, on-screen dialogue and caption)
       python3 gen/voicecheck.py --caption FILE TEAM    (checks one caption file, e.g. at schedule time)
"""
import re, sys, json, pathlib

VERBS = (r"win|wins|won|fall|falls|fell|lose|loses|lost|beat|beats|led|lead|leads|are|were|take|takes|took|trade|trades|traded|"
         r"turned|turn|forced|force|stand|stands|draft|drafts|drafted|sign|signs|signed|went|go|goes|hold|held|flipped|"
         r"pulled|pull|move|moved|improve|improved|need|needs|have|had|get|got")
NAMES = {"raptors": ["Raptors", "Toronto"], "warriors": ["Warriors", "Golden State", "Dubs"]}


def check(texts, team):
    """texts: list of (where, text). Returns a list of human-readable problems."""
    names = NAMES.get(team, [team.title()])
    pats = [re.compile(rf"\b(?:the\s+)?{re.escape(n)}\s+(?:{VERBS})\b", re.I) for n in names]
    pats += [re.compile(rf"\b(?:led|for|beat|joined|traded to|drafted by)\s+the\s+{re.escape(n)}\b", re.I) for n in names]
    pats += [re.compile(rf"\bthey(?:'re|'ve|\s+(?:{VERBS}))\b", re.I)]
    out = []
    for where, t in texts:
        if not t: continue
        line = t.replace("|", " ")
        for p in pats:
            m = p.search(line)
            if m: out.append(f"{where}: says {m.group(0)!r} about our team (use we/our/us): {line[:90]!r}"); break
    return out


def caption_body(cap):
    """The caption without its hashtag block (hashtags like #Raptors are fine)."""
    return "\n".join(l for l in cap.splitlines() if not l.strip().startswith("#"))


def check_reel(base):
    base = str(base); data = json.loads(pathlib.Path(base + ".data.json").read_text())
    team = pathlib.Path(base).name.split("_")[0]
    texts = []
    for i, b in enumerate(data.get("story", {}).get("beats", [])):
        texts += [(f"beat {i} narration", b.get("vo", "")), (f"beat {i} on-screen", b.get("dlg", ""))]
    st = data.get("starter") or {}
    texts += [("poll text", st.get(k, "")) for k in ("l1", "q", "boxA", "boxB", "rest")]
    cap = pathlib.Path(base + ".caption.txt")
    if cap.exists(): texts.append(("caption", caption_body(cap.read_text())))
    return check(texts, team)


if __name__ == "__main__":
    if sys.argv[1] == "--caption":
        probs = check([("caption", caption_body(pathlib.Path(sys.argv[2]).read_text()))], sys.argv[3])
    else:
        probs = check_reel(sys.argv[1])
    print("\n".join(probs) or "fan voice OK")
    sys.exit(1 if probs else 0)
