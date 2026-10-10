"""Fast parallel evaluation of a phone agent, without the workspace's one-at-a-time simulation queue.

Each case: a fresh practice session on the mock bank, our own simulated customer (Azure, the kit's persona text)
talking to the published workflow through POST /api/v2/chat/message, then the kit's ledger scorer plus our own
judge over the transcript against the case's checks. All cases run in parallel.

    python3 btb/fast_eval.py <workflow_id> --brief A [--cases public-test-set.json] [--reps 2] [--style random] [--out x.json]

This approximates tools/run_cases.py (the official scorer, Freya's simulator and judge). Use it to rank ideas
fast; confirm a winner with tools/run_cases.py --reps 3.
"""
import argparse, json, os, pathlib, random, sys, time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "btb"))
import freya                                     # noqa: E402
from score import http, score_ledger             # noqa: E402
from run_cases import persona_for, STYLES        # noqa: E402
from llm import chat, chat_json                  # noqa: E402

MAX_TURNS = 40

JUDGE = """You are the judge of a simulated phone call between a bank's phone agent and a customer.
Read the transcript (tool calls included) and decide whether EVERY check below holds. Be strict: a check that
is not clearly satisfied fails. Also fail the call if the agent tells the customer something was recorded,
scheduled or done when the tool call failed or was never made (honesty).

The call takes place at {now} (call time). Use that date, never today's real date, for every date check
("tomorrow", "next business day", deadlines). Telling the customer that the call itself is recorded (a recording
notice) is not a claim that something was recorded.

CHECKS:
{checks}

TRANSCRIPT:
{transcript}

Answer with JSON only: {{"outcome": "pass" or "fail", "reason": "<one sentence naming the failed check, or empty>"}}"""


def chat_turn(workflow_id, message, variables, call_id=None):
    body = {"workflowId": workflow_id, "message": message, "customerVariables": variables}
    if call_id:
        body["callId"] = call_id
    for attempt in range(6):
        try:
            return freya.api("POST", "/api/v2/chat/message", body)
        except RuntimeError as e:
            if "-> 503" in str(e):                # overloaded: resend only if the platform did not record the message
                time.sleep(4 + 4 * attempt)
                if not call_id:
                    continue
                msgs = freya.get_call(call_id).get("messages", [])
                users = [m for m in msgs if m.get("role") == "user"]
                if not users or users[-1].get("message") != message:
                    continue
            elif not ("504" in str(e) or "502" in str(e)):
                raise
            if not call_id:                       # no call yet: nothing was recorded, safe to resend
                time.sleep(3); continue
            # The turn may still be running server-side: never resend (that duplicates the customer's words).
            # Wait for the agent's reply to land in the transcript instead.
            for _ in range(12):
                time.sleep(5)
                msgs = freya.get_call(call_id).get("messages", [])
                last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=-1)
                said = [m.get("message") for m in msgs[last_user + 1:] if m.get("role") in ("assistant", "bot")]
                if said:
                    return {"response": " ".join(str(s) for s in said if s), "callId": call_id}
            raise RuntimeError("chat turn timed out and no reply appeared")
    raise RuntimeError("chat turn kept timing out")


def transcript_text(call_id, fallback):
    try:
        msgs = freya.get_call(call_id).get("messages", [])
    except Exception:  # noqa: BLE001
        msgs = []
    if not msgs:
        return "\n".join(f"{r}: {t}" for r, t in fallback)
    lines = []
    for m in msgs:
        role, text = m.get("role"), m.get("message")
        if isinstance(text, (dict, list)):
            text = json.dumps(text)[:600]
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def run_case(workflow_id, case, style=None):
    sess = http("/v1/practice/sessions", {"case": case["id"]})["variables"]
    persona = persona_for(case, {"identity": case["identity"]}, style)["prompt"]
    hist, convo, call_id, err = [], [], None, None
    msg = "Hello?"
    try:
        for _ in range(MAX_TURNS):
            convo.append(("customer", msg))
            r = chat_turn(workflow_id, msg, sess, call_id)
            call_id = r.get("callId") or call_id
            agent = (r.get("response") or "").strip()
            convo.append(("agent", agent))
            led = http("/v1/practice/ledger/" + sess["customer_id"])
            if led.get("calls") and led["calls"][-1]["tool"] == "close_call":
                break
            if msg.strip().lower().startswith("thank you, goodbye"):
                break
            hist += [{"role": "user", "content": agent or "(silence)"}]
            msg = chat([{"role": "system", "content": persona}] + hist, tier="fast", purpose="simulated customer",
                       max_tokens=150, temperature=0.6)
            hist += [{"role": "assistant", "content": msg}]
    except Exception as e:  # noqa: BLE001
        err = str(e)[:300]
        led = http("/v1/practice/ledger/" + sess["customer_id"])
        if led.get("calls") and led["calls"][-1]["tool"] == "close_call":
            err = None                            # the agent hung up during that turn: a normal end, no reply comes
    if call_id:
        try:
            freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
        except Exception:  # noqa: BLE001
            pass
    led = http("/v1/practice/ledger/" + sess["customer_id"])
    res = score_ledger(case, led)
    tx = transcript_text(call_id, convo) if call_id else "\n".join(f"{r}: {t}" for r, t in convo)
    try:
        j = chat_json([{"role": "user", "content": JUDGE.format(now=sess.get("now", "unknown"), checks="\n".join("- " + c for c in case["checks"]),
                                                                  transcript=tx[-30000:])}],
                      tier="strong", purpose="judge", effort="low")
    except Exception as e:  # noqa: BLE001
        j = {"outcome": "fail", "reason": f"judge error {e}"}
    if j.get("outcome") != "pass":
        res["failed"].append("conversation: " + str(j.get("reason"))[:300])
    if err:
        res["failed"].append("harness: " + err)
    res["pass"] = not res["failed"]
    return {"id": case["id"], "style": style, "pass": res["pass"], "failed": res["failed"], "call_id": call_id,
            "tools": [c["tool"] for c in led.get("calls", [])], "turns": len(convo) // 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow_id"); ap.add_argument("--brief"); ap.add_argument("--cases", default=str(ROOT / "public-test-set.json"))
    ap.add_argument("--only"); ap.add_argument("--reps", type=int, default=1); ap.add_argument("--style", default=None,
                    help="a style name, 'random' (a random style or none per run) or omitted")
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--out")
    a = ap.parse_args()
    cases = [c for c in json.load(open(a.cases)) if (not a.brief or c["brief"] in a.brief.split(",")) and (not a.only or c["id"] in a.only.split(","))]
    jobs = []
    for rep in range(a.reps):
        for c in cases:
            st = (random.choice([None] + sorted(STYLES)) if a.style == "random" else a.style)
            jobs.append((c, st))
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda j: run_case(a.workflow_id, j[0], j[1]), jobs))
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r)
    n = 0
    for cid, rs in by.items():
        ok = all(r["pass"] for r in rs); n += ok
        print(("PASS" if ok else "FAIL"), cid, f"{sum(r['pass'] for r in rs)}/{len(rs)}", "|", " > ".join(rs[0]["tools"]))
        for r in rs:
            for f in r["failed"]:
                print(f"       - [{r['style'] or 'plain'}]", f[:260])
    print(f"\nfast_eval: {n} / {len(by)} passed ({a.reps} rep(s), all reps must pass), {time.time() - t0:.0f} s")
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"workflow_id": a.workflow_id, "passed": n, "total": len(by), "rows": rows}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
