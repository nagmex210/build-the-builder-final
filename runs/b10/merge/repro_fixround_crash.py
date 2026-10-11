"""b10 merge repro: an SDK error inside the self-test fix round must not kill the build (main-A/main-B crashed with
CLIJSONDecodeError, no result line). Stubs: selftest (one failed persona check), claude_stream (raises), final_pass.
Exit 0 = the build survives and the workflow file is the build's own. KIT env = the kit to test (default: this repo)."""
import asyncio, json, os, pathlib, sys, tempfile, types
KIT = pathlib.Path(os.environ.get("KIT") or pathlib.Path(__file__).resolve().parents[3])
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder")); sys.path.insert(0, str(KIT / "btb"))
import build
st = types.ModuleType("selftest")
row = {"title": "p", "customer": "c", "failed": ["close_call missing"], "tools": [], "script": "s", "call_id": "x"}
st.write_personas = lambda *a, **k: [{"title": "p", "customer": "c", "script": "s", "checks": []}]
st.run_tests = lambda *a, **k: {"where": "workspace 1", "workflow_id": "w", "n": 2, "n_failed": 1, "n_checks_failed": 1, "rows": [row, dict(row, failed=[])]}
st.failure_text = lambda r: "- fail"
sys.modules["selftest"] = st
async def boom(*a, **k):
    raise RuntimeError("Failed to decode JSON: JSON message exceeded maximum buffer size of 1048576 bytes")
build.claude_stream = boom
d = pathlib.Path(tempfile.mkdtemp()); wf = d / "wf.json"; wf.write_text('{"nodes": {"a": 1}}'); orig = wf.read_text()
trace = d / "t.jsonl"; trace.write_text("")
build.BUILD_T0 = __import__("time").time()
class O: pass
import dataclasses
@dataclasses.dataclass
class Opt:
    skills: object = None; allowed_tools: object = None; max_turns: int = 0
try:
    asyncio.run(build.self_simulate("repro", "tools/openapi.json", [str(KIT / "briefs" / "brief-a.md")], trace, wf, lambda tag: True, Opt()))
except Exception as e:
    print("CRASH:", e); sys.exit(1)
print("survived; file is the build's own:", wf.read_text() == orig); sys.exit(0 if wf.read_text() == orig else 1)
