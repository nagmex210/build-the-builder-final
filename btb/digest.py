"""Transcript digest on Azure (saves the Claude budget): one strong-model call per evaluated call.

    python3 btb/digest.py runs/b3/**/eval*.json ... --out runs/analyst/digest-b3.jsonl [--workers 8]

Input: fast_eval JSON files (rows with id, pass, failed, call_id). For every call it fetches the transcript
(tool calls included), the case's checks, and asks gpt-6-astra (fallback chain in btb/llm.py) to classify it:
failure kind, the mechanism (why the agent did what it did), whether builder or harness is at fault, and for
passes what carried the call. The standing analyst reads this digest instead of every raw transcript.
"""
import argparse, json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "btb"))
import freya                      # noqa: E402
from llm import chat_json         # noqa: E402

KINDS = ["misread_rule", "wrong_route", "tool_order_or_duplicate", "date_or_amount_math", "honesty",
         "mandatory_wording", "identity", "multi_product", "harness_or_judge_noise", "platform_error", "other"]

PROMPT = """You analyse one simulated debt-collection phone call made by an AI phone agent (a Freya workflow run by a
small model). Outcome: {outcome}. Failed checks: {failed}

The case's checks:
{checks}

Transcript (roles: assistant = phone agent, user = customer, system/tool = tool calls and results):
{tx}

Answer with JSON only:
{{"kind": one of {kinds} (for a pass: "pass"),
 "mechanism": "one sentence: WHY the agent did this, as a general property of the workflow (e.g. 'the promise node
   leaves the deadline to the model, which used a relative weekday'), not a retelling of the call",
 "fault": "builder" | "harness" | "platform",
 "evidence": "the decisive turn, quoted briefly",
 "carried_by": "for a pass: what in the workflow made it work; else empty",
 "fix_rule": "a one-line rule a builder could apply to ANY brief to prevent this; empty for a pass"}}"""


def cases_by_id(paths):
    out = {}
    for p in paths:
        try:
            for c in json.load(open(p)):
                out[c["id"]] = c
        except Exception:  # noqa: BLE001
            pass
    return out


def transcript(call_id):
    msgs = freya.get_call(call_id).get("messages", [])
    lines = []
    for m in msgs:
        t = m.get("message")
        if isinstance(t, (dict, list)):
            t = json.dumps(t)[:700]
        lines.append(f"{m.get('role')}: {t}")
    return "\n".join(lines)[-24000:]


def one(row, case, src):
    try:
        tx = transcript(row["call_id"])
        j = chat_json([{"role": "user", "content": PROMPT.format(
            outcome="PASS" if row.get("pass") else "FAIL", failed="; ".join(row.get("failed", []))[:1500] or "none",
            checks="\n".join("- " + c for c in (case or {}).get("checks", [])) or "(unknown)", tx=tx, kinds=KINDS)}],
            tier="strong", purpose="analyst digest", effort="low")
    except Exception as e:  # noqa: BLE001
        j = {"kind": "digest_error", "mechanism": str(e)[:200]}
    return {"source": src, "case": row.get("id"), "style": row.get("style"), "pass": row.get("pass"),
            "call_id": row.get("call_id"), **j}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("evals", nargs="+"); ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    cases = cases_by_id([ROOT / "public-test-set.json", ROOT / "btb/brief_c/cases-c.json"])
    jobs = []
    for p in a.evals:
        try:
            for r in json.load(open(p)).get("rows", []):
                if r.get("call_id"):
                    jobs.append((r, cases.get(r.get("id")), p))
        except Exception:  # noqa: BLE001
            continue
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda j: one(*j), jobs))
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in res))
    kinds = {}
    for r in res:
        kinds[r.get("kind")] = kinds.get(r.get("kind"), 0) + 1
    print(f"digest: {len(res)} calls -> {out}; kinds: {json.dumps(kinds)}")


if __name__ == "__main__":
    main()
