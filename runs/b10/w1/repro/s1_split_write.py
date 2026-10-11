import os, pathlib
KIT = os.environ.get('KIT') or str(pathlib.Path(__file__).resolve().parents[4])
import os, io, sys
os.environ["FREYA_API_KEY"] = "abcd1234efgh5678ijkl"
sys.path.insert(0, KIT + '/btb'); from scrub import Redacting
buf = io.StringIO(); r = Redacting(buf)
r.write("key=abcd1234ef"); r.write("gh5678ijkl\n")
print(repr(buf.getvalue())); assert "abcd1234efgh5678ijkl" not in buf.getvalue(), "secret leaked across two write() calls"
