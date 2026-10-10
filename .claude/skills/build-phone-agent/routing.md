# Workflow structure and routing recipe

A shape that works for any collections-style brief. Fill every rule, value, field name, enum, outcome and reason
from THE BRIEF and THE TOOL API FILE you were given. Node names below are suggestions; stage contents come from the brief.

## Principle

The agent model is small. It follows one short task well and many mixed tasks badly. So:
- one conversation node per stage of the call, each with only the tools of that stage;
- the call moves between stages on **tool results** (deterministic `equals` / `greater_than` on result variables),
  never on what the customer said (`matches_intent`) when a tool result can decide it;
- every node that can close the call has the close tool, and a transition on the close tool's success sends the
  call to an `end_call` node. Nothing else hangs up.

## Stages (adapt to the brief)

```text
opening (conversation)          who is on the line; third-party branch (callback / wrong number / deceased / unclear)
   │  tools: the callback tool, the close tool
   │  → identity            when the extracted variable `party` equals "customer"  (extraction_schema enum, default "unknown")
   │  → hang_up             when close tool succeeded
identity (conversation)         security questions, one verify call per answer
   │  tools: verify tool, close tool, transfer tool (if the brief allows a human request before verification)
   │  post-hook on verify adds data.what_to_do_next (next question / ask again / hint retry / failed → close)
   │  → load_account        when verify response says all verified (test "true" AND "True")
   │  → hang_up             when close tool succeeded
load_account (api_request, passthrough, silent)   pre_action = account lookup, node-level response_mapping data.<list>
   │  → prepare (always)
prepare (code, passthrough, silent)               Python: every number/date the conversation needs, as STRINGS:
   │  per-product summary line, floors, bands, deadlines, offer dates, "today", the business-day list for the next
   │  weeks, which product is current. Read the account list defensively (list / JSON string / flattened keys).
   │  → negotiate (always)
negotiate (conversation)        state the debt, all the promise logic, objections, transfers, notes, closing
   │  tools: promise tool, transfer tool, note tool (only if the brief uses it), close tool
   │  task_message shows the computed facts with {{vars}}, never asks the model to do calendar math
   │  post-hook on the promise tool adds what_to_do_next ("say it is recorded and the confirmation sentence" /
   │  "it failed: try once more" / "failed twice: say it could not be recorded, then close with <reason>")
   │  → hang_up             when close tool succeeded
hang_up (end_call)              message_mode "custom", spoken_message = the goodbye, on_enter silent. The PLATFORM says
                                the goodbye after the close tool succeeded; the model never says goodbye itself.
```

Multi-product briefs: keep ONE negotiate node and let the code node build an ordered product list with a summary
per product; the prompt walks through them in order (one promise per product). Do not create one node per product.

## Exact routing patterns

Close tool → end node (put this FIRST in the transitions of every conversation node that has the close tool):
```json
{ "target_node": "hang_up", "description": "The call was closed",
  "condition": { "logic": "or", "conditions": [
    { "variable": "close_call_response.data.ok", "operator": "equals", "operand": "true" },
    { "variable": "close_call_response.data.ok", "operator": "equals", "operand": "True" } ] } }
```
Never use `close_call_success_count` here: it counts every 2xx, including a guard's blocked close.

Identity passed (boolean from the API, test both spellings):
```json
{ "target_node": "load_account", "description": "Identity verified",
  "condition": { "logic": "or", "conditions": [
    { "variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "true" },
    { "variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "True" } ] } }
```
(Use the field names of the tool API file you were given.)

Who is on the line (opening): an `extraction_schema` variable `party` with enum such as
`customer | other_person | unknown`, default `unknown`, and transitions with `equals`. Only route to identity on a
clear confirmation as the brief defines it; let the opening node handle everything else itself.

## Tool rules in every node

- Each `api_call` tool: `post_process_code` that pops `header`, and adds `data.what_to_do_next`: one plain sentence
  saying what the result means and what to say or call next, derived from the brief's rule for that tool
  (success, `ok: false`, specific hints/errors). Wrap in `try/except Exception: pass`.
- A pre-hook must never point `config['url']` at localhost / 127.0.0.1 / any other host: the platform refuses
  it ("Localhost URLs are not allowed") and the turn breaks. To stop a call that would break a brief rule (date
  outside the window, amount below the floor, a second close), the pre-hook removes a required body field (so the
  bank answers `ok: false` and records nothing) and stores the reason in a `vars` flag; the post-hook then puts
  that reason into `data.what_to_do_next` ("not recorded because ...; offer ... instead").
- Close tool: `outcome` and `reason` are model-filled leaves with the enums of the API file; descriptions list
  the brief's outcome table (which reason belongs to which outcome). Pre-hook drops `reason` for outcomes that the
  brief says take none.
- `customer_id` and other ids that the model must not invent: `default: "{{customer_id}}"`; product ids: list them
  in the code node's summary so the model copies them exactly.
- The task_message of each node starts with: "After every tool result, speak to the customer or call the next
  tool. Never end a turn with nothing. Call one tool per message. Never say goodbye yourself: when the call is done, call the close tool; the system says the goodbye."
- Set `max_node_turns` high (40-60) on conversation nodes; a whole negotiation can take many turns.

## Global nodes

Only for interrupts that are identical everywhere AND do not need tools (e.g. "are you a robot?" → fixed line,
passthrough back to `__previous__`). Exclude `hang_up`. Most interrupts (human request, dispute, hardship) need
tools and outcome logic: handle them inside the stage node instead.

## Before saving

Run `python3 builder/lint_workflow.py out/<slot>.workflow.json` and fix every ERROR it prints.
