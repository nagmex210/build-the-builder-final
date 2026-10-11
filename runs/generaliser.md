# Domain generaliser (2026-10-11)

Goal: the builder was tuned on collections. Every collections-specific step now runs only when its preconditions
hold; otherwise it does nothing. Nothing from the final case is written into `builder/` (no names, values, rules).

## How a case is classified

`builder/datecalc.py` first asks one cheap question about the case documents + tool API: is this a collections
case (overdue debt + a tool that records payment promises)? Kept as collections when the classifier errs, answers
anything other than a clear `false`, or the tool API mentions promises/payment arrangements (safety net: the
collections path must not be lost). `build.py` exports the answer as `BTB_COLLECTIONS=0|1` (inherited by the build
agent's `save.py` calls and the self-test).

## What changed (all conditional)

| part | collections case | any other case |
|---|---|---|
| datecalc | unchanged (bands, floors, deadlines, promise guards) | extracts the documents' OWN date rules (weekly options, next dates, due dates...) + a tested generic calendar code node (today, 6-week calendar, weekdays, business days, the rules); none -> clean skip; never fails the build (`ok: false, generic: true`) |
| build prompt CODE STEPS block | unchanged | replaced by an optional DATE FACTS block (or a plain list of the documents' date rules) |
| guards / check_promise_date / once / floor / offer_instead | installed when datecalc `ok` | never installed (datecalc not `ok`) |
| situations / router / specialists (A1) | unchanged | extraction result moved aside (`*.situations.skipped.json`): no prompt block, no apply, no check |
| identity_gate | identity/verify tool -> gate | only if the tool's API also lists the security questions it checks (a second-factor or verify tool alone is not enough) |
| close-call gates (canned `close_structure`, CLOSING rule, "goodbye is not yours") | unchanged | only a tool that really ends the call (close / end_call / hang_up / finish / terminate, never a transfer); none -> the case's end node; the documents' closing sentence is then the agent's own FIXED SENTENCE |
| canned (mandatory sentences) | | prompt no longer says "outbound"/collections; examples generic (collections ones marked as such); call variables the documents name are allowed |
| customer-speech block (`robustness.md`) | | examples no longer assume debts/promises; language line unchanged (case language) |
| harden identity-status text | | "never mention any amount, product or account detail" (no "debt") |
| idempotent writes, honesty labels (`tool_outcome`), mock-url pin, api-required repair, hook repair | generic, kept | generic, kept |
| lint_workflow / hookcheck / apicheck | no practice-tool assumptions found (only comments name them) | same |
| buildcheck | unchanged | "no write tool called in any chat" is not catastrophic (an inquiry can be read-only) |
| self-test personas | practice customers + ledger checks | `write_personas_generic`: personas from the case's OWN test customers / example scenarios with the documents' call variables; checks (must_call / must_not_call / before / max_calls) from the documents, evaluated on the tool calls read from the Freya call (best effort; unreadable -> not failed); no practice session / ledger |
| skill (`SKILL.md`, `routing.md`) | the collections skeleton is a GUIDELINE for collections cases only | follow the case's own flow drawing and documents: stages in their order, routes on tool results / extracted variables, every branch reachable, tool-call honesty, ids from results, every mandatory sentence verbatim in the case language, end at the documents' ending |

## Grep audit (`builder/`, skill)

Remaining hits of the 7 practice tools / promise / floor / persuasion / band / deadline / note / callback:
- `datecalc.py`, `guards.py`, `situations.py`: the collections machinery itself, reached only when collections.
- `selftest.py`: `check_ledger` / `_run_one` collections path; generic personas never reach it (`sc["generic"]`).
- `build.py`: the CODE STEPS prompt (only when datecalc `ok`), log texts.
- `harden.py` (a `band/deadline` exclusion in the id matcher: harmless), `hookcheck.py`, `apicheck.py`, `save.py`,
  `canned.py`: comments, or a collections example labelled as such.
- `routing.md`: the "Stages (COLLECTIONS cases only)" skeleton.

## Tests

- Dry run, non-collections English case `/tmp/GenericCase` (parcel status; tools list_parcels, get_parcel,
  reschedule_delivery, transfer_to_agent), dummy mock `http://dummy-mock.invalid:9`:
  BUILD END in 460 s, no crash. datecalc: "not a collections case: 1 date rule(s), calendar code node"; A1
  situations skipped; final save lint 0 errors 0 warnings; mock url 6/6 api_call urls on the dummy mock;
  buildcheck 0; export ok (`submission/GenericCase.workflow.json`: 10 steps, start code node, 5 tools, no close tool,
  2+ end_call). FIXED SENTENCES = the 4 sentences of the brief verbatim; no close tool -> the brief's goodbye is the
  agent's own closing sentence (verified offline with BTB_COLLECTIONS=0; the run itself predates that edit and still
  said "the system says it after the close tool"). Prompts: 0 x promise / floor / persuasion / callback / close_call /
  negotiat. Remaining "band/deadline" are a key-exclusion list inside harden's id-matcher code (not prompt text);
  "debt" was in harden's identity-status text of that run (fixed after it: now "amount, product or account detail").
  Self-test: 3 personas written from the brief's own test customers (1001/1002/1003 scenarios); every chat
  timed out against the dummy URL in both workspaces -> "self-test did not run: untested", no fix round, no crash.
- Collections still works: `build.py briefs/brief-a.md tools/openapi.json --slot gen-A`:
  BUILD END in 408 s. datecalc collections spec ok (56 s), A1 situations refused / hardship / already_paid / dispute /
  payment_plan_transfer / human, lint 0, guards installed (check_promise_date in the export), self-test 1: 2/6 passed,
  fix kept, self-test 2: 5/6 passed, export ok.
