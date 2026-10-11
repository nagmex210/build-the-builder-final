"""Deterministic quality of each build's workflow (b10 w4 stability): python3 runs/b10/w4_quality.py <round letter>"""
import json, pathlib, re, sys, glob
KIT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(KIT), str(KIT / "builder")]
from lint_workflow import lint
import hookcheck, apicheck, buildcheck, situations
R = sys.argv[1]
TOOLS = {"C": "btb/brief_c/openapi-c.json"}
for log in sorted(glob.glob(f"runs/b10/w4-*-{R}[123].build.log")):
    slot = pathlib.Path(log).name.replace(".build.log", "")
    b = slot.split("-")[1]
    txt = open(log).read()
    status = "FAILED" if ("BUILD FAILED" in txt or "finished without saving" in txt) else ("ok" if "BUILD END" in txt else "running")
    if "WARNING: the final save failed" in txt: status = "ok(agent save)"
    m = re.search(r"BUILD END \S+ \((\d+) s\)", txt); secs = m.group(1) if m else "-"
    wf_f = KIT / "out" / f"{slot}.workflow.json"
    api = json.loads((KIT / TOOLS.get(b, "tools/openapi.json")).read_text())
    if not wf_f.exists():
        print(f"{slot:10} {status:14} {secs:>5}s  NO WORKFLOW FILE"); continue
    wf = json.loads(wf_f.read_text())
    le, lw = lint(wf)
    he = hookcheck.errors(wf); ae = apicheck.missing(wf, api); be, bw = buildcheck.problems(wf, api)
    code = json.dumps(wf)
    guard = "BTB_GUARD_V1" in code
    sit_f = KIT / "out" / f"{slot}.situations.json"
    sp = situations.check(wf, json.loads(sit_f.read_text())) if sit_f.exists() else ["no situations"]
    budget = "BUDGET" if "time budget reached" in txt else ""
    fb = len(re.findall(r"\(Azure, btb/llm.py\)", txt)), len(re.findall(r"gpt-4.1-mini \(Azure", txt)), txt.count("[model fallback")
    st = re.search(r"self-test 1 \(([^)]*)\): (\S+)", txt)
    print(f"{slot:10} {status:14} {secs:>5}s {budget:6} lint {len(le)}e hook {len(he)}e api {len(ae)}e buildcheck {len(be)}e "
          f"guard {'Y' if guard else 'N'} sit-problems {len(sp) if isinstance(sp, list) else sp} azure {fb[0]} mini {fb[1]} fallbacks {fb[2]} "
          f"selftest {st.group(1) + ' ' + st.group(2) if st else '-'} | {'; '.join((le + he + ae + be))[:200]}")
