---
name: build-phone-agent
description: Build a Freya phone agent from a bank's brief, test it on the practice customers and fix what fails. Use when asked to build or improve a phone agent from a brief.
---

# Build a phone agent from a brief

Work from the kit folder. Use only what the brief and the tool API file say. Do not copy rules from another brief.

## Steps

1. Read the brief files you were given, then the tool API file you were given (default `tools/openapi.json`). Take every tool field and allowed value from THAT file.
2. Read `docs/workflow-format.md` and `docs/tools-and-code.md`.
3. Read `.claude/skills/build-phone-agent/routing.md`: the node-per-stage structure and the exact routing patterns to use.
   Read `examples/base-agent.json`. It is a small working agent with two steps. Use it as the pattern for the JSON, not as the answer.
4. Write the workflow to `out/<slot>.workflow.json`. `<slot>` is the slot you were given.
   - Follow routing.md: one conversation node per stage (opening, identity, negotiation), a passthrough account
     lookup + code node between identity and negotiation, a close tool in every stage that can close, and a
     transition on the close tool's result to an `end_call` node.
   - Move to the next step on a tool result or an extracted enum variable, not on `matches_intent`.
   - Take every tool field and allowed value from the tool API file you were given.
   - Leave `agent_config` out.
   - Run `python3 builder/lint_workflow.py out/<slot>.workflow.json` and fix every ERROR before saving.
5. Save it: `python3 builder/save.py <slot> out/<slot>.workflow.json`
   It first hardens every `api_call` tool (see "Tool failures and honesty" below), then prints `workflow_id` and
   `agent_id`. The same slot updates the same workflow. Always save with this command, never with `freya` directly.
6. Check it starts: one chat turn, `python3 -c "import freya,json; print(freya.api('POST','/api/v2/chat/message',{'workflowId':'<workflow_id>','message':'Hello?','customerVariables':{'customer_id':'c_test','first_name':'Ann','last_name':'Lee','title':'Ms','now':'2026-10-14T11:00'}}))"`. A 500 means the workflow cannot start a call: fix and save again.
7. Re-read the brief rule by rule against your workflow and fix every rule that is not enforced. Do this once.
8. Finish with one line: the `workflow_id` and the `agent_id`.

## Tool failures and honesty (part of every workflow)

`builder/save.py` adds hooks to every `api_call` tool. Build the workflow so that it works with them:
- Every failed tool result (HTTP error or `ok: false`) carries a `tool_outcome` line starting with `FAILED:` and the
  failure number of that tool in this call; a recorded write carries `tool_outcome` starting with `SUCCESS:`. In every
  node prompt that has tools, say: "After every tool result read `tool_outcome` first. If it starts with FAILED, nothing
  was recorded: never say it was recorded, booked or done." Do not write your own retry loop in a hook.
- Find the brief's rule for a failed tool call (how many attempts, what to tell the customer, which outcome/reason to
  close with) and write it into the prompt of every node that can call a write tool, and into routing where possible
  (a transition can move to the closing node with the brief's failure outcome; test, in one OR group, both the
  engine's counter `<tool>_failure_count` and the hook's counter `tool_failures_<tool>`, each with `greater_than`). Writes are never retried by the platform (`maxRetries: 0`); the model makes each attempt itself.
  If the brief has no such rule: try once more, then tell the customer it could not be done.
- Only after a SUCCESS result may the agent say a thing is recorded, booked, scheduled, transferred or sent. Never
  announce it before the call ("I have recorded..." while calling the tool is a lie if it then fails).
- Ids (product ids and any other `*_id`) come only from the account/lookup result. Map them (`data.<list>`) and put
  them in the prompt with each item's details, and tell the model to copy the id exactly. Never let the model guess an
  id from the product's name. The pre-hook repairs an id only when there is a single candidate.
- When a tool returns `ok: false` for a reason other than a service failure (wrong id, already recorded, refused), the
  agent tells the customer the truth in one sentence and follows the brief; it does not repeat an identical call.

## Rules

- Never edit the agent on the platform by hand. Change the file and save it.
- When a tool call fails, the agent must say so. It must never tell the customer something is recorded when it is not.
- A customer that passes once can fail the next time. Prefer rules in routes and code over rules in prompts.
