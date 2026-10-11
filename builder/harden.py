"""Tool-call hardening applied to every workflow before it is saved. Brief-agnostic: it reads only the workflow's
own tools (names, body fields) and the shape of the bank's responses, never a rule from a brief.

    python3 builder/harden.py <workflow.json>          # rewrites the file in place, prints a summary

What it adds to every `api_call` tool (in node `tools`, node `pre_actions` and workflow-level `tools`):
- a post-hook that turns every failed call (HTTP error, envelope status not success, `ok: false`) into an explicit
  `tool_outcome` line: FAILED, nothing was recorded, failure number N of this tool in the call, do not claim it;
  and, for pure acknowledgement writes (`{ok, <x>_id}` responses), a SUCCESS line so the model speaks after it.
  Read tools (`get_*`) also store every `*_id` they return as the call's known ids. A response with `verified: true`
  adds the passed question to `verified_items` in the call variables and a `verified_so_far` line, so the model
  never re-asks a passed security question (seen: the same question verified up to 8 times in one call).
- a pre-hook that repairs an id field the model filled with something that is not a known id (case, or the only
  id there is), so ids always come from the account lookup.
- `maxRetries: 0` on every tool that is not a `get_*` read: retries of a failed write follow the brief's own rule,
  made by the model, so the ledger and the transcript show them (a silent platform retry would hide them).
Existing builder hooks are kept: ours run after (post) or before (pre) them in the same snippet.
"""
import json, sys

POST = r'''
try:
    import json as _json
    _t = __TOOL__
    _v = vars if isinstance(globals().get('vars'), dict) else None
    if isinstance(result, dict):
        result.pop('header', None)
        _d = result.get('data')
        if not isinstance(_d, dict):
            _d = {'raw': _d}
            result['data'] = _d
        try:
            _sc = int(result.get('status_code') or 0)
        except Exception:
            _sc = 0
        _st = str(result.get('status') or 'success').lower()
        _failed = _st not in ('success', 'ok') or _sc >= 400 or _d.get('ok') in (False, 'false', 'False')
        _same = ''
        if _v is not None and __WRITE__:
            # Idempotent writes: a re-send the pre-hook sent to the no-op path, or a bank "already exists" answer after
            # our own success for the same tool and product, is reported as ALREADY RECORDED (never as a failure).
            try:
                _wq = _json.loads(_v.get('write_req_' + _t) or '[]')
                _wok = _json.loads(_v.get('writes_ok') or '{}')
            except Exception:
                _wq, _wok = [], dict()
            _prev = _wok.get(_t + '#' + str(_wq[0])) if (len(_wq) == 2 and isinstance(_wok, dict)) else None
            _err0 = str(_d.get('error') or result.get('message') or '').lower()
            _ack = all(str(k).endswith(('_id', '_ref')) for k in _d.keys() if k not in ('ok', 'error', 'tool_outcome', 'what_to_do_next', 'message'))
            _bare = not [k for k in _d.keys() if k not in ('ok', 'status', 'message', 'what_to_do_next', 'tool_outcome')]
            if _v.get('dup_hit_' + _t) and _bare:
                # only the no-op's bare answer: a parallel sibling of the same tool (M20 shares the flag) keeps its own result
                _same = 'the same values were sent again'
            elif _failed and isinstance(_prev, dict) and (any(w in _err0 for w in ('exist', 'duplicate')) or ('already' in _err0 and 'closed' not in _err0)):
                _same = ('the bank answered: ' + str(_d.get('error') or result.get('message'))[:120] +
                         '; the values on record are the earlier ones: ' + str(_prev.get('fp') or '').replace('|', ', '))
            if _same:
                _v['dup_hit_' + _t] = ''
                if _v.get('last_tool_failed') == _t:
                    _v['last_tool_failed'] = ''
                result['status'] = 'success'
                result['status_code'] = 200
                result['message'] = 'already recorded'
                _d = dict(ok=True, already_recorded=True)
                _d.update((_prev or dict()).get('ids') or dict())
                _d['tool_outcome'] = ('ALREADY RECORDED earlier in this call: do not send it again. ' + _t +
                                      (' for ' + str(_wq[0]) if _wq and _wq[0] else '') + ' succeeded earlier in this call ('
                                      + _same + '), so it IS recorded and nothing new was sent. This is not a failure: never '
                                      'tell the customer it could not be saved and never treat it as a service error. '
                                      'Continue with the next step.')
                result['data'] = _d
                _failed = False
            elif not _failed and _ack and len(_wq) == 2 and isinstance(_wok, dict) and not _v.get('guard_block_' + _t):
                _wok[_t + '#' + str(_wq[0])] = dict(fp=_wq[1], ids=dict((k, x) for k, x in _d.items()
                                                                       if str(k).endswith(('_id', '_ref')) and isinstance(x, (str, int))))
                _v['writes_ok'] = _json.dumps(_wok)
        if _failed:
            _n = 1
            if _v is not None:
                try:
                    _n = int(_v.get('tool_failures_' + _t) or 0) + 1
                except Exception:
                    _n = 1
                _v['tool_failures_' + _t] = _n
                _v['last_tool_failed'] = _t
            _err = _d.get('error') or result.get('message') or 'service error'
            if 0 < _sc < 500:
                # b10-w2: the bank ANSWERED and rejected these values (ok=false with its reason). The same values get the
                # same answer, so never tell the model to resend them (seen: an unreadable date "call again now with
                # the same values" next to the identity code's "ask again"; a rejected write re-sent as a duplicate).
                _msg = ('FAILED: ' + _t + ' was NOT carried out and NOTHING was recorded: the bank rejected the values '
                        '(error: ' + str(_err) + '). This is failure number ' + str(_n) + ' of ' + _t + ' in this call. '
                        'Never tell the customer it was recorded, booked, sent or done. Never send the same values '
                        'again: they get the same answer. Correct the value the error names (ask the customer if '
                        'needed) and follow the brief.')
            else:
                _msg = ('FAILED: ' + _t + ' was NOT carried out and NOTHING was recorded (error: ' + str(_err) + '). '
                        'This is failure number ' + str(_n) + ' of ' + _t + ' in this call. Never tell the customer it was '
                        'recorded, booked, sent or done. Apply the brief rule for a failed tool call: if it allows another '
                        'attempt, call ' + _t + ' again now with the same values; otherwise tell the customer plainly that '
                        'it could not be done and continue as the brief says.')
            if 'id' in str(_err).lower() and _v is not None and _v.get('known_ids'):
                _msg += ' Use only these ids, exactly as written: ' + str(_v.get('known_ids')) + '.'
            _d['tool_outcome'] = _msg
        else:
            if _v is not None and _v.get('last_tool_failed') == _t:
                _v['last_tool_failed'] = ''
            _keys = [k for k in _d.keys() if k not in ('ok', 'error', 'tool_outcome', 'what_to_do_next')]
            if _same:
                pass
            elif __WRITE__ and all(str(k).endswith(('_id', '_ref')) for k in _keys):
                _d['tool_outcome'] = ('SUCCESS: ' + _t + ' was carried out and recorded. Only now may you tell the '
                                      'customer it is recorded. Speak to the customer now.')
            if _v is not None and str(_d.get('verified')).lower() == 'true':
                # Identity memory (b4-5): a passed question is stored in the call's variables, so a repeated or
                # replayed turn never asks it again. The pre-hook stashed the request's selector values.
                _done = [x for x in str(_v.get('verified_items') or '').split('|') if x]
                _sel = str(_v.get('last_request_' + _t) or '')
                if _sel and _sel not in _done:
                    _done.append(_sel)
                _v['verified_items'] = '|'.join(_done)
                _all = str(_d.get('all_verified')).lower() == 'true'
                if _all:
                    _v['identity_verified'] = 'true'
                _d['verified_so_far'] = ('Already passed in this call (never ask these again): '
                                         + (', '.join(_done) or str(len(_done)) + ' question(s)')
                                         + ('. Identity is fully verified: do not ask any security question again.' if _all else
                                            '. Ask only a question that is not in this list.'))
            # Identity gate (M18): while the tool's all-verified flag is false, the result says so in words; seen
            # officially: after one wrong and one right answer the model "moved on" and invented an amount.
            _allk = [k for k in _d.keys() if 'verif' in str(k).lower() and 'all' in str(k).lower()]
            if _allk and str(_d.get(_allk[0])).lower() in ('false', '0', 'none', ''):
                _d['identity_status'] = ('NOT VERIFIED YET (' + str(_allk[0]) + ' is false). You know nothing about '
                                         'the account: never mention any amount, product or account detail. '
                                         'Follow the brief\'s identity rule: ask the next security question (a '
                                         'question answered wrongly is asked again if the brief allows), or end '
                                         'the check when no attempts are left.')
            if _t.startswith('get_') and _v is not None:
                _known = {}
                _stack = [_d]
                while _stack:
                    _o = _stack.pop()
                    if isinstance(_o, dict):
                        for _k2, _x in _o.items():
                            if str(_k2).endswith('_id') and _k2 != 'customer_id' and isinstance(_x, (str, int)):
                                _known.setdefault(str(_k2), [])
                                if str(_x) not in _known[str(_k2)]:
                                    _known[str(_k2)].append(str(_x))
                            else:
                                _stack.append(_x)
                    elif isinstance(_o, list):
                        _stack.extend(reversed(_o))
                if _known:
                    _v['known_ids'] = _json.dumps(_known)
                # b10-w2 (M7, port of idea/b7-1 e9dfe52 + cca104a, mapping part only): every listed item with an id and
                # its short text fields, so the pre-hook maps an id the model BUILT ('credit_card_2288', 'pl_1234') to
                # the one listed item it can only mean, instead of a refused write and a second write for the item.
                _items = []
                _stack = [_d]
                while _stack:
                    _o = _stack.pop()
                    if isinstance(_o, list):
                        _stack.extend(reversed(_o))
                    elif isinstance(_o, dict):
                        _ik = [k for k in _o.keys() if str(k).endswith('_id') and k != 'customer_id' and isinstance(_o.get(k), (str, int))]
                        if _ik and _o is not _d:
                            _items.append({'_key': str(_ik[0]), '_id': str(_o.get(_ik[0])),
                                           '_text': [str(x).lower() for k, x in _o.items() if k not in _ik and k not in ('band', 'deadline', 'deadline_weekday')
                                                     and isinstance(x, str) and 2 <= len(str(x)) <= 40]})
                        for _x in _o.values():
                            if isinstance(_x, (dict, list)):
                                _stack.append(_x)
                if _items:
                    _v['known_items'] = _json.dumps(_items)
except Exception:
    pass
'''

PRE = r'''
try:
    _o2, _c2 = chr(123) * 2, chr(125) * 2
    _b0 = config.get('body') if isinstance(config, dict) else None
    if isinstance(_b0, dict):
        for _k0 in list(_b0.keys()):
            _x0 = _b0.get(_k0)
            if isinstance(_x0, str) and _o2 in _x0:
                _nm = _x0.replace(_o2, '').replace(_c2, '').strip()
                _cand = [vars.get(__TOOL__ + '_args.' + _k0), vars.get(__TOOL__ + '_args.' + _nm), vars.get(_nm), vars.get(_k0)]
                _cand = [c for c in _cand if c not in (None, '') and _o2 not in str(c)]
                if _cand:
                    _b0[_k0] = _cand[0]
                else:
                    _b0[_k0] = ''
except Exception:
    pass
try:
    _b1 = config.get('body') if isinstance(config, dict) else None
    if isinstance(_b1, dict):
        _sel1 = [str(_x1) for _k1, _x1 in _b1.items() if isinstance(_x1, str) and _x1
                 and not str(_k1).endswith('_id') and not any(w in str(_k1).lower() for w in ('answer', 'value', 'response', 'digits', 'dob', 'date', 'amount'))]
        vars['last_request_' + __TOOL__] = ' '.join(_sel1)[:60]
except Exception:
    pass
try:
    import json as _json
    _kn = vars.get('known_ids')
    if isinstance(_kn, str) and _kn:
        _kn = _json.loads(_kn)
    _b = config.get('body') if isinstance(config, dict) else None
    if isinstance(_kn, dict) and isinstance(_b, dict):
        for _k, _ids in _kn.items():
            if _k in _b and _ids:
                _val = str(_b.get(_k) or '').strip()
                if _val in _ids:
                    continue
                _low = dict((str(i).lower(), i) for i in _ids)
                if _val.lower() in _low:
                    _b[_k] = _low[_val.lower()]
                elif len(_ids) == 1:
                    _b[_k] = _ids[0]
                elif _val:
                    # An id the model built: the one listed item whose own text fields (type, last digits, name, or
                    # the initials of a multi-word type) appear in it. A tie or no match: sent as it is (bank answers).
                    _its = _json.loads(vars.get('known_items') or '[]')
                    _al = lambda z: ''.join(ch for ch in str(z).lower() if ch.isalnum())
                    _vl = _al(_val)
                    _sc = []
                    for _it in _its:
                        if _it.get('_key') != _k:
                            continue
                        _n = sum(len(_al(x)) for x in _it.get('_text') or [] if len(_al(x)) >= 2 and _al(x) in _vl)
                        _ini = [''.join(w[0] for w in str(x).replace('-', ' ').replace('_', ' ').split() if w) for x in _it.get('_text') or []]
                        _n += sum(len(i) for i in _ini if len(i) >= 2 and _vl.startswith(i))
                        _sc.append((_n, _it.get('_id')))
                    _sc.sort(reverse=True)
                    if _sc and _sc[0][0] > 0 and (len(_sc) == 1 or _sc[1][0] < _sc[0][0]):
                        _b[_k] = _sc[0][1]
except Exception:
    pass
try:
    # Idempotent writes (M12): an identical re-send of a write that already SUCCEEDED in this call goes to the host's
    # no-op path (nothing reaches the bank) and the post-hook answers ALREADY RECORDED. Key = tool + the request's own
    # *_id fields (the product), value = the request's fields except free text.
    import json as _json
    vars['dup_hit_' + __TOOL__] = ''
    vars['write_req_' + __TOOL__] = ''
    _bq = config.get('body') if isinstance(config, dict) else None
    if isinstance(_bq, dict):
        def _nv(x):
            try:
                return str(round(float(str(x).replace(',', '').strip()), 2))
            except Exception:
                return str(x).strip().lower()
        _pk = '|'.join(str(_bq.get(k)) for k in sorted(_bq) if str(k).endswith(('_id', '_ref', '_no', '_number', '_index')) and not str(k).startswith('customer'))
        _fp = '|'.join(str(k) + '=' + _nv(_bq.get(k)) for k in sorted(_bq)
                       if not (isinstance(_bq.get(k), str) and len(str(_bq.get(k)).split()) >= 4))
        vars['write_req_' + __TOOL__] = _json.dumps([_pk, _fp])
        try:
            _wok = _json.loads(vars.get('writes_ok') or '{}')
        except Exception:
            _wok = dict()
        _prev = _wok.get(__TOOL__ + '#' + _pk) if isinstance(_wok, dict) else None
        _u = str(config.get('url') or '').split('/')
        if isinstance(_prev, dict) and _prev.get('fp') == _fp and __NOOP__ and len(_u) > 2 and _u[0] in ('http:', 'https:') and _u[2]:
            vars['dup_hit_' + __TOOL__] = _pk or 'this call'
            config['url'] = _u[0] + '//' + _u[2] + __NOOP__
except Exception:
    pass
'''


def _api_tools(wf):
    for node in (wf.get("nodes") or {}).values():
        for key in ("tools", "pre_actions"):
            for t in node.get(key) or []:
                yield t
    for node in (wf.get("global_nodes") or {}).values() if isinstance(wf.get("global_nodes"), dict) else []:
        for key in ("tools", "pre_actions"):
            for t in node.get(key) or []:
                yield t
    for t in wf.get("tools") or []:
        yield t


def _noop(t):
    """The tool host's no-op path (guards.find_noop, probed once per host): an identical re-send of a write goes there."""
    try:
        from guards import find_noop, _url
        return find_noop(_url(t))
    except Exception:  # noqa: BLE001
        return ""


def harden(wf):
    done = []
    for t in _api_tools(wf):
        fn = t.get("function") or {}
        if fn.get("handler") != "__function__:api_call":
            continue
        name = fn.get("name") or "tool"
        write = not name.startswith("get_")
        # A body leaf without `default` is dropped from the request on this platform (seen b1 merge: verify_identity
        # sent only customer_id). The kit's working pattern: a model-filled field gets "default": "{{<field>}}".
        body = (((fn.get("parameters") or {}).get("properties") or {}).get("body") or {})
        for fld, leaf in (body.get("properties") or {}).items():
            if isinstance(leaf, dict) and "default" not in leaf and leaf.get("type") != "object":
                leaf.pop("const", None)
                leaf["default"] = "{{" + fld + "}}"
        cfg = t.setdefault("config", {})
        if write:
            cfg["maxRetries"] = 0
        cfg.setdefault("timeoutMs", 12000)
        post = POST.replace("__TOOL__", repr(name)).replace("__WRITE__", "True" if write else "False")
        old_post = (t.get("post_process_code") or "").strip()
        if "tool_outcome" not in old_post:
            t["post_process_code"] = (old_post + "\n" if old_post else "") + post.lstrip("\n")
        old_pre = (t.get("pre_process_code") or "").strip()
        if write and "known_ids" not in old_pre:
            pre = PRE.replace("__TOOL__", repr(name)).replace("__NOOP__", repr(_noop(t)))
            t["pre_process_code"] = pre.lstrip("\n") + ("\n" + old_pre if old_pre else "")
        done.append(name)
    return done


if __name__ == "__main__":
    p = sys.argv[1]
    wf = json.load(open(p))
    names = harden(wf)
    json.dump(wf, open(p, "w"), indent=1)
    print(json.dumps({"hardened_tools": names}))
