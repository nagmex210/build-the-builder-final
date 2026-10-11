# Owner notes for the next merger (read before step 1; delete a note once handled)

## b10 = the LAST batch, a consolidation batch (owner decision); its five families were written to runs/next_families.txt by the b9 merger.
## and for the b10 MERGER: VERIFY before keeping anything. A bug fix is kept only with its before/after repro
## re-run by you; a simplification only if the workflow diff is empty and official A/B do not drop. Unverified = not kept.
## No next families after b10 (the loop stops; final rehearsal follows).


## Standing: the owner may append notes while you work. Re-read runs/merger_notes.md before each official run and before your final keep/discard decision.

## b10 merger: two extra workers (owner): idea/b10-6 (once.py once-only limits, from idea/b9-4) and idea/b10-7 (memory tool, from exp/memory-tool)
Both measure fixes for the last official A failures (PUB-05, PUB-06). Reports: runs/b10/w6.md and runs/b10/w7.md on their branches.
Take one ONLY if its first line says VERDICT: WORKS and you can re-run its PUB-05/PUB-06 with/without check yourself; otherwise leave it out and say why in the journal.
