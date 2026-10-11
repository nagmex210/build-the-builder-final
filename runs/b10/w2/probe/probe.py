"""Probe: how Freya runs pre/post hooks of PARALLEL calls of the same tool in one turn.
pre-hook appends 'pre:<label>' to vars['ptrace'] and sets vars['last_label']; post-hook appends
'post:<last_label seen>/<config label if visible>' and returns the trace in the result."""
import json, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))
import freya
_api = freya.api
def _retry(method, path, body=None, **kw):
    for k in range(10):
        try:
            return _api(method, path, body, **kw)
        except RuntimeError as e:
            if not any(c in str(e) for c in ("-> 502", "-> 503", "-> 504", "-> 500")) or k == 9 or "chat/message" in path:
                raise
            time.sleep(6)
freya.api = _retry
PRE = """
try:
    _l = str((config.get('body') or {}).get('label'))
    vars['ptrace'] = str(vars.get('ptrace') or '') + ' pre:' + _l
    vars['last_label'] = _l
except Exception as e:
    vars['ptrace'] = str(vars.get('ptrace') or '') + ' preERR:' + str(e)[:40]
"""
POST = """
try:
    _c = globals().get('config')
    _cl = str((_c.get('body') or {}).get('label')) if isinstance(_c, dict) else 'noconfig'
    vars['ptrace'] = str(vars.get('ptrace') or '') + ' post:' + str(vars.get('last_label')) + '/' + _cl
    if isinstance(result, dict) and isinstance(result.get('data'), dict):
        result['data']['trace'] = vars.get('ptrace')
except Exception as e:
    if isinstance(result, dict):
        result['data'] = dict(err=str(e)[:80])
"""
tool = {"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 0},
        "function": {"name": "probe_write", "handler": "__function__:api_call",
                     "description": "Record one label. When asked for several labels, call it once per label, all in the same turn (parallel).",
                     "parameters": {"type": "object", "properties": {
                         "url": {"type": "string", "default": "https://freya-bank-mock.freyavoice.workers.dev/health"},
                         "method": {"type": "string", "default": "POST"},
                         "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                         "body": {"type": "object", "properties": {"label": {"type": "string", "default": "{{label}}", "description": "the label"}}, "required": ["label"]}},
                         "required": ["body"]}},
        "pre_process_code": PRE, "post_process_code": POST}
HANG = json.load(open(pathlib.Path(__file__).resolve().parents[4] / "out" / "w2-A.workflow.json"))["nodes"]["hang_up"]
wf = {"initial_node": "talk", "system_prompt": "You are a test assistant.", "global_nodes": {},
      "nodes": {"talk": {"name": "talk", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Ready."},
                         "on_enter_first_entry_only": True,
                         "task_message": "When the user gives labels, call probe_write once per label, ALL IN THE SAME TURN as parallel tool calls. Then report each result's `trace` field verbatim.",
                         "tools": [tool], "transitions": [{"target_node": "hang_up", "description": "never", "condition": {"logic": "or", "conditions": [{"variable": "probe_write_success_count", "operator": "greater_than", "operand": 50}]}}]},
                "hang_up": HANG}, "test_variables": {"now": "2026-10-11T10:00:00"}}
if __name__ == "__main__":
    st = freya.save_workflow("w2-rA", wf, state_file=str(pathlib.Path(__file__).resolve().parents[4] / ".freya-agents.json"))
    print(st)
    wid = st["workflow_id"]
    if "--save-only" in sys.argv: sys.exit(0)
    r = freya.api("POST", "/api/v2/chat/message", {"workflowId": wid, "message": "Hi", "customerVariables": {"now": "2026-10-11T10:00:00"}})
    cid = r.get("callId"); print("A:", r.get("response"))
    r = freya.api("POST", "/api/v2/chat/message", {"workflowId": wid, "callId": cid, "fromMessageId": r.get("messageId"),
                  "message": "Please record these three labels at once: alpha, beta, gamma.", "customerVariables": {"now": "2026-10-11T10:00:00"}})
    print("A:", r.get("response"))
    time.sleep(3)
    msgs = freya.get_call(cid).get("messages", [])
    json.dump(msgs, open(pathlib.Path(__file__).with_name("probe_call.json"), "w"), indent=1)
    for m in msgs:
        s = json.dumps(m)
        if "ptrace" in s or "probe_write" in s:
            print(m.get("role"), s[:600])
