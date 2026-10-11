# Final builder fix (general, no case content in builder/)

## FIX A: no document can be skipped
- `builder/casefolder.py`: `extract_rules()`: one strong-tier Azure call per text document of the case folder (parallel,
  ThreadPoolExecutor), each listing every rule (stage, condition, must do/say, verbatim sentences in the document's
  language, number/digit/date/amount reading, failure handling, tool usage, closing) with the document's date (file
  name or header, `_doc_date`); then one merge call: one digest, newer document wins, conflicts noted, every rule as
  `- R<n> ... (source: file, date)`. Written to `runs/case/<slot>/rules.md` (+ the per-document lists) and
  `runs/case/<slot>/documents.json` (every document path). case.md's header names rules.md as the primary spec.
  `BTB_NO_RULES=1` switches it off.
- `builder/build.py`: the build prompt lists every document ("read every document before you write anything") and says
  rules.md is the primary spec: implement every rule, read the documents for detail, check rule by rule before the final save.
- `builder/buildcheck.py`: `rules_coverage(wf, rules_md)`: each R-rule must share >= 50 % of its content words (or its
  verbatim sentence) with some text of the workflow; `build_check` logs `rules coverage: k/n` and every missing rule as
  warnings in the trace (warnings only, no repair round).

## FIX B: identifiers must come from an earlier tool response
- `builder/harden.py` `IDPOST` (every api_call tool, after the other post hooks): stores every scalar of each response
  per normalised field name in `vars['seen_vals']`.
- `IDPRE` (every api_call tool, after harden's template/known-ids repair, before the builder's own hooks): on the first
  call snapshots the call-start variables (test_variables / caller variables) as seen values (`seen_start`). For every
  body field (nested bodies too) named like an identifier (last name token id/no/nr/num/number/ref/code/iban/pan) or a
  short code-like value (digits, no spaces, not a date/amount/name/email/... field) of a field a response returned:
  value must equal a seen value for that field (or a call-start value). Else: case-insensitive match, then unique
  longest trailing-digit match (>= 3 digits), then unique substring match -> replaced. Otherwise NOT SENT: the request
  goes to the host's no-op path (or a .invalid URL), and the post-hook replaces the result with `ok:false, not_sent:true,
  tool_outcome: "NOT SENT ... use exactly one of: <values>"`; failure counter untouched, no ALREADY-RECORDED entry.
  A field no earlier tool returned is never checked (first call passes).

## Tests
- Unit test (/tmp/idtest.py, simulated vars): first call not blocked; exact value passes; last-4 -> full value; invented
  number with right trailing digits -> repaired; ambiguous trailing digits (two items) -> NOT SENT with the value list;
  junk -> NOT SENT; caller variable accepted; unresolved placeholder and free fields ignored; harden idempotent. ALL OK.
- harden on the last real workflow: 7 tools hardened, every hook compiles. `python3 -m py_compile builder/*.py` ok.
- rules_coverage on a toy workflow: finds the one uncovered rule of three.
