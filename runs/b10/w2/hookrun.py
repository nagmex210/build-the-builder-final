"""Offline hook harness: runs the REAL pre/post hook code of a saved workflow (out/<slot>.workflow.json) with a
vars dict, a request config and a bank result, in a chosen order. Used for the b10-w2 repros."""
import copy, json, sys


def tool(wf, name, node=None):
    for k, n in wf["nodes"].items():
        if node and k != node:
            continue
        for t in (n.get("tools") or []) + (n.get("pre_actions") or []):
            if (t.get("function") or {}).get("name") == name:
                return t
    raise KeyError(name)


def pre(t, vars, body):
    url = t["function"]["parameters"]["properties"]["url"]["default"]
    config = {"url": url, "method": "POST", "headers": {}, "body": copy.deepcopy(body)}
    exec(t.get("pre_process_code") or "", {"vars": vars, "config": config})
    return config


def http(config):
    """What the mock bank answers: its no-op path /health -> {ok: true}; a tool path -> given by the caller."""
    if config["url"].endswith("/health"):
        return {"status": "success", "status_code": 200, "message": "ok", "data": {"ok": True}, "header": {}}
    return None


def post(t, vars, result, config=None):
    g = {"vars": vars, "result": result}
    if config is not None:
        g["config"] = config
    exec(t.get("post_process_code") or "", g)
    return result
