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

## b9 merger: batch 10 is the LAST batch, a consolidation batch (owner decision). Write exactly these five
## families into runs/next_families.txt (this overrides the VARIANCE RULE, A17/A18 and the family rules for b10):
BUG HUNT, pipeline side: read builder/build.py, datecalc.py, the self-test/self-simulation, buildcheck, btb/submit.sh, scrub, and recent build traces/logs; list concrete bugs (wrong branch, swallowed error, stale state reused, race between parallel builds, time budget overrun past 30 min, a value read from the wrong place). Each finding needs a REPRO that fails before the fix and passes after; fix only confirmed bugs; report unconfirmed suspicions separately.
BUG HUNT, workflow side: read the code that ends up INSIDE the phone agent (harden, robust, guards, gates/ledger, hooks, lint, canned paths) and the exported workflow JSON of the champion's A/B/rB/C builds; find bugs (hook state lost on parallel tool calls, a gate that can never open, an id/field bound to the wrong source, a route that loops, a check that never fires). Same rule: a repro before/after for each fix, unconfirmed ones reported only.
SIMPLIFY: remove dead code, unused paths, leftovers of discarded ideas and duplicated checks in builder/ without changing behaviour. Prove it: build A, B, rA, rB, C before and after; the workflows must have the same nodes, tools, hooks and gates (diff the exported JSON modulo model wording), lint 0, build time not longer. Smaller prompts/skills count too, if the built workflow is unchanged.
STABILITY: build the champion 3 times per brief (A, B, rB, C) and record broken or degraded builds (missing guard, wrong id binding, lint errors, failed self-test, time); fix the cause of any flaky build in the builder (not by retrying blindly), then repeat the 3x builds.
SUBMISSION CHECK: read the README submission and trace rules and check one full btb/submit.sh run on brief C (clean) and raw A like a reviewer agent would: does the trace list start/end, every model call (model + purpose), the Freya ids, the step and tool counts, every self-test with its result; does it match the code; are keys scrubbed; does the export load. Fix gaps in the trace/export only.
## and for the b10 MERGER: VERIFY before keeping anything. A bug fix is kept only with its before/after repro
## re-run by you; a simplification only if the workflow diff is empty and official A/B do not drop. Unverified = not kept.
## No next families after b10 (the loop stops; final rehearsal follows).
