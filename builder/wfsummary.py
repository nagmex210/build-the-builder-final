"""One-line summary of a Freya workflow for the trace: steps (nodes by type), tools (bank API functions), hooks.

    python3 builder/wfsummary.py <workflow.json | export.json>      # an export file ({"workflow": ...}) works too
"""
import json, sys


def _tools(node):
    for t in (node.get("tools") or []) + (node.get("pre_actions") or []):
        if isinstance(t, dict) and isinstance(t.get("function"), dict):
            yield t


def summary(wf):
    wf = wf.get("workflow", wf) if "nodes" not in wf else wf
    nodes = wf.get("nodes") or {}
    nodes = nodes if isinstance(nodes, dict) else {n.get("name", str(i)): n for i, n in enumerate(nodes)}
    by_type, names, bindings, hooks = {}, set(), 0, 0
    for n in nodes.values():
        by_type[n.get("node_type", "?")] = by_type.get(n.get("node_type", "?"), 0) + 1
        for t in _tools(n):
            bindings += 1
            names.add(t["function"].get("name"))
            hooks += sum(1 for k in ("pre_process_code", "post_process_code") if (t.get(k) or "").strip())
    trans = sum(len(n.get("transitions") or []) for n in nodes.values())
    types = ", ".join(f"{v} {k}" for k, v in sorted(by_type.items()))
    return (f"{len(nodes)} steps ({types}), start {wf.get('initial_node') or '?'}, {trans} transitions; "
            f"{len(names)} tools ({', '.join(sorted(x for x in names if x))}) in {bindings} bindings, {hooks} tool hooks; "
            f"{len(wf.get('global_nodes') or {})} global nodes")


if __name__ == "__main__":
    print(summary(json.load(open(sys.argv[1]))))
