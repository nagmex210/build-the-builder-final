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
    import copy
    for order in ("sequential", "interleaved", "sibling-vars"):
        v = fresh()
        b1 = {"customer_id": "C1", "product_id": "P1", "amount": "500", "date": "2026-10-30"}
        b2 = {"customer_id": "C1", "product_id": "P2", "amount": "300", "date": "2026-10-16"}
        if order == "sequential":
            c1 = pre(T, v, b1); r1_ = post(T, v, http(c1) or BANK_OK("P1"), c1)
            c2 = pre(T, v, b2); r2_ = post(T, v, http(c2) or BANK_OK("P2"), c2)
        elif order == "sibling-vars":
            # seen on Freya (probe): a post-hook can read a SIBLING's vars instead of its own pre-hook's writes
            v1, v2 = copy.deepcopy(v), copy.deepcopy(v)
            c1 = pre(T, v1, b1); c2 = pre(T, v2, b2)
            x1 = http(c1) or BANK_OK("P1"); x2 = http(c2) or BANK_OK("P2")
            r1_ = post(T, v2, x1, c1); r2_ = post(T, v1, x2, c2); v = v1
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



def route(node, v, last):
    """First matching transition of a node (equals / or groups only), with the last result flattened like the platform."""
    flat = dict(v)
    for k, x in (last.get("data") or {}).items():
        flat["verify_identity_response.data." + k] = str(x)
    def ok(c):
        if isinstance(c.get("conditions"), list):
            r = [ok(x) for x in c["conditions"]]
            return all(r) if c.get("logic") == "and" else any(r)
        if c.get("operator") == "equals":
            return str(flat.get(c.get("variable"))) == str(c.get("operand"))
        return False
    for tr in wf["nodes"][node]["transitions"]:
        if not tr.get("is_tool_call") and ok(tr.get("condition") or {}):
            return tr["target_node"]
    return "(stays in " + node + ")"


def r5():
    print("R5 identity gate: (a) bank result without a call-wide flag, both answers right; (b) two verify calls in one turn, the stale sibling's result lands last")
    V = tool(wf, "verify_identity", "identity")
    ok = lambda d: {"status": "success", "status_code": 200, "message": "", "data": dict(d), "header": {}}
    v = fresh()
    for b, d in [({"field": "date_of_birth", "answer": "1989-02-23"}, {"ok": True, "verified": True, "wrong_answers_left": 3}),
                 ({"field": "phone_last4", "answer": "9904"}, {"ok": True, "verified": True, "wrong_answers_left": 3})]:
        c = pre(V, v, dict(b, customer_id="C1")); last = post(V, v, ok(d), c)
    print("  (a) identity_state =", v.get("identity_state"), "| say_next:", last["data"].get("say_next", "")[:70], "| route ->", route("identity", v, last))
    v = fresh()
    c1 = pre(V, v, {"customer_id": "C1", "field": "date_of_birth", "answer": "1989-02-23"})
    c2 = pre(V, v, {"customer_id": "C1", "field": "phone_last4", "answer": "9904"})
    r2_ = post(V, v, ok({"ok": True, "verified": True, "wrong_answers_left": 3, "all_verified": True}), c2)
    r1_ = post(V, v, ok({"ok": True, "verified": True, "wrong_answers_left": 3, "all_verified": False}), c1)
    print("  (b) identity_state =", v.get("identity_state"), "| route ->", route("identity", v, r1_))



def r6():
    print("R6 negatives (must NOT pass): one right + one wrong without a flag; both right but the bank flag says false; three wrong")
    V = tool(wf, "verify_identity", "identity")
    ok = lambda d: {"status": "success", "status_code": 200, "message": "", "data": dict(d), "header": {}}
    for name, seq in [("right+wrong, no flag", [("date_of_birth", {"ok": True, "verified": True, "wrong_answers_left": 3}),
                                                ("phone_last4", {"ok": True, "verified": False, "wrong_answers_left": 2})]),
                      ("both right, flag false", [("date_of_birth", {"ok": True, "verified": True, "wrong_answers_left": 3, "all_verified": False}),
                                                  ("phone_last4", {"ok": True, "verified": True, "wrong_answers_left": 3, "all_verified": False})]),
                      ("three wrong", [("date_of_birth", {"ok": True, "verified": False, "wrong_answers_left": 2, "all_verified": False}),
                                       ("date_of_birth", {"ok": True, "verified": False, "wrong_answers_left": 1, "all_verified": False}),
                                       ("phone_last4", {"ok": True, "verified": False, "wrong_answers_left": 0, "all_verified": False})])]:
        v = fresh()
        for f, d in seq:
            c = pre(V, v, {"customer_id": "C1", "field": f, "answer": "x"}); last = post(V, v, ok(d), c)
        print(f"  {name:24s} identity_state = {v.get('identity_state'):14s} route -> {route('identity', v, last)}")



def r7():
    print("R7 an id the model BUILT ('credit_card_2288', 'pl_1234', 'CC_2288') on a multi-product account: what reaches the bank?")
    A = tool(wf, "get_account", "load_account")
    v = fresh()
    acc = {"status": "success", "status_code": 200, "message": "", "header": {}, "data": {"ok": True, "products": [
        {"product_id": "p1", "type": "credit_card", "card_last4": "2288", "past_due": 300, "days_late": 9, "minimum_payment": 90},
        {"product_id": "p2", "type": "personal_loan", "account_last4": "1234", "past_due": 500, "days_late": 20, "instalment_amount": 250}]}}
    post(A, v, acc)
    for pid in ("credit_card_2288", "pl_1234", "CC_2288", "loan", "p3"):
        c = pre(T, v, {"customer_id": "C1", "product_id": pid, "amount": "300", "date": "2026-10-16"})
        print(f"  model sent {pid:18s} -> request product_id = {c['body']['product_id']}")



def r8():
    print("R8 regressions: identical re-send of a recorded promise; a bank 500 while a stray block flag is set")
    v = fresh()
    good = {"customer_id": "C1", "product_id": "P1", "amount": "500", "date": "2026-10-16"}
    print("  first send   :", outcome(call(v, good, lambda: BANK_OK("P1")))[:90])
    print("  re-send      :", outcome(call(v, good, lambda: BANK_OK("P1")))[:90])
    v = fresh()
    c = pre(T, v, dict(good, product_id="P2", amount="300"))
    v["guard_block_create_promise"] = "a sibling's reason"
    print("  500 + flag   :", outcome(post(T, v, BANK_500(), c))[:90])


if __name__ == "__main__":
    for f in sys.argv[2:] or ["r1", "r2"]:
        globals()[f]()
