"""Offline test of the datecalc rule kinds (deadline roll back/forward, floor rounding, cut-off time, minimum gaps,
code-computed offer on a block) on a SYNTHETIC spec (made-up values, no brief), through the DATE FACTS code, the local rule tests and
the guard hooks (builder/guards.py).   python3 btb/test_rule_kinds.py"""
import datetime, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "builder"))
import datecalc, guards  # noqa: E402

SPEC = {"now_variable": "now", "weekend_days": [5, 6], "holidays": ["2027-03-10"], "account_tool": "get_acc",
        "products_key": "items", "product_id_field": "ref", "type_field": "kind", "band_field": "",
        "bands": [{"name": "k1", "min": None, "max": None, "product_types": ["k1"], "deadline_count": 9, "deadline_unit": "calendar_days",
                   "deadline_counts_today": False, "if_not_business_day": "back", "attempts": 1},
                  {"name": "k2", "min": None, "max": None, "product_types": ["k2"], "deadline_count": 9, "deadline_unit": "calendar_days",
                   "deadline_counts_today": False, "if_not_business_day": "forward", "attempts": 1}],
        "floors": [{"product_types": [], "field": "", "percent_of_field": "owed", "percent": 40, "fixed": None, "min_amount": None,
                    "round": "up", "round_to": 5}],
        "promise_cutoff_time": "13:30", "promise_min_days_ahead": None, "promise_min_days_unit": "calendar_days",
        "promise_dates_min_gap_days": 10,
        "callback": {"business_days_ahead": 1, "from": "08:00", "to": "18:00", "must_be_after_now": True,
                     "min_minutes_after_now": 90, "slot_minutes": 15},
        "next_weekday_rule": "following_week", "this_weekday_rule": "current_week",
        "guards": {"promise_tool": "promise", "promise_product_field": "ref", "promise_amount_field": "amt", "promise_date_field": "on",
                   "max_amount_field": "owed", "promise_date_business_day": True, "promise_date_not_before_today": True,
                   "promise_date_not_after_deadline": True, "promise_amount_at_least_floor": True,
                   "callback_tool": "cb", "callback_date_field": "day", "callback_time_field": "at"},
        "rule_coverage": [{"rule": "deadline moves back", "encoded_as": "bands.if_not_business_day"},
                          {"rule": "total of promises in one call at most 999", "computes": "amount", "encoded_as": "UNHANDLED"}]}
fails = []
def check(c, msg):
    if not c:
        fails.append(msg)
node, hook = datecalc.snippet(SPEC, datecalc.NODE_CODE), datecalc.snippet(SPEC, datecalc.HOOK_CODE)
probs, _ = datecalc.selftest(SPEC, node, hook)
check(not probs, f"selftest problems: {probs}")
# 2027-03-05 is a Friday: +9 calendar days = Sunday 2027-03-14 -> back Friday 03-12, forward Monday 03-15
now = "2027-03-05T14:00"
v = {"now": now}; exec(node, {"vars": v}); f = v["date_facts"]
check("2027-03-12" in [l for l in f.splitlines() if 'band "k1"' in l][0] and "moves back" in f, "k1 deadline not moved back")
check("2027-03-15" in [l for l in f.splitlines() if 'band "k2"' in l][0], "k2 deadline not moved forward")
check("EARLIEST PROMISE DATE: Monday 2027-03-08" in f, "cut-off not in facts")
check("RULES NOT COMPUTED IN CODE" in f and "at most 999" in f, "unhandled rule not flagged")
res = {"status": "success", "data": {"items": [{"ref": "A", "kind": "k1", "owed": 387.0}]}}
exec(hook, {"vars": v, "result": res})
res["data"]["items"].append({"ref": "B", "kind": "k2", "owed": 100.0})
check(res["data"]["items"][0]["floor_amount"] == 155.0, f"floor rounding up: {res['data']['items'][0].get('floor_amount')}")
check(res["data"]["items"][0]["deadline"] == "2027-03-12", "hook deadline back")
cal = [l for l in res["data"]["date_facts"].splitlines() if l.startswith("  Saturday 2027-03-13")][0]
check("k1" in cal and "k2" not in cal, "calendar after the hook must tag only the customer's own bands: " + cal)
# guards
wf = {"nodes": {"n": {"tools": [
    {"type": "function", "function": {"name": n, "handler": "__function__:api_call", "parameters": {"type": "object", "properties": {
        "url": {"type": "string", "default": "https://bank.example/" + n}, "body": {"type": "object", "properties": {k: {"type": "string"} for k in ks}}}}}}
    for n, ks in (("get_acc", ["x"]), ("promise", ["ref", "amt", "on"]), ("cb", ["day", "at"]))]}}}
guards.find_noop = lambda u: "/health"
done = guards.install(wf, SPEC)
check(set(done) == {"get_acc", "promise", "cb"}, f"guarded {done}")
T = {t["function"]["name"]: t for t in wf["nodes"]["n"]["tools"]}
gv = {"now": now}
exec(T["get_acc"]["post_process_code"], {"vars": gv, "result": json.loads(json.dumps(res))})
def call(tool, body):
    cfg = {"url": "https://bank.example/" + tool, "body": body}
    exec(T[tool]["pre_process_code"], {"vars": gv, "config": cfg})
    return gv.get("guard_block_" + tool) or ""
check("too early" in call("promise", {"ref": "A", "amt": 155, "on": "2027-03-05"}), "cut-off not guarded")
check(call("promise", {"ref": "A", "amt": 155, "on": "2027-03-12"}) == "", "valid promise blocked: " + gv.get("guard_block_promise", ""))
check("below the lowest" in call("promise", {"ref": "A", "amt": 154.8, "on": "2027-03-12"}), "rounded floor not guarded")
check("after the deadline" in call("promise", {"ref": "A", "amt": 160, "on": "2027-03-15"}), "rolled-back deadline not guarded")
check("apart" in call("promise", {"ref": "A", "amt": 160, "on": "2027-03-08"}), "gap not guarded")
check(call("promise", {"ref": "B", "amt": 40, "on": "2027-03-15"}) == "", "rolled-forward deadline blocked: " + gv.get("guard_block_promise", ""))
# code answers: a blocked date/amount carries the ONE value to offer (next business day, capped at the deadline; the floor)
call("promise", {"ref": "A", "amt": 155, "on": "2027-03-13"})          # Saturday -> next bd Mon 03-15 is after k1's 03-12 -> 03-12
check("2027-03-12" in gv.get("guard_offer_promise", ""), "offer for weekend past deadline: " + gv.get("guard_offer_promise", ""))
call("promise", {"ref": "B", "amt": 40, "on": "2027-03-10"})           # holiday -> Thursday 03-11
check("2027-03-11" in gv.get("guard_offer_promise", ""), "offer for holiday: " + gv.get("guard_offer_promise", ""))
call("promise", {"ref": "A", "amt": 100, "on": "2027-03-12"})          # below floor -> 155
check(gv.get("guard_offer_promise") == "amount 155.0", "offer for low amount: " + gv.get("guard_offer_promise", ""))
r = {"status": "success", "status_code": 200, "data": {"ok": True}}
exec(T["promise"]["post_process_code"], {"vars": gv, "result": r})
check(r["data"].get("ok") is False and r["data"].get("offer_instead") == "amount 155.0" and "Offer exactly" in r["data"]["tool_outcome"], "post: " + json.dumps(r))
check(call("cb", {"day": "2027-03-05", "at": "15:30"}) == "", "valid callback blocked: " + gv.get("guard_block_cb", ""))
# spec without any of the new rules: nothing changes (no new lines, guards as before)
plain = {k: v for k, v in SPEC.items() if k not in ("promise_cutoff_time", "promise_dates_min_gap_days", "rule_coverage")}
plain["bands"] = [{**b, "if_not_business_day": "none"} for b in SPEC["bands"]]
plain["floors"] = [{**SPEC["floors"][0], "round": "none"}]
plain["callback"] = {**SPEC["callback"], "min_minutes_after_now": None, "slot_minutes": None}
v2 = {"now": now}; exec(datecalc.snippet(plain, datecalc.NODE_CODE), {"vars": v2})
check(not any(x in v2["date_facts"] for x in ("EARLIEST", "GAP", "RULES NOT", "moves")), "plain spec got new lines")
check(not datecalc.selftest(plain, datecalc.snippet(plain, datecalc.NODE_CODE), datecalc.snippet(plain, datecalc.HOOK_CODE))[0], "plain selftest")
print("FAIL" if fails else "ALL OK", *fails, sep="\n")
sys.exit(1 if fails else 0)
