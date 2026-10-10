#!/usr/bin/env bash
# (Re)start the brief C mock bank (tmux `bankc`) and its Cloudflare quick tunnel (tmux `tunnelc`), then write the
# new public URL into btb/brief_c/BANK_URL and the servers of btb/brief_c/openapi-c.json.
# A quick tunnel gets a NEW URL on every restart: rebuild the agent (or re-save its tool URLs) after running this.
#   bash btb/brief_c/start.sh [port]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8787}"
CF="${CLOUDFLARED:-/home/ubuntu/btb/bin/cloudflared}"
PY="${PYTHON:-python3}"
if [ ! -x "$CF" ]; then
  mkdir -p "$(dirname "$CF")"
  curl -sL -o "$CF" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x "$CF"
fi
tmux kill-session -t bankc 2>/dev/null || true
tmux kill-session -t tunnelc 2>/dev/null || true
: > "$DIR/bank.log"; : > "$DIR/tunnel.log"
tmux new-session -d -s bankc "cd '$DIR' && $PY mock_bank.py --port $PORT 2>&1 | tee -a '$DIR/bank.log'"
for i in $(seq 1 20); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.5; done
curl -sf "http://127.0.0.1:$PORT/health" || { echo "mock bank did not start, see $DIR/bank.log"; exit 1; }; echo
tmux new-session -d -s tunnelc "'$CF' tunnel --no-autoupdate --url http://localhost:$PORT 2>&1 | tee -a '$DIR/tunnel.log'"
URL=""
for i in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$DIR/tunnel.log" | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "$URL" ] || { echo "no tunnel URL, see $DIR/tunnel.log"; exit 1; }
echo "$URL" > "$DIR/BANK_URL"
$PY - "$DIR/openapi-c.json" "$URL" <<'PY'
import json, sys
p, url = sys.argv[1], sys.argv[2]
s = json.load(open(p)); s["servers"] = [{"url": url + "/v1"}]; json.dump(s, open(p, "w"), indent=1)
PY
for i in $(seq 1 30); do curl -sf -A brief-c "$URL/health" >/dev/null && break; sleep 2; done
echo "bank: $URL"; curl -s -A brief-c "$URL/health"; echo
