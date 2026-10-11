"""Score an official simulation whose run_cases process died (transient 5xx while polling): wait for it to finish,
map personas to cases by name, read each call's customer_id, score the bank ledger + the judge like run_cases."""
import sys, json, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import freya
from score import http, score_ledger
sim_id, brief = sys.argv[1], sys.argv[2]
def get(path):
    for i in range(30):
        try: return freya.api("GET", path)
        except RuntimeError as e:
            if "-> 5" not in str(e): raise
            time.sleep(15)
while True:
    s = get(f"/api/v2/simulations/{sim_id}")
    if s["simulation"]["status"] in ("completed", "failed", "paused"): break
    time.sleep(20)
cases = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json")) if c["brief"] == brief}
pname = {p["id"]: p["name"].split()[0] for p in s["personas"]}
its = get(f"/api/v2/simulations/{sim_id}/iterations")
its = (its.get("iterations") or its.get("items") or its) if isinstance(its, dict) else its
it = freya.get_iteration(sim_id, its[0]["id"])
n = 0
for r in sorted(it["runs"], key=lambda r: pname.get(r["personaId"], "")):
    cid = pname.get(r["personaId"]); c = cases[cid]
    call = get(f"/api/v2/call/{r['callId']}")
    v = json.dumps(call)
    import re; m = re.search(r'customer_id\\*"\s*:\s*\\*"([^"\\]+)', v)
    led = http("/v1/practice/ledger/" + m.group(1)) if m else {"calls": []}   # no tool call: no customer id, empty ledger
    res = score_ledger(c, led)
    if r.get("outcome") != "pass": res["failed"].append("conversation: " + " ".join(str(r.get("reason") or "no verdict").split())[:400])
    ok = not res["failed"]; n += ok
    print(("PASS" if ok else "FAIL"), cid, "|", " > ".join(x["tool"] for x in led["calls"]), "| call", r["callId"])
    for f in res["failed"]: print("       -", f[:260])
print(f"\n{n} / {len(it['runs'])} passed (salvaged simulation {sim_id}, status {s['simulation']['status']})")
