# Submission rehearsal (Sat 10 Oct, b4 w5)

Exactly as on Sunday: `bash btb/submit.sh <brief> <tool_api.json> <name>` on two briefs in parallel, no manual
step. Builder commit `bd1d84f` (branch harness/submit = main 7aa964a + the submission harness).

```bash
cd /home/ubuntu/btb/wt5 && bash btb/submit.sh btb/brief_c/brief-c.md btb/brief_c/openapi-c.json rehearsal-c &
cd /tmp && bash /home/ubuntu/btb/wt5/btb/submit.sh ../home/ubuntu/btb/wt5/btb/briefs_raw/brief-a-raw.md \
    ../home/ubuntu/btb/wt5/tools/openapi.json rehearsal-rA &          # other cwd, relative paths
```

The shell had no `CLAUDE_CODE_OAUTH_TOKEN`: submit.sh fetched it from Parameter Store (that path is tested too).

## Results

| | brief C (clean spec, held-out) | raw brief A (from /tmp) |
|---|---|---|
| start / end (UTC) | 21:19:32 / 21:22:35 | 21:19:32 / 21:22:37 |
| build seconds (submit.sh, incl. export) | 185 (under 30 min: yes) | 186 (under 30 min: yes) |
| datecalc self-test | ok (25 s) | ok (7 s) |
| model calls printed | 1 Azure (gpt-6-astra) + 18 SDK turns (claude-opus-5-5) | 1 Azure + 21 SDK turns |
| lint of the saved workflow | 0 errors, 0 warnings | 0 errors, 0 warnings |
| workflow_id | 22e77552-5386-412e-8fad-fb7c79964797 | 7f08e817-2364-4323-80c6-ebde9452f6b9 |
| agent_id | a2414d3e-1ea2-4dae-91f1-1d870d350db4 | 750a6088-56d9-4ee7-a0ad-41d7b59f5c32 |
| export (json loads, nodes) | `submission/rehearsal-c.workflow.json` (6 nodes, 130 KB) | `submission/rehearsal-rA.workflow.json` (7 nodes, 148 KB) |
| printed trace | `traces/rehearsal-c.log` (14 KB) | `traces/rehearsal-rA.log` (17 KB) |
| jsonl trace | `runs/traces/rehearsal-c-20261010-211932.jsonl` | `runs/traces/rehearsal-rA-20261010-211932.jsonl` |
| keys in log/jsonl/export | none (env values and fak_/sk-/JWT patterns: 0) | none |
| exit code | 0 | 0 |

Both slots landed in `.freya-agents.json` (no lost update) and the two runs used distinct out/, calc, trace,
log and export files. Paths are in /home/ubuntu/btb/wt5 (not committed: `traces/` and `submission/` are
gitignored; brief C material stays out of git).

## Problems found and fixed

1. **Parallel builds could lose a slot**: `freya.save_workflow` does read-modify-write on the shared
   `.freya-agents.json`; two builds saving at the same moment overwrite each other's entry and the loser exits
   "finished without saving a workflow" (and the next run creates a new workflow). Fixed: `builder/save.py` holds an
   exclusive `flock` on `.freya-agents.json.lock` around the save (covers the build agent's own saves too).
2. **The printed log was not a full trace**: no start/end time, Azure calls only in the jsonl, Freya ids only in the
   final JSON line, no test results. Fixed in build.py (additive): `BUILD START/END` (UTC), a thread that tails the
   jsonl and prints every btb/llm.py call (model + purpose) from any process (datecalc, scripts the build agent
   runs), one `[model call]` line per Claude Agent SDK message with the tools used, the first 400 chars of every
   Bash result of the build agent (saves, lint, chat tests), `[test] datecalc ...`, `[freya] slot ... workflow_id
   ... agent_id ... version`, `[freya] exported: ...`.
3. **No export, no scrubbing**: added (`submission/<slot>.workflow.json`; `btb/scrub.py`; stdout/stderr wrapped).
   Scratch test: printing FREYA_API_KEY, AZURE_KEY, FREYA_BANK_TEAM_KEY, CLAUDE_CODE_OAUTH_TOKEN, a JWT and an
   sk-ant key through the wrapped streams gave only `[REDACTED]` (0 key occurrences in the output file);
   `btb/scrub.py` on a file with two keys replaced 2.
4. The export is checked for keys but never rewritten by the scrubber (a scrubbed workflow would not be what
   Freya holds and scores). The bank team key is not in the workflows (checked).
5. Not fixed, for the record: the Claude tool's Bash timeout is 10 min, so on Sunday run submit.sh in tmux/nohup,
   not in an agent's foreground shell. The Azure call line can appear a second after the `[test] datecalc` line
   (tail thread polls every 1 s; each line has its own timestamp).
6. Observation (builder behaviour, not changed): in both runs the build agent finished in ~3 min of its 21 and did
   not run the one-turn chat start check from the skill; the final save + lint passed.

## Filled sample of the submission (per brief)

| Field | Brief "rehearsal-rA" (raw A) |
|---|---|
| Phone agent file | `submission/rehearsal-rA.workflow.json` (workflow_id 7f08e817-..., agent_id 750a6088-...) |
| Code | repo at commit `bd1d84fb00df8d9b9de7d2096e9826b326e78ea6` (on Sunday: the frozen main, see FINAL.md open question) |
| Trace | `traces/rehearsal-rA.log` (plain text; detailed `runs/traces/rehearsal-rA-20261010-211932.jsonl`) |
| Run command | `bash btb/submit.sh <brief.md> <tool_api.json> <name>` = `python3 builder/build.py --slot <name> <brief.md> <tool_api.json>` + export + scrub |
| Build time | 186 s |
