"""The builder: reads a bank's brief (+ its tool API file) and creates a phone agent on Freya.

    python3 builder/build.py --slot <name> --tools <openapi.json> <brief.md> [<brief2.md> ...]

Prints {"workflow_id": ..., "agent_id": ...} as its last line. Writes the run's trace (start/end, every model
call with its purpose, what it created on Freya, tests it ran) to runs/traces/<slot>-<time>.jsonl.
Steps: datecalc (generated, locally tested date/amount code) -> Claude Agent SDK + build-phone-agent skill
(routing recipe + lint) under a hard time budget -> final deterministic pass on the saved file (harden tool hooks,
customer-speech block, lint) and one last save. Then a self-simulation (builder/selftest.py, idea A17): personas
written from the brief play against the saved workflow in Freya workspace 2, judged only by deterministic ledger /
tool-order / date-amount checks; one fix round as an EDIT with the exact failed checks; re-test; ship the better one.
"""
import argparse, asyncio, dataclasses, json, os, pathlib, subprocess, sys, time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, query

KIT = pathlib.Path(__file__).resolve().parent.parent


BUDGET_S = int(os.environ.get("BUILD_AGENT_BUDGET_S", "720"))    # Claude build part; the whole run must stay < 30 min
SELFTEST = os.environ.get("BUILD_SELFTEST", "1") != "0"
SELFTEST_N = int(os.environ.get("BUILD_SELFTEST_N", "6"))
SELFTEST_BUDGET_S = int(os.environ.get("BUILD_SELFTEST_BUDGET_S", "900"))   # self-test + fix + re-test, at most
ROUND_S = 420                                                      # one round of parallel chats, worst case


def log(trace, **ev):
    with trace.open("a") as out:
        out.write(json.dumps(ev, default=str) + "\n")


async def self_simulate(slot, tools, briefs, trace, wf_file, final_pass, options_base):
    """A17: personas from the brief -> chats in workspace 2 -> deterministic checks -> one EDIT fix round -> re-test."""
    import selftest
    t_start = time.time()
    left = lambda: SELFTEST_BUDGET_S - (time.time() - t_start)
    text = "\n\n".join(pathlib.Path(b).read_text() for b in briefs)
    calc_file = KIT / "out" / f"{slot}.calc.json"
    loop = asyncio.get_running_loop()
    try:
        personas = await loop.run_in_executor(None, selftest.write_personas, text, tools, KIT / "public-test-set.json", SELFTEST_N)
        log(trace, event="test", what="self-simulation: personas + ledger checks written from the brief",
            personas=[{"title": p["title"], "customer": p["customer"], "script": p["script"], "checks": p["checks"]} for p in personas])
        wf1 = json.loads(wf_file.read_text())
        r1 = await loop.run_in_executor(None, selftest.run_tests, slot, wf1, personas, calc_file, ROUND_S)
    except Exception as e:  # noqa: BLE001
        log(trace, event="test", what="self-simulation round 1", error=str(e)[:300]); print(f"self-test skipped: {e}", flush=True)
        return
    log(trace, event="test", what="self-simulation round 1: deterministic ledger checks", where=r1["where"], n=r1["n"],
        failed=r1["n_failed"], checks_failed=r1["n_checks_failed"], seconds=round(time.time() - t_start), rows=r1["rows"])
    print(f"self-test 1 ({r1['where']}): {r1['n_failed']}/{r1['n']} personas failed a check ({r1['n_checks_failed']} checks)", flush=True)
    (KIT / "out" / f"{slot}.selftest1.json").write_text(json.dumps({"personas": personas, **r1}, indent=1, default=str))
    r1_s = time.time() - t_start
    retest_s = min(ROUND_S, r1_s + 60)          # the re-test takes about as long as round 1 did (platform load)
    if not r1["n_failed"] or r1["n"] < len(personas) or left() < retest_s + 90:
        log(trace, event="ship", what="no fix round", why="no failed check" if not r1["n_failed"] else
            ("too few valid chats" if r1["n"] < len(personas) else "no time left"))
        return
    best = wf_file.read_text()
    fails = selftest.failure_text(r1)
    fix_s = max(90, min(300, left() - retest_s))
    options = dataclasses.replace(options_base, skills=None, allowed_tools=["Read", "Edit", "Grep", "Bash"], max_turns=60)
    prompt = (f"You fix a Freya phone-agent workflow after a self-simulation. The workflow file is out/{slot}.workflow.json. "
              f"Brief files: {' '.join(briefs)}. Tool API file: {tools}. Docs: docs/. Test personas written from the brief talked to it; "
              f"the record (scripts, transcripts) is out/{slot}.selftest1.json. These DETERMINISTIC checks on the bank's ledger failed (each persona was played twice):\n{fails}\n\n"
              "A tool result with ok=false is the bank refusing the call: fix what made the agent send it (for example an id that "
              "is not in the account tool's result, a call after the call was closed, a missing required field). "
              "First decide for each failure whether the BRIEF really requires the check for that customer's behaviour (a persona check "
              "can be wrong; then ignore it). EDIT the existing workflow file in place with the Edit tool: change ONLY the prompts, "
              "transitions or hook lines needed for real failures; keep everything else exactly (do not restructure, do not drop any "
              "rule of the brief, do not touch the start code node or the account post_process_code). Fix general behaviour, never "
              "anything specific to one test customer. Then check the JSON loads with python3. Do not save to Freya and do not run any "
              f"eval or chat. You have {int(fix_s // 60)} minutes. End with one line per failure: fixed how / ignored why.")
    t = time.time()
    try:
        await asyncio.wait_for(claude_stream(prompt, options, trace), timeout=fix_s)
    except asyncio.TimeoutError:
        log(trace, event="budget", what="fix round stopped at its time budget")
    log(trace, event="fix", what="self-simulation fix round: Claude EDITs the workflow with the failed checks", seconds=round(time.time() - t))
    try:
        wf2 = json.loads(wf_file.read_text())
    except Exception:  # noqa: BLE001
        wf_file.write_text(best); final_pass("restore"); log(trace, event="ship", what="fix broke the JSON: restored the build")
        return
    if wf_file.read_text() == best:
        log(trace, event="ship", what="fix round changed nothing"); return
    if not final_pass("fix"):
        wf_file.write_text(best); final_pass("restore"); return
    t = time.time()
    try:
        r2 = await loop.run_in_executor(None, selftest.run_tests, slot, json.loads(wf_file.read_text()), personas, calc_file,
                                        max(120, min(ROUND_S, left())))
    except Exception as e:  # noqa: BLE001
        r2 = None; log(trace, event="test", what="self-simulation round 2", error=str(e)[:300])
    if r2:
        log(trace, event="test", what="self-simulation round 2: same personas after the fix", where=r2["where"], n=r2["n"],
            failed=r2["n_failed"], checks_failed=r2["n_checks_failed"], seconds=round(time.time() - t), rows=r2["rows"])
        print(f"self-test 2: {r2['n_failed']}/{r2['n']} personas failed a check ({r2['n_checks_failed']} checks)", flush=True)
    rate = lambda r: (r["n_failed"] / r["n"], r["n_checks_failed"] / r["n"])
    if r2 is None or r2["n"] < len(personas) or rate(r2) > rate(r1):
        (KIT / "out" / f"{slot}.workflow.rejected-fix.json").write_text(wf_file.read_text())
        wf_file.write_text(best); final_pass("restore build")
        log(trace, event="ship", what="fix tested worse or could not be tested: restored the build's workflow")
    else:
        log(trace, event="ship", what="fix kept: no worse on the deterministic checks")


async def claude_stream(prompt, options, trace):
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
        await claude_stream(prompt, options, trace)
    try:
        await asyncio.wait_for(agent(), timeout=max(60, BUDGET_S - (time.time() - t0)))
    except asyncio.TimeoutError:
        print("build agent stopped: time budget reached; finishing with the last written workflow file", flush=True)
        with trace.open("a") as out:
            out.write(json.dumps({"event": "budget", "what": "Claude build agent stopped at the time budget", "seconds": round(time.time() - t0)}) + "\n")
    # Final deterministic pass on whatever the agent wrote: hooks (honesty / ids / failures), speech block, lint, save.
    wf_file = KIT / "out" / f"{slot}.workflow.json"
    sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))

    def final_pass(tag):
        if not wf_file.exists():
            return None
        try:
            from lint_workflow import lint
            from save import finish_and_save
            wf = json.loads(wf_file.read_text())
            names, saved = finish_and_save(slot, wf)
            wf_file.write_text(json.dumps(wf, indent=1))
            errs, warns = lint(wf)
            with trace.open("a") as out:
                out.write(json.dumps({"event": "harden+robust+save", "round": tag, "tools": names, "saved": saved}) + "\n")
                out.write(json.dumps({"event": "test", "what": "structural lint of the saved workflow", "errors": errs, "warnings": warns}) + "\n")
            print(f"final save ({tag}): {saved}; lint: {len(errs)} errors, {len(warns)} warnings", flush=True)
            return saved
        except Exception as e:  # noqa: BLE001  keep whatever the agent saved
            print(f"final pass failed: {e}", flush=True)
            with trace.open("a") as out:
                out.write(json.dumps({"event": "final pass failed", "error": str(e)[:300]}) + "\n")
            return None

    if final_pass("build") and SELFTEST:
        await self_simulate(slot, tools, briefs, trace, wf_file, final_pass, options)
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
