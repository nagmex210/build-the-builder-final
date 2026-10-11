"""clear_slot(slot) moves every out/ and scratch/ file whose name contains the slot between non-alphanumerics. '-' counts
as a boundary, so a build of slot 'brief-a' moves away the files of a parallel/other build 'brief-a-raw'
(its workflow.json, calc.json, canned.json...), and a slot 'a' (brief file a.md) moves 'w1-a.calc.json'. The
submission form names the slot after the brief file, so prefix-related hidden brief names hit this."""
import os, pathlib, sys, tempfile
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
sys.path.insert(0, KIT + '/builder'); sys.path.insert(0, KIT + '/btb'); sys.path.insert(0, KIT)
import build
d = pathlib.Path(tempfile.mkdtemp()); (d / "out").mkdir(); build.KIT = d
own = ["brief-a.workflow.json", "brief-a.calc.json", "brief-a.gen.py", "gen_brief-a.py", "gen_brief_a", "briefa.workflow.prev.json"]
other = ["brief-a-raw.workflow.json", "brief-a-raw.calc.json", "brief-a2.workflow.json", "w1-a.calc.json", "x-brief-a.workflow.json"]
for f in own + other:
    (d / "out" / f).write_text("{}")
moved, _ = build.clear_slot("brief-a")
moved2, _ = build.clear_slot("a")
print("slot brief-a moved:", sorted(moved)); print("slot a moved:", sorted(moved2))
assert set(own) <= set(moved), "own stale files must still be moved"
assert not set(other) & set(moved + moved2), f"moved another slot's files: {sorted(set(other) & set(moved + moved2))}"
