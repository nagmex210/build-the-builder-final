"""Harden (builder/harden.py) and save a workflow file under a slot. Prints {"workflow_id", "agent_id", "version"}.

    python3 builder/save.py <slot> <workflow.json>
"""
import json, pathlib, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
import freya                      # noqa: E402
from harden import harden         # noqa: E402

if __name__ == "__main__":
    slot, path = sys.argv[1], sys.argv[2]
    wf = json.load(open(path))
    names = harden(wf)
    json.dump(wf, open(path, "w"), indent=1)
    state = freya.save_workflow(slot, wf, state_file=str(KIT / ".freya-agents.json"))
    print(json.dumps({"hardened_tools": names}))
    print(json.dumps(state))
