# canned.extract / situations.extract: PROMPT.replace("BRIEF", brief) also replaces the "BRIEF:" header -> brief sent twice
from common2 import *
import llm, pathlib
seen = []
def fake(msgs, **k):
    seen.append(msgs[0]["content"]); return {"exits": [], "gated_words": [], "opening": ""}
llm.chat_json = fake
canned.KIT = situations.KIT = pathlib.Path("/tmp/bh2/kit"); (canned.KIT / "out").mkdir(parents=True, exist_ok=True)
pathlib.Path("/tmp/bh2/brief.md").write_text("UNIQUE_BRIEF_MARKER rule 1.")
canned.extract("x", KIT + "/tools/openapi.json", ["/tmp/bh2/brief.md"])
situations.extract("x", KIT + "/tools/openapi.json", ["/tmp/bh2/brief.md"])
for name, p in zip(("canned", "situations"), seen):
    print(name, "brief copies in prompt:", p.count("UNIQUE_BRIEF_MARKER"), "| 'BRIEF:' header present:", "BRIEF:" in p)
assert all(p.count("UNIQUE_BRIEF_MARKER") == 1 for p in seen), "BUG: the brief is inserted twice (header replaced too)"
