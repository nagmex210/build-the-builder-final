# Mechanisms (maintained by the standing analyst)

General rules only: no case ids, names, brief values or scenario details. Evidence is in runs/analyst/<batch>.md
(b7: `git show merge/b7:runs/analyst/b7.md`, never merged to main) and fix/cases:runs/mechanisms.md.
Last update: after batch b8 workers + the aborted b7 merge (2026-10-11 ~07:40 UTC).

## 0. Read first (b8)

- **The b7 merge candidate after its two fixes (merge/b7 66d7282) beat the champion OFFICIALLY on A and raw-B, tied B and raw-A**:
  A 9/10, B 2/3, rA 10/10, rB 3/3 = 24 vs champion (b6) 7+2+10+1 = 20; fast 14/26 vs 12; C 3/12 vs 1-2. The abort
  was on the PRE-fix 0/3 raw-B (hook over the size limit, M53). Re-measure it or carry its fixes (section 4).
- **Self-simulation has been a no-op since b7**: workspace 2 answers 402 Insufficient credits, every build logs
  "self-test 1: 0/0 personas" and the trace still says a self-test ran (M55). All b7 merge and b8 builds lack it.
- **Platform hook limit 131072 bytes (code + data)**; main's biggest hooks are 88-107 KB (M53).

## 1. Failure kinds (running counts, primary kind per failing run, platform-dead runs excluded)

| kind | b1-b5 | b6 | b7 | b8 (63 fails, digest) | total | at fault |
|---|---|---|---|---|---|---|
| dates: deadline as TARGET; callback date resolved by the model (stale year, outside window) | ~73 | ~8 | ~20 | 5 (all callback, stale year) | ~106 | builder |
| amounts: invented "minimum" before the labelled floor | ~37 | ~17 | ~19 | 3 (only where the check tool was not called) | ~76 | builder |
| tool order / duplicates (invented ids then retries; re-sent writes after success) | ~58 | ~22 | ~6 | 7 | ~93 | builder |
| per-item attempts / outcome counted wrong (incl. counteroffer counted as a refusal) | ~37 | ~10 | ~8 | 6 | ~61 | builder |
| multi-product binding (one date for all, values swapped, an item never written) | ~38 | ~9 | ~8 | 4 | ~59 | builder |
| identity gate (verdict misread, no stop at 0 left, answer never checked, parallel verify) | ~26 | ~11 | ~16 | 5 | ~58 | builder |
| wrong route (own plan instead of transfer; router with no matching transition loops) | ~20 | ~8 | ~8 | 7 | ~43 | builder |
| "once only" broken (floor twice; support/sympathy twice) | ~18 | ~7 | ~1 | 3 | ~29 | builder |
| mandatory wording / honesty | ~29 | 4 | ~13 | 1 | ~47 | builder |
| call ended without close (goodbye -> platform end_call; max node turns) | official only | - | official rB 2/3, A 1/2 | - | | builder+platform |
| build defect shipped (hook raises; field dropped; hook over size limit; unbound {{var}}; stale slot reused) | 1 official | caught | rB 0/3, B 0/3 official (pre-fix) | 2 branches 0-1/10 (size), 2/9 builds (w3) | | builder |
| harness: fast judge misses what IS in the transcript; persona leaks correct identity data | ~78 | 24 | ~18 | 4 | ~124 | harness |
| platform: timeouts / branch-resume / 402 / 404 under load | heavy | ~19 | 8 | 16 (most = hook size, really builder) | - | platform |

b8: 110 digested calls (8 evals; most worker evals did not finish under load), 47 pass. With the amount check
(b8-4) no invented round figure appeared where the check was called; callback dates are now the top date kind.

## 2. General mechanisms (each holds for ANY collections brief)

Values and dates
M1/M2. Show only this customer's facts; compute dates/amounts in code, one labelled line per product; a guard on the
    write blocks a wrong value with reason + right value (2xx ok=false), but too late for "offered once" (M27).
M3. Every date/amount rule reaches code or is listed "not computed, apply yourself"; a schema with no slot drops it
    silently (call-wide caps, stage order M34).
M27. The value to OFFER comes from code. Dates: a code-only check tool answering "keep the customer's day" / the one
    date (dates ~38 -> ~8). Amounts: a code-only amount check (customer's amount, or 0 for "too much / you tell me")
    answering the one sentence removed every invented minimum where it was called (b7-2 4/4, b8-4 all read calls);
    official floor-twice case 2/2 on merge/b7 (1/2 in every earlier official run). Residuals: the model names a
    figure WITHOUT calling the check (on a plan-request path), or restates the floor from memory with the day (judge:
    second offer): the first answer must say "amount settled, ask only for the day". Callback days still have no
    code path: stale year, valid slot answered "cannot" even after the tool listed the allowed day (b8 5/5 date fails).
M50. Calendar semantics are brief rules (weekend days, holidays, same-day cut-off, "next <weekday>"): spec fields
    with a trace line each, never one bank's calendar wired in.
M28. A customer's own date or amount is never a refusal; the deadline is an upper bound, never a target.

Identity and privacy
M4/M29. Identity terminal state is decided by code and routed by structure (identity_state + say_next per state;
    failed -> terminal node). A per-answer success field is read as "verified"; text lines were ignored, routes held.
M5. One answer, one check (also volunteered, corrected, in words, in pieces); never re-send. An answer the model
    answers with "go on" is never checked: the bank's count lags, the gate never reaches 0. Two verify calls in one
    turn: the route can fire on a stale sibling result (M20).
M18. Before identity passes no account content, including the opening's purpose words (M33).

Tool calls and state
M7. Ids are copied from a listed line, never built. A code "ids to use" list + repair/refusal of an unlisted id in the
    write pre-hook (b7-1) and any code tool that answers an unknown id with the real list (b8-1/4/5) make the model
    retry with the right id. A refused NOTE is not re-sent: the model closes instead.
M12/M20/M32. Parallel tool calls in one turn: order not guaranteed, sibling hooks miss each other's state writes.
    Keep per-item state in SEPARATE call variables (one JSON ledger is overwritten by a sibling); one call per message.
M37/M44. Writes are idempotent and dedup touches only writes; but a "do not send again" answer does not stop the
    model re-sending on every courtesy turn (b8: 2 items x several re-sends). After the last write route to a node
    without write tools.
M19/M8/M11. Routes out of a guarded tool test its ok field only; a block is 2xx ok=false with its own reason.
M30/M38. Per-item values come from explicit tool arguments, not extraction. An OPTIONAL tool runs only on the happy
    path: b8 per-item gates were consulted AFTER the model had already made the next offer. A counter must sit on a
    path the model needs anyway (see M56).
M54. A failed account lookup (5xx, sandbox error) must route to a service-error/close path. An unconditional
    lookup -> negotiate transition lets the model negotiate with invented ids, amounts and deadlines (b8: every call
    of two hook-oversize builds; also on the held-out brief's error path).

Per-item and once-only
M13/M21. Per-item counters and call-wide "once only" flags live in code and are shown each turn.
M56. A per-item gate fails in two ways (b8-1 live): (a) the model calls it late, after speaking the next offer;
    (b) the model labels the event: a counteroffer (a day or an amount of their own) was sent as "declined"
    and the item noted refused (2/3 calls). Rules: the model passes WHAT the customer said (a date / an amount /
    nothing), code classifies (a proposal goes to the value check, never counts); count attempts where the model
    must go anyway to get the value it will say (each floor/date offer comes from the check tool, so the check call
    IS the attempt counter), and block the write/close of an item whose budget state disagrees.
M23. Multi-product: bind amount, date, id per item; a late "same date for all" never overwrites an item's own valid
    date; every item gets its write (needs per-item agreed values in code).

Routes, hand-offs, closing
M22. A required exit (cannot pay even the floor / plan request -> transfer) needs triggers + a transition in EVERY
    node where it can come up.
M31/M40/M46/M48. Router + specialists: the hand-off is silent and structural; every tool-call transition needs an
    explicit condition; a router that sees account content but has no write tool negotiates and fakes the write; a
    router whose only exit is a failure branch loops "is that correct?" to max turns ("No transition matched").
    Check at build time: from every node holding account content, a route to the write tools exists.
M26/M35. The goodbye belongs to the platform after close succeeded; override the default end_call agent_config.
    A looping node hits max node turns and ends with no close (official only): code-route to a wrap-up node.
M6/M24/M10/M14/M15/M16/M33/M34. Close is last (code, not prompt); mandatory lines in the tool result verbatim;
    any payment word to a third party discloses; after "no" ask what to change; route on persisted vars under
    replays; reworded mandatory text keeps content and position; stage order is a brief rule.

Build robustness
M9. A failing step never takes the build down. A run that saved nothing must FAIL, never print the previous build's
    ids (seen b6 x2, b7, b8: missing Claude login -> "build" in ~1 min exporting the old agent).
M53. The platform caps one hook's code + data at 131072 bytes; over it, EVERY call of that tool errors with
    function_call_error. Seen 3 times (b7 merge raw-B account hook 136 KB -> official 0/3; b8-1 on C 156 KB; b8-5
    158 KB -> 0/10). main's hooks are 88-107 KB: a longer brief (more holidays/bands/rule text in the hex SPEC) can
    cross it. Embed only the functions and spec keys a hook uses; fail the build check on any hook > ~110 KB.
M57. Local builds reuse the slot's old files (out/<slot>.workflow.prev.json, an old generator script): the inner
    agent edited them instead of building from the brief (2/9 builds, b8-3), so one commit measured an older
    builder. On Sunday the slot is new: clear the slot before every test build.
M58. Static defects the model then reads raw (unbound {{var}} in a prompt) appear in ~8% of builds; a deterministic
    post-build check + one EDIT round fixed every one in < 20 s (b8-3). Reachability: an unreachable negotiate node
    (b8-4 B build) is a static defect too.
M45/M47/M49/M51. Dry-run every hook at save (post hooks get vars, not config); raise the SDK buffer; finalizers strip
    their own old blocks by signature; read API keys by shape, not A/B's names.
M55. A self-test that ran 0 chats must say so in the trace and fall back (workspace 1, or offline personas); a
    silent 0/0 is reported as a pass and disables every fix round that depends on it.
M17/M25/M52. LLM mistake counts / best-of-N cannot pick builds; rule TEXT coverage is 92-97% already: remaining
    failures are structural (who decides a value, which node holds which tool, which state routes).

## 3. What carries the calls that pass (keep intact)

- Structural routing on tool-result fields (identity -> account on the all-verified field; close -> end on ok).
- Account loaded by a code path; products, band, deadline, floor in state first.
- Code answers the model can copy: date/amount check "offer exactly ...", guard NOT RECORDED + right value,
  identity say_next, SAY NEXT lines; an unknown id answered with the real ids.
- Short decision chains; each extra decision left to the model is a coin-flip point.
- Hardship: one sympathy sentence, one support offer, close. Multi-product: all items before the first ask, one
  combined read-back.

## 4. Carry-overs (fix exists off main; champion main 37451d5 still shows the failure)

| failure kind still on main | branch / commit with the fix | status |
|---|---|---|
| hook over 128 KB (M53); tool names with '/' in the calc spec -> no guard (official B 0/3) | merge/b7 66d7282 (compact spec) + cedb5ea | **official on merge/b7: A 9, B 2, rA 10, rB 3 (best ever)**; size flag now in main hookcheck (b03d0a9, b8 merge); shrinking hooks still only on merge/b7 66d7282, b8-1 fc3beb3, b8-5 83381f9 |
| invented floor / floor twice (M27) | idea/b7-2 0e86b1b check_promise_amount; idea/b8-4 39e86d1..af9d73e (amount in check_promise_date + floor_offered count) | b7-2 is in merge/b7 (official floor case 2/2); b8-4 rA 6/10 = champion, A 5/10 (noise) |
| silent stale build when nothing saved (M9); stale slot files (M57); unbound vars / reachability (M58) | idea/b8-3 d3b1ed9, 1454263, bbfc17e buildcheck.py | measured: 2/9 -> 0/9 defects, 2/9 -> 0/9 stale reuse; no score effect expected |
| condition-less transitions (M46), SDK buffer (M47) | idea/b7-2 8d47ffc, 4723aef (in merge/b7) | pure robustness |
| invented ids + retries (M7) | idea/b7-1 e9dfe52 + cca104a (in merge/b7) | official rB 3/3 on merge/b7 |
| per-item attempts (owner target, official B residual 1/2) | idea/b8-1 gates.py (close gate, note gate, item_gate), idea/b8-2 itemgate.py (separate vars), idea/b8-5 policy.py | b8-1 rB 0/3 fast (gate late + counteroffer labelled refusal, M56); b8-2/b8-5 v2 unmeasured |
| lookup failure routes into negotiation (M54) | none | open |
| self-test 0 chats reported as run (M55) | none | **open: A17 is currently a no-op** |
| callback date resolved by the model (M27) | none | open, top date kind |
| platform end_call path (M26) | idea/b6-5 899dd95 | official only |
| calendar semantics (M50), call-wide cap (M3), stage order (M34) | none | open, held-out C |

## 5. Variance sources (pass in one run, fail in another)

- a value left to the model among candidates (floor, date, item id): M2/M7/M23/M27; a label left to the model
  (refusal vs counteroffer): M56;
- parallel tool calls (order, lost hook state): M12/M20; optional tools skipped or called late: M38/M56;
- the simulated customer: "you tell me" -> floor restated; fast personas leak correct identity data, revise every
  item to one date;
- the fast judge: transcript fetched before final turns (~10%); fast B lower bound (merge/b7: fast B 1/3, rB 2/3 vs
  official 2/3, 3/3): never rank B changes by one fast case;
- the BUILD: stale slot files (M57), static defects (M58), hook size near the limit (M53), self-sim silently off
  (M55): the same commit builds different agents; compare builds made under the same conditions;
- platform: 402/404/5xx, branch-resume under load (20+ parallel fast_evals in b8: most never finished).
