#!/bin/zsh
# Template regression: build the worst-case torture specs and run the strict QA. Run after ANY change to gen/reel_t.html.
cd /Users/ryanhelou/Developer/8bitraptors
python3 gen/history.py specs/test_torture_history.json >/dev/null 2>&1 && python3 gen/qa.py out/raptors_torture_history 2>&1 | grep -E "^==|s \[" | sed -E 's/^ *[0-9.]+s //' | sort -u
python3 gen/alltime.py specs/test_torture_poll.json >/dev/null 2>&1 && python3 gen/qa.py out/warriors_torture_poll 2>&1 | grep -E "^==|s \[" | sed -E 's/^ *[0-9.]+s //' | sort -u
