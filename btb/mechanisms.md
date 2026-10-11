# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md
(b7: `git show merge/b7:runs/analyst/b7.md`) and fix/cases:runs/mechanisms.md.
Last update: after batch b9 workers + the b8 merge (2026-10-11 ~09:45 UTC). Champion = b8 merge a575bbf.

## 0. Read first (b9)

- **Fast (chat) evals do not run the workflow's INITIAL node** (b9-5, M59). The official simulation does. So every
  chat measurement (fast_eval A/B/raw, all of brief C, the chat self-test) ran WITHOUT the start code node: no
  `{{date_facts}}` until a tool result carries them. b8 merge: fast A 4/10 vs official 8/10, fast rB 0/3 vs
  official 3/3. Fast date failures before b9-5 are partly harness; never rank a date change on fast evals without M59 fixed.
- **Official residuals of the champion are hardship once-only + the turn before routing** (M60): the customer states
  hardship before the account is loaded or before the router has routed; sympathy is said there, then again in the
  specialist, and a payment ask comes in between. Official A 0/2, rA 0/1 on that kind; floor offered twice 1/2.
- **Identity can stick with both answers passed** (M61): the code state waits for the bank's call-wide flag; when the
  flag is missing the call stays in identity and the model INVENTS account content (seen official rA, fast A).
- b9 measured almost nothing: about 30 fast_evals ran at once and none finished in 55 min (platform 500/502/503/504,
  branch resumes). Judge b9 mechanisms by their offline/live repro evidence, not by scores.

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b6 | b7 | b8 | b9 (b8 merge fast + w1 rA; 53 fails) | total | at fault |
|---|---|---|---|---|---|---|
| dates: deadline as TARGET; date resolved by the model (stale year, wrong weekday, one day off) | ~81 | ~20 | 5 | 7 (most on chat without date facts, M59) | ~113 | builder (+harness M59) |
| amounts: invented "minimum" / floor restated | ~54 | ~19 | 3 | 3 (floor said again with no tool call, M62) | ~79 | builder |
| tool order / duplicates (invented ids then a second write; re-sent writes; repeated transfer) | ~80 | ~6 | 7 | 9 (fast B: every fail had display ids built by the model) | ~102 | builder |
| per-item attempts / outcome counted wrong | ~47 | ~8 | 6 | 4 | ~65 | builder |
| multi-product binding (one date for all, item never written, call-wide cap lost) | ~47 | ~8 | 4 | 10 (6 on C) | ~69 | builder |
| identity gate (no stop at 0 left; stuck after both passed; account invented in identity) | ~37 | ~16 | 5 | 4 + official rA 1 | ~63 | builder |
| wrong route (own plan instead of transfer; hardship stated before the router) | ~28 | ~8 | 7 | 3 + official A 2 | ~48 | builder |
| "once only" broken (floor twice; sympathy/support twice) | ~25 | ~1 | 3 | 2 + official 3 | ~34 | builder |
| mandatory wording / honesty ("recorded" after NOT RECORDED) | ~33 | ~13 | 1 | 2 (own gate bug, fixed) | ~49 | builder |
| build defect shipped (hook raises / does not compile; field dropped; size; unbound {{var}}) | 1 off. | 2 off. | 2 br. | 1 branch (b9-4 v2 check hook did not compile, lint saw it, build saved) | | builder |
| harness: fast judge misses what IS in the transcript; persona leaks; start node skipped on chat | ~102 | ~18 | 4 | 8 + M59 | ~132 | harness |
| platform: timeouts / branch-resume / 402 / 5xx / DNS of the C bank tunnel | heavy | 8 | 16 | 3 + all b9 evals | - | platform |

## 2. General mechanisms (each holds for ANY collections brief)

Values and dates
M1/M2. Show only this customer's facts; compute dates/amounts in code, one labelled line per product; a guard on the
    write blocks a wrong value with reason + right value (2xx ok=false), but too late for "offered once" (M27).
M3. Every date/amount rule reaches code or is listed "not computed, apply yourself"; a schema with no slot drops it
    silently (call-wide caps, stage order M34).
M27. The value to OFFER comes from code (date check / amount check: "keep the customer's day", the one sentence);
    invented minimums vanished where the check was called. Residuals: a figure named WITHOUT calling the check;
    the model overriding a "keep the customer's date" answer (fast rB); callback days still have no code path.
M50. Calendar semantics (weekend days, holidays, cut-off, "next <weekday>") are brief rules: spec fields + trace line.
M28. A customer's own date or amount is never a refusal; the deadline is an upper bound, never a target.

Identity and privacy
M4/M29. Identity terminal state is decided by code and routed by structure (identity_state + say_next per state).
M61. The code state must be computable from the call's OWN ledger (required questions passed in this call) when the
    bank's call-wide flag is missing or stale; waiting on the bank flag alone left a fully verified call in the
    identity node, and a node with no lookup tool then INVENTED account details (product, balance, due date) when
    the customer pressed. Any node where account talk can come up needs either the lookup or a hard "no data" path.
M5. One answer, one check; never re-send. Two verify calls in one turn: the route can fire on a stale sibling (M20).
M18. Before identity passes no account content, including the opening's purpose words (M33).

Tool calls and state
M7. Ids are copied from a listed line, never built. Answering an unknown id with the real list makes the model retry,
    but the retry is a SECOND write for that item (judge: one call per item): repair the id in the write PRE-hook to
    the one listed row it can only mean (type + card/account ending), refuse only when ambiguous.
M12/M20/M32. Parallel tool calls: order not guaranteed, sibling hooks miss each other's writes: one variable per item.
M37/M44. Writes are idempotent; a "do not send again" answer does not stop re-sends on courtesy turns. After the last
    write (and after a transfer) route to a node WITHOUT write tools (presence gating, b9-3 gating.py).
M19/M8/M11. Routes out of a guarded tool test its ok field only; a block is 2xx ok=false with its own reason.
M30/M38/M56. Per-item values come from explicit tool arguments. An optional gate tool is called late or fed a
    model-made label (a counteroffer sent as "declined"): the model passes WHAT was said, code classifies; counts come
    from CONFIRMED writes only (counting the in-flight write refused a legitimate retry after a service error and
    the model then said "recorded"); block the write/close of an item whose budget state disagrees.
M54. A failed account lookup must route to a service-error/close path, never into negotiation.
M23. Multi-product: bind amount, date, id per item; call-wide caps and an agreed common date need code slots.

Once-only and the turn before routing
M13/M21. Per-item counters and call-wide "once only" flags live in code and are shown each turn.
M62. A once-only line is repeated in the NEXT turn of the same node with no tool call (floor restated on "what should
    I pay?", support offered again after a reply): a tool-side counter never sees it. Fix in the graph: the entry turn
    and the following turns are different nodes (talk -> after), the after-node states "already said: never again",
    and a call-wide said-list set by code is shown in every later node (b9-4 once.py, unmeasured).
M60. The turn between identity pass and routing (account-loading node that speaks, router) has no hardship/transfer
    exit: the customer's first hardship statement is answered there (sympathy #1, then a payment ask), and the
    specialist repeats it. Load the account silently (api/code node, no spoken turn) and give the router the
    situation exits on the FIRST statement; the hand-off is silent (M40).

Routes, hand-offs, closing
M22. A required exit (cannot pay the floor / plan request -> transfer) needs triggers + a transition in EVERY node where
    it can come up; fast A: a "something more manageable" request was negotiated, never transferred.
M31/M40/M46/M48. Router + specialists: silent structural hand-off; every tool-call transition has a condition; a router
    seeing account content without write tools fakes writes; a router with only a failure exit loops.
M26/M35. The goodbye belongs to the platform after close succeeded; a looping node hits max turns with no close.
M6/M24/M10/M14/M15/M16/M33/M34. Close is last (code); mandatory lines in the tool result verbatim; reworded mandatory
    text keeps content and position; stage order is a brief rule.

Build and measurement robustness
M9/M57/M58. A run that saved nothing FAILS; clear the slot before a build; deterministic post-build checks (unbound
    {{var}}, reachability) + one EDIT round (on main since b8). Gap: a hook that does not COMPILE is a lint error
    but buildcheck does not fail/repair it (b9-4 shipped 3 such builds): wire hook lint errors into the repair round.
M53. Platform caps one hook's code + data at 131072 bytes; over it every call of that tool errors. Put spec/library
    only in the hooks that use them (b9-1: gate data only in write/close/transfer hooks, largest 55 KB).
M59. The chat endpoint skips the INITIAL node's pre_actions; a code node entered later does run. Anything the start
    chain computes (today, date facts, ledgers) is absent on chat. Re-run the start chain on the opening's exits
    (b9-5 livevars.py, idempotent) and check one live chat after save. Until then fast evals mis-measure dates.
M55. The self-test runs on chat too: workspace 2 answers 402 (no credits) -> fall back to workspace 1 with true counts
    in the trace (b9-2: 6/6 chats in ws1, build 18 min); with M59 unfixed the self-test also runs without date facts.
M45/M47/M49/M51. Dry-run hooks at save; raise SDK buffer; finalizers strip their own blocks; API keys by shape.
M17/M25/M52. LLM mistake counts / best-of-N cannot pick builds; remaining failures are structural.
M63. Gates as data (b9-1 gategraph: AND/OR/XOR/AT_MOST/AT_LEAST/CHAIN over code atoms, linted, boundary-tested
    offline, soft except per-item write caps): an extracted gate must be droppable when the guarded action cannot
    raise the counted quantity, else it blocks a transfer the brief demands; fail-open on unknown atoms.

## 3. What carries the calls that pass (keep intact)

- Structural routing on tool-result fields (identity -> account on the all-verified field; close -> end on ok).
- Account loaded by a code/api path; products, band, deadline, floor, date facts in the account result.
- Code answers the model can copy: date/amount check, guard NOT RECORDED + right value, identity say_next.
- Short decision chains; hardship: one sympathy sentence, one support offer, close; multi-product: all items before
  the first ask, one combined read-back.

## 4. Carry-overs (fix exists off main; champion a575bbf still shows the failure)

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| start node skipped on chat (M59): fast evals and C without date facts | idea/b9-5 381aa28 + b300c7d livevars.py | being merged (merge/b9 b1efc99); live repro before/after on the held-out brief |
| self-test 0 chats (M55) | idea/b9-2 8e97261..dfc5b06 | being merged (merge/b9 e29bb78); +15 min build time |
| invented display ids -> second write per item (M7) | idea/b7-1 e9dfe52 + cca104a (pre-hook repair); idea/b8-1 6738f0d / b9-1 gates.py (display id -> ledger row) | not on main; fast B/rB every fail |
| once-only repeated next turn (M62), official A residual | idea/b9-4 932daa9 once.py (use 932daa9+) | unmeasured; B/rB v2 builds broken, do not score them |
| hardship before routing (M60) | none (b9-4 does not cover the router's sentence) | open, official A 0/2 |
| identity stuck when bank flag missing (M61) | none | open, official rA 1 |
| re-sent writes, writes after transfer/close, 2nd note per item (M37/M44) | idea/b9-3 6267143 gating.py (presence gating, BTB_GATING=0 to disable) | unmeasured; offline idempotent, lint 0 on 5 builds |
| per-item attempts (M56) | idea/b9-1 89465e8 (gate graph, confirmed-write counts) | rA v1 4/10 fast (own bugs, fixed after); v2 unmeasured |
| hook compile error not repaired (M58 gap) | none | open |
| lookup failure into negotiation (M54); callback date by the model (M27); calendar semantics (M50) | none | open |

## 5. Variance sources (pass in one run, fail in another)

- a value or label left to the model (floor, date, item id, refusal vs counteroffer): M2/M7/M23/M27/M56;
- parallel tool calls and optional tools called late: M12/M20/M38/M56;
- WHERE the customer first says it: before routing (M60) vs inside the specialist;
- the bank mock: call-wide identity flag present in one run, missing in another (M61);
- the simulated customer: "you tell me" -> floor restated; fast personas leak identity data;
- the harness: chat skips the start node (M59: fast date cases fail that pass officially); fast judge misses ~10%;
  fast B is a lower bound (b8 merge fast B 1/3, rB 0/3 vs official 3/3, 3/3);
- the BUILD: stale slot (M57), static defects (M58), hook size (M53), self-sim off (M55);
- platform: 402/5xx, branch-resume; >20 parallel fast_evals = nothing finishes (b8, b9).
