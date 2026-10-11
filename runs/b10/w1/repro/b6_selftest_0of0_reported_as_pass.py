"""When no self-test chat completes (workspace 2: 402 Insufficient credits on every chat, 28 b8 builds), the build printed
'self-test 1 (workspace 2): 0/0 personas failed a check' and logged ship 'no fix round' why='no failed check': the
submitted trace reads as a passed self-test. Wrong branch: n_failed is tested before n. Repro: fake run_tests with
every chat a harness error."""
import asyncio, contextlib, io, json, os, pathlib, sys, tempfile, types
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
sys.path.insert(0, KIT + '/builder'); sys.path.insert(0, KIT + '/btb'); sys.path.insert(0, KIT)
import build
fake = types.ModuleType("selftest")
P = [{"title": f"p{i}", "customer": "c", "script": "s", "checks": []} for i in range(6)]
fake.write_personas = lambda *a: P
fake.run_tests = lambda slot, wf, personas, calc, timeout=420, **k: {"where": "workspace 2", "n": 0, "n_failed": 0, "n_checks_failed": 0,
    "rows": [{"title": p["title"], "harness_error": "POST /api/v2/chat/message -> 402: Insufficient credits", "failed": [], "tools": []} for p in P]}
sys.modules["selftest"] = fake
d = pathlib.Path(tempfile.mkdtemp()); (d / "out").mkdir(); build.KIT = d
wf = d / "out" / "x.workflow.json"; wf.write_text("{}"); brief = d / "b.md"; brief.write_text("b")
out = io.StringIO()
with contextlib.redirect_stdout(out):
    asyncio.run(build.self_simulate("x", "t.json", [str(brief)], d / "trace.jsonl", wf, lambda tag: True, None))
ev = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines()]
ship = [e for e in ev if e.get("event") == "ship"]
print(out.getvalue().strip()); print("ship:", ship)
assert "DID NOT RUN" in out.getvalue(), "printed trace reports a self-test that never ran like a result"
assert not any(e.get("why") == "no failed check" for e in ship), "trace says 'no failed check' for 0 completed chats"
