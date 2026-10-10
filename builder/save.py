"""Harden (builder/harden.py), add the customer-speech block (builder/robust.py) and save a workflow file under a
slot. Prints {"workflow_id", "agent_id", "version"}.

    python3 builder/save.py <slot> <workflow.json>
"""
import fcntl, json, pathlib, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
import freya                      # noqa: E402
from harden import harden         # noqa: E402
from robust import robustify      # noqa: E402


def finish_and_save(slot, wf):
    names = harden(wf)
    robustify(wf)
    # Lock the shared slot file: two builds running in parallel (two briefs) must not overwrite each other's slot.
    with open(KIT / ".freya-agents.json.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = freya.save_workflow(slot, wf, state_file=str(KIT / ".freya-agents.json"))
    return names, state


if __name__ == "__main__":
    slot, path = sys.argv[1], sys.argv[2]
    wf = json.load(open(path))
    names, state = finish_and_save(slot, wf)
    json.dump(wf, open(path, "w"), indent=1)
    print(json.dumps({"hardened_tools": names}))
    print(json.dumps(state))
