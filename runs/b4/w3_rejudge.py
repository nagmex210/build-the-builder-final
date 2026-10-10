"""Re-judge fast_eval rows whose only failures are 'conversation:' ones, using the transcript fetched now (complete).
fast_eval fetches the transcript right after the last turn; under load the final assistant turn (canned lines +
close_call) is often not persisted yet, so the judge reports sentences as never said. Ledger failures are kept."""
import json, sys
sys.path.insert(0, "btb"); sys.path.insert(0, ".")
import fast_eval as fe
from llm import chat_json
d = json.load(open(sys.argv[1]))
cases = {c["id"]: c for c in json.load(open(fe.ROOT / "public-test-set.json"))}
by = {}
for r in d["rows"]:
    fails = r["failed"] if isinstance(r["failed"], list) else eval(r["failed"])
    p = r["pass"] in (True, "True")
    if not p and fails and all(f.startswith("conversation:") for f in fails) and r.get("call_id"):
        c = cases[r["id"]]
        tx = fe.transcript_text(r["call_id"], [])
        j = chat_json([{"role": "user", "content": fe.JUDGE.format(now="(see transcript variables)", checks="\n".join("- " + x for x in c["checks"]), transcript=tx[-30000:])}],
                      tier="strong", purpose="re-judge", effort="low")
        p = j.get("outcome") == "pass"
        print(r["id"], r["style"], "REJUDGE", "pass" if p else "fail: " + str(j.get("reason"))[:200])
    by.setdefault(r["id"], []).append(p)
print("rejudged:", sum(all(v) for v in by.values()), "/", len(by), {k: v for k, v in by.items()})
