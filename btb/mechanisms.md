# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md and
fix/cases:runs/mechanisms.md. Last update: after batch b5 (2026-10-11 ~00:35 UTC).

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b2 | b3 | b4 | b5 (362 fast calls, digest) | total | at fault |
|---|---|---|---|---|---|---|
| dates: deadline used as the TARGET, not an upper bound (holiday or valid earlier day answered with the deadline; own date counted as refusal) | 17 | 1 | 17 | ~38 | ~73 | builder |
| amounts: invented floor named before the labelled one, below-floor promise | 7 | 0 | 8 | ~22 | ~37 | builder |
| tool order / duplicates (invented ids then retries, close with notes, re-sent writes) | 24 | 2 | 15 | ~17 | ~58 | builder |
| per-item attempts / outcome counted wrong | 7 | 1 | 13 | ~16 | ~37 | builder |
| multi-product binding (one date for all, values swapped between items) | (per-item) | - | 28 | ~10 | ~38 | builder |
| identity gate (wrong answer re-sent, read back, "verified" claimed, no stop at 0 left) | 8 | 2 | 6 | ~10 | ~26 | builder |
| wrong route: cannot pay -> own plan instead of the brief's transfer | 3 | 0 | 8 | ~9 | ~20 | builder |
| "once only" broken (floor twice, sympathy/support twice incl. router+specialist hand-off) | 0 | 0 | 12 | ~6 | ~18 | builder |
| mandatory wording | 6 | 1 | 2 | 7 | 16 | builder |
| honesty ("noted"/"recorded"/"verified" before the tool says so) | 0 | 2 | 1 | 3 | 6 | builder |
| call ended without close (model goodbye -> platform end_call) | some | - | 3 official | 0 (fast cannot see it) | | builder+platform |
| harness: fast judge misses lines/tools that ARE in the transcript; persona refuses the expected date | 11 | 6 | ~42 | 19 | ~78 | harness |
| platform: timeouts / branch-resume replays | heavy | ~55/69 | low | 30 unfetchable + many INVALID re-runs | - | platform |

b5: 160/362 public fast calls pass. Official-only kinds (fast never shows them): "recorded" in the opening read as a
premature claim (3 official b4 runs), call hung up without close (3). Fast-heavy kind: invented floor (fast personas
ask "what do you suggest?"; official passes that case 5/6).

## 2. General mechanisms (each holds for ANY collections brief)

M1. Show only this customer's facts: list and tag only this customer's own deadlines. Necessary, NOT sufficient: with
    correct own-band facts the model still answers a holiday (or a valid earlier day) with "the latest I can record is
    <deadline>" (M27).
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
M26. The goodbye belongs to the platform, after close succeeded: the end node's spoken_message on the close tool's ok
    route; the model is told never to say goodbye and to call close when the customer says bye. A model goodbye before
    close lets the customer answer bye and the platform's own end_call hang up with no outcome (the platform's default
    agent config ships an end_call tool and "use it after you say goodbye", H). Quoting the goodbye in the close tool's
    description makes the model say it too (double goodbye, M10).
M27. The value to OFFER must come from code, not only the value to RECORD. A write guard cannot catch a wrong choice
    that is itself valid (the deadline instead of the next business day or the customer's own earlier day). Pattern: a
    code-only check tool (no-op path, hooks only) the model calls with the customer's day before answering; code
    replies "keep it" or the one date to offer. Same for amounts: the model invents a "minimum" (small round number)
    before the labelled floor; the guard blocks the write and it recovers, but "offered once" is already broken.
M28. A customer's own date or amount is never a refusal; the deadline is an upper bound, never a target. Say it in the
    node and let the check tool (M27) state "keep the customer's date".
M29. The identity tool result needs a verdict for EVERY answer, not only passes: "this answer is wrong, N left, identity
    NOT verified, ask <next>", and at 0 left a terminal instruction (say the referral line, close with the outcome).
    Without it the model re-sends an earlier wrong answer with the next one (burning attempts), reads one passed
    question as "identity verified", and loops "still processing" at 0 left. Block a re-sent answer in the pre-hook.
M30. Extraction is not a data path for values the model agreed: "yes" to the agent's own proposal extracts nothing;
    typed extraction variables cannot be reset from code; a node-level response mapping may be absent in a later code
    node's vars (read lists defensively). Per-item values must come from a tool call's explicit arguments.
M31. Router + specialist exits work (tool-call transitions with named triggers fixed cannot-pay -> transfer), but the
    hand-off must be silent: if the router speaks and the specialist speaks, sympathy/offers are said twice. The
    specialist never repeats a sentence already said in the call and carries the brief's "no persuasion" first.
M32. Parallel calls of the SAME hooked tool in one turn share its result variable (M20): two checks both answer for the
    first item. One call per message, or key results by request.
M33. Rewording a mandatory text to dodge a literal judge (a gated word in the opening) must keep the brief's required
    content AND its position (e.g. "in the first sentence"); dropping or moving it trades one failure for another.
M34. The builder's fixed stage order (opening -> identity -> account) can contradict a brief that orders stages
    differently (state the accounts before any question). Stage order is a brief rule like any other (M3).
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
- A code answer the model can copy (check tool's "offer exactly <date>", guard's NOT RECORDED + the right value): the
  model follows it and recovers (b5: holiday date right 2/2 once code named it).

## 4. Carry-overs (fix exists on a non-champion branch; champion main 779b267 still shows the failure)

merge/b5 (40b0d79, in progress) = idea/b5-1 + idea/b5-4 + idea/b5-5 (opening part). Rows marked (merge/b5) land if kept.

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| deadline offered instead of the customer's / next business day (M27/M28) | idea/b5-4 4a96534 check_promise_date (+b61c885 one per message, ade16ff valid ids) | (merge/b5); measured on re-saved slots only: right date 2/2 on the holiday case, own-date case 0/2 -> 2/2 |
| below-floor / after-deadline promise recorded (M2) | idea/b5-4 3aeb428 guards.py | (merge/b5); never fired on A/B in v1 (the model's choices were valid but wrong: M27) |
| invented floor named before the labelled one (M27) | none: a check_promise_amount tool (same pattern) or a code-rendered floor sentence | **open, top fast failure** |
| rule kinds dropped by the date schema (M3) | idea/b5-4 datecalc.py (roll, rounding, cut-off, min days, gap, unhandled_rules) | (merge/b5); cut-off kind seen failing on the C check |
| call ends without close / model goodbye (M26) / blocked close hangs up (M19) | idea/b5-1 ddc2695, e8e891f, bfa3791 canned.close_structure | (merge/b5); only the OFFICIAL scorer can measure it |
| "recorded" in the opening (judge) | idea/b5-5 2036739 gated words + opening rewrite | (merge/b5); official-only; mind M33 |
| invented ids + retries; bank accepts invented ids on notes (M7) | merge/b2, merge/b3 harden id resolver (`ids_to_use`) | **still not in main or merge/b5**; ~17 b5 fast failures |
| identity: no verdict for wrong answers, re-sent answers, no stop at 0 left (M29) | none (main's harden.py only annotates passes) | **open** |
| wrong route: cannot pay -> own plan (M22) | idea/b5-3 situations.py + router/specialist recipe (silent hand-off commit) | not merged; best cannot-pay -> transfer rate of the batch (5/6); hand-off fix measured once |
| per-item attempts / binding (M13/M23) | none working: idea/b5-2 A5 loop 0/3 (M30); idea/b4-1 items.py (M20) | open; next try: per-item settle tool with explicit args |
| close in parallel with notes (M12) | idea/b3-3 wrap_up node; A5 readback node (b5-2) | unmeasured / failed |
| build "succeeds" with no build agent when the Claude token is missing | none | **open, Sunday risk**: fail loudly |
| build dies on inner Claude quota (M9) | merged into main in b4 | done |

## 5. Variance sources (pass in one run, fail in another)

- a value left to the model among several candidates (which deadline, which floor, which item's date): M1/M2/M23;
- parallel tool calls in one turn: order of close vs notes, and lost hook state, differ per run (M12/M20);
- per-item and "once only" counts in the model's head (M13/M21);
- the simulated customer: talkative/asks_back styles push the model off the rule order ("what do you suggest?" makes
  it invent a floor); the fast customer may refuse every allowed offer, "correct" to a date the case does not expect,
  or move every item to one date;
- the fast judge: (a) transcript fetched before the agent's FINAL message is saved, so closing sentences look missing
  (seen on 19k-char transcripts: not truncation; main's fast_eval still fetches once); (b) old 30k-tail truncation of
  the raw transcript (fixed on main: judge sees dialogue + tool calls only). Re-judging flipped whole cases to pass.
  The official judge sometimes counts the recording notice as a premature "recorded" claim;
- platform: 5xx, timeouts, branch-resume replays under load (cap concurrent chats; workspace 2 is quieter);
- fast vs official: official-only kinds (opening wording, hang-up without close) and fast-heavy kinds (invented floor)
  mean fast_eval alone cannot rank w1/w5-type changes; fast_eval ends chats itself, so it never sees platform hang-ups;
- build-to-build variance is real (same builder scored 0/10 and 6/10 on clean vs raw brief in one batch) but is not
  the main source of judge-visible defects (M17).
