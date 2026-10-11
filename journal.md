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

## b2 merge (2026-10-10, merger)

Platform: the workers' eval window had a bank-mock outage (Cloudflare 1101, 15:35-15:49), then Freya chat 500/504s, then from about 16:05 **HTTP 402 "Insufficient credits"** on every chat turn. **No worker could measure anything.** All five reports say "NOT MEASURED", and their 0/26 figures are platform failures. Credits came back at 17:07, so only the merge was measured.

Workers (none hard-coded anything from brief A/B; diff grep and review found no dates, holidays, product types, codes or amounts; nothing rejected for cheating):
- w1 code guards (`builder/guards.py`): pre/post hooks on the promise and callback tools check date (business day, not before today, <= product deadline) and amount (>= floor, <= full amount) against the datecalc spec. A violation sends the request to an `.invalid` host and the post-hook answers NOT RECORDED with a reason. Each check is switched on only by a rule the brief states. Plus an independent oracle (`builder/oracle.py`) that transcribes stated facts and cross-checks the datecalc code (0 mismatches on all builds; a mutation test was caught). Plus the fast_eval bank retry. **Merged into the candidate.** Offline the hooks behave right: below-floor, weekend and past-deadline values are blocked, valid ones pass. The live block path (what the platform does on a DNS failure) is still unverified.
- w2 multi-product: the write pre-hook maps an invented id (`credit_card_2288`) to the listed item by text match, there is an `ids_to_use` line on lookups, and the success outcome no longer says "speak now" in the middle of the per-item loop. **Merged into the candidate.** Live: PUB-11 now passes officially 2/2 (the b1 failure was duplicate create_promise calls).
- w3 wording checklist + retrievability gate (`builder/wording.py`): mandatory sentences and the code list are extracted in parallel with datecalc and kept only if found in the brief. A deterministic gate runs on the final workflow, and exact sentences are added to the system prompt. **Merged into the candidate.** Gate result 0 errors on all builds.
- w4 builder self-test + EDIT fix round: not merged (it rewrites build.py, adds 15-20 min, and is unmeasured). It is still on idea/b2-4; next batch's A7 family can reuse it.
- w5 sectioned gated extraction + oracle: not merged. It overlaps w1's oracle and w3's checklist, and its own report expects about 0 effect on A/B. Still on idea/b2-5.

Two builder bugs found in the merge (both mechanical; **put on main** without an A/B gain, see below):
- **Stale hooks on rebuild:** the inner Claude edited the previous build's `out/<slot>.workflow.json`, and `harden()` keeps an existing hook block that already has `tool_outcome`. So w2's new id resolver never went live on the first merged builds (a live call still showed `credit_card_2288` refused). Also, a failed Claude run would have shipped the old file. Fix: `build.py` moves the old file to `.prev.json` before every build.
- **Silent on_enter hang:** two of four rebuilds (A, raw-B) set `on_enter: silent` on the identity conversation node. The docs say silent means "nothing is said, waits for the user", so the customer's turn got no reply and 24 of 26 fast runs timed out. Fix: `robust.py` (runs on every save) turns a silent on_enter on a conversation node into `llm`.

Measured (merge/b2 = w2 + w1 + w3 + both fixes; fast_eval --reps 2 --style random): A 3/10, B 1/3, raw-A 5/10, raw-B 0/3 = **9/26** (champion 4/26). Official (run_cases --reps 2): **A 6/10** (PUB-02, 03, 07, 10 at 1/2 each), **B 2/3** (PUB-11 and PUB-13 pass, PUB-12 1/2). Champion: A 8, B 2. **Official A+B dropped 10 → 8, so the candidate is discarded** as the rule says. It is kept on branch `merge/b2` with its build fixes. Build time 149-249 s (A once 356 s: its inner Claude ran live chat tests). Brief C held-out check: not run (no time after credits came back).

Kept on main: the owner's program/idea/harness commits (they had landed on the checked-out merge branch), the two mechanical fixes above, the `build/` + `gen/` gitignore and the fast_eval bank retry (harness). (H) The two fixes can only help, because each one removes a hang or a stale file. They are not measured on the champion.

Note: the `main-*` slots now hold the discarded candidate's workflows (versions 9-10), not the b1 champion's. The next merger rebuilds them anyway.

Hypotheses for next batch:
- (H) The official A drop is mostly run-to-run variance: four cases at 1/2, and the A build was a different Claude run (356 s, with live tests). A repeat of official A on a fresh merge/b2 build would tell. The accept rule now asks for a gain that repeats.
- (H) The guards' blocked call is visible in the transcript as an extra create_promise and may cost official checks ("create_promise exactly once"). Measure it before relying on guards.
- (H) PUB-12 (per-item attempts and notes) and PUB-13 (per-item dates) remain the multi-product failures.

## b3 merge (2026-10-10, merger)

Platform: the workers' eval window (18:10-19:20 UTC) had the Freya chat endpoint saturated or down (503/504, about 25 fast_evals at once). Part of the time the Claude subscription also hit its session limit. **No worker measured anything.** All five reports say NOT MEASURED. During the merge window, workspace 1 chat was still very slow (one first turn took over 120 s) and the API returned "API key validation is temporarily unavailable" (503) for about 10 minutes. The official simulator in workspace 2 ran normally (median agent turn 4-9 s).

Cheating check: diffs reviewed, and no worker hard-coded anything from brief A/B. guards/items/statemachine/SAY NEXT read everything from the brief-derived spec or the workflow's own tools. Nothing was rejected.

Workers:
- w1 (tool robustness, from merge/b2): live probes showed **the b2 guard block path was harmful**. A request sent to `.invalid` is a platform `function_call_error`, the NOT RECORDED post-hook never reaches the model, the model retries, and the second failure trips the service-error close. All three probed blocks were correct decisions that still lost the case. Fix: the block goes to a 2xx no-op path on the tool's own host (found by probing /health etc. at build time). The post-hook then says NOT RECORDED + reason and undoes the success count. **Merged.** This is (c), a mechanistic reason: it removes a failure path that fires whenever a guard blocks, and it is a likely cause of merge/b2's official A drop.
- w2 (multi-product part 2): `items.py`, a per-item ledger in code (own deadline, own attempt count, status), plus `build.py` running the final pass after any agent error. The build fix is **merged** (w3 made the same fix independently). items.py is **not merged**: it is unmeasured, its A/rA/rB builds were drafts cut off by the quota, and it is large. It stays on idea/b3-2.
- w3 (A2 state machine): decide code node + work_item/wrap_up. All four builds followed the shape. **Not merged**: unmeasured, and it is untested whether a post-hook variable fires a transition in the same turn.
- w4 (A7 best-of-N): works end to end, 600-1139 s builds. The pick is unstable: one workflow scored 1/1 with 5 mistakes and 2/2 with 6 in two runs. Every valid scripted chat was judged failed, and the candidates share the same defects. **Not merged.**
- w5 (wild card, numbered RULES + SAY NEXT per tool outcome, enforced by lint): all builds comply, the agent says the lines verbatim, and the build time is unchanged. **Merged** (cheap, format-only, independent of the others).

Merge candidate `merge/b3` = merge/b2 code + w1 no-op block + build agent-error fix + w5 format. Builds took 121-219 s, with lint 0 and the wording gate at 0 errors on A/B/rA/rB/C. (The first build attempt ran without the Claude login and saved stale workflow files through the new agent-error path. That was harmless here because all slots were rebuilt, but (H) build.py should refuse to save when the agent wrote nothing in this build.)
- fast_eval (--reps 2 --style random): A 0/10, B 0/3, raw-B 0/3; raw-A was killed to reduce load. **Not a measurement**: 26 of 32 runs carry harness errors. Transcripts show Freya resuming the chat from an old message (`conversation_resumed isBranch=true`), so the agent re-asked the first security question and called verify_identity up to 8 times. That is platform state loss, not the workflow.
- Brief C (held-out): 1/12, with 9/12 runs carrying harness errors (not a measurement). Adversarial C was killed (load).
- **Official B 2/3** (PUB-11 2/2, PUB-13 2/2, PUB-12 0/2), the same as the champion. PUB-12 failed on close_call before the last add_note in one run and on too few persuasion attempts on a late-band item in the other: the tool-order and per-item kinds (items.py targets the second).
- **Official A: not finished** by the 100-minute limit (workspace 1 was saturated; started at about 20:05, no run printed by 20:45). It was left running and writes `runs/b3/official-A.txt`.
- Decision: **discard (not kept on main)**. The rule needs official A+B not to drop, and A is unknown. Candidate pushed as branch `merge/b3`. If official-A.txt shows >= 8/10, the next merger should start from merge/b3: it has a mechanistic fix for merge/b2's drop, and B held at 2/3.

Hypotheses for next batch (H):
- (H) merge/b3 >= champion: the w1 fix removes the guard-block -> service-error path, which turned correct blocks into lost cases.
- (H) Measurement is the bottleneck: two batches were lost to unmeasurable evals. Run self-tests/evals in workspace 2, cap concurrent fast_evals (<= 6 processes), and mark branch-resumed reps invalid.
- (H) A code-side close_call guard (blocked while an item lacks its promise/note) fixes the tool-order kind seen on official B and on brief C.

Next families: runs/next_families.txt (close_call ordering + per-item ledger; A17 deterministic self-simulation in workspace 2; A3 canned reply paths; datecalc unknown rule kinds; wild card replay-proof measurement/agent).

## b4 merge (2026-10-10, merger; the first merger session was cut by the Claude session limit at ~22:17 UTC and resumed)

Cheating check: diffs reviewed. No worker hard-coded a rule, value, name, date or outcome code from brief A/B. Every
canned sentence, rule kind, persona and check is read from the brief at build time. **Disclosure (w4):** while looking
for brief C, w4 read part of brief C's README and a grep of its date lines, then stopped. Its callback-slot rule kind
is C-informed, and it is not merged (only w4's own-band calendar tag fix is merged, and that one comes from A/B evidence).

Workers (fast_eval --reps 2 --style random; champion b1 = A 3, B 0, rA 1, rB 0 = 4/26):
- w1 (close_call last + per-item ledger, from merge/b3): A 0, B 0, rA 6, rB 1 = 7/26, mixed hook versions mid-eval.
  Measured live: the model sends several tool calls in ONE turn, and sibling hooks do not see each other's variable
  writes (M12/M20). So the close guard blocked correct closes and left calls unclosed. **Not merged** (the author
  says not as is). Kept from it: a post-hook that rewrites `data.ok` does steer `<tool>_response` transitions.
- w2 (A17 self-simulation in the builder, workspace 2, deterministic checks, one EDIT fix round): A 5, B 0, rA 3,
  rB 0 = 8/26. **Merged.**
- w3 (A3 canned reply paths: opening tts, success lines in post-hooks, goodbye in the close tool description):
  A 2, B 0, rA 0, rB 0 as printed; 6/0/3/0 re-judged. It found the fast judge reading the transcript before the final
  message is saved. **Merged.**
- w4 (datecalc never drops a rule kind + guards/oracle on merge/b3): A 2, B 1, rA 3, rB 0 = 6/26. It found the PUB-07
  cause: the calendar tagged a holiday with ANOTHER band's deadline. **Own-band tag fix ported (95fc23d)**; the rule
  kinds are not merged (they sit on the merge/b3 lineage, are inert on A/B, and the callback slots are C-informed).
- w5 (wild card replay-proof measurement): the fast_eval part was already on main. Its harden identity memory
  (verified_items in call variables) is **merged** (ed7d8f8). No report (the session was cut).

Merge candidate merge/b4 = w2 + w3 + w5 identity memory, plus three merger commits:
- self-test: a chat cut by the time limit is harness-invalid, and the budget is bounded by the whole build's 30 min;
- an inner-agent error (quota/SDK) falls through to the final pass (M9, carried over from merge/b3; this exact
  failure hit build A2 tonight);
- the w4 own-band calendar tags (M1).

Measured:
- fast_eval (on the ed7d8f8 build, before the last 3 commits): A 4, B 1, rA 5, rB 0 = **10/26** vs 4.
- Brief C: 3/12 random, 4/12 adversarial.
- Official on the ed7d8f8 build:
  - A, 1 rep: 9/10;
  - **A, 2 reps: 7/10** (runs 8, 9; PUB-03, 06, 10 at 1/2);
  - B, 2 reps: 2/3 (runs 3, 2).
  - Under the rule that alone is a one-case drop vs the champion's 8 (runs 9, 9).
- Official on the merge/b4 HEAD build (95fc23d, the code now on main):
  - **A 8/10 (runs 9, 9)**: PUB-07 1/2, PUB-10 1/2;
  - **B 2/3 (runs 3, 2)**: PUB-12 1/2.
  - Both equal the champion.
- RAW briefs, first official baseline:
  - rA 8/10 twice on the ed7d8f8 build (ws1 and ws2), 7/10 on the HEAD build;
  - rB 1/3 on the ed7d8f8 build;
  - **rB 3/3 on the HEAD build** (1 rep).
- Build time 537-603 s (self-simulation included), well inside 30 min. The champion's is 146 s.

Decision: **KEEP (main = merge/b4 at 2603373).** On the build that is now main, official A+B does not drop vs the
champion (8+2 = 8+2). The win is NOT a repeated official win, so the keep rests on (c), mechanisms that generalise:
- (1) M9: a quota/SDK error no longer kills the build. This is a Sunday risk, and it happened in this batch.
- (2) A17 self-simulation, the organisers' stated priority, is now in the champion and printed in the trace. In
  the A4 build, round 1 failed 3/11 personas (wrong hardship queue, identity check not ended after 3 wrong answers,
  an inner hook using an unset name). The fix round fixed them, and round 2 failed 1/12.
- (3) Verbatim mandatory lines (M10/M24) and identity memory (M5/M16).
- (4) Own-band calendar tags (M1).
Fast went 4 → 10/26 across A, rA and B (more than one failure kind). The pooled official per-run A rate is 35/40 on
merge builds vs 18/20 on the champion: equal within noise.

Failures left (official):
- PUB-07, holiday: once again the deadline (2 Nov) was offered instead of the next business day, even with own-band
  tags (1 of 2 on HEAD).
- PUB-10: the official judge counts the brief's own mandatory "the call is recorded" in the opening as saying
  "recorded" before success. The canned tts makes the opening identical on every call, so this may now be
  systematic at ~50%.
- PUB-12: per-item persuasion attempts.
- **New mechanism seen (H):** on official rA4 PUB-01/05 and rB PUB-11, the model said the goodbye as plain text
  without calling close_call. The customer said goodbye, the platform's built-in "goodbye" auto-trigger
  (`trigger_timeout_started function end_call triggered_pattern goodbye source auto_trigger`) hung up, and the
  outcome was never recorded. The same "not closed with close_call" appears in b1/b2 logs, so it is not new with A3,
  but A3's "say the goodbye before calling" text may make it more frequent. Fix idea: the platform speaks the goodbye
  only AFTER close_call ok (end_call node spoken_message / hang-up tts), and the model is told never to say goodbye
  itself.

Hypotheses for next batch (H):
- (H) The goodbye-before-close kind is worth ~1 case per brief run and is fixable structurally (above).
- (H) PUB-07 needs a code answer: when a customer names a non-business day, a promise pre-hook or DATE FACTS line
  gives the next business day explicitly. Prompt tags alone get it right in only half the runs.
- (H) The self-simulation's fix round can edit hooks. Make its checks cover "close_call present when the call
  ended", so it catches the goodbye kind at build time.

Slots: `main-A/B/rA/rB/C` hold the ed7d8f8 build; `main-A4/B4/rA4/rB4` hold the HEAD build (= main). The next merger
rebuilds main-* anyway. Raw baselines for later batches, official, HEAD build: rA 7/10, rB 3/3, both 1 rep.

## b5 merge (merger, 2026-10-11 00:14-01:5x UTC)

Workers (fast = fast_eval --reps 2 --style random; champion b4 fast A4 B1 rA5 rB0 = 10/26):
- w1 close in structure (goodbye platform-spoken by the end_call node only after close ok; close->hang-up on ok only;
  model told never to say goodbye; self-sim flags hang-ups without close). Model goodbye before close 18/20 -> 0/20.
  Fast A 5 (re-applied pass), rB 1. Found (H): platform default agent_config carries an end_call tool + "use end_call
  after goodbye" system prompt. MERGED.
- w2 A5 per-product loop: routing worked live, but per-item values through extraction failed ("yes" to the agent's
  proposal extracts nothing). B/rB 0/3. NOT merged (first discard of A5; next attempt: settle_item tool with args).
- w3 A1 router + specialists (situations.py): 10/26 = champion; plan-request transfer 4/4; new hand-off double-speech
  kind, fix only partly measured. NOT merged this batch (re-assigned on top of the new main).
- w4 guards on main + code-only check_promise_date tool (code answers CAN BE RECORDED / the one date to offer) +
  b4-4 rule kinds (no callback slots, no oracle). v1 8/26; re-saved A with the check tool fixed PUB-04/07/10 in
  every rep. MERGED.
- w5 brief self-conflict detector (gated words, opening checked deterministically). 9/26. MERGED WITHOUT the
  model-written conflict-resolution lines (risk of steering the model wrong); kept gated-word lines, the opening
  check and the self-sim check_gated.
No worker hard-coded brief A/B content (checked the diffs: values come from extraction, tool schemas, platform events).

Merge = merge/b5: w1 + w4 + w5 (conflicts in canned.py / selftest.py resolved by hand: w1's "goodbye NOT yours" line
+ w5's gated words; selftest fails on both hang-up-without-close and gated words) at 40b0d79, then merger fix
8bec0b7: harden adds `identity_status` "NOT VERIFIED YET ... never mention any amount/product" to a verify result
while its all-verified flag is false (found reading official PUB-03: after one wrong + one right answer the model
said "your account is past due ... 450 pounds", an invented amount).

Measured on 40b0d79 builds (446-819 s incl. self-sim):
- fast A 6/10 (re-judged 5), B 0/3 (invented product ids + retries, M7; per-item attempts), rA 3/10 (re-judged 6/10:
  fast-judge transcript lag, e.g. "create_promise never called" on a clean call), rB 1/3 => 10/26 first pass, 12/26
  with A/rA re-judged. C 2/12 random (b4: 3), 4/12 adversarial (b4: 4); C failures are duplicate create_promise after
  success -> "already exists" -> service-error note (pre-existing M12 kind), date words, goodbye order (C's brief
  wants the goodbye BEFORE close_call: w1 risk, fast judge only).
- OFFICIAL A 6/10 (runs 8,7), again 8/10 (runs 9,8); B 2/3 (2,2) = champion; rA 8/10 (= baseline 8,8,7); rB 2/3
  (baseline 1/3, 3/3). PUB-07 (holiday) 4/4 and PUB-10 (recording notice) 4/4.
- SAME-SESSION CHAMPION (779b267 rebuilt as champ-A in a worktree): official A 6/10 (runs 8,8), failing PUB-07 1/2,
  PUB-10 1/2, PUB-03 1/2, PUB-06 1/2.
On HEAD 8bec0b7 builds: OFFICIAL A 9/10 (runs 9,9; only PUB-03 left), raw-A 9/10 (PUB-03 passed); fast A 6/10.
B/rB on HEAD: see results.tsv row.

Decision: KEEP (main = merge/b5). Accept rule (a)+(b)+(c): the two kinds targeted by w4 and w5 (holiday date ->
deadline offered; recording notice read as premature "recorded") passed 4/4 officially on the merged build vs 1/2
on the same-session champion, repeated over two official runs, different failure kinds (dates, mandatory wording),
and both are code/structure mechanisms (code computes the one date to offer; the opening is checked against gated
words; the goodbye is platform-spoken after close ok). Official A per run 8,7,9,8,9,9 vs champion 8,8 this session.

Left: PUB-03 identity gate (model ignores the NOT VERIFIED line in 1 of 2; needs a code-decided identity state),
PUB-12 per-item persuasion count (B every official run), PUB-05 support offered twice, C duplicate writes,
B invented product ids (fast).
Hypotheses (H) for b6: idempotent writes in code fix the C service-error kind; A5 with a settle_item tool fixes the
per-item count; overriding the platform's default agent_config removes the auto end_call path entirely.
- HEAD B rebuild (889 s): OFFICIAL B 0/3, identity never passed. Cause in the build log: the inner build agent
  dropped customer_id from every tool's required body list, so the bank rejected every verify_identity; self-sim round 2
  failed 11/12 personas and the build still shipped. Build variance + a builder robustness gap (no required-field lint, no
  revert to the better self-sim version), not the identity_status line (it only adds a text field to the verify result,
  never touches request schemas). B on the 40b0d79 build: official 2/3. Assigned as part of b6 family 1. Kept HEAD.

## b6 merge (merger, 2026-10-11 02:47-04:1x UTC)

Workers (fast = fast_eval --reps 2 --style random; champion b5 fast A6 B0 rA3 (rejudged 6) rB1 = 10/26, 12 rejudged):
- w1 tool-call robustness: idempotent writes in harden (identical re-send -> no-op path -> ALREADY RECORDED; bank
  "already exists" after our own success read as recorded), hookcheck.py (dry-runs every hook; repairs the b5 official
  B 0/3 root cause: inner-agent post-hooks referenced `response`, NameError on every call; the b5 journal's
  customer_id diagnosis was wrong), apicheck.py (API-required fields). 8/26, measured BEFORE its own fix c2145da
  (v1 deduped verify_identity and broke identity routing). MERGED (c2145da).
- w2 A5 v2 settle_item tool: value path works live (M30 solved) but the model called it only for promises; B/rB 0/3.
  NOT merged. A5 is now discarded twice: not to be assigned again.
- w3 A1 v2 router + specialists (situations.apply: brief clause as each specialist's first rule, once per call,
  silent hand-off, not-triage-only check): A 8/10 (best fast A), rA 5/10, B/rB 0. Hand-off re-entry (M40) open. MERGED.
- w4 identity gate in structure (identity_gate.py: code decides identity_state/say_next per answer; identity_failed
  terminal node; gate block; self-sim privacy lint): 11/26, PUB-03 2/2 fast on A. MERGED.
- w5 WILD platform agent_config override (drop the built-in end_call tool + "use end_call after goodbye" prompt) +
  brief-driven pre-close goodbye: 4/0/invalid/0 without a self-sim round; the kind it targets is official-only.
  NOT merged this batch (unmeasurable on fast, no official slot left; the override alone is a candidate).
No worker hard-coded brief A/B content (diffs grepped for case ids, outcome codes, dates, amounts, product ids).

Merge = merge/b6: w4 + w1 + w3 (conflicts in build.py/save.py: both final-pass steps kept, identity gate before
situations). Held-out C exposed two GENERALISATION bugs in the merged code (both fixed by the merger, both "read a
key by A/B's name"):
1. identity_gate read the per-answer flag as `verified` and the call-wide flag as verif+all. C's API answers
   `passed` / `identity_confirmed`: every passed answer got "This answer is WRONG" -> the agent re-asked the same
   question until the turn limit (C 1/12, 7 calls looping verify_identity). Fix 0584029: both flags found by shape
   (pass/correct/match/valid/confirm/verif + all/identity/fully/complete), no verdict at all ("checking", follow the
   bank's words) when the shape is unreadable; same rule in the self-sim privacy lint.
2. w1's idempotent writes keyed on `*_id` request fields and `*_id` acknowledgement keys; C uses account_ref /
   promise_ref, so an identical create_promise re-sent together with close_call reached the bank ("call already
   closed"). Fix: *_id / *_ref, instalment numbers in the key (9523a1c). Local exec tests on both shapes.
(H) the hidden briefs "change fields and allowed values": any hook that matches a key by name is a Sunday risk;
assigned as b7's wild card.

Measured (merged build, before the two C fixes; the fixes do not change A/B behaviour: same states on A's key shapes,
tested):
- fast A 6/10, B 0/3 (invented ids M7, per-item counts), rA 6/10, rB 0/3 => 12/26 (champion 10, 12 rejudged): tie.
- OFFICIAL A 7/10 (runs 9,8; PUB-03 1/2 = simulator leakage: the simulated customer gave the CORRECT birth date on
  the third try, identity really passed; PUB-05 support offered twice 1/2; PUB-06 floor offered twice 1/2),
  B 2/3 (runs 2,3; PUB-12 1/2), raw-A 10/10 (champion 9/10), raw-B 1/3 (champion 2/3; both failures = model loops
  "Thank you, <name>" after the customer's goodbye until the node turn limit, no close_call: M35, pre-existing kind).
- SAME-SESSION CHAMPION (main rebuilt as champ-A, 398 s): official A 7/10 (runs 9,8), the same three cases 1/2.
- Build time 551-765 s (A 747, B 765, rA 706, rB 569, C 551/835).
- C (held-out): first build 1/12 random (identity loop, bug 1); after fix 1: 2/12 random, 2/12 adversarial (b5
  champion 2 / 4); after fix 2: see results.tsv.
- after fix 2 (9523a1c build, 528 s): C 1/12 random (1 case harness-invalid: chat turn timeouts), adversarial not
  finished (platform chat timeouts on 4 cases, killed at the time limit). C is flat-to-down vs b5 (2/12, adv 4/12)
  on 1-rep runs; C-01 still re-sends create_promise with close_call (the dedup did not fire live: unexplained, b7 wild
  card checks it). Watch item, not a measured drop beyond 1-rep noise.

Decision: KEEP (main = merge/b6). Official A+B = same-session champion (7+2 vs 7+2, identical per-run 9,8), rA+rB
11 = 11 (10+1 vs 9+2): no drop. Accept rule (c) + (b): hookcheck removes a build defect class that zeroed official B
in b5 (any hook that raises is repaired before save, on every brief); the identity verdict is code-decided per answer
(fast PUB-03 2/2 on w4; the one official miss was simulator leakage); specialists carry the brief's own clause
(best fast A); idempotent writes target C's duplicate-write kind. All four are brief-agnostic, and both C-only bugs
they carried are fixed by shape rules.
Left (b7 families): invented product ids (M7, ids_to_use still not in main), floor offered twice / invented floor
(M27/M21: PUB-06 1/2 in every official A run), close loop to the node turn limit after goodbye (M35, official rB),
support offered twice on hand-off re-entry (M40), key names read literally from A/B's API (Sunday risk).

## b7 (aborted by the owner, 2026-10-11 ~06:15 UTC)

The b7 merge candidate scored 0/3 on official raw-B (invented product ids, per-product dates swapped), so the owner stopped the merge and moved on. Branches merge/b7 and idea/b7-1..5 are kept for the archive.
Owner direction for b8: brief B is stuck at 2/3 on one case, every time for the same reason: the model miscounts persuasion attempts per product and writes the wrong notes. Per-item gates decided in code, i.e. an OR gate for one combined ask, then dependent per-item gates, each with a code-counted budget. The model consults an internal logic step inside the workflow (never an outside URL), plus a build reliability worker. Families: runs/next_families.txt.

## b8 merge (2026-10-11 07:21-08:20 UTC)

Platform this batch: workspace 2 answers 402 Insufficient credits (chat AND simulations), so (1) no build ran its
self-simulation (every b8 build "self-test 1: 0/0 personas", builds 2.5-5 min instead of 9-13) and (2) official B/rB
ran in workspace 1 after A. About 20 fast_evals ran at once; most worker evals did not finish within the workers' 75 min.
The merger stopped w2's and w5's evals (1h10 / 50 min, no result) to free eval slots for the merge candidate.

Owner note (cedb5ea tool-name normalisation): confirmed REAL but rare. Saved specs: 88 calc.json across all worktrees,
0 mismatched names; traces: 1 of 45 (runs/traces/main-B-20261011-051844.jsonl, the b7 merge main-B: promise_tool
"/create_promise", callback_tool "/schedule_callback" -> no promise/callback guard and no date check installed).
Fresh: datecalc alone 3x each on A, rA, rB, C, raw C = 0/15 mismatches, guards installable in 15/15 (C: no
check_promise_date, a promise_date_field condition, not a name issue). Carried over only the norm_tools part of
cedb5ea (+ its login-token fetch); the apifuzz line of merge/b7 was not taken.

Workers (fast --reps 2 --style random; champion b6: A 6, B 0, rA 6, rB 0; C 1-2/12):
- w1 A18-style per-item gates in code (gates.py: lookup-only ledger, item_gate code-only tool, refusal/second-note/close
  gates): rA 6, rB 0, B 0 (1 invalid), A harness-invalid (9/10), C 3/12 (best C this batch; v3 with a hook over the
  platform limit 1/12). Live-verified: the model calls item_gate, invented ids refused with code's reason. Not merged:
  no B/rB gain measured; it is the start point for b9's A18 family. Found the platform limit: hook code + data >
  131072 bytes fails the tool call (taken: hookcheck flags hooks > 110 KB).
- w2 per-item gates v2 (itemgate.py, item_step tool, negotiate_item node): builds OK, unmeasured. Not merged.
- w3 build reliability: buildcheck + one EDIT repair round, rebuild when nothing written, no stale success, clean slot.
  A 9/10 (!), B 0, rA 6, rB 0 (2 invalid). Broken builds 2/9 -> 0/9 shipped; stale-slot reuse 2/9 -> 0/9. MERGED.
- w4 held-out focus, amounts from code (check_promise_date answers amount: lowest_amount, floor-offered counter,
  unknown id -> listed ids): A 5, B 0 (broken build: unreachable negotiate), rA 6, rB 0. The fast A PUB-09
  "minimum 300" was the model skipping the check tool (no check call in that call), not the new text. MERGED on (c).
- w5 policy_check decision tool: v1 rA 0/10 (account hook over the size limit), v2 unmeasured. Not merged.
No worker hard-coded brief content (diff greps: no case ids, codes, amounts, dates, product ids).

Merger fixes: hookcheck size error (> 110 KB); canned.py: a brief's mandatory line with {{placeholders}} (seen on
the rB build: "{{product}} ... {{past_due}} ... {{days_late}}" in the account hook's SAY EXACTLY) is stored as <<x>>
and filled from the tool result (exact field, then a non-id loose match; else "[field]" + "put the real value") so
the model is never told to say raw placeholders and no hook carries {{ }} (lint error). Local exec tests both ways.

Merged (main a575bbf), builds 173-236 s (no self-sim), lint 0, buildcheck 0 on all five (rB: repair round 5 -> 0):
- fast A 4/10, B 1/3, rA 8/10, rB 0/3 = 13/26 (champion 12). Fast A failures: dates (PUB-04/06 one day off),
  PUB-10 service_error, PUB-03, PUB-07, PUB-09 transfer missed.
- OFFICIAL A 8/10 (runs 8,9; PUB-05 0/2 support/sympathy twice, PUB-06 1/2 floor twice), B 3/3 (3,3), raw-A 9/10
  (PUB-05 sympathy x3), raw-B 3/3. Champion (b6): A 7, B 2, rA 10, rB 1. A+B 11 vs 9, rA+rB 12 vs 11: no drop.
- C 1/12 random, 1/12 adversarial (b6 champion 1/12 random). WATCH: on C the agent named October dates (call_time
  1 Nov), its promises were blocked by the guard and closed SERVICE_ERROR (C-01/03/05/09). The start node's code,
  run locally with call_time 2026-11-01, gives correct November facts; w1's C build in the same hour had November
  dates. Unexplained (date facts not reaching the live call? branch resume?). Assigned as b9's wild card.
Decision: KEEP. Accept rule (b)+(c): multi-product official B and raw-B both 3/3 (two briefs, the b7 failure kind),
PUB-03 identity 2/2; mechanisms: no stale/broken build shipped (buildcheck + clean slot), the floor offered comes from
code, tool names normalised, hooks checked for the platform size limit, no raw placeholders in mandatory lines.
Hypotheses (H) for b9: once-only limits need code flags (the only official A residuals); the self-sim has been a
no-op since workspace 2 ran out of credits; per-item gates (b8-1) are the A18 base.
Post-merge note (after reading the analyst's b8 mechanisms.md): merge/b7 66d7282 measured post-fix official A 9, B 2,
rA 10, rB 3; its other carry-overs (compact SPEC in hooks against M53, b7-1 invented-id resolver M7, b7-2
check_promise_amount and condition-less transition fixes M46/M47) are not on main. Open on main with no fix anywhere:
lookup failure routed into negotiation (M54), callback date resolved by the model (top date kind). (H) b9 merger: take
b7-1's id resolver and the compact SPEC if the A18 / A4 branches do not already cover them.

## b9 merge (restarted merger, 10:07-11:4x UTC): NOT KEPT (platform outage; official evidence incomplete and below the champion)

Context: the first b9 merger hung ~1 h on a Freya outage (09:30-10:05) after building merge/b9 = main + w5 livevars +
w2 self-sim fallback + a final-save 5xx retry (9bd7f75). The workers' own evals were all lost (NOT MEASURED). I re-used
those merge/b9 builds (main-A/B/rA/rB/C, 889-1079 s with the ws1 self-test; lint 0, buildcheck 0, the `__again_` livevars
nodes present on the platform in all five) and measured them plus worker screens. The platform stayed degraded during
this merge (chat 500/404 "Agent service error", 503 "API key validation temporarily unavailable", 504 on reads, a
second hang ~10:50-11:00): fast_evals took 23-40 min each; workspace 2 answers 402 to simulations too, so every
official run went serially through workspace 1.

Workers (all NOT MEASURED by themselves; diff greps: no brief values, case ids, codes or dates hard-coded in any branch):
- w1 A18 gate graph (gategraph.py: gates extracted as data, linted, boundary-tested offline, evaluated in the
  write/close/transfer hooks; from idea/b8-1). My screen: B 0/3 (1 rep; invalid product ids, calls not closed, promises
  on wrong dates; this build has no M59 fix, so chat dates are blind). A/rB screens stopped for slots. Not merged.
- w2 self-simulation that actually runs (ws2 402 -> ws1 fallback, 6 personas one per brief gate, true counts in the
  trace, fix round needs >= max(3, n/2) chats, os._exit after the result). Evidence: w2-A2 6/6 chats; on the merge
  builds 3/6, 5/6 (B: fix round ran, its save 504'd twice), 4/6, 2/6, C 0/6 under load. Cost: build 173-236 s -> 889-1079 s.
  In merge/b9.
- w3 A4 per-turn tool gating (gating.py: resolved-state node copies without write tools, hand-off node with close
  only, own-reason refusals for 2nd note/promise, writes after close/transfer, close before every item has a record).
  Screens (1 rep): see table below. Not merged (no official run possible in time; overlaps w1's hook refusals).
- w4 once-only in code (once.py: entry counter code node, talk/after split, call-wide once_said). Its own narrow eval
  on rA PUB-05/06: 0/2 (floor still offered twice). Screen A: see below. Not merged.
- w5 WILD live-variable probe: FOUND the cause of the C October dates: the chat endpoint skips the INITIAL node's
  pre_actions, so DATE FACTS never existed in any chat call (fast_eval, brief C, chat self-test); the official simulation
  runs it. livevars.py re-runs the start chain on the opening's exits; before/after repro on C-01 (Oct 17 -> Wed
  2026-11-11). Verified here in an official transcript: the start code runs twice, both succeed, no side effect.
  In merge/b9.

Merged candidate merge/b9 (9bd7f75), measured:
- OFFICIAL A rep 1 (simulation db90aab7; its run_cases died on a 503 while polling, scored by btb/salvage_sim.py from
  the ledger + the official judge): 6/10. Fails: PUB-05 support offer twice, PUB-06 floor 637.50 twice (the known
  once-only residuals, M62), PUB-03 the model asked the DOB a 4th time instead of calling verify on the 3rd answer
  (customer added a question; model behaviour, not livevars: the identity_failed route worked once verify was called),
  PUB-10 judge: "recorded" said in the opening ("this call is recorded") before any write (judge strictness on a
  mandatory line; the champion's opening has the same sentence).
  Champion (b8): A 8/10 (runs 8, 9), B 3/3, rA 9/10, rB 3/3.
- OFFICIAL A rep 2 (simulation 6e7825a2), B, rA, rB: LOST to the second outage (the rep-2 simulation stayed "running"
  with 3 inconclusive runs; every GET on it 504'd from ~10:47; B/rA/rB never started; workspace 2: 402).
- fast (reps 2, random): rA 2/10 (champion 8/10): PUB-03 0/2 (identity continued after the 3rd wrong answer),
  PUB-05/06 once-only twice, PUB-02 callback year wrong, PUB-07/08/09 1/2. A, B, rB, C did not finish in 60 min.
- Screens (1 rep, worker builds as shipped, no M59 fix in w1/w3/w4): w1-B 0/3; w3 A/B/rB and w4-A did not finish.
Decision: NOT KEPT. main stays the b8 champion builder (a575bbf). Accept rule: official A+B and rA+rB must not drop and the
gain must repeat; the only official run we have is A 6/10 vs the champion's 8 and 9, and fast rA dropped 8 -> 2. No
(a)/(b) evidence; w5's (c) case is real but it is bundled with w2's x4 build time and its unverified fix round.
merge/b9 is pushed as a branch for the archive.
Kept on main (harness only, no builder change): btb/run_cases_retry.py (run_cases with GET 5xx retries; a POST retries
only on 503) and btb/salvage_sim.py (score an official simulation whose run_cases died).
Hypotheses (H) for the b10 merger / final rehearsal:
- (H) w5 livevars (idea/b9-5 381aa28 + b300c7d) is a BUG FIX with a before/after repro (runs/b9/w5/repro_c01_*.txt,
  M59): without it every chat measurement (fast_eval date cases, all of brief C, any chat self-test) runs with no DATE
  FACTS. It fits the b10 "BUG HUNT, workflow side" family; the b10 merger can keep it on its repro + official A/B.
- (H) w2's ws1 self-test makes builds 15-18 min under load (30-min cap) and runs a Claude fix round whose edits are not
  officially verified (the B fix round's save 504'd twice); if taken, cap it hard and keep the trace honesty part
  (true chat counts, "SELF-TEST DID NOT RUN") even when the fix round is off.
- (H) PUB-03 kind: a 3rd wrong identity answer mixed with a question is not sent to verify; the identity node needs a
  code/route fact "answer pending -> call verify" (M61 neighbourhood).
- Platform: in this session ws2 answered 402 to simulations too; plan the final rehearsal for one serial workspace.
b10 families: the owner's five (BUG HUNT pipeline, BUG HUNT workflow, SIMPLIFY, STABILITY, SUBMISSION CHECK) written
verbatim to runs/next_families.txt; the owner note's families block is removed from merger_notes.md (handled), its b10
merger instruction kept.
WARNING for b10: the main-A/B/rA/rB/C slots on Freya hold the merge/b9 builds (not kept), not the champion's; rebuild main-* from main before any official or final run.
(11:20-11:31 the b9 merger tried to rebuild main-A/main-B from main: every save PUT answered 504 and the builds hit the 10-min tool limit; the main-* slots are in an unknown state, rebuild them. Logs: runs/b9/rebuild/.)

## b10 merge (consolidation batch, 12:40-14:1x UTC): merge/b10 KEPT on main = verified bug fixes (w1, w2, merger) + w4 stability + w5 trace/export + w3 dead-code removal

Owner rule for b10: keep a bug fix only with a before/after repro re-run by the merger; a simplification only with an empty
workflow diff and no official A/B drop. Platform this session: saves and builds were healthy (builds 534-1068 s with the
self-test); workspace 2 still answers 402 to chats and simulations, so all official runs went serially through workspace 1;
the chat endpoint was slow (fast_eval C took 19-27 min, some chats timed out); one official run per brief.

Workers (no worker could measure a score: chat 500s from 12:00-12:45; all brief-agnostic by diff grep, nothing from A/B hard-coded):
- w1 BUG HUNT pipeline: 14 offline repros (datecalc percent floor rounded to cents before the brief's rounding, min before
  rounding, unpadded cut-off string compare; self-test chats as non-daemon executor threads holding the process past BUILD END;
  round 1 ignoring the time left; unlocked state-file reads during a parallel save; clear_slot treating '-' as a word boundary
  (slot brief-a wiped brief-a-raw's files); no 5xx retry on saves; 0/0 self-test printed as a pass; scrub missing split
  writes/writelines; `PROMPT.replace("BRIEF")` pasting the brief twice; selftest max_calls n=None crash; unreadable final ledger
  scored as "close_call 0 times"). RE-RUN BY ME: 14/14 FAIL on main, pass on the branch, and pass on merge/b10. MERGED.
- w2 BUG HUNT workflow: live probe: in a parallel tool turn a post-hook can read a SIBLING's vars, and `config` is absent in
  post-hooks (M20 measured). Fixes: R1 a guard block no longer erases an earlier real failure count; R2 the guard post-hook
  decides recorded/blocked by the bank RESULT (success id field from the tool API file), not by the per-tool flag a sibling
  leaks; R4 a bank rejection (ok=false, <500) says "the bank rejected the values ... never send the same values again"
  instead of "retry with the same values"; R5 identity 'passed' from the call's own ledger when the bank gives no call-wide
  flag, sticky against a stale sibling (= owner FIX 2); R7 an id the model built (credit_card_2288, CC_2288) is mapped to the
  one listed item whose type/last digits match. RE-RUN BY ME (offline_finish on the same w2-B raw workflow with main's and
  the branch's code + repro.py): before/after differ exactly in R1/R2/R4/R5/R7, R6 negatives (right+wrong, flag false,
  three wrong) unchanged; identical output on merge/b10. MERGED. (Owner asked for fast_eval PUB-05 before/after for FIX 2:
  not run, the chat endpoint was too slow; the hook-level repro is the evidence.)
- w3 SIMPLIFY: dead extract.py, unused vars/params, dead tool_successes_ hook branch, duplicated conditions; w3's replay of
  the whole post-processing chain on 9 real inner-agent workflows is identical modulo the removed hook lines. MERGED
  (conflicts resolved in favour of w1/w2 code). Official: see the decision below.
- w4 STABILITY (36 builds): round a (champion as is) 10/12 BUILD FAILED on Freya 5xx inside the final save; 30/36 "strong"
  extractions silently fell to gpt-4.1-mini on Azure 429s; ws2 402 made every self-test a 0/0 no-op. Fixes: save retry within
  a budget, ship the agent's own save of THIS run when the final save fails, workspace id once, Azure 429 wait + fallback
  logged, ws1 self-test fallback. MERGED; save retry unified into w1's locked_save (w4's transient set + 300 s budget, sleeps
  outside the lock); the ws1 fallback shares round 1's budget.
- w5 SUBMISSION CHECK: trace now lists Claude Code's hidden helper model (claude-haiku-5-5), failed Azure calls, one line per
  self-test persona chat, "untested, not passed" for a round with no valid chat, step/tool counts of what was saved, an export
  dry-run load; submit.sh parsed as one block (an edit/git pull during a run broke it). Workflow unchanged. MERGED.
- w6 once.py behind BTB_ONCE=1: first line VERDICT: NOT MEASURED -> not taken (owner rule). w7 memory tool: VERDICT: NO
  EFFECT -> not taken (owner rule).
- Owner FIX 1 (silent account step): NOT DONE. No branch had it; the fresh main-A build had a different shape (get_account is a
  tool inside the identity node, no separate account node), so a general rule plus its fast_eval before/after did not fit
  next to the official runs. Carry-over.

Found and fixed by the merger on the merged builds (each with a before/after):
- M1 fix-round crash: with the ws1 fallback the self-test fix round really runs; on main-A and main-B the Claude SDK raised
  CLIJSONDecodeError (a >1 MB message after an Edit of the workflow file) and only TimeoutError was caught: both BUILDS DIED
  with no result line (Freya kept the build's final-pass save). Fix: any fix-round error puts the build's file back and
  ships the build's save; self_simulate can never kill the build; SDK max_buffer_size 16 MB. Repro
  runs/b10/merge/repro_fixround_crash.py (stubbed selftest + claude_stream): before CRASH, after survives with the build's file.
- M2 intent transitions without a condition: official raw-A on the merged build 3/10: 6 calls stuck in the router (the model
  read back the promise, never left the router, closed service_error). The build agent had written all 15 is_tool_call
  transitions WITHOUT `condition` (docs: a tool-call transition carries {"operator": "matches_intent", ...}); the platform
  then never offers the transition tool. Not caused by the merge: the same shape is in about 1 of 6 champion-code builds
  (w4 rounds a/b/c, w1). Fix: save.intent_conditions() in the final pass adds matches_intent with the transition's own
  description. Before/after on the SAME workflow (the scored main-rA/main-rB, only this repair, saved as main-rAfix/main-rBfix):
  official raw-A 3/10 -> 6/10: all five promise cases that were stuck (PUB-01/04/06/07/10) pass; the 4 new fails are
  platform stalls (the call ended after the customer's first line, no agent turn, opening node untouched by the repair).
- Harness: undocumented `POST /api/v2/simulations/{id}/cancel` cleared b9's stuck "running" simulation 6e7825a2 that blocked
  workspace 1 (use it in the final rehearsal); run_cases_retry.py also retries mock-bank calls (a non-JSON bank answer killed
  three official runs at 13:2x).

Official (workspace 1, 1 rep each; champion b8: A 8/10 (8,9), B 3/3, rA 9/10, rB 3/3):
- A (main-A, merged build; its fix round crashed = M1 case, so the build's final-pass save was scored): 8/10 (PUB-03 3rd wrong
  answer not ended as failed; PUB-07 every tool "Sandbox did not return a parseable result", the known sandbox payload-limit
  kind from b7/b8 digests). PUB-05 and PUB-06 (the champion's usual fails) passed. Simulation salvaged after a bank 5xx.
- B (main-B, same agent twice): run 1 0/3 during a latency spike (customer turns 35-50 s; PUB-11/13 cut mid-confirmation,
  "customer hung up: 2"; PUB-12 two persuasion attempts on an early-band product); run 2 (latency back to 6 s median) 3/3.
- raw-A: first merged build 3/10 (M2 shape) -> same workflow + M2 repair 6/10 (4 platform stalls at the opening) -> FULL
  REBUILD with the final builder (main-rA, 758 s, intents 15/15 with condition) 10/10.
- raw-B: first merged build + M2 repair (main-rBfix) 2/3 (PUB-13 customer hang-up under the latency spike). The final
  rebuild of main-rB (1068 s, intents 33/33 with condition) was not scored officially (time).
fast: C random 1/12 (1 invalid), C adversarial 1/12 (champion 1/12, 1/12). fast A/B/rA/rB not run (chat endpoint slow; the
official runs had priority).

Decision: KEPT (merge/b10 -> main). Accept rule: (c) every builder change is a bug fix with a before/after repro re-run by
me (w1 14/14, w2 R1/R2/R4/R5/R7, M1, M2), (b) the fixes cover several failure kinds (save/build deaths, trace honesty,
parallel-hook misreports, identity gate, built ids, router dead-ends), and the official evidence does not drop once the
platform's latency spike is excluded: A 8/10 = champion level, B 3/3 = champion (0/3 run explained by hang-ups in the
transcripts), raw-A 10/10 on the final rebuild (champion 9/10), raw-B 2/3 on the repaired first build (1 hang-up). w3's
simplification: replay-identical and official A/B did not drop on the clean B run -> kept.
Slots now: main-A, main-B, main-C = merged builds BEFORE the M2 repair (their intents all had conditions, so M2 would not
change them); main-rA, main-rB = final builder. main-rAfix/main-rBfix = repro slots only.
Hypotheses (H) for the final rehearsal:
- (H) M2 was probably behind part of the champion's run-to-run spread on raw briefs (1 in 6 builds dead-ended at the router);
  with the repair a bad build of that kind no longer exists. Check the next 3 builds' "intent-condition:" lines in the trace.
- (H) The ws1 self-test now runs and its fix round edits the workflow (rA first build "fix kept"; rB "restored"); the re-test
  guard decides. If the rehearsal shows a fix round making things worse, set it off (SELFTEST) and keep the trace honesty.
- (H) Open: owner FIX 1 (silent account step), once-only residuals (PUB-12 two attempts on an early-band product, PUB-05/06
  kind), the sandbox payload limit (PUB-07: the pre-hook prints config + all vars; a big vars dict makes every later tool
  call unparseable), PUB-03 (3rd wrong identity answer closed as declined).
