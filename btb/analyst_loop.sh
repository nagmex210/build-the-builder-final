#!/bin/bash
# Standing analyst: after each batch's workers finish, analyse every new result and update btb/mechanisms.md on
# main (general rules only). Workers read it at start, the merger reads it before choosing next families.
#   tmux new -d -s analyst "bash /home/ubuntu/btb/repo/btb/analyst_loop.sh"
set -u
BASE=/home/ubuntu/btb; R=$BASE/repo; LOG=$BASE/batch.log
export PATH="$HOME/.local/bin:$PATH" CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
source "$BASE/venv/bin/activate"
ssm() { aws ssm get-parameter --region eu-central-1 --name "$1" --with-decryption --query Parameter.Value --output text; }
export CLAUDE_CODE_OAUTH_TOKEN=$(ssm /video-iq/claude_token) FREYA_API_KEY=$(ssm /btb/freya_api_key) FREYA_BANK_TEAM_KEY=$(ssm /btb/bank_team_key) AZURE_KEY=$(ssm /btb/azure_key) FREYA_API_URL=https://staging-app.freyavoice.ai
FREEZE=$(date -d "2026-10-11 16:30 UTC" +%s)
done_b=$(cat $BASE/analyst_done 2>/dev/null || echo 2)
while [ "$(date +%s)" -lt "$FREEZE" ]; do
  nb=$((done_b + 1))
  if ! grep -q "batch $nb workers done" $LOG; then sleep 120; continue; fi
  # wait for the one-off analyst (fix/cases) before the first standing run
  while pgrep -f "FAILURE-MECHANISM ANALYST for the Build" >/dev/null; do sleep 60; done
  echo "[$(date -Is)] analyst b$nb start" >> $LOG
  P="You are the STANDING ANALYST for batch b$nb. Read btb/program.md (section ANALYST) and follow it exactly. Workers of batch b$nb are on branches idea/b$nb-1..5 (reports: git show idea/b$nb-<N>:runs/b$nb/w<N>.md). The merger is working in the same repo right now: touch ONLY btb/mechanisms.md and runs/analyst/b$nb.md, commit only those paths (git commit -- <paths>; retry if index.lock exists), push. Hard limit 55 minutes. Never ask questions."
  ( cd "$R" && timeout 55m claude -p --model claude-opus-5-5 --dangerously-skip-permissions "$P" > "$BASE/analyst_b$nb.log" 2>&1 )
  echo "[$(date -Is)] analyst b$nb done" >> $LOG
  done_b=$nb; echo $done_b > $BASE/analyst_done
done
