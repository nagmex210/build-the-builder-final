# Brief C (held-out) — first measurement of the builder

Date: 2026-10-10, builder = branch `harness/brief-c` at c74baa9 (= main's builder, untouched).
Brief C is HELD-OUT: merger-only check, never tune `builder/` on it (see `btb/brief_c/README.md`).

## Build

`python3 builder/build.py --slot c-test --tools btb/brief_c/openapi-c.json btb/brief_c/brief-c.md`

- **Build time: 3 min 9 s** wall (Claude part 166 s, 17 turns). Trace `runs/traces/c-test-20261010-173101.jsonl`, log `btb/brief_c/build.log`.
- Result: workflow `474ccf0d-3045-4ea7-9c20-5ccdca928ad6`, agent `7ff83cbb-40cd-427a-b899-2dd5383892bb`, saved twice (version 2), lint 0 errors / 0 warnings.
  Freya chat worked (no 402): the builder ran two live chat turns itself.
- datecalc extraction of C was mostly right: calendar-day deadlines by kind, 7 days at arrears >= 1,000, attempts by
  arrears size, Sun-Thu business days + the 5 holidays, callback window (2 business days, 09:00-17:30),
  "next/this <weekday>" = nearest upcoming. **Missed:** "deadline moves BACK to the previous business day" (its
  schema has no roll direction; its test print showed a personal-loan deadline on a Saturday — the Claude step
  patched it in the account hook, but the DATE FACTS text still shows the unpatched deadline) and "overdraft floor =
  half the arrears **rounded up** to a whole unit" (schema has percent but no rounding: floor 193.75 instead of 194).

## Shape of the built workflow

5 nodes: `date_facts_setup` (code, start) -> `opening` (callback / wrong number / deceased / unclear; 2 tools) ->
`identity` (3 tools) -> `negotiate` (ONE conversation node for all accounts and all branches: get_account,
create_promise, add_note, transfer_to_agent, close_call; 57 KB of JSON) -> `hang_up` (end_call). No global nodes.
The Claude step wrote heavy `pre_process_code` guards with C's rules hard-coded from the brief (holidays,
15:00 cutoff, deadline, floor, 2,000 limit, part-2 window), which is legitimate (read from the brief at build time).

## fast_eval on C (--reps 1, plain style): **2 / 12**

`python3 btb/fast_eval.py 474ccf0d-... --cases btb/brief_c/cases-c.json --bank $(cat btb/brief_c/BANK_URL) --reps 1`
(172 s; full rows in `runs/brief_c/fast_eval_c-test.json`). PASS: C-04 (two wrong answers), C-06 (two-part plan
with holiday + weekend + odd cents). Every failure below was checked against the mock's ledger (`.state.json`):
the mock answered correctly each time; these are agent failures.

| case | what went wrong | rule(s) of C | likely builder cause (generic) |
|---|---|---|---|
| C-01 | "call is recorded" only in the 2nd sentence | 1 (exact first sentence) | mandatory sentence not forced verbatim |
| C-02 | said tomorrow = "2025-05-15" (wrong year), then booked 11-08 09:30 correctly | 7, 8 | opening node has no DATE FACTS / call_time anchoring |
| C-03 | "next Wednesday" (Monday call) recorded as the deadline 11-23, not 11-11 | 27 | model did not use the weekday lookup in DATE FACTS |
| C-05 | 5x create_promise without amount/date -> REFUSED; offered 193.75 and 100, no plan before floor | 30, 32 | **guard pops `amount`/`pay_date` on its own check failure, so the bank says "amount must be a number" and the model never learns the real reason**; floor rounding lost in extraction |
| C-07 | close_call after the first BREATHING_SPACE note, second note after close | 42, 50 | close before all per-account notes; no "notes done" gate |
| C-08 | asked postcode twice; loan noted REFUSED instead of offering the deadline; duplicate DISPUTED note | 26, 37, 50 | date-after-deadline -> treated as refusal; no dedupe of notes |
| C-09 | recorded 1500 + 500 correctly, then a 3rd create_promise, told customer it failed (dishonest), close, then calls after close | 34, 38 | guard-rejected call reported as failure; tools after close_call |
| C-10 | REFUSED note on A1 twice; persuasion offered 50.00 not floor 120; card date 12-10 not the customer's 12-07 | 30, 35, 50 | overdraft floor wrong (50%, no rounding / used other value); no note dedupe |
| C-11 | close_call(transferred/PLAN) BEFORE transfer_to_agent -> transfer rejected | 46 | **order: transfer must precede close** (same in C-12) |
| C-12 | close_call before transfer_to_agent | 44 | same as C-11 |

## Generic lessons for the builder (no C content needed to fix them)

1. A failed pre-process guard must not send a half-empty body: return the guard's reason to the model (or skip the
   call) instead of popping fields (C-05, C-09). This was introduced by "harden: no default = field dropped".
2. Enforce tool order: `transfer_to_agent` before `close_call`; all `add_note`s before `close_call`; nothing after it (C-07, C-11, C-12).
3. Notes: at most one per product (C-08, C-10).
4. datecalc schema: add deadline roll direction (forward/back) and rounding for computed floors (C, likely hidden briefs).
5. Exact mandatory sentences (first sentence) need verbatim enforcement (C-01).
6. Every node that may talk about dates (incl. the third-party/callback opening) needs the date anchors (C-02).

Not done: raw-C build (`brief-c-raw.md`), --reps 2 / --style random, official run_cases on C.
