"""Apply save.py's final pass (harden, guards, robust, canned, identity gate, situations) WITHOUT saving to Freya."""
import json, sys, pathlib
KIT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
import save
class _F:
    @staticmethod
    def save_workflow(slot, wf, state_file=None): return {"offline": True}
save.freya = _F
slot, src, dst = sys.argv[1:4]
wf = json.load(open(src))
names, _ = save.finish_and_save(slot, wf)
json.dump(wf, open(dst, "w"), indent=1)
print(len(names), "steps")
