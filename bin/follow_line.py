#!/usr/bin/env python3
"""Add the follow line to a caption, just above the hashtags (Ryan 2026-11-25: "add a follow to keep up with raptors news").
Started 2026-11-25 so the Nov 30 review can compare follows per day before and after.
usage: python3 bin/follow_line.py CAPTION_FILE ACCOUNT   (edits the file in place; does nothing if the line is already there)"""
import sys, pathlib
LINE = {"raptors": "Follow @8bitraptors to keep up with Raptors news, trades and stories every day.",
        "warriors": "Follow @8bitwarriors to keep up with Warriors news, trades and stories every day."}


def add(path, account):
    p = pathlib.Path(path); s = p.read_text(); line = LINE[account]
    if line in s: return False
    parts = s.rstrip("\n").split("\n")
    i = next((k for k in range(len(parts) - 1, -1, -1) if parts[k].strip().startswith("#")), None)   # the hashtag line
    if i is None: parts += ["", line]
    else: parts[i:i] = [line, ""]
    p.write_text("\n".join(parts) + "\n"); return True


if __name__ == "__main__":
    print("added" if add(sys.argv[1], sys.argv[2]) else "already there")
