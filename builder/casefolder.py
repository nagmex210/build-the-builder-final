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


def detect_language(text):
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
              "response schemas. Keep names exactly as in the contract. Answer with the JSON only.\n\nCONTRACT ("
              + path.name + "):\n" + path.read_text(errors="replace"))
    txt = chat([{"role": "user", "content": prompt}], purpose="case folder: service contract -> OpenAPI JSON", max_tokens=16000)
    txt = txt if isinstance(txt, str) else str(txt)
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0))


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
    paths = list(api.get("paths") or {})
    if op and not up.urlparse(mock_url).path.strip("/") and paths:
        first = "/" + paths[0].split("{")[0].strip("/")
        a, b = _status(mock_url + first), _status(mock_url + op + first)
        if a == 404 and b not in (None, 404):
            print(f"case: {mock_url}{first} answers 404, {mock_url}{op}{first} answers {b}: tools use {mock_url}{op}", flush=True)
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
        api = contract_from_text(contract_txt)
    set_server(api, mock_url)
    out = KIT / "runs" / "case" / slot      # not out/: the build's clear_slot moves out/<slot>.* away
    out.mkdir(parents=True, exist_ok=True)
    tools = out / "tools.json"
    tools.write_text(json.dumps(api, indent=1, ensure_ascii=False))
    order = [p for p in (brief, readme) if p] + [p for p in files if p not in (brief, readme)]
    parts, images, convo_txt = [], [], ""
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
    bt = brief.read_text(errors="replace") if brief else ""
    lang = detect_language(bt + "\n" + convo_txt)
    head = (f"# CASE FOLDER {folder.name}\nAll documents of the case folder follow, each under its file name. "
            f"The service contract (tool API) is {tools} (servers[0].url is the bank-services mock every tool must call: "
            f"{mock_url or 'as given'}).\n{language_instruction(lang)}\n")
    if images:
        head += "Images in the folder (flow drawings etc.; open them with the Read tool): " + ", ".join(sorted(set(images))) + "\n"
    case = out / "case.md"
    case.write_text(head + "".join(parts))
    return str(case), str(tools), lang


if __name__ == "__main__":
    print(prepare(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else "x"))
