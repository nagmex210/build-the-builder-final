"""A3 canned reply paths: every sentence the brief makes mandatory becomes fixed text the model cannot reword or reorder.

    python3 builder/canned.py extract --slot <slot> --tools <openapi.json> <brief>...   # -> out/<slot>.canned.json
    (apply(wf, canned) is called by builder/save.py's final pass)

1. extract: one Azure call reads the briefs (clean spec or raw bank material, memo overrides win) and returns the
   mandatory sentences as data: the opening (first words of every call, with its recording notice), sentences the
   brief quotes word for word and when they are due (after a tool succeeds / fails, or on a customer situation), and
   the goodbye before the close tool. Nothing is hard-coded: every text and tool name comes from the brief.
2. apply (deterministic, idempotent):
   - opening -> `on_enter: tts` of the first conversation node (`on_enter_first_entry_only`): spoken by the platform,
     no model call, so it cannot be reworded, preceded by small talk or lose the recording notice;
   - a line due after a tool result -> the tool's post-hook puts `say_now: SAY EXACTLY "<text>"` into the result
     on that outcome (success / failure), so the sentence arrives as data at the moment it is due;
   - the goodbye -> the close tool's description ("before calling, say exactly ...");
   - all lines -> a FIXED SENTENCES block in `system_prompt` (seen in every node), with when each is due.
"""
import argparse, json, pathlib, re, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "btb"))
MARK = "## FIXED SENTENCES"

PROMPT = """You read a bank's brief for an outbound phone agent (it may be a clean spec or raw bank material: mails, a policy
extract, a memo that overrides it, a code list; a later memo or override beats the base policy). Tool API file below.

Extract every sentence the agent is REQUIRED to say, as fixed text. Return JSON only:
{
 "opening": "<the exact first thing the agent says on every call, built from the brief's opening rule: who is calling (and that it is a digital assistant if the brief says so), the recording notice if the brief requires one, and the first question the brief wants (e.g. asking for the named customer using call variables). Use {{var}} placeholders only from this list: VARS. It must not mention anything the brief forbids before identity is verified. One or two short sentences.>",
 "lines": [
   {"text": "<exact sentence; if the brief quotes it, copy the quote verbatim; otherwise a short neutral sentence that says exactly what the brief requires>",
    "when": "<one line: the situation in which it is said>",
    "tool": "<tool name if it is due right after that tool's result, else empty>",
    "outcome": "<success|failure|empty>"}
 ],
 "goodbye": "<the sentence said right before the call-closing tool, if the brief requires a thank-you/goodbye, else empty>",
 "close_tool": "<name of the tool that closes/ends the call, else empty>",
 "gated_words": [
   {"word": "<a word the brief allows the agent to say only after an event (e.g. a word it may say only after a tool succeeds), exactly as the brief writes it>",
    "tool": "<the tool whose result opens it, else empty>", "outcome": "<success|failure|empty>",
    "rule": "<the brief's rule, quoted briefly>"}
 ],
 "conflicts": [
   {"rules": "<the two (or more) brief rules, quoted briefly>",
    "literal_reading": "<how a strict, literal reviewer could read them as contradicting each other>",
    "resolution": "<how the agent satisfies BOTH literally, keeping the meaning of each>"}
 ]
}
SELF-CONFLICTS (check the brief for them before you write any text): a strict reviewer checks every rule literally,
word by word. Look for pairs of rules that such a reviewer can read as contradicting: (a) a sentence the brief makes
mandatory (the opening, a notice) that contains a word another rule allows only after an event (list that word in
`gated_words`); (b) two limits or counts on the same thing; (c) "once only" against a retry or second-attempt rule;
(d) "never say X" against a required sentence that says X; (e) an order rule against another order rule.
List each in `conflicts` with a resolution. Then word the opening and every line so BOTH rules hold literally:
keep the required meaning, but never use a gated word, in exactly that form, in a text that is said before its event
(use another form of the word or a synonym that says the same thing, e.g. an active sentence instead of a passive
one). Empty lists if there are none.
Rules for `lines` (at most 10):
- include only (a) sentences the brief quotes word for word, and (b) fixed statements the brief requires in a fixed
  situation ("say that ..."): e.g. after a recorded promise, the customer died, a payment already made, a scam question,
  the identity check finally failed, a write failed for the last allowed time. NOT questions or negotiation steps
  (asking for a date, offering an amount, read-backs): the agent phrases those itself.
- `tool`/`outcome`: set them ONLY if the sentence is due after EVERY result of that tool with that outcome (for example
  every successful promise-recording call). If it depends on a count, a hint, or which question passed (the second
  failure, a swapped-date hint, the last allowed attempt), leave both empty.
- Do not include the opening or goodbye in `lines`. Do not invent rules. Keep each text short and natural for a phone
  call. Never put amounts, dates or product details that vary per call into a text unless as a {{var}} from the list.

TOOL API FILE:
TOOLS

BRIEF:
BRIEF
"""


def extract(slot, tools, briefs, variables=("customer_id", "first_name", "last_name", "title", "now")):
    from llm import chat_json
    brief = "\n\n".join(f"===== {b} =====\n" + pathlib.Path(b).read_text() for b in briefs)
    tool_txt = pathlib.Path(tools).read_text()[:30000]
    prompt = (PROMPT.replace("VARS", ", ".join(variables)).replace("TOOLS", tool_txt).replace("BRIEF", brief))
    spec = chat_json([{"role": "user", "content": prompt}], tier="strong", purpose="A3: extract the brief's mandatory sentences as fixed text",
                     max_tokens=3000, effort="medium")
    spec = resolve_conflicts(spec)
    out = KIT / "out" / f"{slot}.canned.json"
    out.write_text(json.dumps(spec, indent=1))
    return spec


def gated_hits(text, gated):
    """Gated words (said only after an event) that appear, in exactly that form, in a text said before the event."""
    return [g["word"] for g in gated if _clean(g.get("word")) and
            re.search(r"(?<![\w])" + re.escape(_clean(g["word"])) + r"(?![\w])", text or "", re.I)]


def _early_texts(spec):
    """Texts the agent says before any tool result (the opening; situational lines are left to the conflicts block)."""
    yield "opening", spec.get("opening") or ""


def resolve_conflicts(spec):
    """Deterministic self-conflict check on the extracted texts: a text said before an event must not contain a word
    the brief allows only after that event. One repair call per hit; what was found and done goes to the trace."""
    from llm import chat
    gated = [g for g in spec.get("gated_words") or [] if isinstance(g, dict) and _clean(g.get("word"))]
    log = []
    for key, text in list(_early_texts(spec)):
        hits = gated_hits(text, gated)
        for attempt in range(2):
            if not hits:
                break
            rules = "; ".join(f'"{g["word"]}": {g.get("rule", "")}' for g in gated if g["word"] in hits)
            new = chat([{"role": "user", "content":
                         "Rewrite this phone sentence so it keeps EXACTLY the same meaning and every required part, but does not "
                         f"contain these words in exactly this form: {', '.join(hits)} (the brief allows them only later: {rules}). "
                         "Use another form of the same word or an active sentence (e.g. 'we are ...ing this call'). Keep any {{var}} "
                         "placeholders unchanged. Reply with the sentence only.\n\n" + text}],
                       tier="strong", purpose="self-conflict: reword a mandatory text so a gated word is not said before its event",
                       max_tokens=300, effort="low").strip().strip('"')
            if new and set(re.findall(r"\{\{\w+\}\}", new)) == set(re.findall(r"\{\{\w+\}\}", text)):
                log.append({"text": key, "gated": hits, "before": text, "after": new})
                text = new
            hits = gated_hits(text, gated)
        if key == "opening":
            spec["opening"] = text
        if hits:
            log.append({"text": key, "gated": hits, "unresolved": True})
    spec["self_conflict_check"] = log
    return spec


def _first_conversation_node(wf):
    nodes = wf.get("nodes") or {}
    name, seen = wf.get("initial_node"), set()
    while name in nodes and name not in seen:
        seen.add(name)
        n = nodes[name]
        if n.get("node_type") == "conversation":
            return n
        nxt = n.get("passthrough_default_transition") or next((t.get("target_node") for t in n.get("transitions") or []), None)
        name = nxt
    return None


def _all_tools(wf):
    for node in (wf.get("nodes") or {}).values():
        for t in node.get("tools") or []:
            yield t
    gn = wf.get("global_nodes")
    for node in (gn.values() if isinstance(gn, dict) else gn or []):
        for t in node.get("tools") or []:
            yield t
    for t in wf.get("tools") or []:
        yield t


HOOK = r'''
try:
    _cl = __LINES__
    if isinstance(result, dict) and isinstance(result.get('data'), dict):
        _dd = result['data']
        _bad = str(_dd.get('tool_outcome') or '').startswith('FAILED') or _dd.get('ok') in (False, 'false', 'False') \
            or str(result.get('status') or 'success').lower() not in ('success', 'ok')
        _say = [x for o, x in _cl if (o == 'failure') == _bad]
        if _say:
            _dd['say_now'] = ('SAY EXACTLY, word for word, in your next message: ' + ' '.join('"' + s + '"' for s in _say)
                              + ' Do not reword it. Then continue with the next step.')
except Exception:
    pass
'''


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def apply(wf, canned):
    """Edit the workflow dict in place. Returns a list of what was fixed."""
    if not canned:
        return []
    done = []
    opening = _clean(canned.get("opening"))
    node = _first_conversation_node(wf)
    if opening and node is not None:
        node["on_enter"] = {"type": "tts", "text": opening}
        node["on_enter_first_entry_only"] = True
        done.append("opening->tts:" + node.get("name", "?"))
    lines = [l for l in canned.get("lines") or [] if _clean(l.get("text"))]
    by_tool = {}
    for l in lines:
        # Only success lines go into a hook: a failure line is usually due on the last allowed attempt only, which the
        # model tracks from the brief's retry rule (prompt block below), not on every failed result.
        if _clean(l.get("tool")) and "succ" in str(l.get("outcome")).lower():
            by_tool.setdefault(_clean(l["tool"]), []).append(("success", _clean(l["text"])))
    goodbye, close_tool = _clean(canned.get("goodbye")), _clean(canned.get("close_tool"))
    for t in _all_tools(wf):
        fn = t.get("function") or {}
        name = fn.get("name")
        if name in by_tool and "say_now" not in (t.get("post_process_code") or ""):
            t["post_process_code"] = ((t.get("post_process_code") or "").rstrip() + "\n" + HOOK.replace("__LINES__", repr(by_tool[name])).lstrip("\n"))
            done.append("say_now:" + name)
        if goodbye and name == close_tool and goodbye not in (fn.get("description") or ""):
            fn["description"] = (f'Before you call this, in the same turn, say exactly: "{goodbye}" (unless you already said it). '
                                 + (fn.get("description") or ""))
            done.append("goodbye:" + name)
    sp = wf.get("system_prompt") or ""
    if MARK not in sp and (opening or lines or goodbye):
        block = [MARK, "These sentences are mandatory. Say them word for word when due, never reword, shorten or reorder them, "
                 "and never say them earlier than their moment:"]
        if opening:
            block.append(f'- Opening (spoken automatically at the start; never repeat or rephrase it, never add to it): "{opening}"')
        for l in lines:
            block.append(f'- {_clean(l.get("when")).rstrip(".")}: "{_clean(l["text"])}"')
        if goodbye:
            block.append(f'- Right before {close_tool or "closing the call"}: "{goodbye}"')
        for g in canned.get("gated_words") or []:
            if isinstance(g, dict) and _clean(g.get("word")):
                ev = f'{_clean(g.get("tool"))} returns {_clean(g.get("outcome")) or "its result"}' if _clean(g.get("tool")) else "its event"
                block.append(f'- Never say the word "{_clean(g["word"])}" in any sentence before {ev} (brief: {_clean(g.get("rule"))[:160]}).')
        res = [c for c in canned.get("conflicts") or [] if isinstance(c, dict) and _clean(c.get("resolution"))]
        if res:
            block.append("Rules that could look contradicting, and how both hold (follow these):")
            block += [f'- {_clean(c.get("rules"))[:200]} -> {_clean(c["resolution"])[:240]}' for c in res[:6]]
        wf["system_prompt"] = (sp.rstrip() + "\n\n" + "\n".join(block)).strip()
        done.append("system_prompt block")
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("--slot", required=True); ap.add_argument("--tools", default="tools/openapi.json")
    ap.add_argument("briefs", nargs="+")
    a = ap.parse_args()
    print(json.dumps(extract(a.slot, a.tools, a.briefs), indent=1))
