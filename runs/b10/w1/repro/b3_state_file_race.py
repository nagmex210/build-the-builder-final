"""Parallel builds share .freya-agents.json. freya.save_workflow truncates and rewrites it (under save.py's lock), but
build.py read it at the end WITHOUT the lock (and selftest.py on the ws1 fallback; the ws2 state file had no lock at
all). A read that lands inside a parallel build's rewrite sees an empty/partial file -> JSONDecodeError -> the build
dies after BUILD END work with no workflow_id line. Repro: one process saves in a loop (Freya calls stubbed), this
process reads the way the build reads (HEAD: unlocked json.loads; fixed: save.read_state)."""
import json, multiprocessing as mp, os, pathlib, sys, tempfile, time
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
sys.path.insert(0, KIT + '/builder'); sys.path.insert(0, KIT + '/btb'); sys.path.insert(0, KIT)
import freya, save
STATE = pathlib.Path(tempfile.mkdtemp()) / ".freya-agents.json"
STATE.write_text(json.dumps({f"slot{i}": {"workflow_id": "w" * 36, "agent_id": "a" * 36, "version": 1} for i in range(400)}))

def writer(stop):
    freya.update_workflow = lambda wid, wf: 2
    while not stop.is_set():
        if hasattr(save, "locked_save"):
            save.locked_save("slot1", {}, STATE)
        else:                                    # HEAD: save.py's inline lock around the same call
            import fcntl
            with open(str(STATE) + ".lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX); freya.save_workflow("slot1", {}, state_file=str(STATE))

def read():
    if hasattr(save, "read_state"):
        return save.read_state("slot7", STATE)
    return json.loads(STATE.read_text()).get("slot7") if STATE.exists() else None   # HEAD build.py:443

if __name__ == "__main__":
    stop = mp.Event(); w = mp.Process(target=writer, args=(stop,)); w.start()
    bad, n, t = 0, 0, time.time()
    while time.time() - t < 4:
        try:
            assert read()["workflow_id"]
        except Exception:  # noqa: BLE001
            bad += 1
        n += 1
    stop.set(); w.join()
    print(f"{bad} of {n} end-of-build state reads failed while a parallel build saved")
    assert bad == 0, "the end-of-build state read races a parallel build's save"
