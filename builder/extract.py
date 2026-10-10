"""Brief extraction: turn any brief (a clean spec, or raw bank material: mail + policy extract + memo + code list)
into one structured rule spec before the phone agent is built.

    python3 builder/extract.py --tools <openapi.json> --out out/<slot>.spec.md <brief.md>...

Pass 1 (strong model) writes the spec in a fixed outline. Pass 2 (strong model) re-reads the sources against the
spec and returns a corrected spec: missed rules, overrides not applied, values copied wrong. Nothing in here
knows any particular brief; the outline only names the kinds of things every collections brief has.
"""
import argparse, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "btb"))
from llm import chat  # noqa: E402

OUTLINE = """# Rule spec

## 0. Sources and precedence
List every source document (mail, policy, memo, code sheet, spec, later brief...). State which overrides which
(later memo/amendment over older policy; a brief that "builds on" another adds to or replaces its rules).
List EVERY override as: `rule <id>: OLD -> NEW (source)`. From here on write only the EFFECTIVE (final) values.

## 1. Call variables
The variables each call starts with (exact names), how to address the customer, and what `now` is used for.

## 2. Tools (from the tool API file)
For each of the seven tools: when it is called, every request field with type/format and the EXACT allowed values
(enums), required fields, what the response contains (fields the agent must read), and error/hint values with
what the agent must do on each. Note fields whose allowed values differ from what a reader might assume.

## 3. Opening and who answered
Exact required opening content; words forbidden before identity is verified; how confirmation of the person is
recognised (what counts / what does not count); how many asks; third party / wrong number / deceased / callback
handling with every limit (time windows, days, number of retries) and the exact outcome+reason for each branch.

## 4. Identity verification
Questions in order, exact formats sent to the tool, how to normalise spoken answers (dates, digits in parts,
words), how many wrong answers end the check and how they are counted, hints and retries that do not count,
what to say and which outcome+reason after failure.

## 5. After verification: debt disclosure and products
What to state (fields from which tool), multi-product rules (order, which product first, per-product promises),
anything that must not be said.

## 6. Payment promises
Every numeric limit (minimum amounts, percentages, full vs partial, instalments, max number of promises),
every date limit (latest date as N days / business days from `now` or from a due date, inclusive or exclusive,
weekends, bank holidays), what to do when the customer's proposal is outside a limit (how many counter-offers,
then which outcome). How to call the promise tool (fields, formats) and what to say only after it succeeds.
Give each date/amount rule as a precise formula so code could compute it, e.g. `latest_date = add_business_days(now, 5)`.

## 7. Calendar
Business-day definition, every holiday date listed (copy all of them exactly), timezone/clock rules.

## 8. Special situations
Hardship, dispute, already paid, refusal, request for a human, complaint, vulnerability, robot question,
callback requests by the customer, language, abuse... For each: trigger, what the agent says/does, which tool
calls (notes, transfers, callbacks with their exact field values), and the outcome+reason.

## 9. Closing and outcome table
The complete table of EXACT outcome codes and reason codes allowed, and for each one: when it applies.
Rules on close_call (exactly once, last tool call, what follows a transfer, etc.). Rules on notes.

## 10. Honesty and general conduct
Every rule about what must never be said, confirmed or invented; tool failures; one question at a time; etc.

## 11. Numbered rule checklist
EVERY rule from the sources, one line each, in effective (post-override) form, with its source clause id:
`R<n> [source clause]: <rule>`. Do not merge or drop small rules: the small rules are where calls fail.

## 12. Ambiguities
Anything unclear or contradictory, with the interpretation you chose and why.
"""

EXTRACT = """You are preparing the build of a phone agent for a bank's debt-collection calls. Below are the bank's
source documents (they may be a clean specification, or raw material: an email, an older policy extract, a memo
that amends it, a code list / field-value sheet) and the bank's tool API file (OpenAPI).

Write ONE complete, precise rule spec in Markdown that follows this outline exactly. Rules:
- Copy every value EXACTLY: numbers, codes, field names, enum values, dates, quoted phrases.
- Apply every amendment/override: the spec states only the effective rule, and section 0 lists what changed.
- Where a code sheet maps codes to meanings, use the exact code strings in every section.
- Where the tool API file and the documents disagree about field names or allowed values, the tool API file
  decides the field names/values; note the disagreement in section 12.
- Be complete rather than short. Nothing outside the sources may be added.

OUTLINE:
{outline}

SOURCE DOCUMENTS:
{briefs}

TOOL API FILE:
{tools}
"""

VERIFY = """Below are a bank's source documents, its tool API file, and a rule spec someone extracted from them.
Check the spec against the sources, line by line:
1. Every rule, limit, number, code, quoted phrase and holiday in the sources is in the spec, correct and exact.
2. Every amendment/memo/override was applied (the spec must show the NEW value everywhere, never the old one).
3. Every outcome/reason code is exactly as the code sheet / tool API file spells it, and each is mapped correctly.
4. Tool field names, formats and enum values match the tool API file.
5. Nothing was invented.
Then output the FULL corrected spec (same outline), and after it a section `## 13. Verifier corrections` listing
what you changed (or "none"). Output only the Markdown spec.

SOURCE DOCUMENTS:
{briefs}

TOOL API FILE:
{tools}

SPEC TO CHECK:
{spec}
"""


def extract(briefs, tools, out):
    src = "\n\n".join(f"===== FILE {p} =====\n{pathlib.Path(p).read_text()}" for p in briefs)
    api = pathlib.Path(tools).read_text()
    t0 = time.time()
    spec = chat([{"role": "user", "content": EXTRACT.format(outline=OUTLINE, briefs=src, tools=api)}], tier="strong",
                purpose="extract a structured rule spec from the brief(s) + tool API", max_tokens=16000, effort="medium",
                timeout=600)
    pathlib.Path(out).write_text(spec)
    try:
        checked = chat([{"role": "user", "content": VERIFY.format(briefs=src, tools=api, spec=spec)}], tier="strong",
                       purpose="verify the rule spec against the sources (missed rules, unapplied overrides, wrong codes)",
                       max_tokens=16000, effort="medium", timeout=600)
        if len(checked) > 0.6 * len(spec):           # a truncated / lazy rewrite must not replace the full spec
            spec = checked
    except RuntimeError as e:
        print(f"spec verify failed, keeping pass-1 spec: {e}", file=sys.stderr)
    pathlib.Path(out).write_text(spec)
    print(f"spec: {out} ({len(spec)} chars, {time.time() - t0:.0f} s)", flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", default="tools/openapi.json"); ap.add_argument("--out", required=True)
    ap.add_argument("briefs", nargs="+")
    a = ap.parse_args()
    extract(a.briefs, a.tools, a.out)
