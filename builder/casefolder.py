"""Final format: `build.py <case_folder> <mock_url>`. Brief-agnostic preparation of a case folder.

- all text documents of the folder -> one combined brief file runs/case/<slot>/case.md (brief first, then README, then the
  rest, each under its file name; binaries skipped; images: file name + path, so the build agent can open them);
- the service contract -> runs/case/<slot>/tools.json (OpenAPI JSON; YAML converted; a markdown/text-only contract is turned
  into OpenAPI JSON by Azure), with servers[0].url set to the mock URL;
- the case language (stopword count over the brief and example conversations) -> a LANGUAGE instruction.
"""
import json, os, pathlib, re, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".tsv", ".html", ".htm", ".xml", ".mmd", ".mermaid", ".puml", ".dot", ".ini", ".toml", ""}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
SKIP_DIRS = {".git", "__MACOSX", "node_modules", "__pycache__"}

STOPWORDS = {
    "Turkish": "ve bir bu için ile da de ne değil müşteri ödeme borç olarak gibi ama çok daha sonra kart ise eğer mı mi var yok size siz biz hesap tarih tutar".split(),
    "English": "the and of to is in for that with you not are this be on customer payment if".split(),
    "German": "und der die das ist nicht zu mit für sie ein eine den auf kunde zahlung".split(),
    "Spanish": "el la de que y en los las por con para una es no cliente pago".split(),
    "French": "le la les de et des est que pour une pas dans avec vous client paiement".split(),
    "Dutch": "de het een en van is niet dat voor met op klant betaling".split(),
    "Italian": "il di che e la per non una sono con cliente pagamento".split(),
    "Portuguese": "o de que e do da em para com não uma os cliente pagamento".split(),
}
GOODBYES = {
    "English": "Thank you for your time. Goodbye.",
    "Turkish": "Zaman ayırdığınız için teşekkür ederim. İyi günler.",
    "German": "Vielen Dank für Ihre Zeit. Auf Wiederhören.",
    "Spanish": "Gracias por su tiempo. Adiós.",
    "French": "Merci pour votre temps. Au revoir.",
    "Dutch": "Bedankt voor uw tijd. Tot ziens.",
    "Italian": "Grazie per il suo tempo. Arrivederci.",
    "Portuguese": "Obrigado pelo seu tempo. Adeus.",
}


LANG_NAMES = ["English", "Turkish", "German", "French", "Spanish", "Italian", "Portuguese", "Dutch", "Arabic", "Russian",
              "Polish", "Greek", "Swedish", "Danish", "Norwegian", "Finnish", "Czech", "Romanian", "Hungarian"]
_EXPLICIT = re.compile(r"\b(?:the\s+)?(?:calls?|conversations?|phone\s+line|customers?|callers?|assistant|agent)\b[^.\n]{0,40}?"
                       r"\b(?:(?:are|is|will\s+be|speaks?|talks?|held|run|conducted)\s+)?in\s+(" + "|".join(LANG_NAMES) + r")\b", re.I)


def explicit_language(text):
    """A language the documents STATE for the calls ("The calls are in X", "callers speak X") beats word counts: a
    pack can be written in one language for a phone line that runs in another."""
    hits = {}
    for m in _EXPLICIT.finditer(text):
        lang = m.group(1).capitalize()
        hits[lang] = hits.get(lang, 0) + 1
    return max(hits, key=hits.get) if hits else None


def detect_language(text):
    stated = explicit_language(text)
    if stated:
        return stated
    words = re.findall(r"[^\W\d_]+", text.lower())
    counts = {lang: sum(1 for w in words if w in set(sw)) for lang, sw in STOPWORDS.items()}
    tr_chars = len(re.findall(r"[ığşİĞŞ]", text))
    counts["Turkish"] += tr_chars // 3
    best = max(counts, key=counts.get)
    return best if counts[best] else "English"


def language_instruction(lang):
    return (f"LANGUAGE: the phone agent speaks {lang}. Every sentence it says to the customer is in {lang}; mandatory "
            f"sentences are quoted from the documents verbatim in their original language (never translate a quote). "
            f"Internal instructions (task messages, tool descriptions) may stay in English, but any sentence meant to be "
            f"said aloud (openings, fallback lines, goodbyes, spoken_message) must be in {lang}.")


def _files(folder):
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not any(part in SKIP_DIRS or part.startswith(".") for part in p.relative_to(folder).parts):
            out.append(p)
    return out


def _is_text(p):
    if p.suffix.lower() not in TEXT_EXT:
        return False
    try:
        p.read_bytes()[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _load_yaml(txt):
    try:
        import yaml
        return yaml.safe_load(txt)
    except ImportError:
        pass
    try:
        from ruamel.yaml import YAML
        return YAML(typ="safe").load(txt)
    except ImportError:
        return None


def _looks_openapi(d):
    return isinstance(d, dict) and ("openapi" in d or "swagger" in d or "paths" in d)


def find_contract(files):
    """(openapi dict or None, contract text file or None)."""
    cands = []
    for p in files:
        s = p.suffix.lower()
        if s in (".json", ".yaml", ".yml"):
            txt = p.read_text(errors="replace")
            d = None
            if s == ".json":
                try:
                    d = json.loads(txt)
                except ValueError:
                    d = None
            else:
                d = _load_yaml(txt)
                if d is None and re.search(r"^(openapi|swagger|paths)\s*:", txt, re.M):
                    return None, p     # YAML contract but no YAML parser: let Azure convert it
            if _looks_openapi(d):
                cands.append((len(d.get("paths") or {}), d))
    if cands:
        return max(cands, key=lambda c: c[0])[1], None
    # markdown / text contract: the file whose name or content says contract / API / service
    best = None
    for p in files:
        if not _is_text(p) or p.suffix.lower() not in (".md", ".txt", ""):
            continue
        name = p.name.lower()
        txt = p.read_text(errors="replace")
        score = 3 * bool(re.search(r"contract|sözleşme|sozlesme|api|servis|service|endpoint|tool", name))
        score += min(5, len(re.findall(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/", txt)))
        score += 2 * bool(re.search(r"endpoint|request body|response|istek|yanıt", txt, re.I))
        if score >= 3 and (best is None or score > best[0]):
            best = (score, p)
    return None, (best[1] if best else None)


def contract_from_text(path):
    sys.path.insert(0, str(KIT / "btb"))
    from llm import chat
    prompt = ("Convert this service contract of a bank (the tool API a phone agent calls) into one OpenAPI 3.0 JSON "
              "document: every operation with its method, path, operationId, summary/description (keep the contract's "
              "own explanations, any language), requestBody schema with required fields and descriptions, and "
              "response schemas. Keep names exactly as in the contract. servers[0].url is the contract's base address "
              "INCLUDING its path (e.g. https://host/some/v1/); paths are relative to it, exactly as the contract names "
              "them. The requestBody schema must contain EVERY field of the contract's example request for that "
              "operation, nested exactly as in the example (e.g. an envelope object holding the service fields), with "
              "the example values as `example`. Leave out authentication/token endpoints: the phone agent never calls "
              "them (auth is not part of the tool). Answer with the JSON only.\n\nCONTRACT ("
              + path.name + "):\n" + path.read_text(errors="replace"))
    api = None
    for attempt in range(3):
        txt = chat([{"role": "user", "content": prompt}], purpose="case folder: service contract -> OpenAPI JSON"
                   + (f" (repair {attempt})" if attempt else ""), max_tokens=24000)
        txt = txt if isinstance(txt, str) else str(txt)
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            api = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            continue
        drop_auth(api)
        empty = [f"{meth.upper()} {pth}" for pth, ops in (api.get("paths") or {}).items() if isinstance(ops, dict)
                 for meth, op in ops.items() if isinstance(op, dict) and not _body_fields(op)]
        if not empty:
            break
        print(f"case: converted contract has operations without request fields: {empty}; asking again", flush=True)
        prompt += ("\n\nYOUR PREVIOUS ANSWER left these operations without any requestBody fields: " + ", ".join(empty)
                   + ". Every operation's example request in the contract has fields: include them all.")
    return api


def _body_fields(op):
    """All property names in an operation's JSON request body schema (nested)."""
    sch = (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    out, stack = [], [sch]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            out += list((x.get("properties") or {}).keys())
            stack += list((x.get("properties") or {}).values()) + [x.get("items")]
    return out


def drop_auth(api):
    """The phone agent never calls an auth/token endpoint: remove it from the tools (it is gateway plumbing)."""
    for pth in list((api.get("paths") or {})):
        if re.search(r"oauth|/token\b|/auth\b|/login\b", pth, re.I):
            api["paths"].pop(pth)
    return api


def _status(url):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return None


def resolve_base(api, mock_url):
    """The mock URL as the tools' base. When the mock URL has no path but the contract's server has one (/v1), probe
    the first operation on both and keep the base that does not answer 404 (default: the mock URL as given)."""
    import urllib.parse as up
    mock_url = mock_url.rstrip("/")
    old = ((api.get("servers") or [{}])[0] or {}).get("url") or ""
    op = up.urlparse(old).path.rstrip("/")
    paths = [p for p in (api.get("paths") or {}) if not re.search(r"oauth|/token\b|/auth\b|/login\b", p, re.I)]
    if op and not up.urlparse(mock_url).path.strip("/") and paths:
        root = with_base = 0                       # majority over up to 4 operations, so one odd path cannot decide
        for pth in paths[:4]:
            first = "/" + pth.split("{")[0].strip("/")
            a, b = _status(mock_url + first), _status(mock_url + op + first)
            root += a not in (None, 404); with_base += b not in (None, 404)
        if with_base > root:
            print(f"case: the mock answers under {op} ({with_base} of {min(4, len(paths))} operations): tools use {mock_url}{op}", flush=True)
            return mock_url + op
    return mock_url


def set_server(api, mock_url):
    if mock_url:
        old = ((api.get("servers") or [{}])[0] or {}).get("url")
        base = resolve_base(api, mock_url)
        api["servers"] = [{"url": base, "description": "mock of the bank's services (all tools call this)"}]
        if old:
            api.setdefault("info", {})["x-original-server"] = old
    return api


def _doc_date(p, txt):
    """The document's date: from the file name, else from its first lines ('' when none)."""
    for src in (p.name, txt[:600]):
        m = re.search(r"(20\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?([0-3]\d)", src)
        if m:
            return "-".join(m.groups())
        m = re.search(r"\b([0-3]?\d)[./]([01]?\d)[./](20\d\d)\b", src)
        if m:
            return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


RULES_ONE = ("You extract the rules a bank phone agent must follow from ONE document of a case folder. List EVERY rule "
             "the document states or implies, nothing invented: conversation stage and its condition, what the agent "
             "must do or say (copy required sentences VERBATIM in the document's own language), how numbers, digits, "
             "card/account numbers, dates, amounts and currencies are read aloud, which amounts/fields to read and "
             "which not, offers and their wording, what to do when a service/tool fails, times out or returns nothing "
             "(retry or not, transfer, closing), which tool to call when and with which values, refusals, identity, "
             "the closing. One rule per line, format:\n- [stage] when <condition>: <what the agent must do/say> "
             "(verbatim: \"...\")\nNo intro, no summary. If the document has no rule for the agent, answer: NONE.")
RULES_MERGE = ("Merge the rule lists extracted from the documents of one case folder into ONE digest for the builder of "
               "the phone agent. Keep EVERY distinct rule (merge duplicates), grouped by conversation stage in call "
               "order, plus sections for number/amount reading, service failures, tool usage and the closing. Keep "
               "verbatim sentences exactly. When documents disagree, the NEWER document (date given with each "
               "document; a later decision over an earlier brief) wins: keep the newer rule and add 'CONFLICT: <older "
               "source> said <...>; newer wins'. Format each rule as one line:\n- R<n> [stage] when <condition>: "
               "<must do/say> (verbatim: \"...\") (source: <file>, <date>)\nAnswer with the digest only, in markdown.")


DIGEST_EXTRACT_S = int(os.environ.get("BTB_DIGEST_EXTRACT_S", "150"))
DIGEST_MERGE_S = int(os.environ.get("BTB_DIGEST_MERGE_S", "150"))


def extract_rules(docs, out):
    """FIX A: one strong Azure call per text document (in parallel), then one merge call -> out/rules.md.
    docs: [(relative name, date, text)]. Returns the path, or None when the model calls fail."""
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, str(KIT / "btb"))
    from llm import chat

    def one(d):
        name, date, txt = d
        try:
            r = chat([{"role": "user", "content": RULES_ONE + f"\n\nDOCUMENT {name} (date: {date or 'unknown'}):\n" + txt[:60000]}],
                     tier="fast", purpose=f"case folder: rules of {name}", max_tokens=6000, temperature=0)
            return name, date, (r or "").strip()
        except Exception as e:  # noqa: BLE001
            print(f"case: rule extraction failed for {name}: {str(e)[:120]}", flush=True)
            return name, date, ""
    # hard time bounds: the whole build has 30 minutes; a slow model call must never stall it
    from concurrent.futures import wait
    ex = ThreadPoolExecutor(max_workers=14)
    futs = {ex.submit(one, d): d for d in docs}
    done, late = wait(futs, timeout=DIGEST_EXTRACT_S)
    per = [f.result() for f in done] + [(futs[f][0], futs[f][1], "") for f in late]
    if late:
        print(f"case: rule extraction: {len(late)} document(s) over {DIGEST_EXTRACT_S}s, skipped", flush=True)
    ex.shutdown(wait=False, cancel_futures=True)
    got = [(n, d, r) for n, d, r in per if r and r.strip().upper() != "NONE"]
    if not got:
        return None
    lists = "".join(f"\n\n### {n} (date: {d or 'unknown'})\n{r}" for n, d, r in got)
    mx = ThreadPoolExecutor(max_workers=1)
    fut = mx.submit(chat, [{"role": "user", "content": RULES_MERGE + "\n\nPER-DOCUMENT RULES:" + lists}], tier="strong",
                    purpose="case folder: merge the rules digest", max_tokens=16000, temperature=0, effort="low")
    try:
        merged = fut.result(timeout=DIGEST_MERGE_S)
    except Exception as e:  # noqa: BLE001  (timeout or model failure)
        print(f"case: rules merge not done in time or failed ({str(e)[:120] or 'timeout'}): keeping the per-document lists", flush=True)
        merged = lists
    mx.shutdown(wait=False, cancel_futures=True)
    path = out / "rules.md"
    path.write_text("# RULES digest of the case folder (every document; newer document wins on conflict)\n"
                    "Documents: " + ", ".join(f"{n} ({d or 'undated'})" for n, d, _ in per) + "\n\n" + merged.strip()
                    + "\n\n## Per-document lists (source detail)\n" + lists + "\n")
    return path


def prepare(folder, mock_url, slot):
    folder = pathlib.Path(folder).resolve()
    files = _files(folder)
    mds = [p for p in files if p.suffix.lower() == ".md"]
    brief = next((p for p in files if p.name.lower() == "brief.md"), None) or (max(mds, key=lambda p: p.stat().st_size) if mds else None)
    readme = next((p for p in files if p.name.lower() == "readme.md" and p != brief), None)
    api, contract_txt = find_contract(files)
    if api is None:
        if contract_txt is None:
            raise SystemExit(f"case folder {folder}: no service contract (OpenAPI json/yaml or a contract text) found")
        print(f"case: service contract {contract_txt.name} is not OpenAPI JSON: converting it (Azure)", flush=True)
        cached = KIT / "runs" / "case" / slot / "tools.json"
        if os.environ.get("BTB_REUSE_PREP") == "1" and cached.exists():
            print(f"case: reusing the converted contract of the previous run ({cached})", flush=True)
            api = json.loads(cached.read_text())
        else:
            api = contract_from_text(contract_txt)
    set_server(api, mock_url)
    out = KIT / "runs" / "case" / slot      # not out/: the build's clear_slot moves out/<slot>.* away
    out.mkdir(parents=True, exist_ok=True)
    tools = out / "tools.json"
    tools.write_text(json.dumps(api, indent=1, ensure_ascii=False))
    order = [p for p in (brief, readme) if p] + [p for p in files if p not in (brief, readme)]
    parts, images, convo_txt, docs = [], [], "", []
    for p in order:
        rel = p.relative_to(folder)
        if p.suffix.lower() in IMG_EXT:
            images.append(str(p))
            parts.append(f"\n\n===== FILE: {rel} (image; open it with the Read tool: {p}) =====\n")
            continue
        if not _is_text(p):
            parts.append(f"\n\n===== FILE: {rel} (binary, skipped) =====\n")
            continue
        txt = p.read_text(errors="replace")
        if p.suffix.lower() in (".json", ".yaml", ".yml") and re.search(r'"?(openapi|swagger)"?\s*:', txt[:2000]):
            parts.append(f"\n\n===== FILE: {rel} (the service contract: use the tool API file {tools}, same content with the mock URL) =====\n")
            continue
        # image references inside markdown: keep alt text + path (resolved)
        for alt, ref in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", txt):
            images.append(str((p.parent / ref).resolve()))
        if re.search(r"konuşma|konusma|conversation|example|örnek|ornek|dialog", str(rel), re.I):
            convo_txt += txt
        note = ""
        if p in (brief,):
            note = " (THE BRIEF: read first)"
        parts.append(f"\n\n===== FILE: {rel}{note} =====\n{txt}")
        if p not in (contract_txt,):
            docs.append((str(rel), _doc_date(p, txt), txt))
    bt = brief.read_text(errors="replace") if brief else ""
    lang = detect_language(bt + "\n" + convo_txt)
    head = (f"# CASE FOLDER {folder.name}\nAll documents of the case folder follow, each under its file name. "
            f"The service contract (tool API) is {tools} (servers[0].url is the bank-services mock every tool must call: "
            f"{mock_url or 'as given'}).\n{language_instruction(lang)}\n")
    if images:
        head += "Images in the folder (flow drawings etc.; open them with the Read tool): " + ", ".join(sorted(set(images))) + "\n"
    rules = None
    if docs and os.environ.get("BTB_NO_RULES") != "1":
        print(f"case: extracting the rules of {len(docs)} document(s) (Azure, parallel) + merge", flush=True)
        if os.environ.get("BTB_REUSE_PREP") == "1" and (out / "rules.md").exists():
            print(f"case: reusing the rules digest of the previous run ({out / 'rules.md'})", flush=True)
            rules = out / "rules.md"
        else:
            rules = extract_rules(docs, out)
    (out / "documents.json").write_text(json.dumps([str(folder / n) for n, _, _ in docs], ensure_ascii=False))
    if rules:
        head += (f"RULES DIGEST (primary spec, every document, newer wins on conflict): {rules}. Implement EVERY rule in it; "
                 "read the documents below for detail.\n")
    case = out / "case.md"
    case.write_text(head + "".join(parts))
    return str(case), str(tools), lang


if __name__ == "__main__":
    print(prepare(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else "x"))
