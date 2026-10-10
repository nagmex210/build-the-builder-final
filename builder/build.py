"""The builder: reads a bank's brief (+ its tool API file) and creates a phone agent on Freya.

    python3 builder/build.py --slot <name> --tools <openapi.json> <brief.md> [<brief2.md> ...]

Prints {"workflow_id": ..., "agent_id": ...} as its last line. Writes the run's trace (start/end, every model
call with its purpose, what it created on Freya, tests it ran) to runs/traces/<slot>-<time>.jsonl.
Steps: datecalc (generated, locally tested date/amount code) -> Claude Agent SDK + build-phone-agent skill
(routing recipe + lint) under a hard time budget -> final deterministic pass on the saved file (harden tool hooks,
customer-speech block, lint) and one last save. No practice-case runs (hidden briefs come without cases).
"""
import argparse, asyncio, dataclasses, json, os, pathlib, subprocess, sys, time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, query

KIT = pathlib.Path(__file__).resolve().parent.parent


BUDGET_S = int(os.environ.get("BUILD_AGENT_BUDGET_S", "1260"))   # Claude part; the whole run must stay < 30 min


async def run(slot, tools, briefs):
    t0 = time.time()
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
              f"Write the workflow to out/{slot}.workflow.json and save it with slot {slot}. "
              f"Do not run tools/run_cases.py or any practice cases (a new brief comes without them), and do not read "
              f"other slots' files in out/: build only from the files named here, the docs and the example. "
              f"Time limit: you have {BUDGET_S // 60} minutes in total, then you are stopped. Save a complete first version "
              f"early (within about 10 minutes), then improve and re-save. Live chat tests: a few turns only, no waiting loops.")
    # Every build starts from no workflow file: the inner Claude would otherwise edit the previous build's file and keep
    # its old hook blocks (harden/robust do not replace a block they already find), and a failed Claude run would ship it.
    old_wf = KIT / "out" / f"{slot}.workflow.json"
    if old_wf.exists():
        old_wf.replace(old_wf.with_suffix(".prev.json"))
    # A3 canned sentences: extracted by Azure in parallel with everything else, applied in the final pass.
    old_canned = KIT / "out" / f"{slot}.canned.json"
    if old_canned.exists():
        old_canned.unlink()
    canned_proc = subprocess.Popen([sys.executable, str(KIT / "builder" / "canned.py"), "extract", "--slot", slot, "--tools", tools, *briefs],
                                   cwd=KIT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env={**os.environ, "BTB_TRACE": str(trace)})
    # Code steps: dates, business days, deadlines and floors are computed by generated, locally tested code.
    t_calc = time.time()
    calc = subprocess.run([sys.executable, str(KIT / "builder" / "datecalc.py"), "--slot", slot, "--tools", tools, *briefs],
                          cwd=KIT, capture_output=True, text=True, env={**os.environ, "BTB_TRACE": str(trace)})
    calc_file = KIT / "out" / f"{slot}.calc.json"
    calc_ok = calc_file.exists() and json.loads(calc_file.read_text()).get("ok")
    with trace.open("a") as out:
        out.write(json.dumps({"event": "test", "what": "datecalc: extract calendar/amount spec, generate code node + account hook, "
                              "run both locally on 5 dates and fake products", "ok": bool(calc_ok),
                              "seconds": round(time.time() - t_calc), "output": calc.stdout[-1500:] + calc.stderr[-800:]}) + "\n")
    if calc_ok:
        prompt += (f" CODE STEPS (tested, use them as given): {calc_file} holds a ready `code_node` and an `account_post_process_code` hook. "
                   "(1) Put `code_node` into the workflow as the START node (set its two '<NEXT NODE>' fields to your opening node); "
                   "do not edit its code. It writes `date_facts`: today, anchor dates (next business day, last business day of this/next week/month), "
                   "the deadline per band, callback days, what 'this/next <weekday>' means, and a day-by-day calendar with business-day flags. "
                   "Put {{date_facts}} in the task_message of every node that handles callbacks, dates or promises, and tell the model there: "
                   "'Never compute a date yourself. Look every date up in DATE FACTS: a named weekday via WEEKDAY WORDS, whether a day is a business "
                   "day and the next business day via CALENDAR, deadlines and attempt dates via the anchor lines.' "
                   "(2) Set `account_post_process_code` verbatim as the `post_process_code` of the tool named in `account_tool` "
                   "(if you need more hook logic, append it after this code, do not change it). It adds to every product: `band`, `deadline`, "
                   "`deadline_weekday`, `persuasion_attempts`, `floor_amount`, and puts the same DATE FACTS block into the result as `date_facts` "
                   "(and into the variable date_facts): this is the reliable copy after identity, because the platform may skip the code of the "
                   "start node. Tell the model to use each product's own `deadline` and `floor_amount` "
                   "from the tool result and never to compute them. Read `example_date_facts` in that file to see the output. "
                   "If the brief's rule differs from these facts, follow the brief and mention it in your final line.")
    with trace.open("a") as out:
        out.write(json.dumps({"event": "start", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "slot": slot, "tools": tools,
                              "briefs": briefs, "model": options.model}) + "\n")

    async def agent():
        with trace.open("a") as out:
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
    try:
        await asyncio.wait_for(agent(), timeout=max(60, BUDGET_S - (time.time() - t0)))
    except asyncio.TimeoutError:
        print("build agent stopped: time budget reached; finishing with the last written workflow file", flush=True)
        with trace.open("a") as out:
            out.write(json.dumps({"event": "budget", "what": "Claude build agent stopped at the time budget", "seconds": round(time.time() - t0)}) + "\n")
    # Final deterministic pass on whatever the agent wrote: hooks (honesty / ids / failures), speech block, lint, save.
    wf_file = KIT / "out" / f"{slot}.workflow.json"
    try:
        canned_err = canned_proc.communicate(timeout=240)[1]
    except subprocess.TimeoutExpired:
        canned_proc.kill(); canned_err = "timeout"
    with trace.open("a") as out:
        out.write(json.dumps({"event": "test", "what": "A3 canned sentences extracted (opening tts, say_now hooks, goodbye, FIXED SENTENCES)",
                              "ok": old_canned.exists(), "error": (canned_err or "")[-400:]}) + "\n")
    if wf_file.exists():
        sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
        try:
            from lint_workflow import lint
            from save import finish_and_save
            wf = json.loads(wf_file.read_text())
            names, saved = finish_and_save(slot, wf)
            wf_file.write_text(json.dumps(wf, indent=1))
            errs, warns = lint(wf)
            with trace.open("a") as out:
                out.write(json.dumps({"event": "harden+robust+save", "tools": names, "saved": saved}) + "\n")
                out.write(json.dumps({"event": "test", "what": "structural lint of the saved workflow", "errors": errs, "warnings": warns}) + "\n")
            print(f"final save: {saved}; lint: {len(errs)} errors, {len(warns)} warnings", flush=True)
        except Exception as e:  # noqa: BLE001  keep whatever the agent saved
            print(f"final pass failed: {e}", flush=True)
            with trace.open("a") as out:
                out.write(json.dumps({"event": "final pass failed", "error": str(e)[:300]}) + "\n")
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
