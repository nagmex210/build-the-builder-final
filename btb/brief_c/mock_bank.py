"""Mock bank for brief C (held-out test brief). Standard library only.

    python3 btb/brief_c/mock_bank.py [--port 8787] [--cases btb/brief_c/cases-c.json] [--state btb/brief_c/.state.json]

Implements btb/brief_c/openapi-c.json under /v1, plus the practice endpoints the kit's mock has:
    POST /v1/practice/sessions {"case": "C-01"}   (x-team-key header, 16+ chars) -> {"ok", "variables"}
    GET  /v1/practice/ledger/<customer_id>         (same x-team-key)              -> the ledger
The ledger uses the kit's keys (outcome, reason, promises[product_id, amount, date], notes[product_id, reason],
callbacks[date, time], transfers[queue], calls) so tools/score.py scores it unchanged. Like the kit's mock, it does
not enforce the brief, only the API: wrong input gets ok:false with an error (and sometimes a hint).
Failure injection: a case's "faults": [{"tool": "create_promise", "fail_first_n": 2}] makes the first n calls of that
tool return HTTP 500 with nothing recorded.
"""
import argparse, hashlib, json, os, re, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()
STATE = {"customers": {}}
CASES = {}
STATE_FILE = None
TOOLS = ("verify_identity", "get_account", "create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call")
RESULTS = ("arranged", "paused", "transferred", "no_payment", "id_failed", "no_contact")
CODES = ("BREATHING_SPACE", "FRAUD", "PLAN", "HUMAN", "SERVICE_ERROR", "DISPUTED", "HARDSHIP", "REFUSED", "PAID_CLAIMED",
         "OVER_LIMIT", "FAILED", "DECLINED", "CALLBACK", "NO_CALLBACK", "WRONG_NUMBER", "DECEASED", "UNCLEAR")
NOTE_CODES = ("REFUSED", "HARDSHIP", "BREATHING_SPACE", "DISPUTED", "PAID_CLAIMED", "SERVICE_ERROR", "OVER_LIMIT")
QUEUES = ("specialist", "payment_plans", "fraud")
MAX_WRONG = 2


def save():
    if STATE_FILE:
        tmp = STATE_FILE + ".tmp"
        json.dump(STATE, open(tmp, "w"))
        os.replace(tmp, STATE_FILE)


def accounts_of(case):
    out = []
    for i, p in enumerate(case["products"], 1):
        a = {"account_ref": f"A{i}", "kind": p["kind"], "arrears": p["arrears"], "days_overdue": p["days_overdue"]}
        for k in ("card_last4", "min_due", "instalment"):
            if k in p:
                a[k] = p[k]
        out.append(a)
    return out


def norm_postcode(v):
    s = re.sub(r"[\s\-.,]", "", str(v)).upper()
    if re.fullmatch(r"\d{4}", s):
        return s, None
    if re.fullmatch(r"\d{4}[A-Z]{2}", s):
        return s[:4], s[4:]
    return None, None


def norm_month(v):
    s = str(v).strip()
    if re.fullmatch(r"\d{1,2}", s) and 1 <= int(s) <= 12:
        return f"{int(s):02d}"
    return None


def tool(name, cust, args):
    """Returns (status, result). Mutates cust."""
    case = CASES[cust["case"]]
    if cust["outcome"] is not None:
        return 200, {"ok": False, "error": "call already closed"}
    for f in case.get("faults", []):
        if f["tool"] == name and cust["failures"][name] < f.get("fail_first_n", 0):
            cust["failures"][name] += 1
            return 500, {"ok": False, "error": "service unavailable, nothing was recorded"}
    verified = all(cust["verified"].get(k) for k in ("postcode", "birth_month"))
    refs = [a["account_ref"] for a in accounts_of(case)]

    if name == "verify_identity":
        check, value = args.get("check"), args.get("value")
        if check not in ("postcode", "birth_month"):
            return 200, {"ok": False, "error": "check must be postcode or birth_month"}
        if value is None or str(value).strip() == "":
            return 200, {"ok": False, "error": "value is missing"}
        if cust["wrong"] >= MAX_WRONG:
            return 200, {"ok": False, "error": "identity check locked after two wrong answers"}
        res = {"ok": True}
        if check == "postcode":
            digits, letters = norm_postcode(value)
            if digits is None:
                return 200, {"ok": False, "error": "value is not a postcode. Send four digits, a space and two letters, like 4021 KL."}
            t_digits, t_letters = norm_postcode(case["identity"]["postcode"])
            if letters is None:
                if digits == t_digits:
                    res.update(passed=False, hint="letters_missing")
                    cust["hinted"] = True
                else:
                    cust["wrong"] += 1; res["passed"] = False
            else:
                ok = (digits, letters) == (t_digits, t_letters)
                res["passed"] = ok
                if ok: cust["verified"]["postcode"] = True
                else: cust["wrong"] += 1
        else:
            m = norm_month(value)
            if m is None:
                return 200, {"ok": False, "error": "send birth_month as two digits, 01 to 12"}
            ok = m == case["identity"]["birth_month_mm"]
            res["passed"] = ok
            if ok: cust["verified"]["birth_month"] = True
            else: cust["wrong"] += 1
        res["attempts_left"] = max(0, MAX_WRONG - cust["wrong"])
        res["identity_confirmed"] = all(cust["verified"].get(k) for k in ("postcode", "birth_month"))
        return 200, res

    if name == "get_account":
        if not verified:
            return 200, {"ok": False, "error": "identity not verified"}
        return 200, {"ok": True, "accounts": accounts_of(case)}

    if name == "create_promise":
        if not verified:
            return 200, {"ok": False, "error": "identity not verified"}
        ref = args.get("account_ref")
        if ref not in refs:
            return 200, {"ok": False, "error": "unknown account_ref", "hint": "use an account_ref from get_account: " + ", ".join(refs)}
        try:
            amount = round(float(args.get("amount")), 2)
        except (TypeError, ValueError):
            return 200, {"ok": False, "error": "amount must be a number"}
        if amount <= 0:
            return 200, {"ok": False, "error": "amount must be more than 0"}
        d = str(args.get("pay_date", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            return 200, {"ok": False, "error": "pay_date must be YYYY-MM-DD"}
        n = args.get("instalment_no", 0)
        try:
            n = int(n if n not in (None, "") else 0)
        except (TypeError, ValueError):
            n = -1
        if n not in (0, 1, 2):
            return 200, {"ok": False, "error": "instalment_no must be 0, 1 or 2"}
        mine = [p for p in cust["promises"] if p["product_id"] == ref]
        if any(p["instalment_no"] == n for p in mine) or (n == 0 and mine) or (n and any(p["instalment_no"] == 0 for p in mine)):
            return 200, {"ok": False, "error": "a promise already exists for this account"}
        pid = "PR-" + uuid.uuid4().hex[:8]
        cust["promises"].append({"product_id": ref, "amount": amount, "date": d, "instalment_no": n, "promise_ref": pid})
        return 200, {"ok": True, "promise_ref": pid}

    if name == "add_note":
        if not verified:
            return 200, {"ok": False, "error": "identity not verified"}
        ref = args.get("account_ref")
        if ref not in refs:
            return 200, {"ok": False, "error": "unknown account_ref", "hint": "use an account_ref from get_account: " + ", ".join(refs)}
        code = args.get("note_code")
        if code not in NOTE_CODES:
            return 200, {"ok": False, "error": "unknown note_code", "hint": "one of " + ", ".join(NOTE_CODES)}
        cust["notes"].append({"product_id": ref, "reason": code, "text": str(args.get("text") or "")})
        return 200, {"ok": True}

    if name == "schedule_callback":
        d, s = str(args.get("date", "")), str(args.get("slot", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or not re.fullmatch(r"\d{2}:\d{2}", s):
            return 200, {"ok": False, "error": "date must be YYYY-MM-DD and slot HH:MM"}
        if s[3:] not in ("00", "30"):
            return 200, {"ok": False, "error": "slot must start on the hour or the half hour", "hint": "round up to the next half hour"}
        cust["callbacks"].append({"date": d, "time": s})
        return 200, {"ok": True}

    if name == "transfer_to_agent":
        q = args.get("queue")
        if q not in QUEUES:
            return 200, {"ok": False, "error": "unknown queue", "hint": "one of " + ", ".join(QUEUES)}
        cust["transfers"].append({"queue": q})
        return 200, {"ok": True}

    if name == "close_call":
        r, c = args.get("result"), args.get("code")
        if r not in RESULTS:
            return 200, {"ok": False, "error": "unknown result", "hint": "one of " + ", ".join(RESULTS)}
        if c in ("", None):
            c = None
        if r != "arranged" and c is None:
            return 200, {"ok": False, "error": "code is required for this result"}
        if c is not None and c not in CODES:
            return 200, {"ok": False, "error": "unknown code"}
        cust["outcome"], cust["reason"] = r, c
        return 200, {"ok": True}
    return 404, {"ok": False, "error": "not found"}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        print(time.strftime("%H:%M:%S"), self.command, self.path, fmt % a if a else "", flush=True)

    def send(self, status, obj):
        b = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def team(self):
        k = self.headers.get("x-team-key") or ""
        return hashlib.sha1(k.encode()).hexdigest()[:24] if len(k) >= 16 else None

    def body(self):
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            return None

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/")
        if p in ("", "/", "/v1", "/health"):
            return self.send(200, {"ok": True, "service": "freya-bank-gulf-mock (brief C)", "cases": len(CASES)})
        m = re.fullmatch(r"/v1/practice/ledger/([\w\-]+)", p)
        if m:
            t = self.team()
            if not t:
                return self.send(401, {"ok": False, "error": "send X-Team-Key: a secret of 16 or more characters that your team chose"})
            with LOCK:
                c = STATE["customers"].get(m.group(1))
                if not c or c["team"] != t:
                    return self.send(404, {"ok": False, "error": "unknown customer_id"})
                return self.send(200, dict({"ok": True}, **{k: v for k, v in c.items()}))
        if p == "/openapi.json":
            return self.send(200, json.load(open(os.path.join(HERE, "openapi-c.json"))))
        self.send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0].rstrip("/")
        b = self.body()
        if b is None or not isinstance(b, dict):
            return self.send(400, {"ok": False, "error": "body must be a JSON object"})
        if p == "/v1/practice/sessions":
            t = self.team()
            if not t:
                return self.send(401, {"ok": False, "error": "send X-Team-Key: a secret of 16 or more characters that your team chose"})
            case = CASES.get(b.get("case"))
            if not case:
                return self.send(404, {"ok": False, "error": "unknown practice case"})
            cid = "k_" + uuid.uuid4().hex[:12]
            v = case["variables"]
            with LOCK:
                STATE["customers"][cid] = {"case": case["id"], "team": t, "call_time": v["call_time"], "verified": {}, "wrong": 0,
                                           "hinted": False, "promises": [], "notes": [], "callbacks": [], "transfers": [],
                                           "outcome": None, "reason": None, "failures": {k: 0 for k in TOOLS}, "calls": [],
                                           "created_at": int(time.time())}
                save()
            return self.send(200, {"ok": True, "variables": {"customer_id": cid, "first_name": v["first_name"], "last_name": v["last_name"],
                                                             "call_time": v["call_time"]}})
        m = re.fullmatch(r"/v1/(\w+)", p)
        if not m or m.group(1) not in TOOLS:
            return self.send(404, {"ok": False, "error": "not found"})
        name = m.group(1)
        with LOCK:
            cust = STATE["customers"].get(str(b.get("customer_id")))
            if not cust:
                return self.send(200, {"ok": False, "error": "unknown customer_id"})
            status, res = tool(name, cust, b)
            cust["calls"].append({"n": len(cust["calls"]) + 1, "tool": name, "args": {k: v for k, v in b.items() if k != "customer_id"},
                                  "status": status, "result": res})
            cust["last_at"] = int(time.time() * 1000)
            save()
        self.send(status, res)


def main():
    global STATE_FILE, STATE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--cases", default=os.path.join(HERE, "cases-c.json"))
    ap.add_argument("--state", default=os.path.join(HERE, ".state.json"))
    a = ap.parse_args()
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    for c in json.load(open(a.cases)):
        c["identity"]["birth_month_mm"] = f"{months.index(c['identity']['birth_month'].lower()) + 1:02d}"
        CASES[c["id"]] = c
    STATE_FILE = a.state
    if os.path.exists(a.state):
        try:
            STATE = json.load(open(a.state))
        except ValueError:
            pass
    print(f"brief C mock bank on :{a.port}, {len(CASES)} cases, {len(STATE['customers'])} customers in state", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
