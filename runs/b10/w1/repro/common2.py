import sys, json
import os, pathlib
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
for p in [KIT, KIT + '/builder', KIT + '/btb', KIT + '/tools']:
    sys.path.insert(0, p)
import selftest, canned, situations
def ok(tool, args=None, **res):
    return {"tool": tool, "args": args or {}, "result": {"ok": True, **res}}
