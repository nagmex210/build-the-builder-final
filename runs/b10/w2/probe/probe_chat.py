import json, sys, time, pathlib
K = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(K)); sys.path.insert(0, str(K / "btb"))
import freya
from fast_eval import chat_turn
wid = json.load(open(K / ".freya-agents.json"))["w2-rA"]["workflow_id"]
V = {"now": "2026-10-11T10:00:00"}
for k in range(8):
    try:
        r = chat_turn(wid, "Hi", V); break
    except Exception as e:
        print("retry", str(e)[:100], flush=True); time.sleep(10)
cid = r.get("callId"); print("A:", r.get("response"), cid, flush=True)
r = chat_turn(wid, "Please record these three labels at once: alpha, beta, gamma.", V, cid, r.get("messageId"))
print("A:", r.get("response"), flush=True)
time.sleep(3)
msgs = freya.get_call(cid).get("messages", [])
json.dump(msgs, open(pathlib.Path(__file__).with_name("probe_call.json"), "w"), indent=1)
for m in msgs:
    s = json.dumps(m)
    if "ptrace" in s or "probe_write" in s:
        print(m.get("role"), s[:800], flush=True)
