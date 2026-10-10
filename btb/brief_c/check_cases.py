"""Sanity-check cases-c.json against brief C's date/amount rules (deadline, business day, cutoff, floor, plan, call limit).

    python3 btb/brief_c/check_cases.py        # prints each case's deadlines and any violation
"""
import datetime as dt, json, math, os, sys

HOL = {dt.date(2026, 11, 3), dt.date(2026, 11, 26), dt.date(2026, 12, 2), dt.date(2026, 12, 24), dt.date(2026, 12, 31)}
DAYS = {"credit_card": 10, "personal_loan": 14, "overdraft": 5}
LIMIT = 2000.0


def bday(d):
    return d.weekday() in (6, 0, 1, 2, 3) and d not in HOL     # Sun..Thu


def deadline(today, p):
    n = DAYS[p["kind"]] if p["arrears"] < 1000 else min(DAYS[p["kind"]], 7)
    d = today + dt.timedelta(n)
    while not bday(d):
        d -= dt.timedelta(1)
    return d


def floor(p):
    return {"credit_card": p.get("min_due"), "personal_loan": p.get("instalment")}.get(p["kind"]) or math.ceil(p["arrears"] / 2)


def check(c):
    bad = []
    now = dt.datetime.fromisoformat(c["variables"]["call_time"]); today = now.date()
    prods = {f"A{i}": p for i, p in enumerate(c["products"], 1)}
    info = {r: (str(deadline(today, p)), floor(p)) for r, p in prods.items()}
    total = 0.0
    for pr in c["expected"]["promises"]:
        p, d = prods[pr["product_id"]], dt.date.fromisoformat(pr["date"])
        dl = deadline(today, p); total += pr["amount"]
        if not bday(d): bad.append(f"{pr} not a business day")
        if d < today or (d == today and now.hour >= 15): bad.append(f"{pr} before the earliest date")
        n = pr.get("instalment_no", 0)
        if n in (0, 1) and d > dl: bad.append(f"{pr} after deadline {dl}")
        if n == 0 and not (floor(p) <= pr["amount"] <= p["arrears"]): bad.append(f"{pr} amount outside floor..arrears")
        if n:
            cents = round(p["arrears"] * 100); half = (cents + 1) // 2 if n == 1 else cents // 2
            if round(pr["amount"] * 100) != half: bad.append(f"{pr} not the right half")
            if n == 2:
                p1 = [x for x in c["expected"]["promises"] if x["product_id"] == pr["product_id"] and x.get("instalment_no") == 1][0]
                if (d - dt.date.fromisoformat(p1["date"])).days < 7 or (d - today).days > 30: bad.append(f"{pr} part 2 date window")
            if p["arrears"] < 300: bad.append("plan below 300")
    if total > LIMIT + 1e-9: bad.append(f"total {total} over the call limit")
    for cb in c["expected"]["callbacks"]:
        d = dt.date.fromisoformat(cb["date"]); t = dt.datetime.combine(d, dt.time.fromisoformat(cb["time"]))
        nxt = [x for x in (today + dt.timedelta(i) for i in range(1, 10)) if bday(x)][:2]
        if not ((d == today and bday(d)) or d in nxt): bad.append(f"callback {cb} not today / next two business days {nxt}")
        if not ("09:00" <= cb["time"] <= "17:30") or cb["time"][3:] not in ("00", "30") or t < now + dt.timedelta(hours=1): bad.append(f"callback {cb} time")
    return info, bad


if __name__ == "__main__":
    cases = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "cases-c.json")))
    nbad = 0
    for c in cases:
        info, bad = check(c); nbad += bool(bad)
        print(c["id"], c["variables"]["call_time"], dt.date.fromisoformat(c["variables"]["call_time"][:10]).strftime("%a"),
              {r: f"deadline {d} floor {f}" for r, (d, f) in info.items()}, c["expected"]["outcome"], c["expected"]["reason"])
        for b in bad: print("   BAD", b)
    print("violations in", nbad, "case(s)")
