# Final-format adapter (2026-10-11)

New form: `python3 builder/build.py {case_folder} {mock_url}` (and `bash btb/submit.sh <case_folder> <mock_url> [name]`,
name default `final` -> traces/<name>.log, submission/<name>.workflow.json). Old forms unchanged
(`build.py brief.md tools.json`, `--slot/--tools`; checked with parse_args).

## What changed (generic, no case content)
- `builder/casefolder.py` (new): walks the folder; brief = BRIEF.md else the largest .md; writes
  `runs/case/<slot>/case.md` = brief, README, then every other text file, each under `===== FILE: <name> =====`
  (binaries skipped, images listed with their path so the Claude build agent can Read the flow drawing).
  The contract: the OpenAPI JSON/YAML with the most paths (YAML via PyYAML/ruamel if installed); else a
  markdown/text contract (name/`GET /x`/endpoint scoring) is converted to OpenAPI JSON by Azure (btb/llm.py).
  Written to `runs/case/<slot>/tools.json` with `servers[0].url` = mock URL (original kept in
  `info.x-original-server`). If the mock URL has no path and the contract server has one (`/v1`), both are probed
  and the non-404 base wins (brief C mock: `/v1` needed, detected). Raw contract is not pasted into case.md.
  (runs/case/, not out/: clear_slot moves out/<slot>.* away at build start.)
- Language: stopword/character detection over brief + example conversations (Turkish, English, German, Spanish,
  French, Dutch, Italian, Portuguese) -> `BTB_LANGUAGE`; a LANGUAGE instruction goes into case.md, the build-agent
  prompt, the canned extraction prompt (texts in that language, quotes verbatim), robust.py (system prompt line:
  the English examples in "How customers talk" are illustrations, speak <lang>), the self-test personas, and the
  default spoken goodbye (canned.default_goodbye, per-language table; was hard-coded English).
  Other hook/guard texts checked: they are internal instructions to the model, not spoken lines.
- Mock URL: `save.pin_mock_url` (start and end of finish_and_save) rewrites every api_call url not on the mock to
  mock base + operation path; final pass adds a lint ERROR for any api_call url not starting with the given mock
  URL and prints `[test] mock url: n/n`. The build agent prompt also states the URL.
- Self-test uses the built workflow's tools -> the mock.

## Tests
- Fake folder /tmp/FreyaBank-Test (BRIEF.md = brief-c.md since the running mock is brief C's, tools/openapi.json =
  openapi-c.json with servers set to a fake host, README.md, a fake flow.png): case.md/tools.json correct,
  servers -> `<BANK_URL>/v1` (probed). Turkish sample sentence -> Turkish.
- pin_mock_url on an existing 23-tool workflow (fx2-A): 23/23 urls rewritten to the mock, lint 0 errors.
- End-to-end `bash btb/submit.sh /tmp/FreyaBank-Test <BANK_URL> final-adapter-test` (nohup, started 16:55Z, log
  /tmp/fa_submit.out + traces/final-adapter-test.log): the build agent built from case.md, final save (build) and
  (fix) round: **lint 0 errors, 0 warnings**, `[test] mock url: 24/24 api_call urls start with <BANK_URL>/v1`
  (guard no-op check tool included). Workflow e63c3f20-..., 14 steps, 8 tools.
  `freya.export_workflow` of it run by hand at 17:05Z: exports OK, 14 nodes, 24/24 urls on the mock.
  The submit run was still in its self-test at the 25-min task limit; its own SUMMARY block was not seen here.
