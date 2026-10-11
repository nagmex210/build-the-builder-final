# _run_one: the final ledger() read failing (4 retries swallowed -> {}) is scored as an agent failure, not a harness error
from common2 import *
selftest.session = lambda cid: {"customer_id": "c1", "now": "2026-10-14T11:00"}
selftest.chat_turn = lambda wid, msg, sess, cid: {"callId": "call1", "response": "Goodbye."}
good = {"calls": [ok("verify_identity", verified=True, all_verified=True), ok("close_call", {"outcome": "paid"})]}
n = {"i": 0}
def http(path, body=None):                  # the real ledger() runs; its HTTP read fails from the 3rd read on (platform down)
    n["i"] += 1
    if n["i"] <= 2:
        return good
    raise RuntimeError("GET " + path + " -> 504")
selftest.http = http
selftest.time.sleep = lambda s: None
selftest.hang_up_events = lambda cid: []
selftest.freya.api = lambda *a, **k: {}
sc = {"title": "t", "script": "s", "checks": [], "cust": {"id": "PUB-01", "name": "x", "now": "2026-10-14T11:00", "identity": {}, "products": []}}
r = selftest.run_one("wf", sc, None)
print({k: r.get(k) for k in ("failed", "harness_error", "tools")})
assert "harness_error" in r or not r["failed"], "BUG: a ledger read failure is reported as the agent failing close_call"
