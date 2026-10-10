"""Code guards on the write tools: check a promise / callback against the computed date and amount facts BEFORE it
reaches the bank, and answer with a clear NOT RECORDED reason instead of recording a wrong value.

    install(wf, spec) -> list of guarded tool names     (called by save.py after harden, on every save)

`spec` is the calendar/amount spec of builder/datecalc.py (out/<slot>.calc.json), read from the brief at build time;
its `guards` block names the tools and body fields (checked here against the workflow's own tool schemas: a field
that is not in the tool body disables that check). Nothing brief-specific lives in this file.

- account tool post-hook: stores per product id {deadline, floor, max} in vars['guard_products'] (own copy, computed
  from the raw product with the same LIB functions as the DATE FACTS, so it works even if the datecalc hook is missing).
- promise tool pre-hook: date valid, not before today, a business day, not after that product's deadline; amount a
  number, >= floor (or the full amount if that is lower), <= full amount. Callback pre-hook: date is one of the
  allowed callback days, time inside the window, later than now. A violation sends the request to a no-op path on
  the tool's host (2xx, records nothing; found by find_noop at build time) and the post-hook replaces the result with ok=false + a NOT RECORDED tool_outcome.
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from datecalc import LIB  # noqa: E402

MARK = "# BTB_GUARD_V1"
BLOCK_URL = "https://not-recorded.btb-guard.invalid/blocked"   # .invalid never resolves (RFC 2606): nothing reaches the bank
# Seen live (b3 w1): the .invalid block is a platform function_call_error, so <tool>_failure_count rises, the post-hook
# never runs, and two blocks route the call to the service-error close. So a block goes to a no-op path on the tool's
# own host that answers 200 and records nothing (found at build time by probing; .invalid only if none answers).
NOOP_PATHS = ("/health", "/healthz", "/status", "/ping")

NOOP_FN = r'''
def noop_url(u):
    _p = str(u or '').split('/')
    if NOOP_PATH and len(_p) > 2 and _p[0] in ('http:', 'https:') and _p[2]:
        return _p[0] + '//' + _p[2] + NOOP_PATH
    return BLOCK_URL
'''

ACCOUNT_POST = r'''
try:
    if isinstance(result, dict) and isinstance(result.get('data'), dict):
        _gp = result['data'].get(SPEC.get('products_key') or 'products')
        if isinstance(_gp, list):
            _G = SPEC.get('guards') or dict()
            _t = today_of(vars.get(SPEC.get('now_variable') or 'now'))
            _out = dict()
            for _p in _gp:
                if not isinstance(_p, dict):
                    continue
                _b = band_for(_p)
                _mx = num(_p.get(_G.get('max_amount_field'))) if _G.get('max_amount_field') else None
                _out[str(_p.get(SPEC.get('product_id_field') or 'product_id'))] = dict(
                    deadline=deadline_of(_b, _t).isoformat() if _b is not None else '',
                    floor=floor_for(_p), max=_mx)
            vars['guard_products'] = json.dumps(_out)
except Exception:
    pass
'''

PROMISE_PRE = r'''
try:
    _T = __TOOL__
    vars['guard_block_' + _T] = ''
    _gb = config.get('body') if isinstance(config, dict) else None
    _G = SPEC.get('guards') or dict()
    if isinstance(_gb, dict):
        _t = today_of(vars.get(SPEC.get('now_variable') or 'now'))
        _why = []
        _pid = str(_gb.get(_G.get('promise_product_field') or 'product_id') or '')
        try:
            _prods = json.loads(vars.get('guard_products') or '[]')
        except Exception:
            _prods = dict()
        _p = _prods.get(_pid) if isinstance(_prods, dict) else None
        _df = _G.get('promise_date_field')
        if _df:
            _ds = str(_gb.get(_df) or '').strip()[:10]
            _d = None
            try:
                _d = D.fromisoformat(_ds)
            except Exception:
                _why.append('the date "' + _ds + '" is not a date in YYYY-MM-DD form')
            if _d is not None:
                if _G.get('promise_date_not_before_today') and _d < _t:
                    _why.append(fmt(_d) + ' is before today (' + fmt(_t) + ')')
                if _G.get('promise_date_business_day') and not is_bd(_d):
                    _why.append(fmt(_d) + ' is not a business day (weekend or bank holiday); the next business day is ' + fmt(next_bd(_d)))
                if _G.get('promise_date_not_after_deadline') and isinstance(_p, dict) and _p.get('deadline'):
                    _dl = D.fromisoformat(_p['deadline'])
                    if _d > _dl:
                        _why.append(fmt(_d) + ' is after the deadline of product ' + _pid + '; the latest date that can be recorded is ' + fmt(_dl))
                if (SPEC.get('promise_cutoff_time') or SPEC.get('promise_min_days_ahead')) and _d >= _t:
                    _ep = earliest_promise(vars.get(SPEC.get('now_variable') or 'now'))
                    if _d < _ep:
                        _why.append(fmt(_d) + ' is too early: the earliest promise date now is ' + fmt(_ep) +
                                    ((' (a promise for today is only possible before ' + str(SPEC.get('promise_cutoff_time'))[:5] + ')') if SPEC.get('promise_cutoff_time') and _d == _t else ''))
                _gap = SPEC.get('promise_dates_min_gap_days')
                if _gap:
                    try:
                        _prev = json.loads(vars.get('guard_promised_dates') or '{}')
                    except Exception:
                        _prev = dict()
                    for _pd in (_prev.get(_pid) or []):
                        try:
                            _dd = abs((_d - D.fromisoformat(_pd)).days)
                        except Exception:
                            continue
                        if 0 < _dd < int(_gap):                 # 0 = the same date again (a retry)
                            _why.append(fmt(_d) + ' is only ' + str(_dd) + ' days from the date already promised (' + _pd + '); dates must be at least ' + str(_gap) + ' calendar days apart')
        _af = _G.get('promise_amount_field')
        if _af:
            _a = num(_gb.get(_af))
            if _a is None or _a <= 0:
                _why.append('the amount "' + str(_gb.get(_af)) + '" is not a positive number')
            elif isinstance(_p, dict):
                _mx = _p.get('max')
                _fl = _p.get('floor')
                if _fl is not None and _mx is not None:
                    _fl = min(_fl, _mx)
                if _G.get('promise_amount_at_least_floor') and _fl is not None and _a < _fl - 0.005:
                    _why.append('the amount ' + str(_a) + ' is below the lowest amount that can be recorded for product ' + _pid + ' (' + str(_fl) + ')')
                if _mx is not None and _a > _mx + 0.005:
                    _why.append('the amount ' + str(_a) + ' is more than the full amount owed on product ' + _pid + ' (' + str(_mx) + ')')
        _off = []
        if _df and _d is not None and _why:
            _o = _d
            _dl = D.fromisoformat(_p['deadline']) if (_G.get('promise_date_not_after_deadline') and isinstance(_p, dict) and _p.get('deadline')) else None
            if _o < _t:
                _o = _t
            if (SPEC.get('promise_cutoff_time') or SPEC.get('promise_min_days_ahead')):
                _o = max(_o, earliest_promise(vars.get(SPEC.get('now_variable') or 'now')))
            if _G.get('promise_date_business_day') and not is_bd(_o):
                _o = next_bd(_o)
            if _dl is not None and _o > _dl:
                _o = _dl if (is_bd(_dl) or not _G.get('promise_date_business_day')) else prev_bd(_dl)
            if _o != _d:
                _off.append('date ' + fmt(_o) + ' (send it as ' + _o.isoformat() + ')')
        if _af and isinstance(_p, dict) and _why:
            _a = num(_gb.get(_af))
            _mx = _p.get('max')
            _fl = _p.get('floor')
            if _fl is not None and _mx is not None:
                _fl = min(_fl, _mx)
            if _a is not None and _G.get('promise_amount_at_least_floor') and _fl is not None and _a < _fl - 0.005:
                _off.append('amount ' + str(_fl))
            elif _a is not None and _mx is not None and _a > _mx + 0.005:
                _off.append('amount ' + str(_mx))
        if _why:
            vars['guard_block_' + _T] = '; '.join(_why)
            vars['guard_offer_' + _T] = ' and '.join(_off)
            config['url'] = noop_url(config.get('url'))
        elif _df and _G.get('promise_date_field') and SPEC.get('promise_dates_min_gap_days'):
            try:
                _prev = json.loads(vars.get('guard_promised_dates') or '{}')
            except Exception:
                _prev = dict()
            _prev.setdefault(_pid, []).append(str(_gb.get(_df) or '')[:10])
            vars['guard_promised_dates'] = json.dumps(_prev)
except Exception:
    pass
'''

CALLBACK_PRE = r'''
try:
    _T = __TOOL__
    vars['guard_block_' + _T] = ''
    _gb = config.get('body') if isinstance(config, dict) else None
    _G = SPEC.get('guards') or dict()
    _cb = SPEC.get('callback') or dict()
    if isinstance(_gb, dict) and _G.get('callback_date_field') and _cb.get('business_days_ahead') is not None:
        _now = str(vars.get(SPEC.get('now_variable') or 'now') or '')
        _t = today_of(_now)
        _why = []
        _raw = str(_gb.get(_G.get('callback_date_field')) or '').strip()
        _ds = _raw[:10]
        _tm = str(_gb.get(_G.get('callback_time_field')) or '').strip() if _G.get('callback_time_field') else _raw[11:16]
        _days = [_t]
        _x = _t
        for _i in range(int(_cb.get('business_days_ahead') or 0)):
            _x = next_bd(_x)
            _days.append(_x)
        _d = None
        try:
            _d = D.fromisoformat(_ds)
        except Exception:
            _why.append('the date "' + _ds + '" is not a date in YYYY-MM-DD form')
        if _d is not None and _d not in _days:
            _why.append(fmt(_d) + ' is outside the callback window; allowed days: ' + ', '.join(fmt(y) for y in _days))
        _hm = _tm[:5]
        if len(_hm) == 4 and _hm[1] == ':':
            _hm = '0' + _hm[:4]
        if _hm:
            if _cb.get('from') and _hm < str(_cb.get('from'))[:5]:
                _why.append(_hm + ' is before the callback window opens (' + str(_cb.get('from')) + ')')
            if _cb.get('to') and _hm > str(_cb.get('to'))[:5]:
                _why.append(_hm + ' is after the callback window closes (' + str(_cb.get('to')) + ')')
            if _cb.get('must_be_after_now') and _d is not None and _d == _t and len(_now) >= 16 and _hm <= _now[11:16]:
                _why.append(_hm + ' today is not later than now (' + _now[11:16] + ')')
        if _why:
            vars['guard_block_' + _T] = '; '.join(_why)
            config['url'] = noop_url(config.get('url'))
except Exception:
    pass
'''

POST = r'''
try:
    _T = __TOOL__
    _r = vars.get('guard_block_' + _T)
    if _r and isinstance(result, dict):
        vars['guard_block_' + _T] = ''
        _o2 = str(vars.get('guard_offer_' + _T) or '')
        vars['guard_offer_' + _T] = ''
        try:
            _n = int(vars.get('tool_failures_' + _T) or 0)
            if _n > 0:
                vars['tool_failures_' + _T] = _n - 1
        except Exception:
            pass
        try:
            _n = int(vars.get('tool_successes_' + _T) or 0)
            if _n > 0:
                vars['tool_successes_' + _T] = _n - 1          # the no-op answered 200: not a recorded success
        except Exception:
            pass
        if vars.get('last_tool_failed') == _T:
            vars['last_tool_failed'] = ''
        result.pop('header', None)
        result['status'] = 'success'
        result['status_code'] = 200
        result['message'] = 'checked, not sent'
        result['data'] = dict(ok=False, error='NOT RECORDED: ' + _r, tool_outcome=(
            'NOT RECORDED: ' + _T + ' was checked against the brief and NOT sent: ' + _r + '. Nothing was recorded '
            '(this is not a service failure and does not count as a failed attempt). Never say it is recorded. '
            'Do not call ' + _T + ' again with the same values. Tell the customer briefly why and follow the brief: '
            'offer a value that is allowed (look dates up in DATE FACTS, use the product deadline and floor), and '
            'call ' + _T + ' again only after the customer agrees to it.' +
            ((' CODE COMPUTED THE VALUE TO OFFER: ' + _o2 + '. Offer exactly this to the customer (it is the brief\'s rule applied to '
              'the value they named; do not pick another date or amount yourself), say why in one short sentence, and when they '
              'agree call ' + _T + ' with it.') if _o2 else '')))
        if _o2:
            result['data']['offer_instead'] = _o2
except Exception:
    pass
'''


def _snip(spec, body, tool=None, noop=""):
    code = (MARK + "\nSPEC_HEX = '" + json.dumps(spec).encode().hex() + "'\nBLOCK_URL = " + repr(BLOCK_URL) +
            "\nNOOP_PATH = " + repr(noop) + "\n" + NOOP_FN + LIB +
            body.replace("__TOOL__", repr(tool)))
    assert "{{" not in code and "}}" not in code
    return "try:\n" + "\n".join("    " + ln for ln in code.splitlines()) + "\nexcept Exception:\n    pass\n"


def _tools(wf):
    from harden import _api_tools
    for t in _api_tools(wf):
        fn = t.get("function") or {}
        if fn.get("handler") == "__function__:api_call":
            yield fn.get("name"), t


def _body_fields(t):
    fn = t.get("function") or {}
    return set((((fn.get("parameters") or {}).get("properties") or {}).get("body") or {}).get("properties") or {})


def _url(t):
    return str(((((t.get("function") or {}).get("parameters") or {}).get("properties") or {}).get("url") or {}).get("default") or "")


_NOOP_CACHE = {}


def find_noop(url):
    """A path on the tool's own host that answers a POST with 2xx (and is not a tool path): the blocked request goes
    there, so the platform sees a normal answer and nothing is recorded. '' when none answers."""
    import urllib.request
    p = url.split("/")
    if len(p) < 3 or p[0] not in ("http:", "https:") or not p[2] or "{{" in p[2]:
        return ""
    origin = p[0] + "//" + p[2]
    if origin in _NOOP_CACHE:
        return _NOOP_CACHE[origin]
    found = ""
    for path in NOOP_PATHS:
        try:
            req = urllib.request.Request(origin + path, data=b"{}", method="POST", headers={"Content-Type": "application/json", "User-Agent": "btb-builder/1"})
            with urllib.request.urlopen(req, timeout=8) as r:
                if 200 <= r.status < 300:
                    found = path
                    break
        except Exception:
            continue
    _NOOP_CACHE[origin] = found
    return found


def install(wf, spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("guards"), dict):
        return []
    g = dict(spec["guards"])
    done = []
    for name, t in _tools(wf):
        fields = _body_fields(t)
        pre = post = None
        if name and name == spec.get("account_tool"):
            post = ACCOUNT_POST
        elif name and name == g.get("promise_tool"):
            for k in ("promise_product_field", "promise_amount_field", "promise_date_field"):
                if g.get(k) and g[k] not in fields:
                    g[k] = ""                       # closed set: only fields the tool really has
            pre, post = PROMISE_PRE, POST
        elif name and name == g.get("callback_tool"):
            for k in ("callback_date_field", "callback_time_field"):
                if g.get(k) and g[k] not in fields:
                    g[k] = ""
            pre, post = CALLBACK_PRE, POST
        else:
            continue
        s = {**spec, "guards": g}
        for key, body in (("pre_process_code", pre), ("post_process_code", post)):
            if body:
                old = (t.get(key) or "").split("try:\n    " + MARK)[0]      # replace an earlier guard block
                t[key] = (old.rstrip() + "\n" + _snip(s, body, name, find_noop(_url(t)) if pre else "")).lstrip("\n")
        done.append(name)
    return done
