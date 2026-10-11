"""A1 router + specialists: the brief's customer situations as named routes, read from the brief at build time.

    python3 builder/situations.py extract --slot <slot> --tools <openapi.json> <brief>...   # -> out/<slot>.situations.json
    python3 builder/situations.py check <workflow.json> <situations.json>                   # coverage report (JSON)

1. extract: one Azure call reads the briefs (clean spec or raw bank material, memo overrides win) and lists every
   situation after the account is loaded that needs its OWN handling: the main path (the customer pays / negotiates)
   and every exit the brief requires (cannot pay even the lowest allowed amount or wants a plan -> transfer, hardship,
   dispute / already paid, a third party took over, ...). Each comes with its named triggers (what the customer says),
   the rules that apply only there, the tools it needs, and how the call ends (outcome / reason from the brief's
   table). Nothing is hard-coded: names, triggers, tools and outcomes all come from the brief and the tool API file.
2. The build agent gets the list and builds one router (the negotiation node) + one short specialist node per exit,
   each reached by a tool-call transition named after the situation (routing.md "Router + specialists").
3. check: deterministic coverage report on the written workflow: every exit situation has a node, the node is reachable
   from the router by a transition, has the tools the brief names for it and can reach the end node. Logged in the
   trace; failures go back to the build agent as a list.
"""
import argparse, json, pathlib, re, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "btb"))

PROMPT = """You read a bank's brief for an outbound debt-collection phone agent (it may be a clean spec or raw bank material:
mails, a policy extract, a memo that overrides it, a code list; a later memo or override beats the base policy). Tool API file below.

After the customer's identity is verified and the account is loaded, the agent talks about the debt. List the
SITUATIONS the brief handles differently at that point, so that each can get its own small node with only its rules
and tools. Return JSON only:
{
 "main": {"name": "pays", "summary": "<one line: the normal path (state the debt, ask for payment, negotiate within the brief's limits, record the promise)>"},
 "exits": [
   {"name": "<short snake_case name, e.g. cannot_pay_transfer, hardship, dispute, already_paid, third_party, callback>",
    "triggers": ["<what the customer says or what happened that puts the call in this situation, as the brief defines it; include the exact threshold, e.g. 'refuses or cannot pay even the lowest allowed amount after the allowed persuasion attempts', 'asks for an instalment plan'>"],
    "rules": ["<each rule of the brief that applies ONLY in this situation, short, in the brief's own terms (what to say, what never to say, what to record)>"],
    "tools": ["<tool names from the tool API file this situation must call, in order (e.g. a transfer tool, then a note tool, then the close tool)>"],
    "close": "<outcome / reason values the brief's table uses to close the call in this situation, exactly as the API file spells them, or empty>",
    "back_to_main": "<true if the customer can still return to paying from here (e.g. changes their mind before anything is recorded), else false>",
    "first_line": "<the brief's own clause that governs the agent's behaviour in this situation, in the brief's words, e.g. a 'make no persuasion attempt' / 'do not describe a plan' / 'do not negotiate' clause; empty if none>",
    "once_only": ["<each thing the brief allows only ONCE in this situation or once per call (a sympathy sentence, a support offer, an explanation), in the brief's words>"],
    "promise_allowed": "<'never' if no promise is recorded in this situation, 'only_if_customer_names' if the brief records a promise here only when the customer themselves names a date or amount, 'yes' otherwise>"}
 ]
}
Rules:
- Only situations the brief really names. A situation that needs a transfer, a note, a specific outcome/reason, a
  special sentence or the absence of persuasion is an exit. Do not invent situations the brief does not mention.
- Name exact triggers: when the brief says the agent must transfer / stop negotiating once a customer cannot pay
  even the floor (or asks for a plan, or disputes), say so with the threshold, so the agent knows WHEN to leave the
  negotiation instead of inventing its own plan.
- An exit is a situation in which the agent STOPS pursuing the normal promise (or hands over / closes in a special way).
  NOT exits (they stay in the main path): tool failures and retries, read-backs, corrections, questions about the
  debt, small talk, choosing among dates or amounts.
- Tool names and outcome/reason values only from the tool API file. At most 6 exits.

TOOL API FILE:
TOOLS

BRIEF:
BRIEF
"""


def extract(slot, tools, briefs):
    from canned import fill_prompt
    from llm import chat_json
    brief = "\n\n".join(f"===== {b} =====\n" + pathlib.Path(b).read_text() for b in briefs)
    tool_txt = pathlib.Path(tools).read_text()[:30000]
    spec = chat_json([{"role": "user", "content": fill_prompt(PROMPT, tool_txt, brief)}], tier="strong",
                     purpose="A1: list the brief's situations after the account lookup (router + specialist routes)",
                     max_tokens=4000, effort="medium")
    exits = [e for e in (spec.get("exits") or []) if isinstance(e, dict) and e.get("name")]
    for e in exits:
        e["name"] = re.sub(r"[^a-z0-9_]+", "_", str(e["name"]).lower()).strip("_")[:40] or "exit"
    spec["exits"] = exits[:6]
    out = KIT / "out" / f"{slot}.situations.json"
    out.write_text(json.dumps(spec, indent=1))
    return spec


def prompt_block(spec):
    """The situations as an instruction block for the build agent."""
    if not spec or not spec.get("exits"):
        return ""
    lines = ["ROUTER + SPECIALISTS (read from the brief by a separate extraction; check each against the brief, the brief wins): "
             "build the post-account part as routing.md section 'Router + specialists' says. Main path: "
             + str((spec.get("main") or {}).get("summary", "")) + ". Exit situations, one specialist node each:"]
    for e in spec["exits"]:
        lines.append(f"- node `{e['name']}` | triggers: {'; '.join(map(str, e.get('triggers') or []))} | rules: "
                     f"{'; '.join(map(str, e.get('rules') or []))} | tools in order: {', '.join(map(str, e.get('tools') or []))} | "
                     f"close: {e.get('close') or '-'} | back to main allowed: {e.get('back_to_main')} | first line of its task_message: "
                     f"{e.get('first_line') or '-'} | once only: {'; '.join(map(str, e.get('once_only') or [])) or '-'} | "
                     f"promise: {e.get('promise_allowed') or '-'}")
    return "\n".join(lines)


MARK = "## THIS SITUATION (from the brief)"
HANDOFF = ("HAND-OFF: when a trigger for another situation holds, call its transition tool AT ONCE and WITHOUT speaking "
           "in that turn (no sympathy, no offer, no 'one moment'): the next node speaks. Never improvise a plan, an amount "
           "below the lowest allowed one, or another date instead of the exit the brief requires.")


def _find(nodes, name):
    if name in nodes:
        return name
    cand = [k for k in nodes if nodes[k].get("node_type") == "conversation" and (name in k or k in name)]
    return cand[0] if cand else None


def apply(wf, spec):
    """Deterministic, idempotent: put each exit's governing clause FIRST in its specialist's task_message, with the
    once-only limits and the promise rule, and a silent hand-off rule into every node that leaves to a specialist.
    Returns what was done."""
    nodes = wf.get("nodes") or {}
    done = []
    spec_nodes = {}
    for e in (spec or {}).get("exits") or []:
        k = _find(nodes, e["name"])
        if k:
            spec_nodes[k] = e
    for k, e in spec_nodes.items():
        n = nodes[k]
        tm = n.get("task_message") or ""
        if MARK in tm:
            continue
        lines = [MARK]
        if str(e.get("first_line") or "").strip():
            lines.append(f"FIRST RULE (brief): {str(e['first_line']).strip()}")
        lines.append("The customer has just told you their situation. Respond to it now, ONCE, in the brief's order. "
                     "Never repeat a sentence you or an earlier node already said in this call.")
        lines.append("EVERY OFFER AND QUESTION OF THIS SITUATION IS MADE AT MOST ONCE PER CALL (even if you enter this node "
                     "again): before you speak, look at the conversation; if the offer (e.g. a transfer or support offer) "
                     "or sympathy was already said, do not say it again: take the customer's latest words as the answer "
                     "and do the next step (if unclear: one short yes/no question that does not repeat the offer).")
        for o in e.get("once_only") or []:
            if str(o).strip():
                lines.append(f"ONCE PER CALL: {str(o).strip()}. If it was already said earlier in this call (look at the "
                             "conversation), do not say or offer it again.")
        pa = str(e.get("promise_allowed") or "").lower()
        if "only" in pa or "name" in pa:
            lines.append("PROMISE: never propose a date or amount here and never ask for one. Record a promise ONLY if "
                         "the customer themselves names a date or an amount, then follow the promise rules.")
        elif "never" in pa:
            lines.append("PROMISE: no promise is recorded in this situation; do not ask for a date or amount.")
        n["task_message"] = "\n".join(lines) + "\n\n" + tm
        done.append("specialist:" + k)
    for k, n in nodes.items():
        if k in spec_nodes or n.get("node_type") != "conversation":
            continue
        if any(t.get("target_node") in spec_nodes for t in n.get("transitions") or []):
            tm = n.get("task_message") or ""
            if "HAND-OFF:" not in tm:
                n["task_message"] = tm.rstrip() + "\n\n" + HANDOFF
                done.append("handoff:" + k)
    return done


def _tool_names(node):
    names = []
    for t in node.get("tools") or []:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict):
            names.append(t.get("name") or (t.get("function") or {}).get("name") or t.get("tool_name") or "")
    return [n for n in names if n]


def check(wf, spec, tool_defs=None):
    """Deterministic coverage report: each exit situation has a node reachable from a conversation node, with its tools,
    and that node can reach an end_call node. Returns a list of problems (empty = covered)."""
    nodes = wf.get("nodes") or {}
    tool_defs = tool_defs or {}
    problems = []
    ends = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    targets = {k: {t.get("target_node") for t in (n.get("transitions") or [])} for k, n in nodes.items()}

    def reaches_end(start):
        seen, todo = set(), [start]
        while todo:
            k = todo.pop()
            if k in ends:
                return True
            if k in seen or k not in nodes:
                continue
            seen.add(k)
            todo += list(targets.get(k, ())) + [nodes[k].get("passthrough_default_transition")]
        return False

    exit_keys = {_find(nodes, e["name"]) for e in (spec or {}).get("exits") or []} - {None}
    # triage-only router: some node that hands off to specialists must also hand off to a separate main-path node
    routers = [k for k, n in nodes.items() if k not in exit_keys and n.get("node_type") == "conversation"
               and {t.get("target_node") for t in n.get("transitions") or []} & exit_keys]
    if routers and not any(t.get("target_node") in routers for k in routers for t in nodes[k].get("transitions") or []):
        problems.append(f"node '{routers[0]}' routes to the specialists but there is no separate main-path node: make it a "
                        "triage-only router (state the debt, route) with a tool-call transition to its own negotiate node")
    for e in (spec or {}).get("exits") or []:
        name = e["name"]
        node = nodes.get(name)
        if node is None:      # accept a node whose key contains the situation name
            cand = [k for k in nodes if name in k or k in name]
            node = nodes.get(cand[0]) if cand else None
            name = cand[0] if cand else name
        if node is None:
            problems.append(f"situation '{e['name']}': no specialist node"); continue
        if not any(name in t for k, t in targets.items() if k != name):
            problems.append(f"situation '{e['name']}': node '{name}' has no incoming transition (router cannot reach it)")
        have = set(_tool_names(node))
        if tool_defs:
            have |= {tool_defs.get(t, t) for t in have}
        want = [re.split(r"[^A-Za-z0-9_]", str(t).strip())[0] for t in e.get("tools") or []]
        missing = [t for t in want if t and t not in have]
        if missing and have:
            problems.append(f"situation '{e['name']}': node '{name}' lacks tools {missing}")
        if not reaches_end(name):
            problems.append(f"situation '{e['name']}': node '{name}' cannot reach an end_call node")
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("extract"); x.add_argument("--slot", required=True); x.add_argument("--tools", required=True); x.add_argument("briefs", nargs="+")
    c = sub.add_parser("check"); c.add_argument("workflow"); c.add_argument("situations")
    a = ap.parse_args()
    if a.cmd == "extract":
        s = extract(a.slot, a.tools, a.briefs)
        print(json.dumps({"exits": [e["name"] for e in s.get("exits", [])]}))
    else:
        print(json.dumps(check(json.loads(pathlib.Path(a.workflow).read_text()), json.loads(pathlib.Path(a.situations).read_text())), indent=1))
