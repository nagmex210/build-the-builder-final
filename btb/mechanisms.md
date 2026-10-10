# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md and
fix/cases:runs/mechanisms.md. Last update: after batch b4 (2026-10-10 ~22:10 UTC).

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b2 | b3 | b4 (226 fast calls, digest) | total | at fault |
|---|---|---|---|---|---|
| multi-product binding (amount/date/deadline of one item applied to another, item left out, stale per-item date) | (in per-item) | - | 28 | 28+ | builder |
| dates (another band's deadline offered for a holiday, weekday phrase, wrong year) | 17 | 1 | 17 | 35 | builder |
| per-item attempts / outcome counted wrong | 7 | 1 | 13 | 21 | builder |
| tool order / duplicates (close in parallel with notes, tools after close, invented ids then retry, re-sent writes) | 24 | 2 | 15 | 41 | builder |
| "once only" limit broken (floor offered twice, two sympathy sentences) | 0 | 0 | 12 | 12 | builder |
| amounts (below-floor promise recorded, floor offered too early, invented floor) | 7 | 0 | 8 | 15 | builder |
| wrong route: cannot-pay -> agent invents its own plan instead of the brief's transfer | 3 | 0 | 8 | 11 | builder |
| identity gate (wrong answer read back instead of checked, attempts not stopped, wrong reason) | 8 | 2 | 6 | 16 | builder |
| mandatory wording | 6 | 1 | 2 | 9 | builder |
| honesty / privacy | 0 | 2 | 1 | 3 | builder |
| harness: fast judge says a sentence/tool is missing that IS in the transcript | 11 | 5 | ~36 | ~52 | harness |
| harness: fast simulated customer refuses or "corrects" to a date the case does not expect | 0 | 1 | ~6 | ~7 | harness |
| platform: timeouts / branch-resume replays | heavy | ~55/69 | low (fast_eval now re-runs invalid reps) | - | platform |

b4: 80/226 fast calls pass. The judge-noise row is the largest single row again (see section 5).

## 2. General mechanisms (each holds for ANY collections brief)

M1. Show only this customer's facts: after the account loads, list and tag only the deadlines of this customer's own
    products. A calendar tagged with every band's deadline ("after <other band> deadline" on a holiday) makes the model
    offer its own deadline instead of the next business day. The single most repeated failure (b1-b4, official too).
M2. Dates and amounts are computed in code and read from one labelled line per product (full, floor, deadline,
    attempts). A code guard on the promise tool blocks a below-floor amount or an after-deadline date with the reason
    (seen working live: the model recovered with the right amount). Without the guard the model records what was said.
M3. Every date/amount rule the brief states reaches code or is listed as "not computed, apply yourself" in the facts
    and the node prompt. A schema with no slot for a rule drops it silently (seen: the "one date for all items, but an
    item whose deadline is earlier keeps its own deadline" rule).
M4. A gate's terminal state is stated by code. Identity: every answer goes to the check tool at once, never read back
    ("just to confirm, X?") and never re-asked unchecked; when attempts run out the result says it is over, with the
    exact close reason and referral sentence.
M5. One answer, one check: never re-send earlier answers. Persist passed questions in call variables.
M6. Close is last, and the prompt alone does not order it.
M7. Ids are copied from a listed line, never built. Without a resolver the model writes display ids and burns a retry.
M8. A guard never blanks request fields to stop a call.
M9. A build step that can fail (inner Claude quota/API error, not only the time budget) never takes the build down:
    fall through to the deterministic final pass on the last written file.
M10. A mandatory sentence tied to an event arrives with the event: put it in the success tool result
    ("say exactly ...") or in the tool description; the model says such lines word for word.
M11. A guard block returns a 2xx tool result with ok=false and the reason, never a transport failure.
M12. The model emits several tool calls in ONE turn; the platform runs them in parallel. close + notes in one turn
    means notes land after close, or a close guard sees the notes as missing.
M19. Routes out of a guarded tool test the result's ok field only. `<tool>_success_count` counts every 2xx, including
    a guard's no-op block, so "ok OR success_count > 0" routes a BLOCKED close to hang-up (seen live).
M20. Hook state is not reliable across one parallel-call turn: sibling hooks do not see each other's variable writes and
    some writes are lost. Never decide a block from writes issued in the same turn; derive item status from the bank's
    own answers or from structure (a close that exists only in a node reached after all items are done).
M13. Per-item counters (attempts, outcome) live in code per item, shown each turn; per-item persuasion is still the
    model's job and drifts (an early-band item gets the late-band ladder). State the remaining attempts per item.
M21. "Once only" limits are call-wide: a floor offer repeated with a new date, or a second sympathy sentence for a
    talkative customer, breaks them. Keep a flag per limit in state ("floor already offered") and show it every turn.
M22. An exit route the brief requires (cannot pay even the floor / asks for a plan -> transfer) needs its triggers named
    in the negotiation node and its own transition; otherwise the model invents a partial plan and closes as refused.
M23. Multi-product: bind amount, date and id per item in one line each; the read-back names every item with its own
    amount and date, and each write must match its item's line (seen: amounts swapped between items, then "recorded"
    claimed: an honesty failure). A late "same date for all" must update every item, not only the next one.
M14. To a third party, any sentence about payment, debt or the account discloses the purpose.
M15. After a "no" to a read-back, ask what to change; never repeat the same read-back.
M16. Under platform load a chat can replay an old message; route on persisted call variables, not "current node".
M18. Before identity passes, no account content at all; identity results carry an explicit verdict line.
M24. Platform-spoken text is verbatim every time: the opening as the first node's on_enter tts, success lines in the
    tool's post-hook, the goodbye in the close tool description. Risk: an extraction error becomes systematic.
M17. Best-of-N / LLM mistake counts cannot pick builds. M25: self-simulation with DETERMINISTIC ledger checks (ok=false
    results, close once and last, no account tool before identity, no repeated write, date <= deadline, amount >=
    floor) finds the same kinds the scorers find, but one prompt EDIT round does not fix code-level kinds (ids, tool
    order), and one play per persona is too noisy for keep/revert (use >= 2).

## 3. What carries the calls that pass (keep intact)

- Structural routing on tool-result fields (identity -> account on the all-verified field; close -> hang-up on ok).
- Account loaded by a code path (load node + datecalc hook): products, band, deadline, floor in state first.
- Short decision chains; each extra rule decision (holiday shift, deadline cap, floor) is a coin-flip point.
- what_to_do_next / SAY NEXT lines in tool results: said word for word.
- Multi-product: all items stated before the first ask, one combined read-back, one write per item id.
- Hardship: one sympathy sentence, one support offer, no persuasion, close.
- Tool failure: retry once, say "recorded" only after SUCCESS.

## 4. Carry-overs (fix exists on a non-champion branch; champion main still shows the failure)

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| dates: other band's deadline on a holiday (M1) | fix/cases builder/datecalc.py (own-band tags after account load); idea/b4-4 4f9a81e (same idea, `build_facts(only_bands)`) | **top priority**: that case failed in 17 of 18 b4 runs on every branch; neither fix is in main or merge/b4 |
| below-floor / after-deadline promise recorded (M2) | merge/b3 + idea/b4-4 builder/guards.py (no-op block path, live-verified) | main-based builds recorded below-floor amounts |
| rule kinds dropped by the date schema (M3) | idea/b4-4 builder/datecalc.py (roll, rounding, cut-off, gap, slots, `unhandled_rules`) | offline-tested; inert on A/B; callback slots are C-informed |
| invented ids + retries (M7) | merge/b2, merge/b3 harden id resolver (`ids_to_use`) | main lacks it; main-based B runs failed on it every time |
| build dies on inner Claude quota (M9) | merge/b3 a257249 | **main still catches only the time budget: Sunday risk** |
| close in parallel with notes (M12/M20) | idea/b3-3 statemachine.py (close only in wrap_up node) | unmeasured; idea/b4-1 close GUARD: do NOT merge as is (M19/M20) |
| blocked close still hangs up (M19) | none: drop `success_count` from close->hang-up conditions (routing.md pattern 1) when the close tool has a guard | new |
| per-item status (M13) | idea/b4-1 builder/items.py (per-item variables; install-bug fix: hook every copy of a tool) | the ledger text shows stale OPEN after parallel turns (M20) |
| re-asking passed identity questions (M5/M16) | idea/b4-5 8d63d15 harden identity memory | taken into merge/b4 (ed7d8f8) |
| verbatim opening/lines/goodbye (M10/M24) | idea/b4-3 builder/canned.py | taken into merge/b4 |
| self-simulation (M25) | idea/b4-2 builder/selftest.py | taken into merge/b4 |

## 5. Variance sources (pass in one run, fail in another)

- a value left to the model among several candidates (which deadline, which floor, which item's date): M1/M2/M23;
- parallel tool calls in one turn: order of close vs notes, and lost hook state, differ per run (M12/M20);
- per-item and "once only" counts in the model's head (M13/M21);
- the simulated customer: talkative/asks_back styles push the model off the rule order; the fast customer may refuse
  every allowed offer or "correct" to a date the case does not expect;
- the fast judge: (a) transcript fetched before the agent's FINAL message is saved, so closing sentences look missing
  (seen on 19k-char transcripts: not truncation; main's fast_eval still fetches once); (b) old 30k-tail truncation of
  the raw transcript (fixed on main: judge sees dialogue + tool calls only). Re-judging flipped whole cases to pass.
  The official judge sometimes counts the recording notice as a premature "recorded" claim;
- platform: 5xx, timeouts, branch-resume replays under load (cap concurrent chats; workspace 2 is quieter);
- build-to-build variance is real (same builder scored 0/10 and 6/10 on clean vs raw brief in one batch) but is not
  the main source of judge-visible defects (M17).
