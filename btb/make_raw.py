"""Rewrite a clean brief as raw bank material with the SAME effective rules (held-out generalisation brief)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from llm import chat
P = """Rewrite the bank specification below as RAW BANK MATERIAL, the way a bank really hands it over. Use these parts, in this order:
1. An internal email from an operations manager to the vendor, informal, that introduces the project and states some of the rules in prose.
2. A "Policy extract" pasted from an older policy document (numbered clauses, legalistic wording) that holds most of the rules. In it, give TWO of the numeric limits or deadlines an OLD value.
3. A later "Memo" (dated, signed) that changes exactly those two values to the values in the specification below, and says the memo overrides the policy extract.
4. A code list / table (outcome and reason codes, tool field values, holidays) in a terse spreadsheet-like format.
Hard requirements: after applying the memo, every rule, value, phrase that must be said, date, holiday, code, tool field and allowed value must be EXACTLY equivalent to the specification. Do not add rules. Do not drop any rule, however small (count them: the spec has numbered rules; all must be present somewhere). Keep exact quoted sentences the agent must say verbatim. Reorder and reword freely otherwise. Output only the material, as markdown.

SPECIFICATION:
"""
src = pathlib.Path(sys.argv[1]).read_text()
pre = pathlib.Path(sys.argv[3]).read_text() if len(sys.argv) > 3 else ""
extra = ("\n\nThis specification builds on an earlier one (given for context only, do NOT rewrite it, rewrite only the new one):\n" + pre) if pre else ""
out = chat([{"role": "user", "content": P + src + extra}], tier="strong", purpose="make raw brief", max_tokens=12000, effort="high")
pathlib.Path(sys.argv[2]).write_text(out)
print(sys.argv[2], len(out))
