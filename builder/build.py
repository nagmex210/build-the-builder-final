"""The builder: reads a bank's brief (+ its tool API file) and creates a phone agent on Freya.

    python3 builder/build.py <brief.md> <tool_api.json>                                  (submission form)
    python3 builder/build.py --slot <name> --tools <openapi.json> <brief.md> [<brief2.md> ...]

Without --slot the slot is the last brief's file name (briefs/hidden-1.md -> hidden-1): reruns update that workflow.

Prints {"workflow_id": ..., "agent_id": ...} as its last line. Writes the run's trace (start/end, every model
call with its purpose, what it created on Freya, tests it ran) to runs/traces/<slot>-<time>.jsonl.
Steps: datecalc (generated, locally tested date/amount code) -> Claude Agent SDK + build-phone-agent skill
(routing recipe + lint) under a hard time budget -> final deterministic pass on the saved file (harden tool hooks,
customer-speech block, lint) and one last save. Then a self-simulation (builder/selftest.py, idea A17): personas
written from the brief play against the saved workflow in Freya workspace 2, judged only by deterministic ledger /
tool-order / date-amount checks; one fix round as an EDIT with the exact failed checks; re-test; ship the better one.
"""
import argparse, asyncio, dataclasses, json, os, pathlib, subprocess, sys, threading, time

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolResultBlock, ToolUseBlock,
                              UserMessage, query)

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "btb"))
from scrub import Redacting, scrub_file  # noqa: E402


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def tail_model_calls(trace, stop):
    """Print every model call that btb/llm.py logs to the trace (datecalc, extract, anything the build agent runs),
    as it happens: the printed log is the submitted trace."""
    pos = 0
    while True:
        done = stop.is_set()
        try:
            with open(trace) as f:
                f.seek(pos)
                for line in f:
                    if not line.endswith("\n"):
                        break
                    pos += len(line.encode())
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if "type" not in e and "model" in e and "purpose" in e:
                        print(f"[model call {e.get('at', '')}] {e['model']} (Azure, btb/llm.py): {e['purpose'] or '-'}", flush=True)
        except FileNotFoundError:
            pass
        if done:
            return
        stop.wait(1)


BUDGET_S = int(os.environ.get("BUILD_AGENT_BUDGET_S", "720"))    # Claude build part; the whole run must stay < 30 min
SELFTEST = os.environ.get("BUILD_SELFTEST", "1") != "0"
SELFTEST_N = int(os.environ.get("BUILD_SELFTEST_N", "6"))
SELFTEST_BUDGET_S = int(os.environ.get("BUILD_SELFTEST_BUDGET_S", "1320"))   # self-test + fix + re-test, at most
BUILD_TOTAL_S = int(os.environ.get("BUILD_TOTAL_S", "1620"))     # the whole run must end before 30 min (1800 s)
BUILD_T0 = time.time()
ROUND_S = 420                                                      # one round of parallel chats, worst case


def log(trace, **ev):
    with trace.open("a") as out:
        out.write(json.dumps(ev, default=str) + "\n")


async def self_simulate(slot, tools, briefs, trace, wf_file, final_pass, options_base):
    """A17: personas from the brief -> chats in workspace 2 -> deterministic checks -> one EDIT fix round -> re-test."""
    import selftest
    t_start = time.time()
    # whichever ends first: the self-test budget or the whole build's 30 min (minus a margin for the final save/export)
    left = lambda: min(SELFTEST_BUDGET_S - (time.time() - t_start), BUILD_TOTAL_S - (time.time() - BUILD_T0))
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
        await asyncio.wait_for(claude_stream(prompt, options, trace, "self-test fix"), timeout=fix_s)
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


async def claude_stream(prompt, options, trace, label="build agent"):
    turn, bash_ids = 0, set()
    with trace.open("a") as out:
        async for message in query(prompt=prompt, options=options):
            out.write(json.dumps({"type": type(message).__name__, **dataclasses.asdict(message)}, default=str) + "\n")
            out.flush()
            if isinstance(message, AssistantMessage):
                turn += 1
                uses = [b.name for b in message.content if isinstance(b, ToolUseBlock)]
                print(f"[model call {now()}] {message.model} (Claude Agent SDK) {label} turn {turn}: "
                      f"{'tools ' + ', '.join(uses) if uses else 'text'}", flush=True)
                bash_ids |= {b.id for b in message.content if isinstance(b, ToolUseBlock) and b.name == "Bash"}
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"  [{block.name}] {str(block.input)[:120]}", flush=True)
            elif isinstance(message, UserMessage) and isinstance(message.content, list):
                for block in message.content:     # results of the agent's commands: saves, chat tests, lint
                    if isinstance(block, ToolResultBlock) and block.tool_use_id in bash_ids:
                        res = block.content if isinstance(block.content, str) else json.dumps(block.content, default=str)
                        res = " ".join((res or "").split())
                        print(f"    -> {'ERROR ' if block.is_error else ''}{res[:400]}{' ...' if len(res) > 400 else ''}", flush=True)
            elif isinstance(message, ResultMessage):
                print(f"\ndone: {message.num_turns} turns, {message.duration_ms / 1000:.0f} s", flush=True)


async def run(slot, tools, briefs):
    t0 = time.time()
    trace = KIT / "runs" / "traces" / f"{slot}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    os.environ["BTB_TRACE"] = str(trace)          # btb/llm.py appends its model calls here too
    print(f"trace: {trace}", flush=True)
    print(f"BUILD START {now()} slot={slot}", flush=True)
    stop_tail = threading.Event()
    tailer = threading.Thread(target=tail_model_calls, args=(str(trace), stop_tail), daemon=True)
    tailer.start()
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
    print(f"[test] datecalc: generated date/amount code run locally on 5 dates and fake products -> "
          f"{'ok' if calc_ok else 'FAILED (build continues without code steps)'} ({time.time() - t_calc:.0f} s)", flush=True)
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
                   "DATE FACTS also carries, when the brief has such rules, EARLIEST PROMISE DATE (cut-off time / minimum days), GAP "
                   "and deadlines already moved back/forward; floors are already rounded the brief's way. "
                   "`unhandled_rules` in that file lists the brief's date/amount rules no code step computes: write each one, in the brief's "
                   "words, into the task_message of the node that applies it (DATE FACTS repeats them under RULES NOT COMPUTED IN CODE). "
                   "Code guards are added to the promise tool after you finish: a date or amount the brief forbids is not sent, and the "
                   "result says NOT RECORDED with `offer_instead` (the one date/amount code computed). Tell the promise node: when a "
                   "result has offer_instead, offer exactly that value. "
                   "If the brief's rule differs from these facts, follow the brief and mention it in your final line.")
    with trace.open("a") as out:
        out.write(json.dumps({"event": "start", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "slot": slot, "tools": tools,
                              "briefs": briefs, "model": options.model}) + "\n")

    print(f"[model] build agent: Claude Agent SDK, {options.model}, skill build-phone-agent, budget {BUDGET_S // 60} min", flush=True)

    async def agent():
        await claude_stream(prompt, options, trace)
    try:
        await asyncio.wait_for(agent(), timeout=max(60, BUDGET_S - (time.time() - t0)))
    except asyncio.TimeoutError:
        print("build agent stopped: time budget reached; finishing with the last written workflow file", flush=True)
        with trace.open("a") as out:
            out.write(json.dumps({"event": "budget", "what": "Claude build agent stopped at the time budget", "seconds": round(time.time() - t0)}) + "\n")
    except Exception as e:  # noqa: BLE001  an SDK/quota error must not skip the final pass on the last written file
        print(f"build agent failed: {str(e)[:300]}; finishing with the last written workflow file", flush=True)
        with trace.open("a") as out:
            out.write(json.dumps({"event": "agent failed", "error": str(e)[:300], "seconds": round(time.time() - t0)}) + "\n")
    # Final deterministic pass on whatever the agent wrote: hooks (honesty / ids / failures), speech block, lint, save.
    wf_file = KIT / "out" / f"{slot}.workflow.json"
    try:
        canned_err = canned_proc.communicate(timeout=240)[1]
    except subprocess.TimeoutExpired:
        canned_proc.kill(); canned_err = "timeout"
    with trace.open("a") as out:
        out.write(json.dumps({"event": "test", "what": "A3 canned sentences extracted (opening tts, say_now hooks, goodbye, FIXED SENTENCES)",
                              "ok": old_canned.exists(), "error": (canned_err or "")[-400:]}) + "\n")
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
    stop_tail.set(); tailer.join(5)
    if state:
        print(f"[freya] slot {slot}: workflow_id={state['workflow_id']} agent_id={state['agent_id']} "
              f"version={state.get('version', 1)} (published)", flush=True)
        # Export what the platform holds: this file is what gets submitted and scored.
        export = KIT / "submission" / f"{slot}.workflow.json"
        export.parent.mkdir(exist_ok=True)
        try:
            sys.path.insert(0, str(KIT))
            import freya
            freya.export_workflow(state["workflow_id"], str(export))
            json.loads(export.read_text())
            print(f"[freya] exported: {export}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[freya] EXPORT FAILED: {e}", flush=True)
    n = scrub_file(trace)
    print(f"BUILD END {now()} ({time.time() - t0:.0f} s); trace scrubbed ({n} secret(s) replaced): {trace}", flush=True)
    if not state:
        sys.exit("builder finished without saving a workflow for slot " + slot)
    print(json.dumps({"workflow_id": state["workflow_id"], "agent_id": state["agent_id"]}))


def parse_args(argv=None):
    """Submission form: build.py <brief.md> <tool_api.json>. Also: build.py [--slot S] [--tools T] <brief.md>...
    A positional ending in .json is the tool API file; the slot defaults to the last brief's file name."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot"); ap.add_argument("--tools"); ap.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    jsons = [p for p in a.paths if p.lower().endswith(".json")]
    briefs = [p for p in a.paths if not p.lower().endswith(".json")]
    if len(jsons) > 1 or (jsons and a.tools):
        ap.error("give exactly one tool API file (a .json positional or --tools)")
    if not briefs:
        ap.error("give at least one brief file")
    tools = jsons[0] if jsons else (a.tools or "tools/openapi.json")
    for p in [tools, *briefs]:
        if not pathlib.Path(p).is_file():
            ap.error(f"file not found: {p}")
    # Absolute paths: the build agent and datecalc run with cwd=KIT, the caller may not.
    tools, briefs = str(pathlib.Path(tools).resolve()), [str(pathlib.Path(b).resolve()) for b in briefs]
    slot = a.slot or pathlib.Path(briefs[-1]).stem
    return slot, tools, briefs


if __name__ == "__main__":
    sys.stdout, sys.stderr = Redacting(sys.stdout), Redacting(sys.stderr)   # never print a key into the submitted trace
    slot, tools, briefs = parse_args()
    print(f"builder: slot={slot} tools={tools} briefs={' '.join(briefs)}", flush=True)
    asyncio.run(run(slot, tools, briefs))
