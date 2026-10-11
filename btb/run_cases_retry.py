"""tools/run_cases.py with retries on transient platform errors (b9: a 503 'API key validation is temporarily
unavailable' while polling a simulation killed a 15-min official run). GETs retry on any 5xx; a POST retries only
on 503 (rejected before it reached the handler, so no duplicate simulation)."""
import runpy, sys, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import freya
_api = freya.api
def api(method, path, body=None, **params):
    for i in range(12):
        try:
            return _api(method, path, body, **params)
        except RuntimeError as e:
            code = str(e).split("-> ")[-1][:3]
            if not code.startswith("5") or (method != "GET" and code != "503") or i == 11: raise
            print(f"[retry] {method} {path} -> {code}, retry {i + 1}", file=sys.stderr); time.sleep(10 + 5 * i)
freya.api = api
import score                                   # the mock bank answered non-JSON for a minute (b10 merge): retry its calls too
_http = score.http
def http(path, body=None):
    for i in range(8):
        try:
            return _http(path, body)
        except Exception as e:  # noqa: BLE001
            if i == 7: raise
            print(f"[retry] bank {path} -> {str(e)[:80]}, retry {i + 1}", file=sys.stderr); time.sleep(10 + 5 * i)
score.http = http
sys.argv = [str(ROOT / "tools" / "run_cases.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
