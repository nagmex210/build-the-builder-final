"""Required-field check of the workflow's tools against the bank's tool API file (OpenAPI). Deterministic, no model.

    python3 builder/apicheck.py <workflow.json> <tool_api.json>      # repairs the file in place, prints what it did

Seen (b5 merge, official B 0/3): the inner build agent dropped `customer_id` from every tool's body `required` list,
the bank rejected every verify_identity and the build shipped. Every api_call tool whose url ends with an API path
must keep every field that path's request body requires: `missing(wf, api)` lists the gaps (a lint ERROR),
`repair(wf, api)` puts them back (`"default": "{{<field>}}"`, the kit's model-filled pattern; an existing leaf is
kept, only the `required` entry is added). Tool names and fields come from the API file, never from a brief.
"""
import json, sys


def api_required(api):
    """{path name: {"required": [...], "properties": {...}}} for every POST/PUT/PATCH body in the API file."""
    out = {}
    for path, ops in ((api or {}).get("paths") or {}).items():
        for m, op in (ops or {}).items():
            if not isinstance(op, dict) or m.lower() not in ("post", "put", "patch"):
                continue
            sch = ((((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {})
            ref = sch.get("$ref")
            if ref and ref.startswith("#/"):
                node = api
                for part in ref[2:].split("/"):
                    node = (node or {}).get(part) or {}
                sch = node
            out[path.rstrip("/").split("/")[-1]] = {"required": list(sch.get("required") or []),
                                                    "properties": dict(sch.get("properties") or {})}
    return out


def _tools(wf):
    for node in list((wf.get("nodes") or {}).values()) + list((wf.get("global_nodes") or {}).values()):
        for key in ("tools", "pre_actions"):
            for t in node.get(key) or []:
                yield t
    for t in wf.get("tools") or []:
        yield t


def _match(t, req):
    fn = t.get("function") or {}
    if fn.get("handler") != "__function__:api_call":
        return None, None
    props = (fn.get("parameters") or {}).get("properties") or {}
    url = str((props.get("url") or {}).get("default") or "").split("?")[0].rstrip("/")
    name = url.split("/")[-1] if url else ""
    if name not in req:
        name = fn.get("name") if fn.get("name") in req else None
    return name, props


def missing(wf, api):
    """['<tool>: required field <f> missing from body properties|required'] for every gap."""
    req, out = api_required(api), []
    for t in _tools(wf):
        name, props = _match(t, req)
        if not name:
            continue
        body = props.get("body") or {}
        have, reqd = body.get("properties") or {}, body.get("required") or []
        tool = (t.get("function") or {}).get("name")
        for f in req[name]["required"]:
            if f not in have:
                out.append(f"{tool}: required field {f!r} of the API file is missing from the body properties")
            elif f not in reqd:
                out.append(f"{tool}: required field {f!r} of the API file is missing from the body required list")
    return out


def repair(wf, api):
    """Put every API-required field back into each tool body (properties + required). Returns the fixes made."""
    req, fixed = api_required(api), []
    for t in _tools(wf):
        name, props = _match(t, req)
        if not name:
            continue
        body = props.setdefault("body", {"type": "object"})
        have = body.setdefault("properties", {})
        reqd = body.setdefault("required", [])
        tool = (t.get("function") or {}).get("name")
        for f in req[name]["required"]:
            if f not in have:
                src = req[name]["properties"].get(f) or {}
                leaf = {"type": src.get("type") or "string", "default": "{{" + f + "}}"}
                for k in ("enum", "description"):
                    if k in src:
                        leaf[k] = src[k]
                have[f] = leaf
                fixed.append(f"{tool}.{f} (property)")
            if f not in reqd:
                reqd.append(f)
                fixed.append(f"{tool}.{f} (required)")
    return fixed


if __name__ == "__main__":
    wf = json.load(open(sys.argv[1]))
    api = json.load(open(sys.argv[2]))
    print(json.dumps({"missing_before": missing(wf, api), "repaired": repair(wf, api), "missing_after": missing(wf, api)}))
    json.dump(wf, open(sys.argv[1], "w"), indent=1)
