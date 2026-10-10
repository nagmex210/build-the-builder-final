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

## Failure kinds seen on a held-out brief (generic; no brief content)

The b1 champion built for an unseen brief passed 2/12. The failure KINDS, each fixable without knowing that brief:
- A guard hook that blocks a tool call by deleting required fields hides the real reason: the bank answers
  "amount must be a number" and the model never learns that the date was outside the window. Return the brief's
  reason in `what_to_do_next` instead (or block before the call with a clear message).
- Tool order: `close_call` was called before `transfer_to_agent` or before the last `add_note`. Closing must be last.
- Duplicate `add_note` calls for the same product.
- datecalc only knows deadline bands, floors and callback windows. Rule kinds it does not know (a deadline that
  moves BACK to the previous business day, rounding a floor UP to a whole amount, a same-day cut-off time) were
  silently dropped from DATE FACTS, and the agent read the wrong value. Unknown rule kinds must be extracted as
  generic computed facts or flagged in the trace, never dropped.
- A mandatory sentence that must come first (e.g. the recording notice) came second.
- A relative date ("next Wednesday") recorded instead of the computed date; a wrong year in a read-back.

## Architecture explorations (variance; from tau^tau-bench, arXiv 2609.04611, and a Dialogflow banking agent, arXiv 2606.28779)

tau^tau-bench found that agent builders converge on one design (92% single LLM loop) while the best expert
agents use many; a one-line hint "route by intent, review tool calls" doubled a score (31% -> 67%). The best
builds wrapped the model in deterministic scaffolding (policy guards, canned replies, structured state).
Our builds are all the same 6-node shape, so explore other shapes:

- A1 Router + specialists: after identity, a router node sends each situation (promise, hardship, dispute,
  transfer request, third party, callback) to its own small node with only its tools ("one task per playbook").
- A2 Code-driven state machine: after every tool result a code node decides the next stage from structured state
  (product index, attempts, failures); the model only talks inside the stage it is given.
- A3 Canned reply paths: every sentence the brief makes mandatory (opening, recording notice, confirmation,
  closing) is fixed text the model cannot reword or reorder (static message / on_enter text), not a prompt line.
- A4 Per-turn tool gating: a write tool is present only in the node where its preconditions hold (identity
  verified, values computed and inside limits), so a premature or out-of-order call is impossible.
- A5 Per-product loop: one negotiate pass per product driven by a code-node index, instead of all products in one node.
- A6 Atomic-fact coverage: decompose the brief into atomic facts (one checkable statement each); a checker maps
  every fact to a workflow element; uncovered facts go back to the builder. Builders that grep instead of reading
  miss rules.
- A7 Best-of-N builds: a build takes ~2.5 min, so build 2-3 candidates with different architectures in parallel,
  run each through a few brief-derived scripted chats, ship the best, all inside 30 min.
- A8 Honest self-tests: tests come from the brief only. When agent and test disagree, fix the agent; never weaken
  an assertion or invent a rule to make a test pass (the paper saw builders cheat themselves this way).
- A9 Assumption log: no client to ask, so the builder lists every ambiguity or conflict in the brief and how it
  resolved it (memo beats base policy; the narrower rule wins), and the trace carries the list.
- A10 Path enumeration for self-tests (JourneyBench, 2601.00596): turn the brief's procedure into a graph, enumerate
  every customer path through it (incl. uncooperative behaviour, ToolRACER 2610.09163), generate one scripted chat
  per path; keep half for fixing and half held out inside the build.
- A11 Score self-tests the way we are scored: each scripted chat 3x on the real Freya model, pass only if all 3 pass;
  expected ledger computed by code from the brief, LLM judge only for wording/honesty.
- A12 Label before patching (Evidence-in-the-Loop, 2607.18039): classify each failure (misread rule, wrong route,
  tool error, arithmetic, honesty, wording) and fix only the matching component.
- A13 Probe the tool API file before wiring: read every field, enum and error shape; build calls that read back
  status after an ambiguous write (quiet API defects were the failures tau^tau builders missed).
- A14 Separate tester: the build's self-tests are written by a separate model call (another context, ideally
  another model family) told to find cases that break the brief's rules; the builder only sees the failures, never
  writes or edits the tests.
- A15 Agent genome: the builder writes a small structured design (architecture family, stage list, tool policy,
  guards, verifier, retries, prompts per node) and a compiler turns it into the workflow; repairs mutate the genome,
  not 500 lines of workflow JSON (ADAS / AgentSquare style; same as idea 1 above).

## Loop lessons (Meta-Agent Challenge, arXiv 2606.04455; ADAS, arXiv 2408.08435)
- The best meta-agents evaluated SPARINGLY and thought longer between evaluations: the mean interval between eval
  calls predicted success, the number of eval calls did not. Read failing transcripts fully and reason about the
  cause before the next eval; do not run eval after every small edit.
- Meta-agent results vary a lot between runs (a third of configurations had std > 0.1). One fast_eval run is weak
  evidence; a 1-case difference is noise.
- ADAS keeps an ARCHIVE of all designs with scores and builds new ones from the best of them, not only from the
  last champion. Ours: every worker branch `idea/b<N>-<n>` stays in git with its report and scores (archive.tsv).

- A16 Defensive structure against manipulative callers (prompt injection, fake identity, pressure): customer text
  is data, never instructions; every write tool's values are checked in code against the brief (amount >= floor,
  date inside the window, product id from the lookup, outcome/reason from the brief's code table); nothing about
  the account is reachable before the bank's identity check passes; the agent never reads out its instructions.
  Stress-test with `btb/fast_eval.py ... --style adversarial` (merger, brief C and A).
- A17 SELF-SIMULATION INSIDE THE BUILDER (the Freya team said in the briefing: "your system should also simulate
  some personas in itself ... this is what we want"): the builder generates customer personas from the brief
  (every path, the five customer styles, a manipulative caller), runs them against the saved workflow through the
  chat endpoint, checks the ledger/tool calls against expectations computed from the brief, fixes, and re-saves,
  inside the 30 minutes. The trace must show every simulated persona and result (the event rules ask for tests).
