"""Format classifier shared by learn.py and gameday.py."""
import re


def fmt(title):
    t = (title or "").upper()
    if "HAD A POK" in t: return "pokemon_trainer"
    if "POKÉMON" in t or "POKEMON" in t: return "pokemon_team"
    if "TRADE COURT" in t or "WHO WON THE" in t: return "trade_court"
    if "CHOOSE YOUR" in t or "PAUSE AND PICK" in t or t.startswith("OUR GOAT"): return "poll"
    if re.match(r"^(RAPTORS|WARRIORS) \d+, |^(VICTORY|FINAL|WIN|LOSS)\b", t): return "recap"
    if re.search(r"GAMES IN|STARTING FIVE|PARTY CHECK|IS OUT|GAME DAY|WHAT'S WRONG", t): return "game_day"
    if re.search(r"HIGH SCORE|HOW WE BUILT|HOW .* GOT HOME", t): return "explainer"
    if re.search(r"\bNEWS\b|BREAKING|JUST IN", t): return "news"
    return "story"
