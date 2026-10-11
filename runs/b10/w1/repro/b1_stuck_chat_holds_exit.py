"""selftest.run_tests gives up on a stuck chat after `timeout`, but the chat's worker thread must not keep the build
process alive past that (ThreadPoolExecutor workers are joined at interpreter exit: the build then ends only when the
stuck chat ends, which can be many minutes after BUILD END under platform 5xx -> the 30-min cap is overrun)."""
import os, pathlib, subprocess, sys, time
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
child = f"""
import sys, time, contextlib
sys.path.insert(0, {KIT!r} + '/builder'); sys.path.insert(0, {KIT!r} + '/btb'); sys.path.insert(0, {KIT!r})
import selftest
selftest.run_one = lambda wid, s, lib: time.sleep(25)           # a chat stuck in 5xx retries
selftest.Workspace2 = lambda slot, wf: contextlib.nullcontext(('wf-x', 'test'))
selftest.calc_lib = lambda f: None
r = selftest.run_tests('x', {{}}, [{{'title': 't', 'cust': {{'id': 'c'}}}}], '/nonexistent', timeout=2, reps=1)
print('run_tests returned', r['rows'][0].get('harness_error'), flush=True)
"""
t = time.time()
subprocess.run([sys.executable, "-c", child], check=True, env={**os.environ, "FREYA_API_KEY": os.environ.get("FREYA_API_KEY", "x" * 20)})
dt = time.time() - t
print(f"process exited after {dt:.1f} s (run_tests timeout 2 s, stuck chat 25 s)")
assert dt < 12, "a stuck self-test chat held the build process open after run_tests returned"
