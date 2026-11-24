#!/bin/zsh
# Daily backup of the whole project to the private repo ryan-helou/8bitraptors (2026-11-24). .gitignore keeps out
# secrets (.env), videos, renders, model weights and logs. Runs at the end of the morning chain.
cd "${0:A:h}/.." || exit 1
git add -A && git diff --cached --quiet || git commit -qm "daily backup $(date +%F)"
git pull -q --rebase --autostash && git push -q && echo "backup pushed"
