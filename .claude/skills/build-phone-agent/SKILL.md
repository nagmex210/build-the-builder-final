---
name: build-phone-agent
description: Build a Freya phone agent from a bank's brief, test it on the practice customers and fix what fails. Use when asked to build or improve a phone agent from a brief.
---

# Build a phone agent from a brief

Work from the kit folder. Use only what the brief and the tool API file say. Do not copy rules from another brief.

## Steps

1. Read the brief files you were given, then the tool API file you were given (default `tools/openapi.json`). Take every tool field and allowed value from THAT file.
2. Read `docs/workflow-format.md` and `docs/tools-and-code.md`.
3. Read `examples/base-agent.json`. It is a small working agent with two steps. Use it as the pattern for the JSON, not as the answer.
4. Write the workflow to `out/<slot>.workflow.json`. `<slot>` is the slot you were given.
   - One step per stage of the call. Identity comes first.
   - Move to the next step on a tool result, not on what the customer says.
   - Take every tool field and allowed value from the tool API file you were given.
   - Leave `agent_config` out.
5. Save it: `python3 -c "import freya,json,sys; print(json.dumps(freya.save_workflow(sys.argv[1], json.load(open(sys.argv[2])))))" <slot> out/<slot>.workflow.json`
   It prints `workflow_id` and `agent_id`. The same slot updates the same workflow.
6. Check it starts: one chat turn, `python3 -c "import freya,json; print(freya.api('POST','/api/v2/chat/message',{'workflowId':'<workflow_id>','message':'Hello?','customerVariables':{'customer_id':'c_test','first_name':'Ann','last_name':'Lee','title':'Ms','now':'2026-10-14T11:00'}}))"`. A 500 means the workflow cannot start a call: fix and save again.
7. Re-read the brief rule by rule against your workflow and fix every rule that is not enforced. Do this once.
8. Finish with one line: the `workflow_id` and the `agent_id`.

## Rules

- Never edit the agent on the platform by hand. Change the file and save it.
- When a tool call fails, the agent must say so. It must never tell the customer something is recorded when it is not.
- A customer that passes once can fail the next time. Prefer rules in routes and code over rules in prompts.
