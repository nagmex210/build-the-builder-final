"""build.self_simulate starts self-test round 1 with ROUND_S (420 s) no matter how much of the 30-min build is left
(the later rounds check left(), round 1 does not). With 150 s left (e.g. after a slow build agent + a rebuild or a
buildcheck repair round), the build runs ~420 s past its own BUILD_TOTAL_S, i.e. past 30 min."""
import asyncio, json, os, pathlib, sys, tempfile, time, types
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
sys.path.insert(0, KIT + '/builder'); sys.path.insert(0, KIT + '/btb'); sys.path.insert(0, KIT)
import build
calls = []
fake = types.ModuleType("selftest")
fake.write_personas = lambda text, tools, cases, n: [{"title": "p", "customer": "c", "script": "s", "checks": []}]
def run_tests(slot, wf, personas, calc_file, timeout=420, **k):
    calls.append(timeout)
    return {"where": "test", "n": 1, "n_failed": 0, "n_checks_failed": 0, "rows": []}
fake.run_tests = run_tests
sys.modules["selftest"] = fake
d = pathlib.Path(tempfile.mkdtemp()); (d / "out").mkdir()
build.KIT = d
wf = d / "out" / "x.workflow.json"; wf.write_text("{}")
brief = d / "b.md"; brief.write_text("brief")
left = 150
build.BUILD_T0 = time.time() - (build.BUILD_TOTAL_S - left)
asyncio.run(build.self_simulate("x", "tools.json", [str(brief)], d / "trace.jsonl", wf, lambda tag: True, None))
print("round-1 timeouts given to run_tests:", calls, "with", left, "s of the build budget left")
assert all(t <= left for t in calls), f"self-test round 1 may run {max(calls)} s with only {left} s of the 30-min budget left"
