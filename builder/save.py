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


def save_with_retry(slot, wf, state_file, budget_s=None):
    """Kept for callers of b10 w4's name: the same as locked_save."""
    return locked_save(slot, wf, state_file, budget_s=budget_s)


def intent_conditions(wf):
    """A tool-call transition (is_tool_call) without a condition: the platform never offers its transition tool, so the
    node can never leave by intent (b10 merge: official raw-A 3/10, 6 calls stuck in the router reading back a promise
    it could not record; 1 in 6 builds of the champion's code had this shape). docs/workflow-format.md: a tool-call
    transition carries {"operator": "matches_intent", "description": ...}. Use the transition's own description."""
    fixed = []
    g = wf.get("global_nodes") or {}
    nodes = list((wf.get("nodes") or {}).items()) + (list(g.items()) if isinstance(g, dict) else [])
    for name, node in nodes:
        for t in (node.get("transitions") or []) if isinstance(node, dict) else []:
            if isinstance(t, dict) and t.get("is_tool_call") and not t.get("condition"):
                t["condition"] = {"operator": "matches_intent", "description": t.get("description") or f"go to {t.get('target_node')}"}
                fixed.append(f"{name}->{t.get('target_node')}")
    return fixed


def finish_and_save(slot, wf, canned=None):
    names = ["intent-condition:" + f for f in intent_conditions(wf)]
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
    state = locked_save(slot, wf, KIT / ".freya-agents.json")
    return names, state


def locked_save(slot, wf, state_file, budget_s=None):
    """freya.save_workflow under an exclusive lock on <state_file>.lock (it reads, then truncates and rewrites the file).
    A transient platform error (5xx, 429, timeout, connection) is retried with backoff inside a time budget, sleeping
    OUTSIDE the lock (b9 main-B: the fix round's save and the restore both 504'd once; b10 w4: 10/12 builds FAILED on one
    5xx inside the final save). A 4xx (the workflow itself is invalid) is raised at once. Every step of save_workflow
    can be repeated: a PUT replaces the whole definition, publish takes the newest version."""
    budget_s = int(os.environ.get("BTB_SAVE_RETRY_S", "300")) if budget_s is None else budget_s
    t0, delay = time.time(), 5
    while True:
        try:
            with open(str(state_file) + ".lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                return freya.save_workflow(slot, wf, state_file=str(state_file))
        except Exception as e:  # noqa: BLE001
            if not _transient(e) or time.time() - t0 + delay > budget_s:
                raise
            print(f"[freya] save {slot}: transient platform error ({str(e)[:120]}); retry in {delay} s", file=sys.stderr, flush=True)
            time.sleep(delay); delay = min(delay * 2, 40)


def read_state(slot, state_file=None):
    """The slot's saved state, read under the same lock: an unlocked read while a parallel build's save rewrites the
    file sees it empty or half-written (JSONDecodeError at the end of an otherwise good build)."""
    f = pathlib.Path(state_file or KIT / ".freya-agents.json")
    with open(str(f) + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        return json.loads(f.read_text()).get(slot) if f.exists() else None


if __name__ == "__main__":
    slot, path = sys.argv[1], sys.argv[2]
    wf = json.load(open(path))
    names, state = finish_and_save(slot, wf)
    json.dump(wf, open(path, "w"), indent=1)
    print(json.dumps({"hardened_tools": names}))
    print(json.dumps(state))
