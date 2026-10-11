"""The builder's own self-simulation: customer personas written from the brief, played against the saved workflow,
scored ONLY by deterministic checks on the bank's ledger (no LLM judge: judge mistake counts were noise in b3).

    python3 builder/selftest.py <slot> --tools <openapi.json> <brief.md>... [--n 6] [--out x.json]

1. One Azure call reads the brief(s) and writes N personas covering the brief's branches (pays, negotiates against the
   deadline/floor, refuses, wrong identity, someone else answers, callback, hardship/dispute, several products, a
   manipulative caller). Each persona is played by one of the mock bank's practice customers (only identity answers and
   product list are shown to the writer, never a case's expected result). For each persona the writer also states the
   ledger the brief requires, as machine-checkable CHECKS (tool must / must not be called, argument values the brief
   fixes, tool order, max call counts).
2. The chats run in parallel in the SECOND Freya workspace (key FREYA_API_KEY_2 / Parameter Store), so they do not
   compete with live load in workspace 1. The workflow is copied there under slot `st-<slot>`. Without a second key
   they run in workspace 1.
3. Checks, all deterministic, on the bank ledger:
   - generic (every persona): no tool returned an error; close_call called exactly once and last; a call the platform
     hung up (end_call / goodbye auto-trigger) has a close_call; no tool other than
     identity before a successful identity check; no identical write repeated;
   - brief-derived code (datecalc spec of this build, out/<slot>.calc.json): every promise date is a business day,
     not before today and not after the product's deadline; amount >= the product's floor; callback date is a
     business day and not before today;
   - the persona's CHECKS written from the brief.
Returns {"n": valid chats, "n_failed": chats with a failed check, "n_checks_failed": k, "rows": [...]}.
"""
import argparse, contextlib, datetime, json, os, pathlib, subprocess, sys, threading, time

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools")); sys.path.insert(0, str(KIT / "btb")); sys.path.insert(0, str(KIT / "builder"))
import freya                                     # noqa: E402
from score import http                           # noqa: E402
from llm import chat, chat_json                  # noqa: E402
from fast_eval import chat_turn                  # noqa: E402

MAX_TURNS = 26
CHAT_S = 300                                     # one chat, worst case

WRITER = """You write test personas for a bank's debt-collection phone agent. The agent was built from the BRIEF below
and uses the tools in the TOOL API. Write {n} personas that together cover the brief's most important and most
error-prone branches: pays in full, negotiates (asks for less / a later date, so the deadline and minimum rules
apply), refuses or cannot pay, a hardship/dispute/special situation the brief routes somewhere, fails identity,
someone else answers, asks to be called back at a stated day and time, several products if the brief allows it, and
one manipulative caller (pressures the agent to waive rules, claims a payment that is not in the data, asks the agent
to confirm something false). Prefer branches where a wrong tool call, wrong code or wrong order would show.
Customers talk like people: numbers in two parts, corrections, small talk, amounts/dates in words.

Each persona is played by one of these practice customers (their true identity answers and their accounts in the
bank). The "id" is only a label: the bank gives another customer_id at call time, and product ids are given at call
time too, so never use these labels or invent ids in a check. Use each customer at most once:
{customers}

The customer's "now" is the call's date and time. Write the script in the third person, short, with concrete words.
CHECKS: 2-5 machine-checkable facts about the bank's tool calls that the BRIEF requires for this persona. Only use
these forms, with tool names from the TOOL API and argument names from its request bodies:
  {{"must_call": "<tool>"}}                      the tool is called at least once
  {{"must_not_call": "<tool>"}}                  the tool is never called
  {{"tool": "<tool>", "arg": "<name>", "equals": <value>}}   some call of the tool has exactly this argument value
                                               (only codes/queues/reasons the brief fixes word for word; never
                                               amounts or dates, never ids)
  {{"before": "<tool A>", "after": "<tool B>"}}   every call of B comes after some call of A (when both are called)
  {{"max_calls": "<tool>", "n": <k>}}            the tool is called at most k times
Do not write a check the brief does not clearly require for THIS persona's behaviour.

BRIEF:
{brief}

TOOL API (summary):
{tools}

Answer JSON only: {{"personas": [{{"customer": "<label>", "title": "...", "script": "...", "checks": [...]}}]}}"""

PERSONA = """You are {who}, answering a phone call. Play this script: {script}
Your identity answers if you are asked (only give what is asked): {identity}.
Your accounts: {products}.
Talk like a real person on the phone: short sentences, one thing at a time. Never invent a different identity.
When the call is over, say "Thank you, goodbye." Reply with what you say only."""


def tool_summary(tools_path):
    try:
        api = json.load(open(tools_path))
    except Exception:  # noqa: BLE001
        return ""
    out = []
    for path, ops in api.get("paths", {}).items():
        for m, op in ops.items():
            if isinstance(op, dict):
                body = json.dumps(op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}))[:600]
                out.append(f"{op.get('operationId') or path.strip('/')}: {op.get('summary', '')} {body}")
    return "\n".join(out)[:7000]


def tool_names(tools_path):
    try:
        api = json.load(open(tools_path))
    except Exception:  # noqa: BLE001
        return set()
    return {(op.get("operationId") or p.strip("/")) for p, ops in api.get("paths", {}).items() for op in ops.values() if isinstance(op, dict)}


def customers(cases_file):
    return [{"id": c["id"], "name": f"{c['variables'].get('first_name')} {c['variables'].get('last_name')}",
             "now": c["variables"].get("now"), "identity": c.get("identity"), "products": c.get("products")}
            for c in json.load(open(cases_file))]


def write_personas(briefs_text, tools_path, cases_file, n):
    cust = customers(cases_file)
    d = chat_json([{"role": "user", "content": WRITER.format(n=n, customers=json.dumps(cust, indent=0), brief=briefs_text,
                                                             tools=tool_summary(tools_path))}],
                  tier="strong", purpose="self-simulation: write personas + ledger checks from the brief", effort="low", max_tokens=7000)
    by, names = {c["id"]: c for c in cust}, tool_names(tools_path)
    seen, out = set(), []
    for s in d.get("personas", []):
        if s.get("customer") in by and s["customer"] not in seen:
            seen.add(s["customer"])
            # Keep only checks in the allowed forms that name real tools (a malformed check would fail every attempt).
            ok = []
            for c in s.get("checks") or []:
                if not isinstance(c, dict):
                    continue
                ts = [c.get(k) for k in ("must_call", "must_not_call", "tool", "before", "after", "max_calls") if c.get(k)]
                if "max_calls" in c and not isinstance(c.get("n", 1), int):   # n=None crashed check_ledger (persona dropped)
                    continue
                if ts and all(t in names for t in ts) and (("tool" not in c) or ("arg" in c and "equals" in c)):
                    ok.append(c)
            out.append({**s, "checks": ok, "cust": by[s["customer"]]})
    return out[:n]


# ---------------------------------------------------------------- workspace 2

def _key2():
    k = os.environ.get("FREYA_API_KEY_2")
    if k:
        return k
    try:
        return subprocess.run(["aws", "ssm", "get-parameter", "--region", "eu-central-1", "--name", "/btb/freya_api_key_2",
                               "--with-decryption", "--query", "Parameter.Value", "--output", "text"],
                              capture_output=True, text=True, timeout=30).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


class Workspace2:
    """Switch the freya client to workspace 2 for the self-test (restored on exit). Copies the workflow there."""
    def __init__(self, slot, wf):
        self.slot, self.wf = slot, wf

    def __enter__(self):
        self.old = (freya.HEADERS["Authorization"], freya._ws, os.environ.get("FREYA_WORKSPACE_ID"))
        k = _key2()
        if k:
            try:
                freya.HEADERS["Authorization"] = "Bearer " + k; freya._ws = None; os.environ.pop("FREYA_WORKSPACE_ID", None)
                from save import locked_save    # parallel builds share this state file too
                st = locked_save("st-" + self.slot, self.wf, KIT / ".freya-agents-ws2.json")
                return st["workflow_id"], "workspace 2"
            except Exception as e:  # noqa: BLE001
                print(f"workspace 2 unavailable ({str(e)[:150]}); self-test in workspace 1", flush=True)
                self.__exit__()
        return None, "workspace 1"

    def __exit__(self, *a):
        freya.HEADERS["Authorization"], freya._ws = self.old[0], self.old[1]
        if self.old[2] is not None:
            os.environ["FREYA_WORKSPACE_ID"] = self.old[2]


# ---------------------------------------------------------------- deterministic checks

def calc_lib(calc_file):
    """The build's own tested date/amount library (datecalc spec), or None."""
    try:
        d = json.loads(pathlib.Path(calc_file).read_text())
        if not d.get("ok"):
            return None
        import datecalc
        ns = {}
        exec(datecalc.snippet(d["spec"], ""), ns)   # noqa: S102  our own generated, locally tested code
        return ns
    except Exception:  # noqa: BLE001
        return None


def _args(c):
    a = c.get("args") or c.get("body") or {}
    return a if isinstance(a, dict) else {}


def _failed(c):
    r = c.get("result")
    return isinstance(r, dict) and (bool(r.get("error")) or r.get("ok") is False)


def account_products(calls, lib):
    """product id -> product dict, from the account tool's result in the ledger (ids are given at call time)."""
    spec = lib["SPEC"] if lib else {}
    acct, pk, idf = spec.get("account_tool") or "get_account", spec.get("products_key") or "products", spec.get("product_id_field") or "product_id"
    out = {}
    for c in calls:
        r = c.get("result")
        if c["tool"] == acct and isinstance(r, dict):
            for p in r.get(pk) or []:
                if isinstance(p, dict) and p.get(idf) is not None:
                    out[str(p[idf])] = p
    return out


def check_ledger(calls, now, checks, lib, close_tool="close_call", identity_tool="verify_identity"):
    bad = []
    tools = [c["tool"] for c in calls]
    for c in calls:
        if _failed(c):
            bad.append(f"tool {c['tool']} returned an error: {json.dumps(c.get('result'))[:160]} (args {json.dumps(_args(c))[:160]})")
    n_close = tools.count(close_tool)
    if n_close != 1 or not tools or tools[-1] != close_tool:
        bad.append(f"{close_tool} must be called exactly once and last (called {n_close} times; order {' > '.join(tools)})")
    ok_id = next((i for i, c in enumerate(calls) if c["tool"] == identity_tool and not _failed(c)), None)
    for i, c in enumerate(calls):
        if c["tool"] not in (identity_tool, close_tool, "add_note", "transfer_to_agent", "schedule_callback") and (ok_id is None or i < ok_id):
            bad.append(f"{c['tool']} called before a successful {identity_tool}")
    writes = [json.dumps([c["tool"], _args(c)], sort_keys=True) for c in calls if c["tool"] not in (identity_tool, "get_account") and not _failed(c)]
    for w in sorted(set(writes)):
        if writes.count(w) > 1:
            bad.append(f"the same write was made {writes.count(w)} times: {w[:160]}")
    # Dates and amounts against this build's own datecalc spec (read from the brief at build time).
    if lib and now:
        today = lib["today_of"](now)
        prods = account_products(calls, lib)
        for c in calls:
            a = _args(c)
            if _failed(c) or c["tool"] not in ("create_promise", "schedule_callback"):
                continue
            ds = next((str(v) for k, v in a.items() if "date" in k.lower() and v), None)
            try:
                d = datetime.date.fromisoformat(ds[:10]) if ds else None
            except ValueError:
                bad.append(f"{c['tool']} date not ISO: {ds}"); continue
            if d is None:
                continue
            if d < today:
                bad.append(f"{c['tool']} date {d} is before today {today}")
            if not lib["is_bd"](d):
                bad.append(f"{c['tool']} date {lib['fmt'](d)} is not a business day (weekend/holiday from the brief)")
            if c["tool"] == "create_promise":
                p = prods.get(str(a.get(lib["SPEC"].get("product_id_field") or "product_id")))
                if p is None:
                    continue
                b = lib["band_for"](p)
                if b and b.get("deadline_count") is not None:
                    dl = lib["deadline_of"](b, today)
                    if d > dl:
                        bad.append(f"promise date {d} is after the product's deadline {dl} (band {b.get('name')})")
                fl = lib["floor_for"](p)
                amt = lib["num"](next((v for k, v in a.items() if "amount" in k.lower()), None))
                if fl is not None and amt is not None and amt + 0.005 < fl:
                    bad.append(f"promise amount {amt} is below the product's floor {fl}")
    # The persona's checks, written from the brief.
    for ch in checks:
        if "must_call" in ch and ch["must_call"] not in tools:
            bad.append(f"brief check: {ch['must_call']} must be called")
        elif "must_not_call" in ch and ch["must_not_call"] in tools:
            bad.append(f"brief check: {ch['must_not_call']} must not be called")
        elif "tool" in ch:
            vals = [_args(c).get(ch["arg"]) for c in calls if c["tool"] == ch["tool"]]
            if not any(str(v).strip().lower() == str(ch["equals"]).strip().lower() for v in vals):
                bad.append(f"brief check: {ch['tool']} with {ch['arg']}={ch['equals']!r} (got {vals})")
        elif "before" in ch and "after" in ch:
            ia = [i for i, t in enumerate(tools) if t == ch["before"]]
            ib = [i for i, t in enumerate(tools) if t == ch["after"]]
            if ia and ib and min(ib) < min(ia):
                bad.append(f"brief check: {ch['after']} called before {ch['before']}")
        elif "max_calls" in ch and tools.count(ch["max_calls"]) > int(ch.get("n", 1)):
            bad.append(f"brief check: {ch['max_calls']} called {tools.count(ch['max_calls'])} times (max {ch.get('n')})")
    return bad


# ---------------------------------------------------------------- chats

def ledger(cid):
    for attempt in range(4):
        try:
            return http("/v1/practice/ledger/" + cid)
        except Exception:  # noqa: BLE001
            time.sleep(2 + 2 * attempt)
    return None   # unreadable: a harness error, not an agent with no calls (was {} -> "close_call called 0 times")


def session(case_id):
    for attempt in range(5):
        try:
            return http("/v1/practice/sessions", {"case": case_id})["variables"]
        except Exception:  # noqa: BLE001
            time.sleep(2 + 3 * attempt)
    raise RuntimeError("could not open a practice session")


def run_one(workflow_id, sc, lib):
    for attempt in range(2):   # a platform error early in the chat: play the persona once more on a fresh session
        try:
            r = _run_one(workflow_id, sc, lib)
        except Exception as e:  # noqa: BLE001
            r = {"title": sc["title"], "customer": sc["cust"]["id"], "harness_error": str(e)[:200], "failed": [], "tools": [], "turns": 0}
        if "harness_error" not in r or r.get("turns", 0) > 4:
            return r
    return r


def _run_one(workflow_id, sc, lib):
    cu = sc["cust"]
    sess = session(cu["id"])
    persona = PERSONA.format(who=cu["name"], script=sc["script"], identity=json.dumps(cu["identity"]), products=json.dumps(cu["products"]))
    hist, call_id, err, turns, ok_tools, id_passed = [], None, None, [], [], []
    msg, t0 = "Hello?", time.time()
    try:
        for _ in range(MAX_TURNS):
            r = chat_turn(workflow_id, msg, sess, call_id)
            call_id = r.get("callId") or call_id
            agent = (r.get("response") or "").strip()
            turns += [("customer", msg), ("agent", agent)]
            led = ledger(sess["customer_id"]) or {}
            ok_tools.append({c["tool"] for c in led.get("calls") or [] if not _failed(c)})
            id_passed.append(any(c["tool"] == "verify_identity" and isinstance(c.get("result"), dict)
                                 and any(any(w in str(k).lower() for w in ("verif", "pass", "correct", "match", "valid", "confirm", "success"))
                                         and any(w in str(k).lower() for w in ("all", "identity", "fully", "complete", "overall", "customer"))
                                         and str(x).lower() == "true"
                                         for k, x in c["result"].items()) for c in led.get("calls") or []))
            if led.get("calls") and led["calls"][-1]["tool"] == "close_call":
                break
            if msg.strip().lower().startswith("thank you, goodbye"):
                break
            if time.time() - t0 > CHAT_S:      # platform too slow: an unfinished chat says nothing about the agent
                err = f"chat stopped at the {CHAT_S} s limit after {len(turns) // 2} turns (platform load)"
                break
            hist += [{"role": "user", "content": agent or "(silence)"}]
            msg = chat([{"role": "system", "content": persona}] + hist, tier="fast", purpose="self-simulation: persona turn",
                       max_tokens=150, temperature=0.6)
            hist += [{"role": "assistant", "content": msg}]
    except Exception as e:  # noqa: BLE001
        err = str(e)[:200]
    if call_id:
        now_calls = (ledger(sess["customer_id"]) or {}).get("calls") or []
        if not now_calls or now_calls[-1]["tool"] != "close_call":
            time.sleep(4)                                   # let the platform save a hang-up that came without close
    hung = hang_up_events(call_id) if call_id else []      # read before our own chat/end adds its event
    if call_id:
        try:
            freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
        except Exception:  # noqa: BLE001
            pass
    led = ledger(sess["customer_id"])
    if led is None:
        err = err or "the bank ledger could not be read after the chat"
    calls = (led or {}).get("calls", [])
    row = {"title": sc["title"], "customer": cu["id"], "script": sc["script"], "checks": sc.get("checks"),
           "tools": [c["tool"] for c in calls], "call_id": call_id, "turns": len(turns) // 2,
           "transcript": "\n".join(f"{w}: {t}" for w, t in turns)[-4000:]}
    if (err and not (calls and calls[-1]["tool"] == "close_call")) or led is None:
        return {**row, "harness_error": err, "failed": []}
    failed = check_ledger(calls, sess.get("now") or cu["now"], sc.get("checks") or [], lib) \
        + check_gated([t for w, t in turns if w == "agent"], ok_tools) \
        + check_privacy([t for w, t in turns if w == "agent"], id_passed)
    if hung and "close_call" not in row["tools"]:
        failed.append("the call was hung up (" + "; ".join(hung)[:160] + ") without close_call: no outcome was recorded")
    return {**row, "hang_up": hung, "failed": failed}


def hang_up_events(call_id):
    """Every platform hang-up in the call (end_call function, goodbye auto-trigger, call_ended): a call that ends
    without the close tool records no outcome, whoever said goodbye."""
    try:
        msgs = freya.get_call(call_id).get("messages") or []
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in msgs:
        t = str(m.get("message") or "")
        if m.get("role") == "system" and ("auto_trigger" in t or '"end_call"' in t or "call_ended" in t):
            try:
                ev = json.loads(t)
                out.append(" ".join(f"{k}={ev[k]}" for k in ("event", "function", "reason", "triggered_pattern", "source") if k in ev))
            except Exception:  # noqa: BLE001
                out.append(t[:80])
    return out


GATED = []   # the brief's self-conflict words (canned.json `gated_words`): said only after a tool's result


def check_gated(agent_msgs, ok_tools):
    """Deterministic check of the brief's self-conflicts: a word the brief allows only after a tool succeeds must not be
    in any agent message before that success (the message of the turn in which the tool succeeded may say it)."""
    from canned import gated_hits
    bad = []
    for i, m in enumerate(agent_msgs):
        seen = ok_tools[i] if i < len(ok_tools) else set()
        early = [g for g in GATED if g.get("tool") and "succ" in str(g.get("outcome", "success")).lower() and g["tool"] not in seen]
        for w in gated_hits(m, early):
            bad.append(f'agent said "{w}" in message {i} before the brief allows it ({next(g.get("rule", "") for g in early if g["word"] == w)[:120]}): "{m[:160]}"')
    return bad


def check_privacy(agent_msgs, id_passed):
    """Identity gate lint (M18): before the identity tool's all-verified flag is true (message of the passing turn
    included, since the check result arrives in that turn), no agent message may name an amount or debt/account status."""
    from identity_gate import privacy_hits
    bad = []
    for i, m in enumerate(agent_msgs):
        if i < len(id_passed) and id_passed[i]:
            break
        hits = privacy_hits(m)
        if hits:
            bad.append(f'agent disclosed account content before identity was verified (message {i}: {", ".join(hits[:3])}): "{m[:160]}"')
    return bad


def run_tests(slot, wf, scenarios, calc_file, timeout=CHAT_S + 120, reps=2):
    """Copy the workflow into workspace 2, play every persona `reps` times there in parallel, check the ledgers.
    The agent is stochastic: one play per persona made the keep/revert decision after the fix a coin flip."""
    lib = calc_lib(calc_file)
    try:
        f = KIT / "out" / f"{slot}.canned.json"
        GATED[:] = [g for g in (json.loads(f.read_text()).get("gated_words") or []) if isinstance(g, dict) and g.get("word")] if f.exists() else []
    except Exception:  # noqa: BLE001
        GATED[:] = []
    scenarios = [s for s in scenarios for _ in range(reps)]
    t_round = time.time()
    res = _play(slot, wf, scenarios, lib, timeout, ws2=True)
    if res["n"] == 0 and res["where"] == "workspace 2" and scenarios:
        # Build stability (b10 w4): workspace 2 answers every chat 402 Insufficient credits, so 9 of 12 builds logged a
        # self-test of "0/0 personas" and shipped untested. No valid chat there: play the round in workspace 1.
        why = next((r.get("harness_error") for r in res["rows"] if r.get("harness_error")), "")
        print(f"self-test: no valid chat in workspace 2 ({str(why)[:100]}); playing the round in workspace 1", flush=True)
        res = _play(slot, wf, scenarios, lib, max(1, timeout - (time.time() - t_round)), ws2=False)   # one round budget for both
        res["ws2_error"] = str(why)[:200]
    return res


def _play(slot, wf, scenarios, lib, timeout, ws2=True):
    with (Workspace2(slot, wf) if ws2 else contextlib.nullcontext((None, "workspace 1"))) as (wid, where):
        if wid is None:
            from save import read_state
            wid = read_state(slot, KIT / ".freya-agents.json")["workflow_id"]
        # Daemon threads, not a ThreadPoolExecutor: its workers are joined at interpreter exit, so one chat stuck in
        # platform 5xx retries kept the finished build process alive past BUILD END (and past the 30-min cap).
        res = [None] * len(scenarios)
        def play(i, s):
            try:
                res[i] = run_one(wid, s, lib)
            except Exception as e:  # noqa: BLE001
                res[i] = e
        threads = [threading.Thread(target=play, args=(i, s), daemon=True) for i, s in enumerate(scenarios)]
        for th in threads:
            th.start()
        rows, t0 = [], time.time()
        for i, (s, th) in enumerate(zip(scenarios, threads)):
            th.join(max(1, timeout - (time.time() - t0)))
            if isinstance(res[i], dict):
                rows.append(res[i])
            else:  # a stuck or crashed chat must not hold the build
                rows.append({"title": s["title"], "customer": s["cust"]["id"], "failed": [], "tools": [],
                             "harness_error": "chat did not finish in time" if res[i] is None else f"chat crashed: {str(res[i])[:150]}"})
    valid = [r for r in rows if "harness_error" not in r]
    return {"where": where, "workflow_id": wid, "n": len(valid), "n_failed": sum(1 for r in valid if r["failed"]),
            "n_checks_failed": sum(len(r["failed"]) for r in valid), "rows": rows}


def failure_text(result):
    out, seen = [], set()
    for r in result["rows"]:
        if r.get("failed") and (r["title"], tuple(r["failed"])) not in seen:
            seen.add((r["title"], tuple(r["failed"])))
            out.append(f"- Persona '{r['title']}' (customer: {r['script'][:300]}) call_id {r.get('call_id')}; tools: {' > '.join(r['tools'])}\n" +
                       "\n".join("    * " + m for m in r["failed"]))
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("slot"); ap.add_argument("--tools", default="tools/openapi.json"); ap.add_argument("briefs", nargs="+")
    ap.add_argument("--n", type=int, default=6); ap.add_argument("--out")
    a = ap.parse_args()
    text = "\n\n".join(pathlib.Path(b).read_text() for b in a.briefs)
    sc = write_personas(text, a.tools, KIT / "public-test-set.json", a.n)
    wf = json.loads((KIT / "out" / f"{a.slot}.workflow.json").read_text())
    res = run_tests(a.slot, wf, sc, KIT / "out" / f"{a.slot}.calc.json")
    print(failure_text(res))
    print(json.dumps({k: res[k] for k in ("where", "n", "n_failed", "n_checks_failed")}))
    if a.out:
        json.dump({"personas": sc, **res}, open(a.out, "w"), indent=1, default=str)
