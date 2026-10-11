"""Dry-run check of every api_call tool's pre/post Python hook, and a repair so a broken hook never kills a tool call.

    python3 builder/hookcheck.py <workflow.json>         # repairs in place, prints what it did

Seen (b5 merge, official B 0/3): the inner build agent's verify_identity post-hook ended with `_wn(response, _m)`;
`response` is not defined in a post-hook (the name is `result`), so every call raised NameError at top level, the
platform reported function_call_error, the model said "technical issue" and no customer passed identity.
`errors(wf)` runs each hook on sample inputs (a success and a failure result) and lists the exceptions that escape.
`repair(wf)`: a NameError for a usual alias of the result (response, resp, res, ...) gets `<alias> = result` in front;
whatever still raises has each top-level statement wrapped in its own try/except, so the other blocks (ours: honesty
lines, guards, ids) still run. Nothing here reads a brief.
"""
import json, sys

ALIASES = {"post_process_code": ("response", "resp", "res", "tool_result", "api_response", "output", "r"),
           "pre_process_code": ("request", "req")}


def _tools(wf):
    for node in list((wf.get("nodes") or {}).values()) + list((wf.get("global_nodes") or {}).values()):
        for key in ("tools", "pre_actions"):
            for t in node.get(key) or []:
                yield t
    for t in wf.get("tools") or []:
        yield t


def _samples(t, key):
    fn = t.get("function") or {}
    props = (fn.get("parameters") or {}).get("properties") or {}
    body = {f: "x" for f in ((props.get("body") or {}).get("properties") or {})}
    url = str((props.get("url") or {}).get("default") or "https://example.invalid/x")
    if key == "pre_process_code":
        return [dict(vars={}, config={"url": url, "method": "POST", "headers": {}, "body": dict(body)})]
    return [dict(vars={}, result={"status": "success", "status_code": 200, "data": {"ok": True}}),
            dict(vars={}, result={"status": "error", "status_code": 400, "data": {"ok": False, "error": "bad request"}})]


def _run(code, env):
    """None when the hook runs through, else the exception it raised."""
    try:
        exec(compile(code, "<hook>", "exec"), {"__builtins__": __builtins__, "json": json, **env})
        return None
    except Exception as e:  # noqa: BLE001
        return e


def _first_error(t, key, code):
    for env in _samples(t, key):
        e = _run(code, json.loads(json.dumps(env)))
        if e is not None:
            return e
    return None


def errors(wf):
    out = []
    for t in _tools(wf):
        for key in ("pre_process_code", "post_process_code"):
            code = t.get(key)
            if not code:
                continue
            e = _first_error(t, key, code)
            if e is not None:
                out.append(f"{(t.get('function') or {}).get('name')}.{key}: the hook raises {type(e).__name__}: {str(e)[:120]}"
                           " (the platform turns this into a failed tool call every time)")
    return out


def _wrap_top_level(code):
    """Each top-level statement that is not a def/class/import/try gets its own try/except (text kept as written)."""
    lines = code.splitlines()
    chunks, cur = [], []
    for ln in lines:
        top = ln[:1] not in ("", " ", "\t", "#")
        cont = ln.lstrip().split(" ")[0].rstrip(":") in ("except", "else", "elif", "finally") and ln[:1] not in (" ", "\t")
        if top and not cont and cur:
            chunks.append(cur); cur = []
        cur.append(ln)
    if cur:
        chunks.append(cur)
    out = []
    for ch in chunks:
        head = ch[0].lstrip()
        if head.startswith(("def ", "class ", "import ", "from ", "try:", "@", "#")) or not head:
            out.extend(ch)
        else:
            out.append("try:")
            out.extend("    " + x for x in ch)
            out.append("except Exception:")
            out.append("    pass")
    return "\n".join(out) + "\n"


def repair(wf):
    fixed = []
    for t in _tools(wf):
        name = (t.get("function") or {}).get("name")
        for key in ("pre_process_code", "post_process_code"):
            code = t.get(key)
            if not code:
                continue
            e = _first_error(t, key, code)
            if e is None:
                continue
            new, how = code, []
            if isinstance(e, NameError) and getattr(e, "name", None) in ALIASES[key]:
                src = "result" if key == "post_process_code" else "config"
                new = f"{e.name} = {src}\n" + new
                how.append(f"{e.name} = {src}")
            if _first_error(t, key, new) is not None:
                try:
                    w = _wrap_top_level(new)
                    compile(w, "<hook>", "exec")
                except SyntaxError:
                    w = "try:\n" + "\n".join("    " + x for x in new.splitlines()) + "\nexcept Exception:\n    pass\n"
                new = w
                how.append("top-level statements isolated in try/except")
            t[key] = new
            fixed.append(f"{name}.{key}: {type(e).__name__} {str(e)[:80]} -> {', '.join(how)}")
    return fixed


if __name__ == "__main__":
    wf = json.load(open(sys.argv[1]))
    print(json.dumps({"errors_before": errors(wf), "repaired": repair(wf), "errors_after": errors(wf)}, indent=1))
    json.dump(wf, open(sys.argv[1], "w"), indent=1)
