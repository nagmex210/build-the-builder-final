# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md
(b7: `git show merge/b7:runs/analyst/b7.md`) and fix/cases:runs/mechanisms.md.
Last update: after batch b10 workers + the b9 merge (2026-10-11 ~12:50 UTC). Champion = b8 merge a575bbf (b9 not kept).

## 0. Read first (b10)

- **b10 measured nothing** (chat 500/502/504, 503 key validation, ws2 402): every b10 branch rests on offline repros,
  replays and build logs. Judge b10 mechanisms by that evidence, not by scores.
- **Build robustness is the top Sunday risk** (M67): under platform load the champion builder FAILED 10/12 builds on a
  single save 5xx (with ~13 of 30 min left) and silently ran 30/36 strong extractions on the small fallback model.
- **Fast (chat) evals skip the INITIAL node** (M59). The b9-5 re-run of the start chain on the opening's exits works on
  chat (date facts present from identity on), but tools used INSIDE the opening still have none (M64).
- **Official residuals of the champion**: once-only repeated in the next turn (M62), hardship before routing (M60),
  the last identity answer not sent to verify (M65), the bank's call-wide flag missing (M61). A visible said-list in
  context did NOT stop a repeat (b10-7 probe): once-only needs graph structure or a code gate.
- **Parallel tool calls, measured live** (b10-2 probe): a post-hook can read a SIBLING call's pre-hook vars, and
  `config` is absent in post-hooks. Any per-tool flag carried pre -> post may belong to another call (M66).

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b8 | b9 (53 fails) | b10 (b9 merge fast rA + w1-B; 13) | total | at fault |
|---|---|---|---|---|---|
| dates: deadline as TARGET; date resolved by the model (stale year, wrong weekday, one day off) | ~106 | 7 | 2 (stale callback year re-sent 4x in the opening M64; "tomorrow" read as past) | ~115 | builder (+harness M59) |
| amounts: invented "minimum" / floor restated | ~76 | 3 | 0 | ~79 | builder |
| tool order / duplicates (built ids then a 2nd write; re-sent writes; repeated transfer) | ~93 | 9 | 1 (built ids, M7) | ~103 | builder |
| per-item attempts / outcome counted wrong | ~61 | 4 | 0 | ~65 | builder |
| multi-product binding (one date for all, item never written, call-wide cap lost) | ~59 | 10 | 1 | ~70 | builder |
| identity gate (no stop at 0 left; stuck after pass; account invented; last answer unverified) | ~58 | 5 | 2 (M65; parallel re-sent verify M5) + official A 1 | ~66 | builder |
| wrong route (own plan instead of transfer; hardship stated before the router) | ~43 | 5 | 0 | ~48 | builder |
| "once only" broken (floor twice; sympathy/support twice) | ~29 | 5 | 3 + official A 2 | ~39 | builder |
| mandatory wording / honesty | ~47 | 2 | 1 + official A 1 (judge: "recorded" in the opening's call-recording line) | ~51 | builder/judge |
| build defect shipped / build failed | 3 off. + br. | 1 br. | champion 10/12 FAILED under load (w4); 30/36 extractions on fallback | | builder |
| harness: fast judge misses what IS there; persona leaks or self-corrects; start node skipped on chat | ~124 | 8 | 3 | ~135 | harness |
| platform: timeouts / branch-resume / 402 / 5xx / DNS | heavy | all b9 evals | all b10 evals | - | platform |

## 2. General mechanisms (each holds for ANY collections brief)

Values and dates
M1/M2. Show only this customer's facts; compute dates/amounts in code, one labelled line per product; a guard on the
    write blocks a wrong value with reason + right value (2xx ok=false), but too late for "offered once" (M27).
    Rounding order: the brief's rounding first, then the minimum; parse times, never compare "H:MM" strings (b10-1).
M3. Every date/amount rule reaches code or is listed "not computed, apply yourself"; a schema with no slot drops it.
M27. The value to OFFER comes from code (date/amount check: "keep the customer's day", one sentence). Residuals: a
    figure named WITHOUT calling the check; the model overriding "keep the customer's date"; callback dates.
M64. A refusal that LISTS the allowed values is not enough: the model said the right year aloud and re-sent the stale
    year in four writes. Every date guard must return ONE computed value to copy (as the promise date check does), and
    the pre-hook may repair a date whose month-day matches exactly one allowed day (date analogue of M7). Tools
    reachable in the opening (third party -> callback) have no date facts on chat even with the start chain re-run.
M50. Calendar semantics (weekend days, holidays, cut-off, "next <weekday>") are brief rules: spec fields + trace line.
M28. A customer's own date or amount is never a refusal; the deadline is an upper bound, never a target.

Identity and privacy
M4/M29. Identity terminal state is decided by code and routed by structure (identity_state + say_next per state).
M61. The code state must be computable from the call's OWN ledger (required questions passed in this call) when the
    bank's call-wide flag is missing, and "passed" must be sticky: a stale parallel sibling result (flag false) landed
    last and its "NOT verified" text made the judge fail a correctly routed call. Any node where account talk can come
    up needs either the lookup or a hard "no data" path (else the model INVENTS account details).
M65. With one attempt left, the model does not send the next answer to verify (asks again, "go on") and a later right
    answer passes: the "stop after N wrong" rule is broken by an uncounted attempt. The model must send EVERY answer;
    the identity say_next on the last attempt must say "send the next answer to the check, whatever it is". Open.
M5. One answer, one check; never re-send a passed question (seen in 3 of 5 fast transcripts, in parallel with the next
    question). A pre-hook could answer a passed field with a no-op instead of a bank call. Open.
M18. Before identity passes no account content, including the opening's purpose words (M33).

Tool calls and state
M7. Ids are copied from a listed line, never built. Answering an unknown id with the real list makes the model retry,
    but the retry is a SECOND write for the item: repair the id in the write PRE-hook to the one listed row it can only
    mean (type / last digits / initials), send unchanged when ambiguous (b10-2 R7).
M12/M20/M66. Parallel tool calls: order not guaranteed; a post-hook can read a sibling's pre vars; no `config` in post.
    So one variable per item, and a post-hook decides from the RESULT (the bank's success id field present = really
    recorded; a bare no-op 2xx = blocked), never from a per-tool flag (b10-2 R2).
M68. A bank REJECTION (2xx/4xx ok=false) and an OUTAGE (5xx/timeout) need different texts: "resend the same values" on a
    rejection invites a duplicate write; a guard block must not erase an earlier real failure count (b10-2 R1/R4).
M37/M44. Writes are idempotent; after the last write (and after a transfer) route to a node WITHOUT write tools.
M19/M8/M11. Routes out of a guarded tool test its ok field only; a block is 2xx ok=false with its own reason.
M30/M38/M56. Per-item values from explicit tool arguments; the model passes WHAT was said, code classifies; counts
    from CONFIRMED writes only; block the write/close of an item whose budget state disagrees.
M54. A failed account lookup must route to a service-error/close path, never into negotiation (still no route on main).
M23. Multi-product: bind amount, date, id per item; call-wide caps and an agreed common date need code slots.

Once-only and the turn before routing
M13/M21. Per-item counters and call-wide "once only" flags live in code and are shown each turn.
M62. A once-only line is repeated in the NEXT turn of the same node with no tool call ("you tell me" -> floor again;
    support offered again after a reply). A tool-side counter never sees it, and a context line "USED UP" was ignored
    (b10-7, n=1). Fix in the graph: entry turn and later turns are different nodes (talk -> after), the after-node says
    "already said: never again" (b9-4/b10-6 once.py, unmeasured).
M60. The turn between identity pass and routing has no hardship/transfer exit: sympathy #1 is said there, a payment ask
    follows, the specialist repeats it. Load the account silently, give the router the situation exits on the FIRST
    statement; the hand-off is silent (M40).

Routes, hand-offs, closing
M22. A required exit (cannot pay the floor / plan request -> transfer) needs triggers + a transition in EVERY node.
M31/M40/M46/M48. Router + specialists: silent structural hand-off; every tool-call transition has a condition; a router
    seeing account content without write tools fakes writes; a router with only a failure exit loops.
M26/M35. The goodbye belongs to the platform after close succeeded; a looping node hits max turns with no close.
M6/M24/M10/M14/M15/M16/M33/M34. Close is last (code); mandatory lines in the tool result verbatim; reworded mandatory
    text keeps content and position; stage order is a brief rule. A strict judge reads "recorded" in a call-recording
    notice as a premature claim: keep that word out of the opening.

Build and measurement robustness
M9/M57/M58. A run that saved nothing FAILS; clear the slot before a build (slot match must not treat '-' as a word
    boundary: a slot clears its prefix-sibling's files, b10-1); deterministic post-build checks + one EDIT round. Gap:
    a hook that does not COMPILE is a lint error but buildcheck does not fail/repair it.
M67. Platform calls in the build need retry with backoff within the budget (save PUT/POST, workspace GET, export GET);
    a build whose final save fails but whose agent saved in THIS run ships that save with a warning; a 429 from the
    model provider waits (Retry-After) before falling back, and every fallback is logged. Without this the extraction
    model silently drops a tier under load and the brief's exits vary between builds (3-4/6 common vs 6/6).
M55/M69. The self-test runs on chat: ws2 answers 402 -> ws1 fallback. A self-test with 0 completed chats must say
    "DID NOT RUN / untested", never "0/0 failed" (it was read as a pass in every b8-b10 trace); round 1 must respect
    the time left; stuck chat threads must not hold the process past BUILD END; an unreadable final ledger is a
    harness error, not an agent failure.
M70. The submitted trace must list every model call (including the coding agent's hidden helper model and failed
    provider calls) and every self-test chat with its result; the run script must be parsed before it runs (an edit or
    pull mid-run broke a running submission) (b10-5).
M53. One hook's code + data is capped at 131072 bytes; put spec/library only in the hooks that use them.
M59. The chat endpoint skips the INITIAL node's pre_actions; a code node entered later does run. Re-run the start chain
    on the opening's exits (b9-5 livevars, seen working on chat) and keep date-dependent tools out of the opening.
M45/M47/M49/M51. Dry-run hooks at save; raise SDK buffer; finalizers strip their own blocks; API keys by shape.
M17/M25/M52. LLM mistake counts / best-of-N cannot pick builds; remaining failures are structural.
M63. Gates as data (b9-1 gategraph): an extracted gate must be droppable when the guarded action cannot raise the
    counted quantity; fail-open on unknown atoms.

## 3. What carries the calls that pass (keep intact)

- Structural routing on tool-result fields (identity -> account on the all-verified field; close -> end on ok).
- Account loaded by a code/api path; products, band, deadline, floor, date facts in the account result.
- Code answers the model can copy: date/amount check ("CODE COMPUTED THE DATE TO OFFER"), guard NOT RECORDED + right
  value, identity say_next.
- Short decision chains; hardship: one sympathy sentence, one support offer, close; multi-product: all items before
  the first ask, one combined read-back.

## 4. Carry-overs (fix exists off main; champion a575bbf still shows the failure)

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| build FAILS on one save 5xx; silent model downgrade (M67) | idea/b10-4 4d2c7b7 (save_with_retry, own-save shipping, 429 wait) or idea/b10-1 53bd5f9 (locked_save 5xx retry) | 24/24 builds shipped (w4 rounds b/c); pick ONE save retry |
| self-test 0 chats read as pass; round-1 overrun; stuck threads (M69) | idea/b10-1 326efe7/1c56716/b733945; b10-4 b168809 + fd8fbb2 (ws1 fallback); b10-5 76a2e78 | repros; three overlapping "DID NOT RUN" fixes: take one |
| trace gaps, submit.sh mid-run edit (M70) | idea/b10-5 a52a3a0, de50d97, acda4c8 | before/after submit.sh runs on C + raw A |
| datecalc rounding order / unpadded cut-off; brief pasted twice; scrub split writes; clear_slot prefix | idea/b10-1 b733945, 731c934 | repros; 0 diffs on 24 900 random floors |
| parallel post-hook trusts a sibling's flag; block erases a failure; rejection says "resend" (M66/M68) | idea/b10-2 b405f88, ea7a079 | repro on real hook code + live probe |
| identity stuck when bank flag missing; stale sibling overwrites passed (M61) | idea/b10-2 618bf51 | repro (a)/(b) + negatives unchanged |
| built display ids -> second write per item (M7) | idea/b10-2 0e43e54 (minimal b7-1 port) | repro; fast B/rB every fail in b9 |
| start node skipped on chat (M59) | idea/b9-5 381aa28 + b300c7d livevars | in merge/b9 (not kept, cause of its drop not livevars) |
| once-only repeated next turn (M62) | idea/b10-6 68df7c2 (once.py, BTB_ONCE=1, default off) | 4 builds saved, 0 evals; memory tool b10-7 NO EFFECT |
| dead code | idea/b10-3 ab15884 | replay identical modulo removed snippets; conflicts with b10-2 hook text |
| re-sent writes, writes after transfer/close (M37/M44); per-item attempts (M56) | idea/b9-3 gating.py; idea/b9-1 gategraph | unmeasured |
| hardship before routing (M60); last identity answer unverified (M65); re-sent passed verify (M5); callback date to copy (M64); lookup failure route (M54); hook compile error not repaired (M58) | none | open |

## 5. Variance sources (pass in one run, fail in another)

- a value or label left to the model (floor, date, item id, refusal vs counteroffer): M2/M7/M23/M27/M56/M64;
- parallel tool calls (sibling vars, stale result last) and optional tools called late: M12/M20/M38/M56/M66;
- WHERE the customer first says it: before routing (M60) vs inside the specialist; in the opening (no date facts, M64);
- the bank mock: call-wide identity flag present in one run, missing in another (M61);
- the simulated customer: "you tell me" -> floor restated; fast personas leak identity data or self-correct answers;
- the harness: chat skips the start node (M59); fast judge misses ~10% (a recorded write read as missing);
- the judge: wording near a mandatory word ("this call is recorded") read as a premature claim;
- the BUILD: stale slot (M57), static defects (M58), hook size (M53), self-sim off (M55), extraction model tier (M67);
- platform: 402/5xx, branch-resume; >20 parallel fast_evals = nothing finishes (b8, b9, b10).
