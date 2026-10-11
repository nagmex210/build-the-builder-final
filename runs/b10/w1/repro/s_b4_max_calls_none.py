# write_personas keeps {"max_calls": tool, "n": None}; check_ledger then raises -> run_one turns the whole persona into a
# harness_error (excluded from n) after REPLAYING the chat once, hiding every real failure of it
from common2 import *
import json, tempfile
selftest.chat_json = lambda *a, **k: {"personas": [{"customer": "PUB-01", "title": "t", "script": "s",
                                                    "checks": [{"max_calls": "create_promise", "n": None}]}]}
sc = selftest.write_personas("brief", KIT + "/tools/openapi.json", KIT + "/public-test-set.json", 1)
print("kept checks:", sc[0]["checks"])
calls = [ok("verify_identity", verified=True, all_verified=True), ok("close_call")]
try:
    print(selftest.check_ledger(calls, None, sc[0]["checks"], None))
except Exception as e:
    print("check_ledger raised:", type(e).__name__, e)
    raise SystemExit("BUG: a kept persona check crashes the ledger check")
