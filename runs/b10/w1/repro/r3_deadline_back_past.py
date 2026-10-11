from common import *
b = {"name": "x", "deadline_count": 1, "deadline_unit": "calendar_days", "deadline_counts_today": False, "if_not_business_day": "back"}
g = lib(dict(BASE, bands=[b]))
t = datetime.date(2026, 10, 10)  # Saturday
dl = g["deadline_of"](b, t)
print("today", t, "deadline", dl); assert dl >= t, f"deadline {dl} is before today {t}"
