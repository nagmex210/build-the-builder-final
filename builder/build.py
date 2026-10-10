"""The builder: reads a bank's brief (+ its tool API file) and creates a phone agent on Freya.

    python3 builder/build.py --slot <name> --tools <openapi.json> <brief.md> [<brief2.md> ...]

Prints {"workflow_id": ..., "agent_id": ...} as its last line. Writes the run's trace (start/end, every model
call with its purpose, what it created on Freya, tests it ran) to runs/traces/<slot>-<time>.jsonl.
Baseline = the kit's example builder (Claude Agent SDK + the build-phone-agent skill), with the test step
changed: no practice-case runs (hidden briefs come without cases).
"""
import argparse, asyncio, dataclasses, json, os, pathlib, sys, time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, query

KIT = pathlib.Path(__file__).resolve().parent.parent


async def run(slot, tools, briefs):
    trace = KIT / "runs" / "traces" / f"{slot}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    os.environ["BTB_TRACE"] = str(trace)          # btb/llm.py appends its model calls here too
    options = ClaudeAgentOptions(
        cwd=KIT,
        model=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"),
        skills=["build-phone-agent"],
        setting_sources=["project"],
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        permission_mode="dontAsk",
        max_turns=150,
        env={"BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1200000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
             "BTB_TRACE": str(trace)},
    )
    prompt = (f"Use the build-phone-agent skill. Slot: {slot}. Tool API file: {tools}. Brief files: {' '.join(briefs)}. "
              f"Write the workflow to out/{slot}.workflow.json and save it with slot {slot}.")
    t0 = time.time()
    with trace.open("a") as out:
        out.write(json.dumps({"event": "start", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "slot": slot, "tools": tools,
                              "briefs": briefs, "model": options.model}) + "\n")
        async for message in query(prompt=prompt, options=options):
            out.write(json.dumps({"type": type(message).__name__, **dataclasses.asdict(message)}, default=str) + "\n")
            out.flush()
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"  [{block.name}] {str(block.input)[:120]}", flush=True)
            elif isinstance(message, ResultMessage):
                print(f"\ndone: {message.num_turns} turns, {message.duration_ms / 1000:.0f} s", flush=True)
    # Guarantee: whatever the agent saved, the published workflow carries the tool-failure/honesty hooks.
    wf_file = KIT / "out" / f"{slot}.workflow.json"
    if wf_file.exists():
        try:
            sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
            import freya
            from harden import harden
            wf = json.loads(wf_file.read_text())
            names = harden(wf)
            wf_file.write_text(json.dumps(wf, indent=1))
            saved = freya.save_workflow(slot, wf, state_file=str(KIT / ".freya-agents.json"))
            with trace.open("a") as out:
                out.write(json.dumps({"event": "harden+save", "tools": names, "saved": saved}) + "\n")
        except Exception as e:  # noqa: BLE001
            with trace.open("a") as out:
                out.write(json.dumps({"event": "harden failed", "error": str(e)[:300]}) + "\n")
    state = json.loads((KIT / ".freya-agents.json").read_text()).get(slot) if (KIT / ".freya-agents.json").exists() else None
    with trace.open("a") as out:
        out.write(json.dumps({"event": "end", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seconds": round(time.time() - t0),
                              "created": state}) + "\n")
    if not state:
        sys.exit("builder finished without saving a workflow for slot " + slot)
    print(json.dumps({"workflow_id": state["workflow_id"], "agent_id": state["agent_id"]}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True); ap.add_argument("--tools", default="tools/openapi.json"); ap.add_argument("briefs", nargs="+")
    a = ap.parse_args()
    asyncio.run(run(a.slot, a.tools, a.briefs))
