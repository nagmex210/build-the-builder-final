# Owner notes for the next merger (read before step 1; delete a note once handled)

## b10 = the LAST batch, a consolidation batch (owner decision); its five families were written to runs/next_families.txt by the b9 merger.
## and for the b10 MERGER: VERIFY before keeping anything. A bug fix is kept only with its before/after repro
## re-run by you; a simplification only if the workflow diff is empty and official A/B do not drop. Unverified = not kept.
## No next families after b10 (the loop stops; final rehearsal follows).


## Standing: the owner may append notes while you work. Re-read runs/merger_notes.md before each official run and before your final keep/discard decision.

## b10 merger: two extra workers (owner): idea/b10-6 (once.py once-only limits, from idea/b9-4) and idea/b10-7 (memory tool, from exp/memory-tool)
Both measure fixes for the last official A failures (PUB-05, PUB-06). Reports: runs/b10/w6.md and runs/b10/w7.md on their branches.
Take one ONLY if its first line says VERDICT: WORKS and you can re-run its PUB-05/PUB-06 with/without check yourself; otherwise leave it out and say why in the journal.

## b10 merger: two BUG FIXES found by transcript analysis of the champion's official failures (owner approved). Verify, then keep only if they hold.
Evidence calls (champion b8, workspace 1): A run 2 PUB-05 84a52d0e-db0c-4d39-934c-40e370140d81; raw-A PUB-05 509373a0-7b44-4d6c-89ef-e1d5f0c30321.
FIX 1, silent account step: in the A build the account step (the node whose job is "call the account tool now") was a CONVERSATION node that spoke first ("Your identity is verified. How can I help you today?"); the customer disclosed hardship there before any router/situation logic, got sympathy too early, then the router (latest-message intent only) sent them to negotiate -> persuasion + a second sympathy. In the rA build the same step was an api_request node and never had this shape. Fix in the final pass (save.py/harden.py, brief-agnostic): a conversation node whose only tool is the account-lookup tool and whose only exit depends on that tool's result becomes a non-speaking api_request (or tool) node. Lint: no node before the router may speak after identity passes except to ask/confirm identity.
FIX 2, identity exit fallback: in the raw-A call both verify_identity results lacked the all-verified flag, so the identity -> account transition (flag == true) never fired: 60 messages stuck in identity, invented products. The workflow already keeps its own per-question ledger (verified_so_far / verified_items, identity memory). Fix (identity_gate.py + the transition): leave identity when the tool's call-wide flag is true OR the own ledger shows every required question passed (the required questions come from the brief at build time); never pass on an unreadable answer. Matters for Sunday: hidden tool APIs may rename or drop that field.
Verify each: fast_eval --only PUB-05 --reps 3 on A and raw-A before/after (count repeats in the transcripts), plus --only PUB-01,PUB-03,PUB-04,PUB-07,PUB-09,PUB-10 --reps 1 as a regression check (identity and routing paths). Keep only with the normal accept rule; write before/after numbers in the journal.
Do NOT take the memory tool (idea/b10-7) unless its verdict is WORKS; analysis of the only valid probe showed the agent ignoring the MEMORY line.
