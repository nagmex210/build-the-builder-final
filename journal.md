# Journal

Baseline: builder/ = kit example builder (Claude Agent SDK + build-phone-agent skill), no practice-case test inside the builder. Example agent (examples/base-agent.json): fast_eval A 0/10 (2026-10-10).

## b1 merge (2026-10-10, merger)

Platform: the workers' evals ran during a Freya outage from 13:37 to about 14:28 UTC (chat 503/504/500 errors and the snekbox hook sandbox down), so the worker scores (w1 3/26, w2 2, w3 0, w4 0, w5 about 3) are mostly noise. The merge was measured after 14:45, when the platform was healthy.

Workers:
- w1 brief extraction (`builder/extract.py`): an Azure extract+verify pass that writes a structured rule spec, memo overrides applied. Accurate, but adds 7-9 min (60-77 KB spec), and fast 3/26 with no visible gain. **Not wired in.** The file is kept for a later low-effort / single-pass try. Its prompt rule "no run_cases.py, no other slots' files" **was kept** (inner Claude really did run the official scorer in w1 and w5).
- w2 routing recipe (`routing.md`) + structural lint (`builder/lint_workflow.py`). **Kept.** Builds are uniform: setup code → opening → identity → (load_account) → negotiate → hang_up.
- w3 datecalc (`builder/datecalc.py`): an 8 s Azure extraction of the calendar/amount spec, generated code node + account post-hook with DATE FACTS, tested locally. **Kept.**
- w4 harden (`builder/harden.py`, `builder/save.py`): FAILED/SUCCESS `tool_outcome`, id repair, template repair, `maxRetries 0` on writes. **Kept.**
- w5 customer-speech block + INTENT_GUARD on classification fields. **Kept**, moved into `builder/robust.py` and applied on every save (`save.py`), not only after the build.
- No worker hard-coded anything from brief A or B: grep and diff review found no dates, holidays, product types, codes or amounts in builder code or prompts. Nothing was rejected for cheating.

Merger changes:
- `build.py`: one pipeline. datecalc → Claude (hard budget `BUILD_AGENT_BUDGET_S`, default 1260 s, via asyncio.wait_for; the prompt says "save early") → final deterministic pass (harden + robustify + save + lint written to the trace).
- **Bug found and fixed in the merge:** the first merged builds of A and B left model-filled api_call body leaves without a `default`. The platform drops such fields, so `verify_identity` sent only `customer_id` and every B call looped on identity (fast B 0/3, nothing recorded). `harden.py` now gives every body leaf without a default `"{{<field>}}"`, the lint reports it as an ERROR, and the skill says so. rA/rB happened to use `{{field}}` defaults, which is why rA still got 1/10 before the fix.
- Build time: **125-146 s** per build (datecalc about 8 s + Claude about 2 min, 14-16 turns). Well inside the 30 min limit.

Measured (fast_eval --reps 2 --style random, after the fix): A 3/10 (PUB-03, 05, 08), B 0/3, raw-A 1/10 (PUB-05), raw-B 0/3 = **4/26**. Before the fix: B 0/3, raw-A 1/10, raw-B 0/3 (A not finished).

Failures left (read from transcripts):
- Multi-product (B, raw-B): the model invents product ids (`credit_card_2288`) on the first create_promise, gets `unknown product_id` and then retries with the right ids. The ledger ends right, but the calls are duplicated and the judge fails them. The id repair only fires when there is a single candidate.
- PUB-02 callback: our judge says the "next business day" counts from the real clock (10 Oct), not `now` (14 Oct). Partly judge noise.
- PUB-07: a holiday date gets moved to the deadline instead of the next business day (date rule, even though DATE FACTS has the calendar). PUB-09: no restructuring transfer. PUB-10: our judge counts "this call is recorded" in the opening as a false "recorded" claim (judge noise, the brief requires that sentence).
- (H) A pre_process_code guard on create_promise / schedule_callback against DATE FACTS (date is a business day, <= deadline; amount >= floor) would fix PUB-07/PUB-04-type failures in code.
- (H) Product ids: the account hook could add a short `id_list` line, and the pre-hook could map an invented id to a known one by product type or last digits, only when exactly one matches.
- (H) Fix our judge in btb/fast_eval.py: give it `now` and the brief's mandatory sentences, so that "this call is recorded" and calendar math stop costing cases. This is harness, not builder, so it is no tuning on brief wording.
- **Official scorer** (tools/run_cases.py --reps 2): **A 8/10** (fails PUB-06: floor offered twice; PUB-07: the holiday date got pushed to the deadline 2 Nov in one rep), **B 2/3** (PUB-12 1/2: 153 recorded instead of 510, a note missing for p3, an extra attempt on the early-band car loan). This is the first champion. **Kept** on main.
- Note: our fast_eval (4/26) is much stricter than the official scorer (10/13 on A+B). Our judge's false "recorded" and real-clock date objections explain part of the gap. Read fast scores as relative only.
- Next batch families: runs/next_families.txt (code-step guards, multi-product, mandatory wording + retrievability gate, self-test inside the build, gated sectioned extraction). Build time is now about 2.5 min, so a self-test inside the 30-minute limit is affordable.
