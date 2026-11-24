#!/bin/sh
# usage: scheduled_post.sh LABEL VIDEO CAPTION_FILE THUMB_MS
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
# Verifies the Raptors still play Milwaukee on Fri (ESPN), publishes a regular reel, then unloads its own launchd job.
cd /Users/ryanhelou/Developer/8bitraptors || exit 1
LOG=data/logs/$1.log
echo "== $(date)" >> $LOG
OK=$(/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -I -c "
import json,urllib.request
d=json.load(urllib.request.urlopen('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/28/schedule',timeout=20))
nxt=[e for e in d['events'] if e['competitions'][0]['status']['type']['state']=='pre']
print('yes' if nxt and 'Milwaukee' in nxt[0]['name'] else 'no')" 2>>$LOG)
if [ "$OK" != "yes" ]; then echo "SKIPPED: next game is not at Milwaukee any more (or ESPN unreachable)" >> $LOG; launchctl bootout gui/$(id -u)/com.8bitraptors.$1 2>/dev/null; exit 0; fi
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -I bin/ig_publish.py "$2" "$(cat $3)" --publish --thumb-offset $4 >> $LOG 2>&1
launchctl bootout gui/$(id -u)/com.8bitraptors.$1 2>/dev/null
