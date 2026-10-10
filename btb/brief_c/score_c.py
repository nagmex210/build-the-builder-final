"""Ledger scorer for brief C: the kit's tools/score.py plus the checks C needs.

    score_ledger(case, ledger) -> {"pass": bool, "failed": [reasons]}

Extra over tools/score.py: a two-part plan must be recorded with the right instalment_no (1 and 2), single promises
with 0; and nothing may be called after close_call. btb/fast_eval.py picks this file up automatically when the
cases file sits next to it (btb/brief_c/cases-c.json).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import score  # noqa: E402


def score_ledger(case, led):
    res = score.score_ledger(case, led)
    bad = res["failed"]
    key = lambda p: (p["product_id"], int(p.get("instalment_no") or 0))
    got, exp = sorted(map(key, led.get("promises", []))), sorted(map(key, case["expected"]["promises"]))
    if got != exp and not any(b.startswith("promises ") for b in bad):
        bad.append(f"promise instalment numbers {got}, expected {exp}")
    calls = led.get("calls", [])
    closes = [i for i, c in enumerate(calls) if c["tool"] == "close_call" and c["result"].get("ok")]
    if closes and closes[0] != len(calls) - 1:
        bad.append("tool calls after close_call")
    return {"pass": not bad, "failed": bad}
