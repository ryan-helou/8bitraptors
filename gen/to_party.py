"""Convert a trainer (r_tr_*/w_tr_*) or core-five (*_every_starter) spec into the @8bitwolves party layout (p_* beats).
usage: python3 gen/to_party.py specs/r_tr_scottie.json ...   (original saved to specs/bak/<name>.preparty.json)"""
import json, sys, pathlib, shutil, re
for f in sys.argv[1:]:
    p = pathlib.Path(f); s = json.loads(p.read_text())
    if any(b.get("kind", "").startswith("p_") for b in s["beats"]): print(p.name, "already party"); continue
    shutil.copy(p, p.parent / "bak" / (p.stem + ".preparty.json"))
    mons = [b for b in s["beats"] if b.get("kind") == "mon"]
    trainer = any(b.get("kind") == "team" for b in s["beats"])
    s["party"] = [{"key": b["key"], "mon": b["mon"], "nick": b["name"], "types": b.get("types", []), "label": b.get("species", ""), "stat": b.get("callout") or ((b.get("lines") or [[None]])[0][0] and " ".join((b.get("lines") or [[""]])[0]))} for b in mons]
    s["mode"] = "trainer" if trainer else "starters"
    beats = []
    if trainer:
        tb = next(b for b in s["beats"] if b.get("kind") == "team")
        first = tb["dlg"].split("|")[0].replace("IF ", "").replace(" WAS A TRAINER...", "").replace(" WAS A TRAINER", "").strip()
        full = re.sub(r"^If (.*?) was a trainer.*$", r"\1", tb["vo"]).strip()
        beats.append({"kind": "p_intro", "vo": f"If {full} had a Pokémon team, here's who we'd send out.", "dlg": f"IF {first} HAD A TEAM|OF MONSTERS..."})
    else:
        tname = "RAPTORS" if s["team"] == "raptors" else "WARRIORS"
        beats.append({"kind": "p_intro", "vo": "If our core five were Pokémon, here's the team.", "dlg": "IF OUR CORE FIVE|WERE MONSTERS..."})
    for k, b in enumerate(mons):
        if trainer: beats.append({"kind": "p_menu", "sel": k, "vo": "", "dlg": "CHOOSE A STARTER.", "hold": 1.0})
        beats.append({"kind": "p_mon", "i": k, "first": True, "stat": True, "vo": b["vo"], "dlg": b["dlg"]})
    beats.append({"kind": "p_sum", "vo": "That's a party we'd run back every night. Who would you swap in? Comment below.", "dlg": "A PARTY WE'D RUN BACK|EVERY NIGHT. WHO'S IN?"})
    s["beats"] = beats
    c = s["caption"]
    c = re.sub(r"^IF (.*?) WAS A POKÉMON TRAINER, THIS IS HIS TEAM", r"IF \1 HAD A POKÉMON TEAM, HERE'S WHO WE'D SEND OUT", c)
    c = c.replace("Which one would you add? 👇", "That's a party we'd run back every night. Which one would you swap in? 👇").replace("Who did we get wrong? 👇", "That's a party we'd run back every night. Who would you change? 👇")
    s["caption"] = c
    p.write_text(json.dumps(s, indent=1, ensure_ascii=False)); print(p.name, s["mode"], len(beats), "beats |", c.splitlines()[0])
