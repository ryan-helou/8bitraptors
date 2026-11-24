#!/bin/zsh
# build + QA + eye-check sheet for each spec. usage: gen/batch.sh specs/a.json specs/b.json ...
cd /Users/ryanhelou/Developer/8bitraptors
# one heavy job at a time (8 GB Mac crashed with 3 parallel builds, 2026-11-18): re-run this script under the lock
if [ -z "$HEAVY_LOCKED" ]; then HEAVY_LOCKED=1 exec python3 gen/heavy_lock.py zsh "$0" "$@"; fi
for s in "$@"; do
  t=$(python3 -c "import json;d=json.load(open('$s'));print(d['team']+'_'+d['name'])")
  if grep -q '"cands"' $s; then python3 gen/alltime.py $s >/dev/null 2>/tmp/b_$t.err; else python3 gen/history.py $s >/dev/null 2>/tmp/b_$t.err; fi || { echo "BUILD FAIL $t"; tail -3 /tmp/b_$t.err; continue; }
  tpl=$(python3 -c "import json;print(json.load(open('$s')).get('template','reel_t.html'))")   # QA the template the reel was built with
  QA_TEMPLATE=$PWD/gen/$tpl python3 gen/qa.py out/$t 2>&1 | grep -E "^==|s \[" ; python3 gen/sheet.py out/$t /tmp/sheet_$t.png >/dev/null
  if [ -d out/${t}_vo ]; then for w in out/${t}_vo/b*.wav; do ffmpeg -loglevel error -y -i $w -ar 16000 -ac 1 /tmp/_bv.wav; echo "  $(basename $w): $(whisper-cli -m ~/.whisper-models/ggml-small.en.bin -f /tmp/_bv.wav -nt -np 2>/dev/null | tr -d '\n')"; done; fi
done
