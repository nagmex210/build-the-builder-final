# Owner notes for the next merger (read before step 1; delete a note once handled)

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

## b9 merger: TRY the memory tool (owner request), on top of your merge, and REPORT it
"Once" limits on things that are only SPOKEN (sympathy sentence, support-team offer, any repeated offer) have no
tool behind them, so w4's entry counter cannot catch a repeat inside the same node visit (official PUB-05 run:
sympathy in two messages of one visit). Add a code-only tool inside the workflow (the code-only tool type idea/b8-1
found; never an outside URL), e.g. `mark_said(item)`: the agent calls it right after saying a once-limited line;
code adds the item to a call-wide variable, and every node prompt shows a MEMORY line rendered from it
("MEMORY (code-kept): sympathy USED; support team offered 1/1; lowest amount offered 1/1 for <product>"). The list
of once-limited items comes from the brief at build time (no brief A/B text in builder/). Combine with w4's entry
counter and floor flag (they cover entries and tool-backed offers).
Measure: official A (PUB-05, PUB-06) and raw-A, plus fast_eval --only PUB-05,PUB-06 --reps 3 with and without the
tool. Keep it under the normal accept rule. Either way, write a "Memory tool (way 2)" section in the journal and in
runs/b9/memory_tool.md: what was built, numbers with/without, kept or not, and why.
