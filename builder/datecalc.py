"""Code steps for the phone agent: date, business-day, deadline and amount-floor facts computed in code, not by the model.

    python3 builder/datecalc.py --slot <slot> --tools <openapi.json> <brief.md>...

1. One model call (Azure, btb/llm.py) reads the briefs + tool API file and extracts a small calendar/amount spec
   (weekend days, holidays, deadline bands, floors, callback window, weekday-phrase meaning) as JSON.
   Nothing brief-specific lives in this file: every value comes from that extraction.
2. Generic Python templates turn the spec into
   - a code node snippet that writes `date_facts` (today, anchor dates, deadline per band, a day-by-day calendar
     with business-day flags and next business day, "this/next <weekday>" table, callback days), and
   - a `post_process_code` hook for the account tool that adds, per product: band, deadline, attempts, floor.
3. Both are executed locally on several `now` values and fake products; a crash fails the step.
Outputs: out/<slot>.calc.json (spec + snippets + ready code node).
"""
import argparse, datetime, json, pathlib, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "btb"))

EXTRACT = """You read a bank's collections brief (it may be raw material: mails, a policy extract, a memo that changes
earlier rules, code lists; when a later memo changes a rule, the memo wins) and its tool API file.
Extract ONLY what is needed to compute dates and amounts in code. Return JSON only, with exactly these keys:

{
 "now_variable": "<call variable holding the current date/time, e.g. now>",
 "weekend_days": [<weekday numbers that are never business days, Monday=0 ... Sunday=6>],
 "holidays": ["YYYY-MM-DD", ...],                     // every bank holiday / non-business date listed
 "account_tool": "<tool name that returns the products>",
 "products_key": "<key in that tool's response body holding the list of products>",
 "product_id_field": "<field of a product holding its id>",
 "type_field": "<field of a product holding its type, or empty>",
 "band_field": "<numeric product field the deadline band depends on (e.g. days late), or empty>",
 "bands": [  // one entry per deadline band / row of the deadline table, in the brief's order
   {"name": "<band name>", "min": <number or null>, "max": <number or null>,
    "product_types": [<types this row applies to, empty = all>],
    "deadline_count": <integer N>,
    "deadline_unit": "business_days" | "calendar_days",
    "deadline_counts_today": <true if today counts as day 1, normally false: "the Nth business day after today">,
    "attempts": <number of persuasion attempts in this band, or null>}
 ],
 "floors": [ // the minimum acceptable promise amount, per product type
   {"product_types": [<types, empty = all>], "field": "<product field holding the floor, or empty>",
    "percent_of_field": "<field the floor is a percentage of, or empty>", "percent": <number or null>,
    "fixed": <number or null>, "min_amount": <number or null>, "note": "<the rule in a few words>"}
 ],
 "callback": {"business_days_ahead": <0 = today only, 1 = today or next business day, ...; null if no rule>,
              "from": "HH:MM or empty", "to": "HH:MM or empty", "must_be_after_now": <true/false>},
 "next_weekday_rule": "following_week" | "nearest_upcoming" | "unspecified",   // what "next Friday" means
 "this_weekday_rule": "current_week" | "nearest_upcoming" | "unspecified"      // what "this Friday" means
}

Use exact field names from the tool API file. Use exact values from the brief. Do not invent rules that are not there.

TOOL API FILE:
{tools}

BRIEF FILES:
{briefs}
"""

# ---- generic runtime library, shared by the code node and the hook (no '{{' or '}}' allowed in it) ----
LIB = r'''
import json, datetime
SPEC = json.loads(bytes.fromhex(SPEC_HEX).decode())
D = datetime.date
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
HOL = set(str(h)[:10] for h in (SPEC.get('holidays') or []))
WEEKEND = set(int(x) for x in (SPEC.get('weekend_days') if SPEC.get('weekend_days') is not None else [5, 6]))
def is_bd(d):
    return d.weekday() not in WEEKEND and d.isoformat() not in HOL
def next_bd(d, include=False):
    d = d if include else d + datetime.timedelta(days=1)
    for _ in range(60):
        if is_bd(d):
            return d
        d = d + datetime.timedelta(days=1)
    return d
def add_units(d, n, unit, counts_today=False):
    n = int(n or 0)
    if unit == 'calendar_days':
        return d + datetime.timedelta(days=(n - 1 if counts_today else n))
    if counts_today and is_bd(d):
        n -= 1
        if n <= 0:
            return d
    x = d
    for _ in range(n):
        x = next_bd(x)
    return x
def fmt(d):
    return WD[d.weekday()] + ' ' + d.isoformat()
def today_of(now):
    return D.fromisoformat(str(now).strip()[:10])
def num(v):
    try:
        return float(v)
    except Exception:
        return None
def band_for(p):
    f = SPEC.get('band_field') or ''
    tf = SPEC.get('type_field') or ''
    v = num(p.get(f)) if f else None
    for b in SPEC.get('bands') or []:
        ts = b.get('product_types') or []
        if ts and str(p.get(tf)) not in [str(t) for t in ts]:
            continue
        if f and v is None:
            continue
        if v is not None and b.get('min') is not None and v < float(b['min']):
            continue
        if v is not None and b.get('max') is not None and v > float(b['max']):
            continue
        return b
    return None
def deadline_of(b, today):
    return add_units(today, b.get('deadline_count'), b.get('deadline_unit'), bool(b.get('deadline_counts_today')))
def floor_for(p):
    tf = SPEC.get('type_field') or ''
    for r in SPEC.get('floors') or []:
        ts = r.get('product_types') or []
        if ts and str(p.get(tf)) not in [str(t) for t in ts]:
            continue
        amt = None
        if r.get('field') and num(p.get(r['field'])) is not None:
            amt = num(p.get(r['field']))
        elif r.get('percent_of_field') and r.get('percent') is not None and num(p.get(r['percent_of_field'])) is not None:
            amt = round(num(p.get(r['percent_of_field'])) * float(r['percent']) / 100.0, 2)
        elif r.get('fixed') is not None:
            amt = float(r['fixed'])
        if amt is None:
            continue
        if r.get('min_amount') is not None:
            amt = max(amt, float(r['min_amount']))
        return amt
    return None
def build_facts(now):
    t = today_of(now)
    one = datetime.timedelta(days=1)
    L = []
    L.append('TODAY: ' + fmt(t) + (' (a business day)' if is_bd(t) else ' (NOT a business day)'))
    L.append('Tomorrow: ' + fmt(t + one))
    L.append('Next business day after today: ' + fmt(next_bd(t)))
    wk_end = t + datetime.timedelta(days=6 - t.weekday())
    def last_bd_on_or_before(d, lo):
        x = d
        while x >= lo and not is_bd(x):
            x = x - one
        return x if x >= lo else None
    lb_this = last_bd_on_or_before(wk_end, t)
    lb_next = last_bd_on_or_before(wk_end + datetime.timedelta(days=7), wk_end + one)
    L.append('Last business day of this week: ' + (fmt(lb_this) if lb_this else 'none left this week') + ('  <- that is TODAY' if lb_this == t else ''))
    L.append('Last business day of next week: ' + (fmt(lb_next) if lb_next else 'none'))
    me = (t.replace(day=28) + datetime.timedelta(days=4))
    me = me - datetime.timedelta(days=me.day)
    lbm = last_bd_on_or_before(me, t)
    L.append('Last business day of this month: ' + (fmt(lbm) if lbm else 'none left this month'))
    dls = []
    for b in SPEC.get('bands') or []:
        dl = deadline_of(b, t)
        dls.append(dl)
        cond = []
        if b.get('product_types'):
            cond.append('types ' + '/'.join(str(x) for x in b['product_types']))
        if SPEC.get('band_field'):
            cond.append(str(SPEC.get('band_field')) + ' ' + str(b.get('min')) + ' to ' + str(b.get('max')))
        L.append('DEADLINE for band "' + str(b.get('name')) + '" (' + ', '.join(cond) + '): ' + fmt(dl) +
                 ' = ' + str(b.get('deadline_count')) + ' ' + str(b.get('deadline_unit')).replace('_', ' ') + ' after today' +
                 ('' if b.get('attempts') is None else '; persuasion attempts: ' + str(b.get('attempts'))))
    cb = SPEC.get('callback') or {}
    if cb.get('business_days_ahead') is not None:
        days = [t]
        x = t
        for _ in range(int(cb.get('business_days_ahead') or 0)):
            x = next_bd(x)
            days.append(x)
        win = (' between ' + str(cb.get('from')) + ' and ' + str(cb.get('to'))) if cb.get('from') else ''
        L.append('CALLBACK allowed only on: ' + ', '.join(fmt(d) for d in days) + win +
                 (' and later than now (' + str(now) + ')' if cb.get('must_be_after_now') else '') +
                 '. Any other day is outside the window.')
    nr = SPEC.get('next_weekday_rule')
    tr = SPEC.get('this_weekday_rule')
    L.append('WEEKDAY WORDS (said today, ' + WD[t.weekday()] + '):')
    mon = t - datetime.timedelta(days=t.weekday())
    for i in range(7):
        this_d = mon + datetime.timedelta(days=i)
        upcoming = t + datetime.timedelta(days=((i - t.weekday()) % 7) or 7)
        nxt = this_d + datetime.timedelta(days=7) if nr == 'following_week' else upcoming
        ths = upcoming if tr == 'nearest_upcoming' else this_d
        s = '  ' + WD[i] + ': "this ' + WD[i] + '" = ' + ths.isoformat() + ('(past)' if ths < t else '') + ', "next ' + WD[i] + '" = ' + nxt.isoformat()
        if nr not in ('following_week', 'nearest_upcoming'):
            s += ', nearest upcoming = ' + upcoming.isoformat()
        L.append(s)
    horizon = max(dls or [t + datetime.timedelta(days=14)]) + datetime.timedelta(days=3)
    L.append('CALENDAR (look a date up here; never compute dates yourself):')
    d = t
    while d <= horizon:
        if is_bd(d):
            s = 'business day'
        else:
            s = ('HOLIDAY' if d.isoformat() in HOL else 'weekend') + ', not a business day -> next business day ' + fmt(next_bd(d))
        tags = []
        for b, dl in zip(SPEC.get('bands') or [], dls):
            if d == dl:
                tags.append('DEADLINE ' + str(b.get('name')))
            elif d > dl:
                tags.append('after ' + str(b.get('name')) + ' deadline')
        L.append('  ' + fmt(d) + ': ' + s + (' [' + '; '.join(tags) + ']' if tags else ''))
        d = d + one
    return t, '\n'.join(L)
'''

NODE_CODE = r'''
try:
    t, f = build_facts(vars.get(SPEC.get('now_variable') or 'now'))
    vars['date_facts'] = f
    vars['today_iso'] = t.isoformat()
    vars['date_facts_state'] = 'known'
except Exception as e:
    vars['date_facts'] = 'Date facts unavailable (' + str(e)[:80] + '). Work from the brief.'
    vars['date_facts_state'] = 'unknown'
'''

HOOK_CODE = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        data = result.get('data')
        prods = data.get(SPEC.get('products_key') or 'products') if isinstance(data, dict) else None
        t = None
        try:
            t = today_of(vars.get(SPEC.get('now_variable') or 'now'))
        except Exception:
            t = None
        if isinstance(prods, list):
            lines = []
            for p in prods:
                if not isinstance(p, dict):
                    continue
                fl = floor_for(p)
                if fl is not None:
                    p['floor_amount'] = fl
                b = band_for(p)
                if b is not None:
                    p['band'] = str(b.get('name'))
                    if b.get('attempts') is not None:
                        p['persuasion_attempts'] = b.get('attempts')
                    if t is not None:
                        dl = deadline_of(b, t)
                        p['deadline'] = dl.isoformat()
                        p['deadline_weekday'] = WD[dl.weekday()]
                lines.append(str(p.get(SPEC.get('product_id_field') or 'product_id')) + ': band ' + str(p.get('band')) +
                             ', deadline ' + str(p.get('deadline_weekday', '')) + ' ' + str(p.get('deadline')) +
                             ', floor ' + str(p.get('floor_amount')))
            try:
                vars['product_facts'] = '\n'.join(lines)
            except Exception:
                pass
        if isinstance(data, dict) and t is not None:
            try:
                _t, f = build_facts(vars.get(SPEC.get('now_variable') or 'now'))
                data['date_facts'] = f
                vars['date_facts'] = f
                vars['date_facts_state'] = 'known'
            except Exception:
                pass
except Exception:
    pass
'''


def snippet(spec, body):
    code = "SPEC_HEX = '" + json.dumps(spec).encode().hex() + "'\n" + LIB + body
    assert "{{" not in code and "}}" not in code
    return code


def selftest(spec, node_code, hook_code):
    """Run both snippets locally on several days and fake products. Returns a list of problems."""
    probs = []
    last = {}
    start = datetime.date.today()
    nowvar = spec.get("now_variable") or "now"
    for k in range(0, 14, 3):
        v = {nowvar: (start + datetime.timedelta(days=k)).isoformat() + "T11:00"}
        exec(node_code, {"vars": v})
        if v.get("date_facts_state") != "known":
            probs.append(f"node failed for {v[nowvar]}: {v.get('date_facts')}")
        last = v
    fake = {}
    for b in spec.get("bands") or []:
        p = {spec.get("product_id_field") or "product_id": f"p{len(fake) + 1}"}
        if spec.get("type_field") and b.get("product_types"):
            p[spec["type_field"]] = b["product_types"][0]
        if spec.get("band_field"):
            p[spec["band_field"]] = b.get("min") if b.get("min") is not None else b.get("max") or 1
        for r in spec.get("floors") or []:
            for f in (r.get("field"), r.get("percent_of_field")):
                if f:
                    p[f] = 100.0
        fake[p[spec.get("product_id_field") or "product_id"]] = p
    res = {"status": "success", "header": {}, "data": {"ok": True, spec.get("products_key") or "products": list(fake.values())}}
    v = {nowvar: start.isoformat() + "T11:00"}
    exec(hook_code, {"vars": v, "result": res})
    for p in res["data"][spec.get("products_key") or "products"]:
        if "deadline" not in p:
            probs.append(f"hook gave no deadline for {p}")
    v["date_facts"] = last.get("date_facts")
    return probs, v


def main():
    from llm import chat_json
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True); ap.add_argument("--tools", default="tools/openapi.json"); ap.add_argument("briefs", nargs="+")
    a = ap.parse_args()
    briefs = "\n\n".join(f"=== {b} ===\n" + pathlib.Path(b).read_text() for b in a.briefs)
    prompt = EXTRACT.replace("{tools}", pathlib.Path(a.tools).read_text()).replace("{briefs}", briefs)
    spec, probs = None, ["not run"]
    for attempt in range(2):
        try:
            spec = chat_json([{"role": "user", "content": prompt}], tier="strong", purpose="extract calendar/amount spec for code steps",
                             max_tokens=4000, effort="medium")
            node_code, hook_code = snippet(spec, NODE_CODE), snippet(spec, HOOK_CODE)
            probs, v = selftest(spec, node_code, hook_code)
            if not probs:
                break
        except Exception as e:  # noqa: BLE001
            probs = [f"{type(e).__name__}: {e}"]
    out = KIT / "out" / f"{a.slot}.calc.json"
    out.parent.mkdir(exist_ok=True)
    if probs:
        print("datecalc: FAILED", probs)
        out.write_text(json.dumps({"ok": False, "problems": probs, "spec": spec}, indent=1))
        return
    node = {
        "name": "date_facts_setup", "node_type": "code", "passthrough": True,
        "passthrough_default_transition": "<NEXT NODE>", "on_enter": {"type": "silent"},
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                         "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": node_code},
                                                                          "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": [{"target_node": "<NEXT NODE>", "description": "always", "condition": {"operator": "always"}}],
    }
    out.write_text(json.dumps({"ok": True, "spec": spec, "code_node": node, "account_tool": spec.get("account_tool"),
                               "account_post_process_code": hook_code, "example_date_facts": v.get("date_facts"),
                               "example_product_facts": v.get("product_facts")}, indent=1))
    print(f"datecalc: ok -> {out}")
    print(json.dumps(spec, indent=1))


if __name__ == "__main__":
    main()
