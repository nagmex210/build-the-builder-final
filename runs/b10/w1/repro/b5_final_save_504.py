"""The build's saves (final pass, fix round, restore) had no retry: one platform 504 on the PUT made final_pass return
None (b9 main-B: 'final pass failed: PUT ... -> 504' for the fix AND the restore; the build then printed the slot's
older version as its result). Repro: stub Freya so the update PUT answers 504 twice, then succeeds."""
import json, os, pathlib, sys, tempfile
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
sys.path.insert(0, KIT + '/builder'); sys.path.insert(0, KIT + '/btb'); sys.path.insert(0, KIT)
os.environ.pop("BTB_TOOLS_API", None)
import freya, save, time
time.sleep = lambda s: None
d = pathlib.Path(tempfile.mkdtemp()); (d / "out").mkdir(); save.KIT = d
(d / ".freya-agents.json").write_text(json.dumps({"x": {"workflow_id": "wf1", "agent_id": "ag1", "version": 3}}))
n = {"put": 0}
def update(wid, wf):
    n["put"] += 1
    if n["put"] <= 2:
        raise RuntimeError(f"PUT /api/v2/workflow/{wid} -> 504: error code: 504")
    return 4
freya.update_workflow = update
wf = {"initial_node": "a", "system_prompt": "", "nodes": {"a": {"node_type": "conversation", "task_message": "hi", "transitions": []}}}
try:
    names, state = save.finish_and_save("x", wf)
    print("saved:", state, "after", n["put"], "PUT(s)")
except Exception as e:  # noqa: BLE001
    print("save failed:", e); state = None
assert state and state["version"] == 4, "one transient 504 on the PUT lost the build's save"
