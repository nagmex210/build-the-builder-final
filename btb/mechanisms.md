# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md and
fix/cases:runs/mechanisms.md. Last update: after batch b3 (2026-10-10 ~21:00 UTC). Includes the fix/cases analysis of b1-b2.

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b2 (fix/cases) | b3 + official merge runs | total | at fault |
|---|---|---|---|---|
| duplicate / repeated tool calls (re-sent checks, invented ids then retry, repeated notes) | 17 | 0 | 17 | builder |
| dates (another band's deadline, holiday not moved, weekday phrase, wrong year) | 17 | 1 | 18 | builder |
| tool order (close before / in parallel with notes or transfer, tools after close) | 7 | 2 | 9 | builder |
| identity gate (answer not processed, attempts counted by the model, wrong failure reason) | 8 | 2 | 10 | builder |
| per-item attempts / outcome counted wrong (multi-product) | 7 | 1 | 8 | builder |
| amounts (invented floor, rounding lost) | 7 | 0 | 7 | builder |
| mandatory wording (first sentence, sentence after an event) | 6 | 1 | 7 | builder |
| honesty / privacy (purpose told to a third party; account facts invented before verification) | 0 | 2 | 2 | builder |
| read-back loop (same read-back repeated after the customer said no) | 0 | 1 | 1 | builder |
| wrong route / outcome only | 3 | 0 | 3 | builder |
| harness: fast judge says a sentence/tool is missing that IS in the transcript | (11 judge, all kinds) | 5 | 16 | harness |
| harness: official judge reads the recording notice as a premature "recorded" claim | (in the 11) | 1 | - | judge (Sunday risk) |
| harness: fast simulated customer stricter than the official one (refuses every allowed offer) | 0 | 1 | 1 | harness |
| platform: chat timeouts / branch-resume replay (agent re-asks passed questions, verify called up to 8x) | ~40% of b1, all of b2 | ~55 of 69 b3 calls | - | platform |

b3 produced almost no valid fast measurement (platform saturated by ~25 parallel conversations). The b3 counts above
come from the official scorer runs of merge/b2 and merge/b3 and the few complete fast runs.

## 2. General mechanisms (each holds for ANY collections brief)

M1. Show the model only the facts that belong to this customer: once the account is loaded, list and tag only the
    deadlines of this customer's own products, per product. A calendar tagged with every band's deadline makes the
    model apply another band's deadline (still seen in the official scorer after b2).
M2. Dates and amounts are computed in code and read from one labelled line per product (full amount, floor, deadline,
    attempts). Never leave the choice among many numbers in a JSON blob to the model.
M3. Every date/amount rule kind the brief states must reach code (roll to previous/next business day, rounding) or be
    flagged in the trace. A schema without a slot for a rule drops it silently.
M4. A gate's terminal state is stated by code, not inferred by the model. When attempts run out the tool result says
    "it is over and did NOT pass" plus the exact closing reason. Left to the model, it asks again, picks the wrong
    close reason (declined instead of failed) or skips an answer that came inside a question.
M5. One answer, one check: the model re-sends earlier answers with new checks, which burns attempts when the first
    answer was wrong.
M6. Close is last. The prompt alone does not order it.
M7. Ids are copied from a listed line, never built. An invented-id resolver removes the refusal and retry.
M8. A guard never blanks request fields to stop a call; the bank then answers with a misleading error.
M9. A build step that can fail (inner Claude quota/session limit, API error) never takes the build down: fall through
    to the deterministic final pass on the last written file. A build that wrote nothing must refuse to save.
M10. A mandatory sentence tied to an event goes in the same reply as the event report.
M11. A code guard that stops a write must return a normal 2xx tool result carrying the reason. A platform-level
    failure (unreachable host) is counted as a tool failure, hides the reason from the model, and trips the
    failure-count route into a service-error close: every correct block became a lost call.
M12. The model emits several tool calls in ONE turn and the platform runs them in parallel: close + notes in one
    turn means a note lands after close and is refused. Order must be structural: the close tool exists only in a
    node reached after every item is resolved, or a close pre-hook refuses while an item is open.
M13. Per-item counters (persuasion attempts, outcome per product) kept in the model's head drift between items
    (one item gets another item's count, a refused item gets no note). Keep them in code per item and show the
    live status each turn.
M14. To a third party, any sentence about payment, debt or the account discloses the purpose. The non-customer path
    needs fixed allowed content (whom we want to reach, when to call back) and nothing else.
M15. After a "no" to a read-back, never repeat the same read-back: ask what to change. A read-back of a relative
    date says the customer's own word and the date ("today, <weekday> <date>"), otherwise the customer does not
    recognise it.
M16. Under platform load a chat can resume from an old message and the engine re-enters an earlier node. Progress
    held only as "the current node" is lost (the agent re-asks verified questions). Route on persisted call
    variables (e.g. identity passed) so a replayed turn skips completed steps.
M17. Best-of-N builds do not fix judge-visible defects: same-prompt Claude candidates share the same defects (callback
    window, first sentence, extra verify calls). An LLM "mistake count" self-test cannot tell candidates apart (the
    same workflow scored 1/1 with 5 mistakes and 2/2 with 6 mistakes). Self-tests must use deterministic checks.
M18. Before the account is loaded the model has no real numbers, yet a prompt that names the call's purpose lets it
    invent a balance and negotiate while identity is still unverified (it then closed with a made-up "technical
    issue"). The identity stage allows no account content at all; its only exits are the verified route and the
    failure close. Every identity tool result carries an explicit verdict line (a bare verified:false was read as
    "could not check").

## 3. What carries the calls that pass (keep intact)

- Structural routing on tool-result fields (identity -> account on the all-verified field; close -> hang-up on
  close ok). Passing calls never depend on the model choosing to leave a node.
- Account loaded by a code path (load node + datecalc hook), so products, band, deadline, floor are in state first.
- Short decision chains: one rule decision after identity passes reliably; each extra one (holiday shift, deadline
  cap, floor) is a coin-flip point.
- what_to_do_next / SUCCESS-FAILED lines in tool results, including the exact sentence to say next: the model says
  them word for word (seen for SAY NEXT lines, the after-event confirmation sentence, the failed-identity referral).
- Multi-product: all items stated before the first ask, one combined read-back, then one write per item id.
- Hardship: one sympathy sentence, one support offer, no persuasion, close.

## 4. Carry-overs (fix exists on a non-champion branch; champion main still shows the failure)

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| dates: cross-band deadline (M1), invented floor (M2), dropped roll/rounding (M3) | fix/cases f7f4a7d (builder/datecalc.py) | offline-verified, live unmeasured (outage); not in main nor merge/b3 |
| identity: no attempts left but model keeps asking / wrong reason (M4) | fix/cases (harden.py NONE LEFT) | offline-verified; not merged |
| invented ids + retries (M7) | fix/cases harden.py; idea/b2-2 (official multi-product 2/2) | merge/b2, merge/b3 have the b2-2 version |
| build dies on inner Claude quota (M9) | merge/b3 a257249 (= idea/b3-2 7291288, idea/b3-3), fix/cases | **main still lacks it: Sunday risk** |
| guard block ends the call (M11) | idea/b3-1 / merge/b3 (guards.py no-op 2xx path) | only matters with guards (merge/b2+); main has none |
| close in parallel with notes (M12) | idea/b3-3 statemachine.py (close only in wrap_up node) | unmeasured; b4-1 adds a close pre-hook |
| per-item attempts/outcome (M13) | idea/b3-2 builder/items.py | unmeasured; b4-1 re-measures |
| exact wording after tool outcomes | idea/b3-5 / merge/b3 (numbered RULES + SAY NEXT, lint-enforced) | lines are used verbatim; score unmeasured |

## 5. Variance sources (pass in one run, fail in another)

- a value left to the model among several candidates (which deadline, which floor): M1/M2;
- a re-sent earlier answer (identity): M5;
- parallel tool calls in the closing turn: order of close vs notes differs per run (M12);
- per-item counts in the model's head (M13);
- a mandatory sentence after an event dropped ~1 in 4 (M10);
- the simulated customer: talkative/asks_back pushes the model off the rule order; the fast simulator can be
  stricter than the official one;
- the judges: the fast judge misses sentences that are in the transcript (often the agent's final turn, despite the
  full transcript being passed); the official judge sometimes counts the recording notice as a "recorded" claim;
- platform: 5xx, chat timeouts and branch-resume replays under load (cap concurrent chats; never measure with
  more than ~8 conversations at once);
- inner Claude build-to-build variance is real but is NOT the main source of judge-visible defects (M17).
