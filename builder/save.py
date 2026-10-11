"""Harden (builder/harden.py), add the customer-speech block (builder/robust.py) and save a workflow file under a
slot. Prints {"workflow_id", "agent_id", "version"}.

    python3 builder/save.py <slot> <workflow.json>
"""
import fcntl, json, os, pathlib, socket, sys, time, urllib.error

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
import freya                      # noqa: E402
from harden import harden         # noqa: E402
from robust import robustify      # noqa: E402
from canned import apply as apply_canned  # noqa: E402
from guards import install as install_guards  # noqa: E402
from identity_gate import apply as apply_identity_gate  # noqa: E402
from situations import apply as apply_situations  # noqa: E402


if os.environ.get("FREYA_WORKSPACE_ID"):   # set once by build.py: one platform call less per save (a 504 there failed builds)
    freya._ws = os.environ["FREYA_WORKSPACE_ID"]


def workspace_id_with_retry(budget_s=180):
    t0, delay = time.time(), 5
    while True:
        try:
            return freya.workspace_id()
        except Exception as e:  # noqa: BLE001
            if not _transient(e) or time.time() - t0 + delay > budget_s:
                raise
            time.sleep(delay); delay = min(delay * 2, 40)


def _transient(e):
    """A Freya gateway/server error or a network timeout: the request may succeed when sent again."""
    if isinstance(e, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError)):
        return True
    return isinstance(e, RuntimeError) and any(f"-> {c}:" in str(e) for c in (429, 500, 502, 503, 504))


def save_with_retry(slot, wf, state_file, budget_s=int(os.environ.get("BTB_SAVE_RETRY_S", "300"))):
    """Build stability (b10 w4: 1 of 12 builds FAILED on one 504 of GET /workspaces inside the final save, and the
    finished workflow was thrown away). A transient platform error is retried with backoff inside a time budget; any
    other error (a 4xx: the workflow itself is invalid) is raised at once. Each step of save_workflow can be repeated:
    a PUT replaces the whole definition, publish takes the newest version."""
    t0, delay = time.time(), 5
    while True:
        try:
            return freya.save_workflow(slot, wf, state_file=state_file)
        except Exception as e:  # noqa: BLE001
            if not _transient(e) or time.time() - t0 + delay > budget_s:
                raise
            print(f"[freya] save: transient platform error ({str(e)[:120]}); retry in {delay} s", file=sys.stderr, flush=True)
            time.sleep(delay); delay = min(delay * 2, 40)


def finish_and_save(slot, wf, canned=None):
    names = []
    api = os.environ.get("BTB_TOOLS_API")
    if api and pathlib.Path(api).exists():          # the build agent can drop a required field (b5: customer_id everywhere)
        from apicheck import repair
        names += ["api-required:" + f for f in repair(wf, json.loads(pathlib.Path(api).read_text()))]
    from hookcheck import repair as repair_hooks   # a hook that raises fails its tool every call (b5: `response`)
    names += ["hook-repair:" + f for f in repair_hooks(wf)]
    names += harden(wf)
    calc = KIT / "out" / f"{slot}.calc.json"
    if calc.exists():
        c = json.loads(calc.read_text())
        if c.get("ok"):
            names += ["guard:" + n for n in install_guards(wf, c.get("spec"))]
    robustify(wf)
    if canned is None:
        f = KIT / "out" / f"{slot}.canned.json"
        canned = json.loads(f.read_text()) if f.exists() else None
    names = names + apply_canned(wf, canned)    # after harden: the say_now hook reads harden's tool_outcome
    names = names + apply_identity_gate(wf, canned)   # code-decided identity_state + failed terminal node (M4/M29)
    sit = KIT / "out" / f"{slot}.situations.json"   # A1: specialist first lines / once-only / silent hand-off
    if sit.exists():
        names = names + apply_situations(wf, json.loads(sit.read_text()))
    # Lock the shared slot file: two builds running in parallel (two briefs) must not overwrite each other's slot.
    with open(KIT / ".freya-agents.json.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = save_with_retry(slot, wf, str(KIT / ".freya-agents.json"))
    return names, state


if __name__ == "__main__":
    slot, path = sys.argv[1], sys.argv[2]
    wf = json.load(open(path))
    names, state = finish_and_save(slot, wf)
    json.dump(wf, open(path, "w"), indent=1)
    print(json.dumps({"hardened_tools": names}))
    print(json.dumps(state))
