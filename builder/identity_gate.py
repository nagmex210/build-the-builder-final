"""Identity gate in structure (M4/M18/M29). Brief-agnostic: it reads only the workflow's own tools and transitions, the
shape of the identity tool's response and the canned sentences extracted from the brief (builder/canned.py).

apply(wf, canned) (called by builder/save.py's final pass, after harden and canned) does:
- identity tool post-hook: CODE decides `identity_state` after every result and writes it to the call variables and
  into the result: `passed`, `asking <next>` (one answer passed, more needed), `retry <field> (...)` (wrong / unreadable /
  swapped answer, attempts left), `failed` (no attempts left). Each state carries one `say_next` instruction; `failed`
  carries the brief's referral sentence verbatim and the close instruction. The model never infers the verdict itself
  (seen: "I have already verified you" with the all-verified flag false; "past due" said after one wrong, one right).
- a terminal node `identity_failed`: every node that holds the identity tool routes there when the state is failed;
  it says the brief's referral sentence verbatim (if not said yet) and its only job is the close.
- an IDENTITY GATE block in every node before identity passes (the first conversation node and the identity nodes):
  until the state is passed the agent knows nothing about any account (no amount, product, debt or status).
"""
import copy, json, re

MARK = "## IDENTITY GATE"

POST = r'''
try:
    _v = vars if isinstance(globals().get('vars'), dict) else None
    _r = result if isinstance(result, dict) else {}
    _d = _r.get('data') if isinstance(_r.get('data'), dict) else None
    if _d is not None:
        def _tf(x):
            return str(x).strip().lower() in ('true', '1', 'yes')
        _ks = list(_d.keys())
        # Key names differ per bank API: the call-wide flag (all_verified, identity_confirmed, fully_verified ...) and
        # the per-answer flag (verified, passed, correct, match ...) are found by shape, never by one fixed name.
        _per_words = ('verif', 'pass', 'correct', 'match', 'valid', 'confirm', 'success')
        _allk = next((k for k in _ks if any(w in str(k).lower() for w in _per_words)
                      and any(w in str(k).lower() for w in ('all', 'identity', 'fully', 'complete', 'overall', 'customer'))), None)
        _ansk = next((k for k in _ks if k != _allk and str(k).lower() in ('verified', 'passed', 'correct', 'match', 'matched', 'valid', 'confirmed', 'success')), None) \
            or next((k for k in _ks if k != _allk and any(w in str(k).lower() for w in _per_words)
                     and not any(w in str(k).lower() for w in ('so_far', 'next', 'status', 'state', 'say', 'list'))), None)
        _leftk = next((k for k in _ks if any(w in str(k).lower() for w in ('left', 'remain'))), None)
        _hint = _d.get('hint')
        _fld = ''
        try:
            _b = config.get('body') if isinstance(globals().get('config'), dict) else None
            if isinstance(_b, dict):
                _fld = str(next((v for k, v in _b.items() if any(w in str(k).lower() for w in ('field', 'question', 'type', 'item'))), '') or '')
        except Exception:
            _fld = ''
        _fld = _fld or str((_v or {}).get('last_request_' + __TOOL__) or 'the same question')
        _left = None
        try:
            _left = int(_d.get(_leftk)) if _leftk is not None and _d.get(_leftk) is not None else None
        except Exception:
            _left = None
        _ok_false = _d.get('ok') in (False, 'false', 'False')
        if _allk is not None and _tf(_d.get(_allk)):
            _state = 'passed'
            _say = 'Identity is verified. Do not ask any security question again.'
        elif _left is not None and _left <= 0 and not (_ansk is not None and _tf(_d.get(_ansk))):
            _state = 'failed'
            _say = __FAILED__
        elif _hint:
            _state = 'retry ' + _fld
            _say = ('Not counted as a wrong answer (' + str(_hint) + '). Follow the brief\'s rule for this hint and ask '
                    + _fld + ' again. Say nothing about any account.')
        elif _ok_false and not (_ansk is not None and str(_d.get(_ansk, '')).strip()):
            _state = 'retry ' + _fld
            _say = 'The answer could not be read (not counted). Ask for ' + _fld + ' again, clearly. Say nothing about any account.'
        elif _ansk is None:
            # The response shape is not readable: no verdict from code (a wrong 'WRONG' loops the call); the bank's
            # own words decide, the gate still holds.
            _state = 'checking'
            _say = ('Follow the result\'s own words (what_to_do_next / message) for this answer. Identity is NOT verified yet. '
                    'Never re-send an answer that already passed. Say nothing about any account.')
        elif _tf(_d.get(_ansk)):
            _state = 'asking next'
            _say = ('This answer is correct, but identity is NOT verified yet. Never say the customer is verified. '
                    'Ask the next security question the brief requires (never one already passed). Say nothing about any account.')
        else:
            _state = 'retry ' + _fld
            _say = ('This answer is WRONG' + (' (' + str(_left) + ' wrong answer(s) left)' if _left is not None else '')
                    + '. Identity is NOT verified. Do not read the answer back and never re-send an earlier answer. '
                    'Ask again as the brief allows (the same question or the next one). Say nothing about any account.')
        if _v is not None:
            _v['identity_state'] = _state
        _d['identity_state'] = _state
        _d['say_next'] = _say
        if _state != 'passed':
            _d['identity_status'] = ('NOT VERIFIED (code state: ' + _state + '). You know NOTHING about the account: never '
                                     'mention any amount, product, debt, balance, due date or account status, and never '
                                     'guess one, even if the customer asks or names one.')
except Exception:
    pass
'''

GATE_TEXT = (MARK + "\n"
             "The identity state is decided by code and arrives in every result of {tool} as `identity_state` with "
             "`say_next` (states: asking next / retry <question> / failed / passed). Follow `say_next`. Until a result "
             "says identity_state = passed you know NOTHING about any account: never say or guess an amount, a product, "
             "a debt, a balance, a due date, that a payment is late or past due, or that the customer is verified, even "
             "if the customer asks (\"how much do I owe?\") or names a figure. Answer such a question with: the security "
             "check comes first, then ask the pending question.{fail}")


def _tools_of(node):
    return [t for k in ("tools", "pre_actions") for t in node.get(k) or []]


def _find_identity_tool(wf):
    names = []
    for t in (wf.get("tools") or []) + [t for n in (wf.get("nodes") or {}).values() for t in _tools_of(n)]:
        nm = ((t.get("function") or {}).get("name") or "")
        if "verif" in nm.lower() or "identit" in nm.lower():
            names.append(nm)
    return names[0] if names else None


def _referral(canned):
    """The brief's sentence for a failed identity check, from canned lines (when it mentions identity/verification
    failing or attempts running out)."""
    for l in (canned or {}).get("lines") or []:
        w = str(l.get("when") or "").lower()
        if any(x in w for x in ("identity", "verif", "security")) and any(x in w for x in ("wrong", "fail", "attempt", "ends", "end")) \
                and not any(x in w for x in ("declin", "refus")):
            return str(l.get("text") or "").strip()
    return ""


def _close_tool(wf, canned):
    nm = str((canned or {}).get("close_tool") or "").strip()
    if nm:
        return nm
    for t in wf.get("tools") or []:
        n = (t.get("function") or {}).get("name") or ""
        if "close" in n.lower() or "end" in n.lower():
            return n
    return "the close tool"


def apply(wf, canned=None):
    done = []
    tool = _find_identity_tool(wf)
    nodes = wf.get("nodes") or {}
    if not tool or not nodes:
        return done
    ref = _referral(canned)
    close = _close_tool(wf, canned)
    failed_say = ("The identity check has FAILED: no attempts are left. Do not ask any more questions and say nothing "
                  "about any account. " + ('Say exactly: "' + ref + '" ' if ref else "Tell the customer where else they can get help, as the brief says. ")
                  + "Then call " + close + " now with the brief's outcome for a failed identity check.")
    post = POST.replace("__TOOL__", repr(tool)).replace("__FAILED__", repr(failed_say))
    id_nodes = []
    for nid, n in nodes.items():
        for t in _tools_of(n):
            if (t.get("function") or {}).get("name") == tool:
                if "identity_state" not in (t.get("post_process_code") or ""):
                    t["post_process_code"] = ((t.get("post_process_code") or "").rstrip() + "\n" + post.lstrip("\n"))
                    done.append("identity_state:" + nid)
                if nid not in id_nodes:
                    id_nodes.append(nid)
    for t in wf.get("tools") or []:
        if (t.get("function") or {}).get("name") == tool and "identity_state" not in (t.get("post_process_code") or ""):
            t["post_process_code"] = ((t.get("post_process_code") or "").rstrip() + "\n" + post.lstrip("\n"))
            done.append("identity_state:global")
    if not id_nodes:
        return done
    # Terminal failed state in structure: route out of every identity node on the code's state.
    fid = "identity_failed"
    if fid not in nodes:
        src = nodes[id_nodes[0]]
        close_tr = [copy.deepcopy(tr) for tr in src.get("transitions") or []
                    if close.lower() in json.dumps(tr.get("condition") or {}).lower()]
        say = (f'If the sentence "{ref}" is not yet in the conversation, say it exactly now (nothing else), then ' if ref
               else "Tell the customer in one sentence where else they can get help, as the brief says, then ")
        fnode = {"name": fid, "node_type": "conversation",
                 "task_message": ("The identity check failed (decided by code: no attempts left). Ask no more questions and "
                                  "say nothing about the call's purpose or any account. " + say + f"call {close} in the same turn "
                                  "with the brief's outcome for a failed identity check. Never say goodbye yourself."),
                 "tools": [], "transitions": close_tr}
        # The close tool must be callable here: workflow-level tools are; a node-level close tool is copied.
        if not any((t.get("function") or {}).get("name") == close for t in wf.get("tools") or []):
            ct = next((t for n in nodes.values() for t in n.get("tools") or [] if (t.get("function") or {}).get("name") == close), None)
            if ct is not None:
                fnode["tools"].append(copy.deepcopy(ct))
        for k in ("llm_config", "model", "temperature"):
            if k in src:
                fnode[k] = copy.deepcopy(src[k])
        nodes[fid] = fnode
        done.append("node:" + fid)
    cond = {"logic": "or", "conditions": [
        {"variable": tool + "_response.data.identity_state", "operator": "equals", "operand": "failed"},
        {"variable": "identity_state", "operator": "equals", "operand": "failed"}]}
    for nid in id_nodes:
        trs = nodes[nid].setdefault("transitions", [])
        if not any(tr.get("target_node") == fid for tr in trs):
            # after the close route (a close in the same turn wins), before any other route
            i = next((k + 1 for k, tr in enumerate(trs) if close.lower() in json.dumps(tr.get("condition") or {}).lower()), 0)
            trs.insert(i, {"target_node": fid, "description": "The identity check failed (code state)", "condition": cond})
            done.append("route:" + nid + "->" + fid)
    # Gate wording in every node before identity passes.
    first = wf.get("initial_node")
    pre = list(id_nodes)
    for nid, n in nodes.items():
        if n.get("node_type") == "conversation" and nid not in pre and nid != fid:
            # the first conversation node reachable from the start (opening)
            if nid == first or any(tr.get("target_node") == nid for tr in (nodes.get(first) or {}).get("transitions") or []):
                pre.append(nid)
    fail_txt = f' When identity_state = failed: say only{(" " + chr(34) + ref + chr(34)) if ref else " the brief referral sentence"} and call {close}.'
    for nid in pre:
        n = nodes[nid]
        tm = n.get("task_message") or ""
        if MARK not in tm:
            n["task_message"] = (tm.rstrip() + "\n\n" + GATE_TEXT.format(tool=tool, fail=fail_txt)).strip()
            done.append("gate:" + nid)
    return done


# Self-simulation lint: words that disclose account content (generic money/debt words; no brief values).
PRIVACY_RE = re.compile(r"([£$€]\s?\d|\d[\d,]*(\.\d{1,2})?\s*(pounds?|euros?|dollars?|eur|gbp|usd|chf|kr)\b|\d+\.\d{2}\b|"
                        r"\b(past[- ]due|overdue|arrears|in debt|your debt|the debt|balance|outstanding|you owe|amount (due|owed)|late payment|missed payment|minimum payment)\b)",
                        re.I)


def privacy_hits(text):
    return [m.group(0) for m in PRIVACY_RE.finditer(text or "")]
