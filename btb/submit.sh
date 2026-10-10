#!/usr/bin/env bash
# One submission run: build -> export -> scrub -> summary. Works from any cwd.
#
#   bash btb/submit.sh <brief.md> <tool_api.json> [name]
#
# name (default: the brief's file name) is the slot on Freya, so two runs on different briefs in parallel use
# distinct workflows, out/ files, traces and logs. Writes:
#   traces/<name>.log                  the printed build log = the submitted trace (scrubbed)
#   runs/traces/<name>-<time>.jsonl    the detailed machine trace (scrubbed)
#   submission/<name>.workflow.json    freya.export_workflow of the built phone agent (what gets scored)
set -uo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ $# -ge 2 ] || { echo "usage: bash btb/submit.sh <brief.md> <tool_api.json> [name]" >&2; exit 2; }
BRIEF="$(realpath "$1")"; TOOLS="$(realpath "$2")"
NAME="${3:-$(basename "${BRIEF%.*}")}"
[ -f "$BRIEF" ] && [ -f "$TOOLS" ] || { echo "brief or tool API file not found" >&2; exit 2; }

# Keys: use the environment, else the box's Parameter Store (same names as the workers' run scripts).
ssm() { aws ssm get-parameter --region eu-central-1 --name "$1" --with-decryption --query Parameter.Value --output text; }
[ -n "${FREYA_API_KEY:-}" ] || export FREYA_API_KEY="$(ssm /btb/freya_api_key)"
[ -n "${FREYA_BANK_TEAM_KEY:-}" ] || export FREYA_BANK_TEAM_KEY="$(ssm /btb/bank_team_key)"
[ -n "${AZURE_KEY:-}" ] || export AZURE_KEY="$(ssm /btb/azure_key)"
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || [ -n "${ANTHROPIC_API_KEY:-}" ] || export CLAUDE_CODE_OAUTH_TOKEN="$(ssm /video-iq/claude_token)"
export FREYA_API_URL="${FREYA_API_URL:-https://staging-app.freyavoice.ai}" CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
PY="${PYTHON:-python3}"
[ -x /home/ubuntu/btb/venv/bin/python3 ] && [ -z "${PYTHON:-}" ] && PY=/home/ubuntu/btb/venv/bin/python3

mkdir -p "$KIT/traces" "$KIT/submission"
LOG="$KIT/traces/$NAME.log"
EXPORT="$KIT/submission/$NAME.workflow.json"
rm -f "$EXPORT"
COMMIT="$(git -C "$KIT" rev-parse HEAD 2>/dev/null)"
T0=$(date +%s)
{
  echo "submit: brief=$BRIEF tools=$TOOLS name=$NAME"
  echo "submit: builder commit $COMMIT$(git -C "$KIT" diff --quiet HEAD 2>/dev/null || echo ' (+ uncommitted changes)')"
  echo "submit: command: python3 builder/build.py --slot $NAME $BRIEF $TOOLS"
} | tee "$LOG"
"$PY" -u "$KIT/builder/build.py" --slot "$NAME" "$BRIEF" "$TOOLS" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
T1=$(date +%s); SECS=$((T1 - T0))

LAST="$(grep '^{"workflow_id"' "$LOG" | tail -1)"
WF="$(echo "$LAST" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["workflow_id"])' 2>/dev/null)"
AG="$(echo "$LAST" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["agent_id"])' 2>/dev/null)"
JSONL="$(grep -o '^trace: .*' "$LOG" | head -1 | cut -c8-)"
# build.py exports already; export again if that failed (the file is what gets scored).
if [ -n "$WF" ] && ! "$PY" -c "import json,sys; json.load(open(sys.argv[1]))" "$EXPORT" 2>/dev/null; then
  (cd "$KIT" && "$PY" -c "import freya,sys; print('submit: exported', freya.export_workflow(sys.argv[1], sys.argv[2]))" "$WF" "$EXPORT") 2>&1 | tee -a "$LOG"
fi
EXPORT_OK=no
"$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['workflow_id']==sys.argv[2] and d['workflow'].get('nodes')" "$EXPORT" "$WF" 2>/dev/null && EXPORT_OK=yes
UNDER=no; [ "$SECS" -lt 1800 ] && UNDER=yes
{
  echo
  echo "=== SUBMISSION SUMMARY ($NAME) ==="
  echo "build exit code : $RC"
  echo "workflow_id     : ${WF:-NONE}"
  echo "agent_id        : ${AG:-NONE}"
  echo "export          : $EXPORT (loads as json with nodes: $EXPORT_OK)"
  echo "trace (log)     : $LOG"
  echo "trace (jsonl)   : ${JSONL:-NONE}"
  echo "builder commit  : $COMMIT"
  echo "build seconds   : $SECS (under 30 min: $UNDER)"
} | tee -a "$LOG"
# Scrub the logs. The export is only checked (below), never rewritten: a changed workflow is not what Freya holds.
"$PY" "$KIT/btb/scrub.py" "$LOG" ${JSONL:+"$JSONL"}
LEFT=0
for v in FREYA_API_KEY FREYA_API_KEY_2 AZURE_KEY FREYA_BANK_TEAM_KEY CLAUDE_CODE_OAUTH_TOKEN; do
  val="${!v:-}"; [ ${#val} -ge 8 ] || continue
  grep -qF -- "$val" "$LOG" ${JSONL:+"$JSONL"} "$EXPORT" 2>/dev/null && { echo "submit: WARNING $v still found in output files"; LEFT=1; }
done
[ "$LEFT" = 0 ] && echo "submit: key check: no key found in $LOG ${JSONL:-} $EXPORT"
[ "$RC" = 0 ] && [ "$EXPORT_OK" = yes ] && [ "$LEFT" = 0 ]
