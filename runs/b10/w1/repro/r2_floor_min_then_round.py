from common import *
spec = dict(BASE, type_field="", floors=[{"product_types": [], "field": "", "percent_of_field": "balance", "percent": 1,
       "fixed": None, "min_amount": 25, "round": "down", "round_to": 10}])
g = lib(spec)
got = g["floor_for"]({"balance": 1000})   # 1% = 10 -> min 25 -> rounded down to 10s = 20 < min_amount
print("floor:", got); assert got >= 25, f"floor {got} below min_amount 25"
