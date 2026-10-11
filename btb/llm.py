"""Azure OpenAI chat with a fallback chain. Standard library only.

    from btb.llm import chat
    text = chat([{"role": "user", "content": "hi"}], tier="strong")   # or "fast"

Key: AZURE_KEY (whodoo-ai) or, on the box, Parameter Store /btb/azure_key.
Every call is appended to the trace file in BTB_TRACE (model + purpose), as the event rules require.
"""
import json, os, subprocess, time, urllib.request, urllib.error

ENDPOINT = os.environ.get("AZURE_ENDPOINT", "https://whodoo-ai.cognitiveservices.azure.com")
URL = ENDPOINT + "/models/chat/completions?api-version=2024-05-01-preview"
# reasoning models take max_completion_tokens; chat models take temperature + max_tokens
CHAINS = {
    "strong": ["gpt-6-astra", "gpt-6-luna", "gpt-4.1-mini"],
    "fast": ["gpt-4.1-mini", "gpt-6-luna", "gpt-6-astra"],
}
REASONING = {"gpt-6-astra", "gpt-6-luna", "gpt-5-mini"}
_KEY = None


def _key():
    global _KEY
    if _KEY:
        return _KEY
    _KEY = os.environ.get("AZURE_KEY")
    if not _KEY:
        _KEY = subprocess.run(["aws", "ssm", "get-parameter", "--region", "eu-central-1", "--name", "/btb/azure_key",
                               "--with-decryption", "--query", "Parameter.Value", "--output", "text"],
                              capture_output=True, text=True, check=True).stdout.strip()
    return _KEY


def trace(event: dict):
    p = os.environ.get("BTB_TRACE")
    if p:
        with open(p, "a") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event}) + "\n")


def chat(messages, tier="strong", purpose="", max_tokens=4000, temperature=0.7, effort="medium"):
    last = None
    for i, model in enumerate(CHAINS[tier]):
        if last:      # the previous model failed: that call is in the trace too, with why we fell back
            trace({"model": CHAINS[tier][i - 1], "purpose": f"{purpose} [FAILED: {last[:120]}; falling back to {model}]"})
        body = {"model": model, "messages": messages}
        if model in REASONING:
            body.update(max_completion_tokens=max_tokens + 8000, reasoning_effort=effort)
        else:
            body.update(max_tokens=max_tokens, temperature=temperature)
        for attempt in range(3):
            try:
                req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                             headers={"api-key": _key(), "content-type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.load(r)
                text = (d["choices"][0]["message"].get("content") or "").strip()
                if not text:
                    raise RuntimeError("empty content")
                trace({"model": model, "purpose": purpose})
                return text
            except urllib.error.HTTPError as e:
                last = f"{model} {e.code}: {e.read().decode()[:300]}"
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(2 + 4 * attempt)
                    continue
                break
            except Exception as e:  # noqa: BLE001
                last = f"{model}: {e}"
                time.sleep(2)
    trace({"model": CHAINS[tier][-1], "purpose": f"{purpose} [FAILED: {(last or '')[:120]}; no model left]"})
    raise RuntimeError(f"all models failed: {last}")


def chat_json(messages, **kw):
    """chat() and parse the first {...} block of the reply (no forced JSON mode: reasoning models return empty)."""
    text = chat(messages, **kw)
    s, e = text.find("{"), text.rfind("}")
    return json.loads(text[s:e + 1])
