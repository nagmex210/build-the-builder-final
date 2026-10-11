from common import *
g = lib(dict(BASE, promise_cutoff_time="9:30"))
e = g["earliest_promise"]("2026-10-12T15:00")   # Monday 15:00, cutoff 9:30 passed
print("earliest", e); assert e > datetime.date(2026, 10, 12), "cutoff 9:30 not applied at 15:00 (string compare '15:00' >= '9:30' is False)"
