from common import *
spec = dict(BASE, type_field="", floors=[{"product_types": [], "field": "", "percent_of_field": "balance", "percent": 10,
       "fixed": None, "min_amount": None, "round": "up", "round_to": 1}])
g = lib(spec)
got = g["floor_for"]({"balance": 100.01})   # 10% = 10.001 -> rounded UP to whole unit must be 11
print("floor:", got); assert got == 11, f"expected 11, got {got}"
