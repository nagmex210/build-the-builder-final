"""Structural lint for a Freya workflow file: routing and wiring mistakes that fail silently on the platform.

    python3 builder/lint_workflow.py out/<slot>.workflow.json

Prints ERROR / WARN lines and exits 1 if there is any ERROR. Brief-agnostic: checks only the workflow graph.
"""
import json, re, sys


def walk_conditions(cond):
    if not isinstance(cond, dict):
        return
    yield cond
    for c in cond.get("conditions", []) or []:
        yield from walk_conditions(c)


def lint(w):
    errs, warns = [], []
    nodes = w.get("nodes", {}) or {}
    gnodes = w.get("global_nodes", {}) or {}
    allnodes = {**nodes, **gnodes}
    if w.get("initial_node") not in nodes:
        errs.append(f"initial_node {w.get('initial_node')!r} is not a node")
    if "agent_config" in w:
        errs.append("remove agent_config")
    ends = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    if not ends:
        warns.append("no end_call node: only an end_call tool can hang up")
    for k, n in allnodes.items():
        nt = n.get("node_type", "conversation")
        trs = n.get("transitions", []) or []
        for t in trs:
            tgt = t.get("target_node")
            if tgt != "__previous__" and tgt not in nodes:
                errs.append(f"{k}: transition to unknown node {tgt!r}")
            if tgt == "__previous__" and k not in gnodes:
                errs.append(f"{k}: __previous__ only works in global nodes")
            c = t.get("condition") or {}
            if c.get("logic") == "and":
                errs.append(f"{k}: top-level condition with logic 'and' (nest it inside an 'or' group)")
            for cc in walk_conditions(c):
                op = cc.get("operator")
                if op == "equals" and str(cc.get("operand")) in ("true", "True", "false", "False"):
                    sib = {str(x.get("operand")) for x in walk_conditions(c)
                           if x.get("variable") == cc.get("variable") and x.get("operator") == "equals"}
                    want = {"true", "True"} if str(cc.get("operand")).lower() == "true" else {"false", "False"}
                    if not want <= sib:
                        errs.append(f"{k}: boolean test on {cc.get('variable')} must test both {sorted(want)}")
                if op in ("greater_than", "less_than"):
                    try:
                        float(cc.get("operand"))
                    except (TypeError, ValueError):
                        errs.append(f"{k}: {op} with non-numeric operand {cc.get('operand')!r}")
        if n.get("passthrough"):
            if not any((t.get("condition") or {}).get("operator") == "always" for t in trs):
                errs.append(f"{k}: passthrough node without an 'always' transition (deadlock)")
            if not n.get("passthrough_default_transition"):
                warns.append(f"{k}: passthrough node without passthrough_default_transition")
        if nt == "end_call":
            if trs:
                errs.append(f"{k}: end_call node must have no transitions")
            if not n.get("terminal"):
                errs.append(f"{k}: end_call node without terminal")
            if (n.get("on_enter") or {}).get("type") not in (None, "silent"):
                p = (((n.get("terminal") or {}).get("function") or {}).get("parameters") or {}).get("properties", {})
                if (p.get("message_mode") or {}).get("default") == "none":
                    warns.append(f"{k}: on_enter text is not spoken when message_mode is none")
        if nt == "conversation" and n.get("pre_actions"):
            errs.append(f"{k}: conversation node with pre_actions (the platform drops them)")
        if nt in ("api_request", "code") and n.get("tools"):
            errs.append(f"{k}: {nt} node with tools (the platform drops them)")
        for pa in n.get("pre_actions", []) or []:
            if pa.get("response_mapping"):
                errs.append(f"{k}: response_mapping inside a pre_action is ignored; put it on the node")
        for tool in (n.get("tools", []) or []) + (n.get("pre_actions", []) or []):
            f = tool.get("function", {})
            name = f.get("name")
            for code_key in ("pre_process_code", "post_process_code"):
                code = tool.get(code_key) or ""
                if "{{" in code or "}}" in code:
                    errs.append(f"{k}/{name}: {code_key} contains {{{{ or }}}}")
                if re.search(r"localhost|127\.0\.0\.1|0\.0\.0\.0", code):
                    errs.append(f"{k}/{name}: {code_key} points a request at localhost (the platform refuses it)")
                if code.strip():
                    try:
                        compile(code, f"{k}/{name}/{code_key}", "exec")
                    except SyntaxError as e:
                        errs.append(f"{k}/{name}: {code_key} does not compile: {e}")
            for code in [((f.get("parameters") or {}).get("properties", {}).get("code") or {}).get("default")]:
                if isinstance(code, str) and code.strip():
                    if "{{" in code or "}}" in code:
                        errs.append(f"{k}/{name}: code contains {{{{ or }}}}")
                    try:
                        compile(code, f"{k}/{name}/code", "exec")
                    except SyntaxError as e:
                        errs.append(f"{k}/{name}: code does not compile: {e}")
            for m in tool.get("response_mapping", []) or []:
                if not str(m.get("path", "")).startswith("data."):
                    warns.append(f"{k}/{name}: response_mapping path {m.get('path')!r} should start with 'data.'")
            if f.get("handler") == "__function__:api_call":
                bp = (((f.get("parameters") or {}).get("properties") or {}).get("body") or {}).get("properties") or {}
                for fld, leaf in bp.items():
                    if isinstance(leaf, dict) and "default" not in leaf:
                        errs.append(f"{k}/{name}: body field {fld!r} has no default (the platform drops it; use \"{{{{{fld}}}}}\")")
            if "const" in json.dumps(f.get("parameters", {})):
                warns.append(f"{k}/{name}: uses 'const' (use 'default')")
        for m in n.get("response_mapping", []) or []:
            if not str(m.get("path", "")).startswith("data."):
                warns.append(f"{k}: response_mapping path {m.get('path')!r} should start with 'data.'")
        # a conversation node that can close the call must route to an end node on the close tool's result
        names = [t.get("function", {}).get("name") for t in n.get("tools", []) or []]
        closers = [x for x in names if x and "close" in x]
        for cl in closers:
            routed = any(cl in json.dumps(t.get("condition", {})) and t.get("target_node") in ends for t in trs)
            if ends and not routed:
                errs.append(f"{k}: has tool {cl} but no transition on its result to an end_call node")
        if nt == "conversation" and n.get("max_node_turns") is not None and n.get("max_node_turns") < 20:
            warns.append(f"{k}: max_node_turns {n.get('max_node_turns')} is low")
    # reachability: every node reachable from initial and every non-end node can reach an end node
    edges = {k: {t.get("target_node") for t in (n.get("transitions") or [])} for k, n in nodes.items()}
    seen, stack = set(), [w.get("initial_node")]
    while stack:
        x = stack.pop()
        if x in seen or x not in nodes:
            continue
        seen.add(x); stack.extend(edges.get(x, ()))
    for k in nodes:
        if k not in seen:
            warns.append(f"{k}: not reachable from initial_node")
    can_end = set(ends) | {k for k, n in nodes.items()
                           if any((t.get("function") or {}).get("handler") == "__function__:end_call" for t in n.get("tools") or [])}
    changed = True
    while changed:
        changed = False
        for k, es in edges.items():
            if k not in can_end and es & can_end:
                can_end.add(k); changed = True
    for k in seen:
        if k not in can_end:
            errs.append(f"{k}: no path from this node to an end_call node")
    return errs, warns


if __name__ == "__main__":
    w = json.load(open(sys.argv[1]))
    errs, warns = lint(w)
    for e in errs:
        print("ERROR", e)
    for x in warns:
        print("WARN ", x)
    print(f"{len(errs)} errors, {len(warns)} warnings")
    sys.exit(1 if errs else 0)
