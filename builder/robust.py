"""Customer-speech robustness (b1/w5), applied deterministically to every saved workflow. Brief-agnostic.

- the "How customers talk" block (builder/robustness.md) goes into `system_prompt` (seen in every node);
- every classification extraction field (enum, or 3+ quoted labels) gets INTENT_GUARD: a question back or small
  talk is not an action category.
Idempotent.
"""
import pathlib, re

INTENT_GUARD = ("Only an explicit statement in the customer's own words counts. A question back (for example whether a "
                "date or amount could be different, why, or what happens if), small talk, hesitation or thinking aloud is "
                "NOT one of the action categories: then use the neutral or none value, or keep the previous value.")
ROBUST = (pathlib.Path(__file__).resolve().parent / "robustness.md").read_text().strip()


def robustify(wf):
    """Edit the workflow dict in place. Returns True if anything changed."""
    changed = False
    sp = wf.get("system_prompt") or ""
    if ROBUST.splitlines()[0] not in sp:
        wf["system_prompt"] = (sp.rstrip() + "\n\n" + ROBUST).strip()
        changed = True
    for node in (wf.get("nodes") or {}).values():
        # A conversation node with a silent on_enter says nothing when entered and waits for the user: the customer's
        # turn that routed there gets no reply (seen b2 merge: identity node silent, every chat turn timed out).
        if node.get("node_type") == "conversation" and (node.get("on_enter") or {}).get("type") == "silent":
            node["on_enter"] = {"type": "llm"}
            changed = True
        for e in node.get("extraction_schema") or []:
            d = e.get("description") or ""
            if INTENT_GUARD in d:
                continue
            if e.get("type", "string") == "string" and (e.get("enum_values") or len(re.findall(r"'[a-z_]+'\s*[:=]", d)) >= 3):
                e["description"] = d.rstrip() + " " + INTENT_GUARD
                changed = True
    return changed
