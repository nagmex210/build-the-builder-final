"""Run the OFFICIAL scorer in our second Freya workspace, in parallel with one in the first.

One simulation runs at a time per workspace, so the merger runs brief A in workspace 1 and brief B here at the
same time:

    python3 tools/run_cases.py <agent_id> --brief A --reps 2 &
    python3 btb/official_ws2.py <slot> --brief B --reps 2 &
    wait

Copies the slot's published workflow from workspace 1 into workspace 2 (same slot name, own state file), then runs
tools/run_cases.py there. Workspace 2 has its own personas, so it runs from its own copy of the kit files
(BTB_WS2_DIR, default ../ws2 next to the repo). Key: FREYA_API_KEY_2 or Parameter Store /btb/freya_api_key_2.
"""
import argparse, json, os, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402  (workspace 1, from FREYA_API_KEY)


def key2():
    k = os.environ.get("FREYA_API_KEY_2")
    if not k:
        k = subprocess.run(["aws", "ssm", "get-parameter", "--region", "eu-central-1", "--name", "/btb/freya_api_key_2",
                            "--with-decryption", "--query", "Parameter.Value", "--output", "text"],
                           capture_output=True, text=True, check=True).stdout.strip()
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slot"); ap.add_argument("--brief"); ap.add_argument("--reps", default="1"); ap.add_argument("--only")
    ap.add_argument("--out"); ap.add_argument("--cases")
    a = ap.parse_args()
    state = json.loads((ROOT / ".freya-agents.json").read_text())
    wf = freya.api("GET", f"/api/v2/workflow/{state[a.slot]['workflow_id']}", workspaceId=freya.workspace_id())["workflow"]["workflow"]

    ws2 = pathlib.Path(os.environ.get("BTB_WS2_DIR", ROOT.parent / "ws2"))
    (ws2 / "tools").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "tools").glob("*"):
        if f.is_file():
            shutil.copy2(f, ws2 / "tools" / f.name)
    for f in ("freya.py", "public-test-set.json"):
        shutil.copy2(ROOT / f, ws2 / f)
    (ws2 / "wf.json").write_text(json.dumps(wf))

    env = {**os.environ, "FREYA_API_KEY": key2()}
    env.pop("FREYA_WORKSPACE_ID", None)
    saved = subprocess.run([sys.executable, "-c", "import json,freya;print(json.dumps(freya.save_workflow("
                            f"{a.slot!r}, json.load(open('wf.json')))))"], cwd=ws2, env=env, capture_output=True, text=True)
    if saved.returncode:
        sys.exit("copy to workspace 2 failed: " + saved.stderr[-800:])
    agent = json.loads(saved.stdout.strip().splitlines()[-1])["agent_id"]
    print(f"workspace 2: {a.slot} -> agent {agent}", flush=True)
    cmd = [sys.executable, "tools/run_cases.py", agent, "--reps", str(a.reps)]
    for k in ("brief", "only", "cases"):
        if getattr(a, k):
            cmd += [f"--{k}", str(pathlib.Path(getattr(a, k)).resolve()) if k == "cases" else getattr(a, k)]
    if a.out:
        cmd += ["--out", str(pathlib.Path(a.out).resolve())]
    sys.exit(subprocess.run(cmd, cwd=ws2, env=env).returncode)


if __name__ == "__main__":
    main()
