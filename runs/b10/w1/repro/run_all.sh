#!/usr/bin/env bash
# Every repro against this branch (must pass) and against main's builder (must fail). Run from the kit root.
set -u
D="$(cd "$(dirname "$0")" && pwd)"; OLD=$(mktemp -d); git archive main | tar -x -C "$OLD"
for f in "$D"/[brs]*.py; do
  case "$(basename "$f")" in r3_*) continue;; esac          # r3 = unconfirmed-as-bug (brief-dependent), not fixed
  python3 "$f" >/dev/null 2>&1 && new=pass || new=FAIL
  KIT="$OLD" python3 "$f" >/dev/null 2>&1 && old=pass || old=FAIL
  printf "%-45s main: %-4s  branch: %s\n" "$(basename "$f")" "$old" "$new"
done
rm -rf "$OLD"
