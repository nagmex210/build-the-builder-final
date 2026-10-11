"""b10-w2 repros on the REAL hook code of a saved workflow.  python3 runs/b10/w2/repro.py out/w2-A.workflow.json"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hookrun import tool, pre, post, http

wf = json.load(open(sys.argv[1]))
T = tool(wf, "create_promise", "negotiate")
BANK_OK = lambda pid: {"status": "success", "status_code": 200, "message": "ok", "data": {"ok": True, "promise_id": "PR-" + pid}, "header": {}}
BANK_500 = lambda: {"status": "error", "status_code": 500, "message": "service unavailable", "data": {"ok": False, "error": "service unavailable"}, "header": {}}


def fresh():
    return {"now": "2026-10-12T10:00:00",   # Monday
            "guard_products": json.dumps({"P1": {"deadline": "2026-10-20", "floor": 100.0, "max": 500.0},
                                          "P2": {"deadline": "2026-10-20", "floor": 50.0, "max": 300.0}})}


def outcome(r):
    d = r.get("data") or {}
    return (str(d.get("ok")) + " | " + str(d.get("tool_outcome"))[:150] + (" | say_now: " + d["say_now"][:80] if d.get("say_now") else ""))


def call(v, body, bank):
    c = pre(T, v, body)
    r = http(c) or bank()
    return post(T, v, r, c)


def r1():
    print("R1 sequential: real failure -> guard block -> real failure: which failure number does the model see?")
    v = fresh()
    good = {"customer_id": "C1", "product_id": "P1", "amount": "500", "date": "2026-10-16"}
    print("  1 bank 500    :", outcome(call(v, good, BANK_500)), "| tool_failures =", v.get("tool_failures_create_promise"))
    bad = dict(good, date="2026-10-30")
    print("  2 guard block :", outcome(call(v, bad, lambda: None)), "| tool_failures =", v.get("tool_failures_create_promise"))
    print("  3 bank 500    :", outcome(call(v, good, BANK_500)), "| tool_failures =", v.get("tool_failures_create_promise"))


def r2():
    print("R2 two create_promise in ONE turn, hooks interleaved (pre1 pre2 call1 call2 post1 post2): P1 after deadline, P2 valid")
    for order in ("sequential", "interleaved"):
        v = fresh()
        b1 = {"customer_id": "C1", "product_id": "P1", "amount": "500", "date": "2026-10-30"}
        b2 = {"customer_id": "C1", "product_id": "P2", "amount": "300", "date": "2026-10-16"}
        if order == "sequential":
            c1 = pre(T, v, b1); r1_ = post(T, v, http(c1) or BANK_OK("P1"), c1)
            c2 = pre(T, v, b2); r2_ = post(T, v, http(c2) or BANK_OK("P2"), c2)
        else:
            c1 = pre(T, v, b1); c2 = pre(T, v, b2)
            x1 = http(c1) or BANK_OK("P1"); x2 = http(c2) or BANK_OK("P2")
            r1_ = post(T, v, x1, c1); r2_ = post(T, v, x2, c2)
        print(f"  {order:11s} P1 sent to {c1['url'].split('/')[-1]:15s} model sees:", outcome(r1_))
        print(f"  {order:11s} P2 sent to {c2['url'].split('/')[-1]:15s} model sees:", outcome(r2_))
        print(f"  {order:11s} writes_ok keys:", list(json.loads(v.get('writes_ok') or '{}')))


def r4():
    print("R4 the bank answers 200 ok=false (rejects the values) vs a 500 (service failure): what does the model hear?")
    V = tool(wf, "verify_identity", "identity")
    v = fresh()
    c = pre(V, v, {"customer_id": "C1", "field": "date_of_birth", "answer": "14 March"})
    r = post(V, v, {"status": "success", "status_code": 200, "message": "", "data": {"ok": False, "error": "answer is not a date. Send it as YYYY-MM-DD."}, "header": {}}, c)
    print("  verify 200 ok=false :", r["data"].get("tool_outcome", "")[:400], "|| say_next:", r["data"].get("say_next"))
    good = {"customer_id": "C1", "product_id": "P1", "amount": "500", "date": "2026-10-16"}
    r = call(v, good, lambda: {"status": "success", "status_code": 200, "message": "", "data": {"ok": False, "error": "amount must be a number"}, "header": {}})
    print("  promise 200 ok=false:", r["data"].get("tool_outcome", "")[:400])
    r = call(v, good, BANK_500)
    print("  promise 500         :", r["data"].get("tool_outcome", "")[:400])


if __name__ == "__main__":
    for f in sys.argv[2:] or ["r1", "r2"]:
        globals()[f]()
