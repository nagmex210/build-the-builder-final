# Owner notes for the next merger (read before step 1; delete a note once handled)

## b8: candidate carry-over from the aborted b7 merge: commit cedb5ea on merge/b7
"tool names normalised in the calc spec (the extractor answered '/get_account': no guard installed)".
FIRST CONFIRM IT IS REAL on the champion (main, before your merge):
1. Look in the champion's recent build traces/logs (runs/b6/merge/build-*.log, runs/traces/main-*.jsonl, runs/b8/w*/)
   for calc-spec tool names that do not match the tool API's names exactly (leading '/', other case, path form).
2. Run the champion's date/amount extraction alone 3 times each on A, rA, rB and brief C (clean + raw) and count
   runs where a tool name does not match, and whether the guard/hook for that tool is then missing from the
   built workflow (count installed guards per build).
3. Write the counts in the journal. If it never happens: skip the fix and say so.
If it IS real: cherry-pick only cedb5ea onto your merge (not the rest of merge/b7), rebuild, confirm the guards
are installed on every build, and keep it under the normal accept rule.
