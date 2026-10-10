#!/bin/bash
# 5 workers in parallel (one git worktree each) + 1 merger, batch after batch, until the freeze.
# Full permissions for the agents were explicitly approved by the repo owner (2026-10-10).
# On the GPU box, as ubuntu, inside tmux:
#   tmux new -d -s btb "bash /home/ubuntu/btb/repo/btb/batch.sh"
# Watch: tail -f /home/ubuntu/btb/batch.log     Stop: tmux kill-session -t btb
# Credentials come from SSM Parameter Store at start; nothing is stored on disk.
set -u
BASE=/home/ubuntu/btb
R=$BASE/repo
LOG=$BASE/batch.log
FREEZE=$(date -d "2026-10-11 16:30 UTC" +%s)
WORKER_MIN=80
MERGER_MIN=100
MODEL=claude-opus-5-5
export PATH="$HOME/.local/bin:$PATH" GIT_TERMINAL_PROMPT=0
source "$BASE/venv/bin/activate"
ssm() { aws ssm get-parameter --region eu-central-1 --name "$1" --with-decryption --query Parameter.Value --output text; }
export CLAUDE_CODE_OAUTH_TOKEN; CLAUDE_CODE_OAUTH_TOKEN=$(ssm /video-iq/claude_token) || { echo "no claude token" >> "$LOG"; exit 1; }
export FREYA_API_KEY; FREYA_API_KEY=$(ssm /btb/freya_api_key) || { echo "no freya key" >> "$LOG"; exit 1; }
export FREYA_BANK_TEAM_KEY; FREYA_BANK_TEAM_KEY=$(ssm /btb/bank_team_key) || { echo "no team key" >> "$LOG"; exit 1; }
export AZURE_KEY; AZURE_KEY=$(ssm /btb/azure_key) || { echo "no azure key" >> "$LOG"; exit 1; }
export FREYA_API_URL=https://staging-app.freyavoice.ai

DEFAULT_FAMILIES="brief extraction: turn any brief (clean or raw mail+memo+code list) into a structured rule spec before building
workflow structure and routing: nodes per call stage, routes on tool results and extracted variables
code steps: dates, business days, holidays, deadlines, amount floors computed in code nodes instead of by the model
honesty and tool-call robustness: failed tools, retries, never claiming a record that failed, ids from get_account
conversation robustness: numbers in two parts, corrections, dates and amounts in words, questions back, small talk"


# Usage limit: a claude run that hit the subscription's session limit exits at once. Without this the loop spun
# through 22 empty batches in 2 minutes (2026-10-10 22:17). Sleep until the printed reset time, then redo the step.
hit_limit() { grep -q "hit your session limit" "$@" 2>/dev/null; }
sleep_until_reset() {
  t=$(cat "$@" 2>/dev/null | grep -o "resets [0-9:apm]* (UTC)" | tail -1 | sed 's/resets //; s/ (UTC)//')
  s=$(date -u -d "$t" +%s 2>/dev/null) || s=$(( $(date +%s) + 1800 ))
  [ "$s" -lt "$(date +%s)" ] && s=$(( s + 86400 ))
  echo "[$(date -Is)] session limit: sleeping until $(date -u -d @$((s + 120)) +%H:%M) UTC" >> "$LOG"
  sleep $(( s + 120 - $(date +%s) ))
}

cd "$R" || exit 1
b=$(cat runs/batch_no 2>/dev/null || echo 0)
while [ "$(date +%s)" -lt "$FREEZE" ]; do
  t0=$(date +%s)
  if [ -n "${START_AT_MERGE:-}" ]; then
    unset START_AT_MERGE; echo "[$(date -Is)] batch $b: resuming at the merger" >> "$LOG"
  else
  b=$((b + 1)); echo "$b" > runs/batch_no; mkdir -p "runs/b$b"
  git -C "$R" checkout -q main
  FAMS=$( [ -s runs/next_families.txt ] && cat runs/next_families.txt || echo "$DEFAULT_FAMILIES" )
  echo "[$(date -Is)] batch $b start" >> "$LOG"
  for n in 1 2 3 4 5; do
    fam=$(echo "$FAMS" | sed -n "${n}p"); [ -z "$fam" ] && fam=$(echo "$DEFAULT_FAMILIES" | sed -n "${n}p")
    wt="$BASE/wt$n"
    [ -d "$wt" ] || git -C "$R" worktree add -q -f "$wt" -b "idea/b$b-$n" main
    git -C "$wt" checkout -q -B "idea/b$b-$n" main && git -C "$wt" clean -qfd -e .freya-agents.json -e .personas.json
    P="You are WORKER $n of batch b$b. Read btb/program.md (section WORKER) and follow it exactly. Your worktree is $wt on branch idea/b$b-$n. Your slots are w$n-A, w$n-B, w$n-rA, w$n-rB. Your idea family: $fam. Write your report to runs/b$b/w$n.md and commit it on your branch. Hard limit $WORKER_MIN minutes from now ($(date -u -d "+$WORKER_MIN min" +%H:%M) UTC). Never ask questions."
    ( cd "$wt" && timeout "${WORKER_MIN}m" claude -p --model "$MODEL" --dangerously-skip-permissions "$P" > "$R/runs/b$b/w$n.log" 2>&1 ) &
  done
  wait
  # workers cut by the usage limit: wait for the reset, resume them in their own worktree (no reset of the branch)
  while hit_limit "$R"/runs/b$b/w*.log; do
    sleep_until_reset "$R"/runs/b$b/w*.log
    for n in 1 2 3 4 5; do
      lg="$R/runs/b$b/w$n.log"; hit_limit "$lg" || continue
      mv "$lg" "$lg.limit.$(date +%H%M)"
      P="You are WORKER $n of batch b$b, RESUMED after a usage limit cut your previous session. Read btb/program.md (section WORKER). Your worktree $BASE/wt$n on branch idea/b$b-$n already holds your earlier work (git log, runs/b$b/): continue from there, do not start over. Slots w$n-A, w$n-B, w$n-rA, w$n-rB. Write your report to runs/b$b/w$n.md and commit it. Hard limit $WORKER_MIN minutes from now ($(date -u -d "+$WORKER_MIN min" +%H:%M) UTC). Never ask questions."
      ( cd "$BASE/wt$n" && timeout "${WORKER_MIN}m" claude -p --model "$MODEL" --dangerously-skip-permissions "$P" > "$lg" 2>&1 ) &
    done
    wait
  done
  echo "[$(date -Is)] batch $b workers done" >> "$LOG"
  fi
  [ "$(date +%s)" -ge "$FREEZE" ] && break
  P="You are the MERGER for batch b$b. Read btb/program.md (section MERGER) and follow it exactly. The worker branches are idea/b$b-1 .. idea/b$b-5 (reports at runs/b$b/w<N>.md on each branch: git show idea/b$b-<N>:runs/b$b/w<N>.md). You work in $R on main. Your slots are main-A, main-B, main-rA, main-rB. Commit and push main when done, and write runs/next_families.txt. Hard limit $MERGER_MIN minutes. Freeze is Sun 11 Oct 16:30 UTC. Never ask questions."
  [ -n "${MERGE_NOTE:-}" ] && { P="$P $MERGE_NOTE"; unset MERGE_NOTE; }
  ML="runs/b$b/merger.log"
  ( cd "$R" && timeout "${MERGER_MIN}m" claude -p --model "$MODEL" --dangerously-skip-permissions "$P" > "$ML" 2>&1 )
  while hit_limit "$ML"; do
    sleep_until_reset "$ML"; mv "$ML" "$ML.limit.$(date +%H%M)"
    P2="$P RESUMED after a usage limit cut your previous session: runs/b$b/ (merge/, official*, merger.log.limit.*) and branch merge/b$b hold what you already did. Continue from there; do not redo finished steps."
    ( cd "$R" && timeout "${MERGER_MIN}m" claude -p --model "$MODEL" --dangerously-skip-permissions "$P2" > "$ML" 2>&1 )
  done
  git -C "$R" checkout -q main
  echo "[$(date -Is)] batch $b merged: $(tail -1 results.tsv 2>/dev/null | cut -c1-200)" >> "$LOG"
  # runaway guard: a whole batch in under 10 minutes means something is broken; do not spin
  [ $(( $(date +%s) - t0 )) -lt 600 ] && { echo "[$(date -Is)] batch $b took under 10 min: pausing 30 min" >> "$LOG"; sleep 1800; }
done
echo "[$(date -Is)] freeze reached" >> "$LOG"
