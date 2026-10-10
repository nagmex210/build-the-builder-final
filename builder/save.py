"""Harden (builder/harden.py), add the customer-speech block (builder/robust.py) and save a workflow file under a
slot. Prints {"workflow_id", "agent_id", "version"}.

    python3 builder/save.py <slot> <workflow.json>
"""
import json, pathlib, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
import freya                      # noqa: E402
from harden import harden         # noqa: E402
from robust import robustify      # noqa: E402
from canned import apply as apply_canned  # noqa: E402


def finish_and_save(slot, wf, canned=None):
    names = harden(wf)
    robustify(wf)
    if canned is None:
        f = KIT / "out" / f"{slot}.canned.json"
        canned = json.loads(f.read_text()) if f.exists() else None
    names = names + apply_canned(wf, canned)    # after harden: the say_now hook reads harden's tool_outcome
    state = freya.save_workflow(slot, wf, state_file=str(KIT / ".freya-agents.json"))
    return names, state


if __name__ == "__main__":
    slot, path = sys.argv[1], sys.argv[2]
    wf = json.load(open(path))
    names, state = finish_and_save(slot, wf)
    json.dump(wf, open(path, "w"), indent=1)
    print(json.dumps({"hardened_tools": names}))
    print(json.dumps(state))
