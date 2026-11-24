#!/usr/bin/env python3
"""Tell Ryan when something needs him: a blocked post, a failed build, a failed self-test, the morning report.

usage: python3 bin/notify.py "TITLE" "message"      (or: from notify import notify)

Channels: a Mac banner (always), and an iMessage to ALERT_IMESSAGE in .env (Ryan's own phone number or Apple ID),
which is what reaches his phone. Every alert is also appended to data/logs/alerts.log.
Plain copy, no emojis (Ryan's rule for notifications).
"""
import sys, subprocess, pathlib, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _env():
    f = ROOT / ".env"
    return dict(l.split("=", 1) for l in f.read_text().splitlines() if "=" in l and not l.startswith("#")) if f.exists() else {}


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title, msg):
    """Never raises: an alert failing must not stop the post pipeline."""
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    sent = []
    try:
        (ROOT / "data/logs").mkdir(parents=True, exist_ok=True)
        with open(ROOT / "data/logs/alerts.log", "a") as f: f.write(f"{stamp} {title}: {msg}\n")
    except Exception: pass
    try:
        subprocess.run(["osascript", "-e", f'display notification "{_esc(msg[:200])}" with title "8bit: {_esc(title)}" sound name "Glass"'], capture_output=True, timeout=20)
        sent.append("banner")
    except Exception: pass
    to = _env().get("ALERT_IMESSAGE", "").strip()
    if to:
        body = f"8bit {title}\n{msg}"
        script = ('tell application "Messages"\n'
                  '  set svc to 1st account whose service type = iMessage\n'
                  f'  send "{_esc(body)}" to participant "{_esc(to)}" of svc\n'
                  'end tell')
        try:
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
            sent.append("imessage" if r.returncode == 0 else f"imessage failed: {r.stderr.strip()[:120]}")
        except Exception as e: sent.append(f"imessage failed: {e}")
    return sent


if __name__ == "__main__":
    print(notify(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
