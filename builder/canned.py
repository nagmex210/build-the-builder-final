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
   - the goodbye -> spoken by the PLATFORM after the close tool succeeded: `spoken_message` of the end_call node that
     the close tool's ok result routes to (close_structure below). The model is told never to say goodbye itself: a
     goodbye said as text before close_call let the customer say bye, the platform's goodbye auto-trigger hung up and
     no outcome was recorded (seen on official runs). Close -> hang-up routes test ok only, never success_count (M19);
   - all lines -> a FIXED SENTENCES block in `system_prompt` (seen in every node), with when each is due.
"""
import argparse, json, os, pathlib, re, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "btb"))
MARK = "## FIXED SENTENCES"

PROMPT = """You read a company's brief for a phone agent (any call type: outbound collections, an inbound inquiry, a service
request, ...; it may be a clean spec or raw bank material: mails, a policy
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
  situation ("say that ..."): e.g. after a write succeeded, before a hand-off to a human, when a lookup finds nothing,
  a check finally failed, a write failed for the last allowed time (in a collections brief also: a recorded promise,
  the customer died, a payment already made). NOT questions or negotiation steps
  (asking for a date, offering an amount, read-backs): the agent phrases those itself.
- `tool`/`outcome`: set them ONLY if the sentence is due after EVERY result of that tool with that outcome (for example
  every successful call of a write tool). If it depends on a count, a hint, or which question passed (the second
  failure, a swapped-date hint, the last allowed attempt), leave both empty.
- Do not include the opening or goodbye in `lines`. Do not invent rules. Keep each text short and natural for a phone
  call. Never put amounts, dates or product details that vary per call into a text unless as a {{var}} from the list.

TOOL API FILE:
TOOLS

BRIEF:
BRIEF
"""


def fill_prompt(prompt, tool_txt, brief):
    """Fill the TOOLS / BRIEF placeholder lines only. A bare .replace("BRIEF", brief) also replaced the "BRIEF:" header
    (the brief went in twice, the header vanished) and any "BRIEF" inside the tool API text."""
    tail = "TOOL API FILE:\nTOOLS\n\nBRIEF:\nBRIEF\n"
    assert prompt.endswith(tail)
    return prompt[:-len(tail)] + "TOOL API FILE:\n" + tool_txt + "\n\nBRIEF:\n" + brief + "\n"


def extract(slot, tools, briefs, variables=("customer_id", "first_name", "last_name", "title", "now")):
    from llm import chat_json
    brief = "\n\n".join(f"===== {b} =====\n" + pathlib.Path(b).read_text() for b in briefs)
    tool_txt = pathlib.Path(tools).read_text()[:30000]
    prompt = fill_prompt(PROMPT.replace("VARS", ", ".join(variables) + " or a call variable the brief itself names"), tool_txt, brief)
    if os.environ.get("BTB_LANGUAGE"):   # spoken texts in the case's language; quotes stay verbatim
        prompt += (f"\nLANGUAGE: the agent speaks {os.environ['BTB_LANGUAGE']}: every text (opening, lines, goodbye) is in "
                   f"{os.environ['BTB_LANGUAGE']}; a quoted sentence is copied verbatim in its original language, never translated.")
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
        if str(_dd.get('tool_outcome') or '').startswith('ALREADY RECORDED'):
            _say = []                     # a re-send of a recorded write: its line was said the first time
        if _say:
            import re as _re
            _src = [_dd] + [_x for _v in _dd.values() if isinstance(_v, list) for _x in _v[:1] if isinstance(_x, dict)] + [vars]

            def _val(_k):                 # a brief placeholder <<k>>: the result's (or first item's, or call) field of that name
                for _loose in (False, True):  # exact name first; a loose match never takes an id field
                    for _d in _src:
                        for _f, _v in _d.items():
                            if isinstance(_v, (str, int, float)) and (_f == _k or _loose and (_k in _f or _f in _k)
                                                                       and not _re.search(r'(^|_)(id|ref)$', _f)):
                                return str(_v)
                return '[' + _k + ']'
            _say = [_re.sub(r'<<\s*(\w+)\s*>>', lambda _m: _val(_m.group(1)), s) for s in _say]
            _dd['say_now'] = ('SAY EXACTLY, word for word, in your next message: ' + ' '.join('"' + s + '"' for s in _say)
                              + ' Do not reword it (only put the real value from this result in place of any [field]).'
                              ' Then continue with the next step.')
except Exception:
    pass
'''


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


DEFAULT_GOODBYE = "Thank you for your time. Goodbye."


def default_goodbye():
    """The platform's spoken goodbye when the brief gives none: in the case's language (BTB_LANGUAGE)."""
    try:
        from casefolder import GOODBYES
        return GOODBYES.get(os.environ.get("BTB_LANGUAGE") or "English", DEFAULT_GOODBYE)
    except ImportError:
        return DEFAULT_GOODBYE


def _close_tool_name(wf, canned):
    names = {(t.get("function") or {}).get("name") for t in _all_tools(wf)}
    want = _clean((canned or {}).get("close_tool"))
    if os.environ.get("BTB_COLLECTIONS") == "0":
        # Non-collections case: only a tool that really ends the call is the close tool (never a transfer / hand-off,
        # which the extractor may name); with none, the case's own end node ends the call and nothing is rewritten.
        ends = lambda n: bool(re.search(r"close|end_?call|hang_?up|finish|terminate", str(n).lower())) and "transfer" not in str(n).lower()
        if want in names and ends(want):
            return want
        return next((n for n in sorted(n for n in names if n) if ends(n)), None)
    if want in names:
        return want
    return next((n for n in sorted(n for n in names if n) if "close" in n), None)


def _ok_conds(close):
    return [{"variable": f"{close}_response.data.ok", "operator": "equals", "operand": v} for v in ("true", "True")]


CLOSING = ("CLOSING (overrides anything above about goodbyes): never say goodbye, bye, \"have a nice day\" or a closing "
           "thank-you yourself, and never announce that you are ending the call. When the conversation is finished, call "
           "{close} (after every note/transfer the brief requires): the system then says the goodbye and hangs up. If the "
           "customer says goodbye or wants to end the call, call {close} in that same turn (notes first if still due).")


_BYE_RULES = [   # phrase-level only: a whole sentence can also carry a mandatory line or a close reason
    (r"Before (?:calling|you call) the close tool,? say (?:the )?goodbye\.[ \t]*", ""),
    (r"(?:thank(?: the customer)?,? and )?say (?:the )?goodbye before (?:calling|you call)", "call"),
    (r"\b(?:(?:say\s+)?thank(?:\s+(?:you|the customer|them|the person))?(?:,|\s+and)?\s*)?(?:say\s+)?(?:the\s+)?(?<!says )(?<!said )goodbye"
     r"(?:\s+once)?(?:\s+in one short sentence)?(?:,|\s+and|\s+then)*\s+(?=(?:then\s+)?(?:call\s+)?`?close)", ""),
]


def _drop_bye(text):
    """Remove 'say goodbye (then close)' instructions: the platform says the goodbye after the close tool now."""
    for pat, rep in _BYE_RULES:
        text = re.sub(pat, rep, text or "", flags=re.I)
    return text


def close_structure(wf, canned=None):
    """The call never ends without the close tool: the goodbye is the end_call node's own spoken_message, reached only
    on the close tool's ok result; the model never says goodbye (so neither side triggers the platform's goodbye
    hang-up before the outcome is recorded). Idempotent."""
    close = _close_tool_name(wf, canned)
    nodes = wf.get("nodes") or {}
    if not close:
        return []
    done = []
    goodbye = _clean((canned or {}).get("goodbye")) or default_goodbye()
    ends = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    close_ends = set()
    for k, n in nodes.items():
        for t in n.get("transitions") or []:
            c = t.get("condition") or {}
            if t.get("target_node") not in ends or close not in json.dumps(c):
                continue
            close_ends.add(t["target_node"])
            conds = c.get("conditions") if isinstance(c.get("conditions"), list) else [c]
            keep = [x for x in conds if f"{close}_success_count" not in json.dumps(x)]
            if len(keep) != len(conds):          # M19: a guard's blocked close is a 2xx too
                t["condition"] = {"logic": "or", "conditions": keep or _ok_conds(close)}
                done.append(f"close-route ok only:{k}")
    for e in close_ends:
        term = nodes[e].setdefault("terminal", {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call"}})
        props = (term.setdefault("function", {}).setdefault("parameters", {"type": "object", "properties": {}})
                 .setdefault("properties", {}))
        props["message_mode"] = {"type": "string", "default": "custom"}
        props["spoken_message"] = {"type": "string", "default": goodbye}
        for x in ("llm_prompt", "interruptible", "trigger_timeout", "trigger_pattern_both"):
            props.pop(x, None)
        nodes[e]["on_enter"] = {"type": "silent"}
        done.append("goodbye->end_call:" + e)
    rule = CLOSING.format(close=close)
    for k, n in nodes.items():
        has = any((t.get("function") or {}).get("name") == close for t in n.get("tools") or [])
        if n.get("node_type") == "conversation" and has and "CLOSING (overrides" not in (n.get("task_message") or ""):
            n["task_message"] = (_drop_bye(n.get("task_message")).rstrip() + "\n\n" + rule).strip()
    for t in _all_tools(wf):
        fn = t.get("function") or {}
        if fn.get("name") != close:     # other tools' descriptions and hook texts ("say goodbye and call close") too
            fn["description"] = _drop_bye(fn.get("description"))
            if t.get("post_process_code"):
                t["post_process_code"] = _drop_bye(t["post_process_code"])
        if fn.get("name") == close:
            d = re.sub(r'Before you call this, in the same turn, say exactly: "[^"]*" \(unless you already said it\)\. ', "", fn.get("description") or "")
            if "says the goodbye" not in d:
                d = _drop_bye(re.sub(r",?\s*after you (?:have )?said[^.,;]*\bgoodbye\b", "", d, flags=re.I))
                # the goodbye text is NOT quoted here: quoted text is said word for word (M10), so the model said it too
                d = ("Call this to end the call, INSTEAD of saying goodbye: after it succeeds the system says the goodbye "
                     "and hangs up. Never say goodbye or a closing thank-you yourself. " + d)
            fn["description"] = d
    sp = wf.get("system_prompt") or ""
    if "CLOSING (overrides" not in sp:
        wf["system_prompt"] = (_drop_bye(sp).rstrip() + "\n\n" + rule).strip()
    return done


def apply(wf, canned):
    """Edit the workflow dict in place. Returns a list of what was fixed."""
    done = close_structure(wf, canned)
    if not canned:
        return done
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
    real_close = _close_tool_name(wf, canned)
    close_tool = real_close or close_tool
    for t in _all_tools(wf):
        fn = t.get("function") or {}
        name = fn.get("name")
        if name in by_tool and "say_now" not in (t.get("post_process_code") or ""):
            t["post_process_code"] = ((t.get("post_process_code") or "").rstrip() + "\n" + HOOK.replace("__LINES__", repr([(o, x.replace("{{", "<<").replace("}}", ">>")) for o, x in by_tool[name]])).lstrip("\n"))
            done.append("say_now:" + name)
    sp = wf.get("system_prompt") or ""
    if MARK not in sp and (opening or lines or goodbye):   # goodbye text itself: close_structure's end_call node
        block = [MARK, "These sentences are mandatory. Say them word for word when due, never reword, shorten or reorder them, "
                 "and never say them earlier than their moment:"]
        if opening:
            block.append(f'- Opening (spoken automatically at the start; never repeat or rephrase it, never add to it): "{opening}"')
        for l in lines:
            block.append(f'- {_clean(l.get("when")).rstrip(".")}: "{_clean(l["text"])}"')
        if goodbye and not real_close:   # no tool ends the call: the documents' closing sentence is the agent's own
            block.append(f'- Closing sentence, at the end of the call as the documents say: "{goodbye}"')
        elif goodbye:
            block.append(f'- Goodbye: NOT yours. The system says it automatically after {close_tool or "the close tool"} succeeds; never say any goodbye yourself.')
        for g in canned.get("gated_words") or []:
            if isinstance(g, dict) and _clean(g.get("word")):
                ev = f'{_clean(g.get("tool"))} returns {_clean(g.get("outcome")) or "its result"}' if _clean(g.get("tool")) else "its event"
                block.append(f'- Never say the word "{_clean(g["word"])}" in any sentence before {ev} (brief: {_clean(g.get("rule"))[:160]}).')
        wf["system_prompt"] = (sp.rstrip() + "\n\n" + "\n".join(block)).strip()
        done.append("system_prompt block")
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("--slot", required=True); ap.add_argument("--tools", default="tools/openapi.json")
    ap.add_argument("briefs", nargs="+")
    a = ap.parse_args()
    print(json.dumps(extract(a.slot, a.tools, a.briefs), indent=1))
