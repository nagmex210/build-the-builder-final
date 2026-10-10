# Idea bank: lessons from a working doc → program pipeline (ICD PDF → device UI)

A previous project turned arbitrary technical PDFs into working programs with a local LLM. These are the
mechanisms that made it reliable. Each is brief-agnostic. Pick from here when it fits your family.

1. **The LLM emits data, a fixed compiler emits the program.** The model fills a schema (rules, values,
   codes, formulas); hand-written code turns the schema into the workflow. No free-form workflow writing.
   Here: a rule-spec JSON (identity steps, products, deadline formulas, floors, outcome table, mandatory
   sentences) → `builder/compile.py` → workflow JSON. Claude only fixes what the compiler cannot express.
   Faster builds, same skeleton every time, every value traceable to the brief.
2. **Make illegal values unrepresentable.** Constrain spec fields to closed sets read at build time: tool
   names and field enums from the tool API file, outcome/reason codes from the brief's code list. A model
   cannot emit a code that is not in the list; a validator rejects one that slipped through.
3. **Deterministic gate, LLM only routes.** A code validator decides pass/fail (unknown codes, unknown tool
   fields, unreachable nodes, a close path with no close tool, a date rule with no code step). The LLM may
   only propose fixes; it never declares the workflow valid.
4. **Independent oracle (anti-circularity).** A *separate* call, with a different prompt, transcribes the
   brief's own worked examples and stated facts (e.g. "a product 10 days overdue has deadline X", a code
   table row, a holiday). The compiled code steps are executed on those inputs and compared. The test must
   not come from the same extraction that produced the spec, or a hallucination checks itself.
   Transcribe, never compute: the expected value must be one the brief states.
5. **Retrievability gate.** Every concrete value in the workflow (amount, percent, day count, code,
   mandatory sentence, holiday date) must be findable in the brief text (exact, or normalised: numbers in
   words, date formats). A value the brief never states is a hallucination → flag and re-extract.
6. **Evidence ownership.** A fact gates only the thing it belongs to. A memo override applies to the rule it
   names; a rule for one product type is not applied to another. Track `source` (file + clause) per rule.
7. **Repair as an EDIT with the previous output.** On a gate failure, send the specific failures plus the
   model's own previous JSON: "return the complete spec, change ONLY these fields". Regenerating blind
   makes the model revert last round's fix. Cap 3 rounds; stop on a repeat.
8. **Coverage anti-gaming.** A repair must not drop coverage: every numbered brief rule must still map to a
   workflow element after the fix. Removing a rule to pass a check is rejected; restore the last good state.
9. **Ship the best attempt.** When repair does not converge, ship the attempt with the fewest gate failures,
   not the last one (the last is often worse than one passed through).
10. **One section per call.** A scout call lists the brief's sections/rules with anchors; code slices the
    text; each slice is extracted in its own small parallel call. Smaller contexts, parallel, fewer
    cross-section mix-ups (worker 1's single-pass spec was 60-77 KB and took 7-9 min).
11. **Jury on the few values that decide cases.** Sample 3 extractions of deadlines, floors, overrides and
    the outcome table; take the majority; disagreement → re-read that clause.
12. **Log every model call and every gate result** in the trace (already required by the event rules).
