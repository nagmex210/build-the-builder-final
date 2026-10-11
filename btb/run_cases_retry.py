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
sys.argv = [str(ROOT / "tools" / "run_cases.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
