"""Smoke-test the brief C mock through its public URL: every tool, validation errors, failure injection, and two
scripted calls scored with score_c against their expected ledgers.   python3 btb/brief_c/smoke.py [bank_url]"""
import json, os, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score_c
from score_c import score
score.HOST = (sys.argv[1] if len(sys.argv) > 1 else open(os.path.join(HERE, "BANK_URL")).read()).strip()
os.environ.setdefault("FREYA_BANK_TEAM_KEY", "brief-c-smoke-test-key")
CASES = {c["id"]: c for c in json.load(open(os.path.join(HERE, "cases-c.json")))}
fails = 0

def t(tool, cid, expect=None, **args):
    global fails
    r = score.http("/v1/" + tool, dict(customer_id=cid, **args))
    ok = expect is None or all(r.get(k) == v for k, v in expect.items())
    fails += not ok
    print("ok " if ok else "BAD", tool, json.dumps(args), "->", json.dumps(r))
    return r

def session(case):
    return score.http("/v1/practice/sessions", {"case": case})["variables"]

# C-10: failure injection on verify_identity (1) and create_promise (2)
v = session("C-01"); c = v["customer_id"]; print("session", v)   # unscored: out-of-order calls
t("get_account", c, {"ok": False, "error": "identity not verified"})
t("create_promise", c, {"ok": False, "error": "identity not verified"}, account_ref="A1", amount=1, pay_date="2026-11-01")
t("close_call", c, {"ok": True}, result="no_contact", code="UNCLEAR")
t("transfer_to_agent", c, {"ok": False, "error": "call already closed"}, queue="fraud")
v = session("C-10"); c = v["customer_id"]
t("verify_identity", c, {"ok": False}, check="postcode", value="1173 RS")            # injected 500
t("verify_identity", c, {"ok": False}, check="postcode", value="11")                 # unreadable
t("verify_identity", c, {"passed": True}, check="postcode", value="1173rs")
t("verify_identity", c, {"ok": False}, check="birth_month", value="September")       # must be MM
t("verify_identity", c, {"passed": True, "identity_confirmed": True}, check="birth_month", value="09")
t("get_account", c, {"ok": True})
t("add_note", c, {"ok": True}, account_ref="A1", note_code="REFUSED")
t("add_note", c, {"ok": False}, account_ref="A9", note_code="REFUSED")
t("add_note", c, {"ok": False}, account_ref="A2", note_code="refused")
t("create_promise", c, {"ok": False}, account_ref="A2", amount=260, pay_date="2026-12-07")
t("create_promise", c, {"ok": False}, account_ref="A2", amount=260, pay_date="2026-12-07")
t("add_note", c, {"ok": True}, account_ref="A2", note_code="SERVICE_ERROR")
t("close_call", c, {"ok": False}, result="no_payment")                               # code missing
t("close_call", c, {"ok": True}, result="no_payment", code="SERVICE_ERROR")
r = score_c.score_ledger(CASES["C-10"], score.http("/v1/practice/ledger/" + c)); print("C-10 scored:", r); fails += not r["pass"]

# C-06: two-part plan
v = session("C-06"); c = v["customer_id"]
t("verify_identity", c, {"passed": False, "hint": "letters_missing"}, check="postcode", value="3388")
t("verify_identity", c, {"passed": True}, check="postcode", value="3388 JN")
t("verify_identity", c, {"passed": True, "identity_confirmed": True}, check="birth_month", value="1")
t("create_promise", c, {"ok": False}, account_ref="A1", amount=622.58, pay_date="29/11/2026", instalment_no=1)
t("create_promise", c, {"ok": True}, account_ref="A1", amount=622.58, pay_date="2026-11-29", instalment_no=1)
t("create_promise", c, {"ok": False}, account_ref="A1", amount=622.58, pay_date="2026-11-29", instalment_no=1)
t("create_promise", c, {"ok": True}, account_ref="A1", amount=622.57, pay_date="2026-12-15", instalment_no=2)
t("close_call", c, {"ok": True}, result="arranged")
r = score_c.score_ledger(CASES["C-06"], score.http("/v1/practice/ledger/" + c)); print("C-06 scored:", r); fails += not r["pass"]

# C-02: callback slots; C-04: two wrong answers lock the check; C-12: transfer
v = session("C-02"); c = v["customer_id"]
t("schedule_callback", c, {"ok": False}, date="2026-11-08", slot="09:15")
t("schedule_callback", c, {"ok": True}, date="2026-11-08", slot="09:30")
t("close_call", c, {"ok": True}, result="no_contact", code="CALLBACK")
r = score_c.score_ledger(CASES["C-02"], score.http("/v1/practice/ledger/" + c)); print("C-02 scored:", r); fails += not r["pass"]
v = session("C-04"); c = v["customer_id"]
t("verify_identity", c, {"passed": False, "attempts_left": 1}, check="postcode", value="4410 BX")
t("verify_identity", c, {"passed": True}, check="postcode", value="4401 bx")
t("verify_identity", c, {"passed": False, "attempts_left": 0}, check="birth_month", value="03")
t("verify_identity", c, {"ok": False}, check="birth_month", value="05")
t("close_call", c, {"ok": True}, result="id_failed", code="FAILED")
r = score_c.score_ledger(CASES["C-04"], score.http("/v1/practice/ledger/" + c)); print("C-04 scored:", r); fails += not r["pass"]
v = session("C-12"); c = v["customer_id"]
t("transfer_to_agent", c, {"ok": False}, queue="general")
t("transfer_to_agent", c, {"ok": True}, queue="fraud")
t("close_call", c, {"ok": False}, result="transferred", code="fraud")
t("close_call", c, {"ok": True}, result="transferred", code="FRAUD")
r = score_c.score_ledger(CASES["C-12"], score.http("/v1/practice/ledger/" + c)); print("C-12 scored:", r); fails += not r["pass"]
# a wrong ledger must fail
r = score_c.score_ledger(CASES["C-01"], score.http("/v1/practice/ledger/" + c)); print("C-01 vs C-12 ledger (must fail):", r["pass"]); fails += r["pass"]
print("\nSMOKE", "OK" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
