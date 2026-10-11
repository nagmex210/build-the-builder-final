import os, pathlib
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
import sys, datetime
sys.path.insert(0, KIT + '/builder'); sys.path.insert(0, KIT + '/btb')
import datecalc
def lib(spec):
    g = {"vars": {}}
    exec(datecalc.snippet(spec, ""), g)
    return g
BASE = {"now_variable": "now", "weekend_days": [5, 6], "holidays": [], "bands": [], "floors": []}
