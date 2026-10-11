"""Post-build reliability check: does this build look BROKEN? Deterministic, no model, nothing read from a brief.

    python3 builder/buildcheck.py <workflow.json> <tool_api.json> [<selftest1.json>]   # prints the problems, exit 1 if any

Seen: the same builder commit sometimes builds a broken agent (b5: the inner agent dropped customer_id from every body,
official B 0/3; b7 raw-B: invented product ids). The lint checks structure; this checks the things that make EVERY call
fail, so the build gets one repair round (build.py) instead of shipping:
- every node is reachable from initial_node and every transition target exists;
- every operation of the tool API file is an api_call tool on some reachable node (a WARNING: a brief may not use one);
- every api_call body leaf has a default; an id field (*_id / *_ref) is a {{template}} (never a literal id), and a
  customer-like id's variable is bound (call variable, mapping/extraction, hook-set variable or a model-filled field);
- every write tool with a product-like id field carries the known-ids pre-hook (ids only from the lookup) and the
  account lookup (pre_action / get_*) carries the post-hook that records them;
- no unbound {{var}} in any prompt text (task_message, on_enter, system_prompt, descriptions);
- self-simulation catastrophic failure (when a round-1 record is given): every valid persona failed, or no write call
  was accepted by the bank in any chat.
"""
import json, re, sys

TPL = re.compile(r"\{\{\s*([A-Za-z_][\w\-]*)(?:[.\w\-]*)\s*\}\}")
ID_FIELD = re.compile(r"(_id|_ref|^id)$", re.I)
CUSTOMER = re.compile(r"customer|client|debtor|person|holder|caller", re.I)


def _node_tools(node):
    for key in ("tools", "pre_actions"):
        for t in node.get(key) or []:
            if isinstance(t, dict):
                yield t


def _api_ops(api):
    out = {}
    for path, ops in ((api or {}).get("paths") or {}).items():
        for m, op in (ops or {}).items():
            if isinstance(op, dict) and m.lower() in ("post", "put", "patch", "get", "delete"):
                out[path.rstrip("/").split("/")[-1]] = op
    return out


def _tool_name(t):
    fn = t.get("function") or {}
    props = (fn.get("parameters") or {}).get("properties") or {}
    url = str((props.get("url") or {}).get("default") or "").split("?")[0].rstrip("/")
    return fn.get("name") or "", (url.split("/")[-1] if url else ""), fn, props


def _targets(obj):
    """Every transition target named anywhere inside a node (transitions, max_turn_transition, passthrough default...)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("target_node", "passthrough_default_transition", "max_turn_transition") and isinstance(v, str):
                out.append(v)
            else:
                out += _targets(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _targets(v)
    return out


def _all_code(wf):
    parts = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and (k.endswith("_code") or k == "code" or ("\n" in v and "vars" in v and "=" in v)):
                    parts.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(wf)
    return "\n".join(parts)


def _defined(wf, code):
    names = set((wf.get("test_variables") or {}).keys())
    def walk(o):
        if isinstance(o, dict):
            for k in ("variable", "target"):
                if isinstance(o.get(k), str):
                    names.add(o[k].split(".")[0])
            if "name" in o and isinstance(o.get("name"), str) and ("type" in o or "enum" in o):
                names.add(o["name"])   # extraction schema entries
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(wf)
    names |= set(re.findall(r"""['"]([A-Za-z_]\w*)['"]""", code))   # any name a hook writes or reads as a key
    return names


def _bound(root, defined, tool_fields):
    return (root in defined or root in tool_fields or root.endswith(("_response", "_args", "_result"))
            or root.startswith(("extractor", "vars", "call", "now", "today", "current", "system", "agent", "user")))


def problems(wf, api=None, selftest=None):
    errs = []
    nodes = wf.get("nodes") or {}
    gnodes = wf.get("global_nodes") or {}
    if isinstance(gnodes, list):
        gnodes = {str(i): g for i, g in enumerate(gnodes)}
    init = wf.get("initial_node")
    if init not in nodes:
        errs.append(f"initial_node {init!r} is not a node")
    # reachability (global nodes are reachable from anywhere; their targets count too)
    seen, stack = set(), [init] + [t for g in gnodes.values() for t in _targets(g)]
    for t in [t for n in list(nodes.values()) + list(gnodes.values()) for t in _targets(n)]:
        if t not in nodes and t not in gnodes:
            errs.append(f"a transition targets {t!r}, which is not a node")
    while stack:
        n = stack.pop()
        if n in seen or n not in nodes:
            continue
        seen.add(n)
        stack += _targets(nodes[n])
    for n in nodes:
        if n not in seen:
            errs.append(f"node {n!r} is unreachable from {init!r}" + (" and holds tools " + ", ".join(_tool_name(t)[0] for t in _node_tools(nodes[n]))
                                                                     if list(_node_tools(nodes[n])) else ""))
    reach_tools = [t for n in seen for t in _node_tools(nodes[n])] + [t for g in gnodes.values() for t in _node_tools(g)] \
        + [t for t in wf.get("tools") or [] if isinstance(t, dict)]
    code = _all_code(wf)
    defined = _defined(wf, code)
    have = set()
    model_fields = set()
    for t in reach_tools:
        name, path, fn, props = _tool_name(t)
        have |= {name, path}
        body = (props.get("body") or {}).get("properties") or {}
        model_fields |= set(body)
        model_fields |= set(((fn.get("parameters") or {}).get("properties") or {}).keys())
    ops = _api_ops(api)
    warns = [f"tool {op!r} of the tool API file is on no reachable node (fine only if the brief never uses it)"
             for op in ops if op not in have]
    lookup_has_known = False
    id_writes = []
    for t in reach_tools:
        name, path, fn, props = _tool_name(t)
        if fn.get("handler") != "__function__:api_call":
            continue
        body = (props.get("body") or {}).get("properties") or {}
        for fld, leaf in body.items():
            if not isinstance(leaf, dict) or leaf.get("type") == "object":
                continue
            d = leaf.get("default")
            if d is None:
                errs.append(f"{name}: body field {fld!r} has no default (the platform drops it from the request)")
                continue
            if ID_FIELD.search(fld):
                m = TPL.search(str(d))
                if not m:
                    errs.append(f"{name}: id field {fld!r} is the literal {str(d)[:40]!r}, not a {{{{variable}}}} bound to the lookup")
                elif not _bound(m.group(1), defined, model_fields) and CUSTOMER.search(fld):
                    # a product id the model fills is resolved by harden's pre-hook (<tool>_args); a customer id cannot be
                    errs.append(f"{name}: id field {fld!r} uses {{{{{m.group(1)}}}}}, which nothing sets")
        pre, post = t.get("pre_process_code") or "", t.get("post_process_code") or ""
        if "known_ids" in post and ("_known" in post or "known_ids'] =" in post):
            lookup_has_known = True
        # a bank write = an operation of the tool API file (code-only helper tools of the builder are not bank writes)
        is_write = (not ops or name in ops or path in ops) and not any(x.startswith(("get_", "check_", "lookup_", "verify_")) for x in (name, path))
        prod_ids = [f for f in body if ID_FIELD.search(f) and not CUSTOMER.search(f)]
        if is_write and prod_ids:
            id_writes.append(name)
            if "known_ids" not in pre:
                errs.append(f"{name}: writes {', '.join(prod_ids)} without the known-ids pre-hook (ids only from the lookup)")
    if id_writes and not lookup_has_known:
        errs.append("no reachable lookup tool records the ids it returns (known_ids post-hook): " + ", ".join(sorted(set(id_writes)))
                    + " cannot be checked against the lookup")
    # unbound {{vars}} in prompt text
    def texts(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("parameters",) or k.endswith("_code") or k == "code":
                    continue
                yield from texts(v, k)
        elif isinstance(o, list):
            for v in o:
                yield from texts(v, key)
        elif isinstance(o, str) and key in ("task_message", "text", "content", "system_prompt", "description", "message", "prompt"):
            yield o
    bad = set()
    for s in texts(wf):
        for m in TPL.finditer(s):
            if not _bound(m.group(1), defined, model_fields):
                bad.add(m.group(1))
    for b in sorted(bad):
        errs.append(f"prompt text uses {{{{{b}}}}}, which no call variable, mapping, extraction or hook sets (the model sees it raw)")
    if selftest:
        rows = [r for r in selftest.get("rows") or [] if not r.get("harness_error") and r.get("turns")]
        if len(rows) >= 3:
            if all(r.get("failed") for r in rows):
                errs.append(f"CATASTROPHIC self-simulation: all {len(rows)} valid persona chats failed a ledger check")
            calls = [str(c if isinstance(c, str) else (c.get("name") or c.get("tool") or "")) for r in rows for c in r.get("tools") or []]
            generic = __import__("os").environ.get("BTB_COLLECTIONS") == "0"
            # a non-collections case may be read-only in most branches (an inquiry): no write is not catastrophic there
            if not generic and not any(c and not c.startswith(("get_", "list_", "verify", "check_", "code_exec")) for c in calls):
                errs.append(f"CATASTROPHIC self-simulation: no write tool was called in any of {len(rows)} persona chats")
    return errs, warns


if __name__ == "__main__":
    wf = json.load(open(sys.argv[1]))
    api = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    st = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    p, w = problems(wf, api, st)
    print("\n".join(["ERROR " + x for x in p] + ["warn " + x for x in w]) or "ok")
    sys.exit(1 if p else 0)
