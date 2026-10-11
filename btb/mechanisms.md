# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md and
fix/cases:runs/mechanisms.md. Last update: after batch b6 workers (2026-10-11 ~03:15 UTC).

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b2 | b3 | b4 | b5 | b6 (240 fast, digest) | total | at fault |
|---|---|---|---|---|---|---|---|
| dates: deadline used as the TARGET (holiday / valid earlier / own day answered with the deadline); callback date resolved by the model (stale year, outside window) | 17 | 1 | 17 | ~38 | ~8 | ~81 | builder |
| amounts: invented "minimum" (small round number) named before the labelled floor | 7 | 0 | 8 | ~22 | ~17 | ~54 | builder |
| tool order / duplicates (invented ids then retries; re-sent writes after success; no-op answer without routing fields) | 24 | 2 | 15 | ~17 | ~22 | ~80 | builder |
| per-item attempts / outcome counted wrong | 7 | 1 | 13 | ~16 | ~10 | ~47 | builder |
| multi-product binding (one date for all, values swapped, an item never written) | (per-item) | - | 28 | ~10 | ~9 | ~47 | builder |
| identity gate (one passed answer read as "verified", no stop at 0 left, volunteered answer never checked) | 8 | 2 | 6 | ~10 | ~11 | ~37 | builder |
| wrong route: cannot pay -> own plan instead of the brief's transfer | 3 | 0 | 8 | ~9 | ~8 | ~28 | builder |
| "once only" broken (floor twice; support/sympathy twice incl. hand-off re-entry) | 0 | 0 | 12 | ~6 | ~7 | ~25 | builder |
| mandatory wording | 6 | 1 | 2 | 7 | 2 | 18 | builder |
| honesty ("noted"/"I have you down" before the tool says so) | 0 | 2 | 1 | 3 | 2 | 8 | builder |
| call ended without close (model goodbye -> platform end_call; node max-turns -> end node) | some | - | 3 official | 1 official | fast cannot see it | | builder+platform |
| build defect shipped (inner agent's hook raises on every call; required field dropped) | - | - | - | 1 official B 0/3 | caught by w1 hookcheck | | builder |
| harness: fast judge misses lines/tools that ARE in the transcript; persona answers the "wrong" identity data right | 11 | 6 | ~42 | 19 | 24 | ~102 | harness |
| platform: timeouts / branch-resume replays (INVALID) | heavy | ~55/69 | low | 30 | ~19 (one rA eval 15/20) | - | platform |

b6: 108/240 worker fast calls pass. Dates fell from ~38 to ~8 since check_promise_date (b5-4, in main). Official
(b5 merge): the only official residual on brief A is the identity gate (0/4 on the merged build); fast-only heavy
kinds: invented floor (official 4/4 pass), callback date.

## 2. General mechanisms (each holds for ANY collections brief)

Values and dates
M1. Show only this customer's facts and tag only their own deadlines. Necessary, not sufficient (M27).
M2. Dates and amounts are computed in code, one labelled line per product; a guard on the write tool blocks a
    below-floor amount / after-deadline date with the reason and the right value (2xx, ok=false: M11). The model
    recovers from the block, but the block comes after the offer, so "offered once" is already broken.
M3. Every date/amount rule in the brief reaches code or is listed "not computed, apply yourself"; a schema with no slot
    drops it silently. Includes call-wide caps (a total per call across items) and stage order (M34).
M27. The value to OFFER comes from code, not only the value to RECORD. Dates: the code-only check tool answers "keep
    the customer's day" or the one date to offer: works (dates ~38 -> ~8). Amounts: still open. The labelled floor IS
    in the lookup result (twice, under two names) and the model still names a small round "minimum" on the turn after
    "too much"; then after the guard block it offers the floor with the deadline instead of the agreed day. Needed: a
    code-rendered offer sentence (the result's SAY NEXT for "cannot pay the full amount" = the floor sentence with the
    customer's/next valid day) or a check_promise_amount tool. Callbacks need the same: the model resolves relative
    callback days itself (stale year, day outside the window) despite the date facts.
M28. A customer's own date or amount is never a refusal; the deadline is an upper bound, never a target.

Identity and privacy
M4. A gate's terminal state is decided by code and routed by structure. Identity: code writes identity_state
    (passed / asking next / retry / failed) + one say_next per state into every verify result; a transition on
    state == failed goes to a terminal node that says the referral line once and closes (b6-4: 2/2 on the failing
    case where prompt lines alone went 0/4 officially).
M29. A per-answer success field ("this answer correct") is read by the model as "identity verified": it says so,
    moves to the account and, with no account loaded, INVENTS an amount. Every result needs an overall verdict line;
    at 0 left the terminal route, not a prompt line, must fire (a NOT VERIFIED text line was ignored 2/4 officially).
M5. One answer, one check: every answer (also one volunteered mid-sentence or "corrected" before checking) goes to the
    check tool at once; never re-send a passed or earlier wrong answer (pre-hook block).
M18. Before identity passes no account content at all; the opening's purpose words count too (a gate list of
    debt words must include the brief's own purpose words: M33).

Tool calls and state
M7. Ids are copied from a listed line, never built: the model writes the display id (card digits, type label) and the
    retry breaks "one write per item". b6: the top multi-item failure on all 5 branches; the resolver exists
    on an old branch and is still not in main (carry-over).
M12. Several tool calls in ONE turn run in parallel: close + notes in one turn lands notes after close.
M20/M32. Hook state is not reliable across one parallel turn (sibling hooks miss each other's writes; same-tool
    siblings share one result variable). Never decide from writes issued in the same turn; one call per message.
M37. Idempotency for writes is needed (a courtesy turn after success re-sends the write; the bank answers "already
    exists"; the model notes a service error), but dedup must touch only state-changing writes and its no-op answer
    must carry every field the outgoing routes test. Dedup applied to a check tool returned an answer without the
    all-verified field: routing stuck in identity, model improvised (4 calls).
M44. After a successful terminal write (promise, transfer) the node still holds the write tool, so a goodbye turn
    re-triggers it. Route on success to a wrap-up node without write tools, or make the write idempotent (M37).
M19. Routes out of a guarded tool test the result's ok field only (success_count counts guard no-ops).
M8/M11. A guard never blanks fields; a block is a 2xx with ok=false and the reason.
M30. Extraction is not a data path for values the model agreed ("yes" extracts nothing). Per-item values come from a
    tool call's explicit arguments: live-verified (settle tool with args, b6-2).
M38. An OPTIONAL bookkeeping tool is called only on the happy path (settle called for promises, never for refusals:
    the per-item refusal counter never ran). A counter must sit on a path the model cannot skip: the write tool and
    close refuse until every item is settled, or one check call before every offer returns the attempt number.

Per-item and once-only
M13. Per-item counters (attempts, outcome) live in code per item and are shown each turn; the late-band ladder
    otherwise spills onto an early-band item.
M21. "Once only" limits are call-wide; keep a flag per limit in state and show it every turn (floor re-offered
    with a new date is a second offer).
M23. Multi-product: bind amount, date and id per item; the read-back names every item; a late "same date for all"
    must not overwrite an item whose own date was already valid; every item gets its write.

Routes, hand-offs, closing
M22. A required exit (cannot pay even the floor / plan request -> transfer) needs named triggers and its own
    transition in EVERY node where it can come up; else the model invents a plan and closes as refused.
M31/M40. Router + specialists: the hand-off must be silent AND structural. A router that speaks and transitions in
    the same turn leaves the next customer turn on the router (platform branch-resume), which hands off again and
    the specialist repeats its offer; prompt rules ("hand off silently", "once per call") did not stop it (4/4).
    Use a code flag set on specialist entry that the router checks, or on_enter first-entry-only speech.
M26. The goodbye belongs to the platform after close succeeded (end node spoken_message on the close ok route); the
    platform's DEFAULT agent_config ships an end_call tool + "use it after you say goodbye": a model goodbye before
    close gets a platform hang-up with no outcome. Overriding agent_config after every save removes that path
    (b6-5, persists live; only the official simulator can show the effect). A brief that orders the goodbye BEFORE
    close needs the goodbye and the close in one message; that brings back "goodbye without close" (b5-1 v1: 18/20).
M35. A node that loops (identity never resolved) hits the platform's max node turns and jumps to the end node with
    no close: no outcome. Terminal states must be reached by routes long before max turns; keep max turns high.
M6/M24/M10. Close is last and the prompt alone does not order it; platform-spoken text is verbatim; a mandatory line
    tied to an event goes in that tool's success result ("say exactly ...").
M14. To a third party any sentence about payment, debt or the account discloses the purpose.
M15. After a "no" to a read-back ask what to change; never repeat the same read-back.
M16. Under platform load a chat can replay an old message; route on persisted call variables.
M33. Rewording a mandatory text to dodge a literal judge keeps the brief's content AND position.
M34. The builder's fixed stage order (opening -> identity -> account) can contradict the brief; stage order is a rule.

Build robustness
M9. A failing build step never takes the build down (falls through to the deterministic final pass). But a missing
    Claude login yields a ~1-minute "build" with no build agent and no error (seen again on 2 workers in b6).
M45. The inner build agent can ship hooks that raise on every call (a post-hook referencing the request name):
    every tool call errors, nobody passes identity, and the self-sim revert restores an equally broken version.
    Dry-run every hook at save and repair/lint it; check API-required fields. A merger's diagnosis from the build log
    alone was wrong: read a self-sim call's tool results before blaming a field.
M17/M25. Best-of-N / LLM mistake counts cannot pick builds; deterministic ledger checks in self-sim find real kinds;
    one play per persona is too noisy for keep/revert.

## 3. What carries the calls that pass (keep intact)

- Structural routing on tool-result fields (identity -> account on the all-verified field; close -> end on ok).
- Account loaded by a code path; products, band, deadline, floor in state first.
- Code answers the model can copy: check tool's "offer exactly <date>", guard's NOT RECORDED + right value,
  identity say_next per state, what_to_do_next / SAY NEXT lines: said word for word.
- Short decision chains; each extra rule decision left to the model is a coin-flip point.
- Hardship: one sympathy sentence, one support offer, no persuasion, close. Tool failure: retry once, "recorded"
  only after SUCCESS. Multi-product: all items stated before the first ask, one combined read-back.

## 4. Carry-overs (fix exists on a non-champion branch; champion main f4dbaf0 still shows the failure)

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| identity: per-answer field read as verified, no terminal at 0 left, invented amount (M4/M29, top OFFICIAL residual) | idea/b6-4 c7ea014 identity_gate.py (+ selftest privacy lint) | fast 2/2 on the case; needs official |
| invented product ids + retries (M7), top multi-item failure | merge/b2 880dc5e + e859772 harden id resolver (`ids_to_use`) | **still not in main**; 14 b6 failures on all branches |
| duplicate write after success -> service error (M37/M44); hook that raises (M45); API-required field dropped | idea/b6-1 d73d17a..c2145da (harden idempotency, hookcheck.py, apicheck.py) | first version stuck identity routing (M37); fixed in c2145da, unmeasured |
| platform default end_call path (M26) | idea/b6-5 899dd95 override_agent_config | official only; take the override, weigh the pre-close goodbye mode separately |
| specialists' own clause / once-per-call / plan-request -> transfer (M22/M31) | idea/b6-3 11893d4 + 5db9db6 situations.apply | best fast A (8/10); hand-off re-entry (M40) open |
| per-item value path (M30) | idea/b6-2 2dc4330 settle_item | value path works; counter unused (M38): needs a mandatory gate |
| invented floor (M27 amounts) | none | **open, top fast failure** |
| callback date resolved by the model (M27) | none (check_promise_date covers promises only) | open |
| node loops to max turns -> end without close (M35) | none | open, official-only |
| build "succeeds" with no build agent when the Claude login is missing (M9) | none | **open, Sunday risk**: fail loudly |

## 5. Variance sources (pass in one run, fail in another)

- a value left to the model among several candidates (which floor, which date, which item's id): M2/M7/M23/M27;
- parallel tool calls in one turn (order of close vs notes; lost or shared hook state): M12/M20/M32;
- per-item and "once only" counts in the model's head (M13/M21); optional bookkeeping tools skipped (M38);
- the simulated customer: "what do you suggest?" makes the model invent a floor; fast personas may give CORRECT
  identity data on a case that expects failure, revise every item to one date, or never ask for a plan;
- the fast judge: transcript fetched before the final turns are saved (closing lines and late close_call look
  missing; ~10% of b6 failures); official judge reads the recording notice as a premature "recorded" claim;
- platform: 5xx, branch-resume replays under load (a router hand-off is especially exposed: M40); the box-wide eval
  slot lock has no queue order, and a 10-minute tool cap killed builds mid self-sim, so several b6 scores are of
  pre-self-sim saves (not comparable to full builds);
- fast vs official: official-only kinds (identity terminal, hang-up without close, opening wording) and fast-heavy
  kinds (invented floor, callback date): fast_eval alone cannot rank identity/goodbye/agent_config changes.
