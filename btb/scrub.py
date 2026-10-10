"""Redact secrets from build output and logs.

    python3 btb/scrub.py <file> [<file> ...]      # scrub logs/traces in place, prints how many secrets were replaced

In code: `scrub(text)`, `scrub_file(path)`, and `Redacting(stream)` (build.py wraps sys.stdout/sys.stderr with it).
Replaces the values of the key variables below (as found in the environment) and anything that looks like a JWT,
an sk-... key or a Freya fak_... key with [REDACTED].
"""
import os, pathlib, re, sys

SECRET_VARS = ["FREYA_API_KEY", "FREYA_API_KEY_2", "AZURE_KEY", "FREYA_BANK_TEAM_KEY", "CLAUDE_CODE_OAUTH_TOKEN",
               "ANTHROPIC_API_KEY"]
PATTERNS = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"   # JWT
                      r"|sk-[A-Za-z0-9_-]{16,}"                                       # sk-..., sk-ant-...
                      r"|fak_[A-Za-z0-9_-]{16,}")                                     # Freya API key
MARK = "[REDACTED]"


def _values():
    vals = {os.environ.get(v, "").strip() for v in SECRET_VARS}
    return sorted((v for v in vals if len(v) >= 8), key=len, reverse=True)


def scrub(text):
    """Return (text with secrets replaced, number of replacements)."""
    n = 0
    for v in _values():
        if v in text:
            n += text.count(v)
            text = text.replace(v, MARK)
    text, k = PATTERNS.subn(MARK, text)
    return text, n + k


def scrub_file(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return 0
    text = p.read_text(errors="replace")
    new, n = scrub(text)
    if n:
        p.write_text(new)
    return n


class Redacting:
    """A text stream that scrubs everything written to it. Line-buffered writes (print) keep keys in one piece."""

    def __init__(self, stream):
        self._s = stream

    def write(self, s):
        return self._s.write(scrub(s)[0])

    def __getattr__(self, name):
        return getattr(self._s, name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    total = 0
    for f in sys.argv[1:]:
        n = scrub_file(f)
        total += n
        print(f"scrub: {f}: {n} secret(s) replaced")
    print(f"scrub: {total} in total")
