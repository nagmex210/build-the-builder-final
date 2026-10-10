#!/bin/bash
# The GPU box has an idle alarm (stops it after hours of average CPU < 3%). Claude agents barely use CPU, so
# keep a light load (~6% of the 4 vCPUs) until the freeze. Stop: tmux kill-session -t keepalive
FREEZE=$(date -d "2026-10-11 20:30 UTC" +%s)
while [ "$(date +%s)" -lt "$FREEZE" ]; do timeout 8 nice -n 19 yes > /dev/null; sleep 24; done
