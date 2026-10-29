"""Backend C bajo UBSan+ASan con el corpus v0.3 y el diferencial de strings.

Uso: python3 tools/c_sanitize_v03.py gcc|clang
Imprime el resumen; la evidencia se guarda redirigiendo la salida a un archivo nuevo.
"""
from pathlib import Path
import os, sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)
from functools import partial
from isyco import run
from isyco.backends import c as C
from isyco.conformance import load_corpus
from isyco.difftest import compare_str
SAN = ("-fsanitize=undefined,address", "-fno-sanitize-recover=all")
K = ("status", "code", "emits", "return", "steps")
cc = sys.argv[1]
os.environ["ISYCO_CC"] = cc
C.BACKEND._toolchain_version = None
cases = load_corpus(Path("programs/conformance_v0.3"))
bad = []
for c in cases:
    ref, _ = run(c["program"], c["input"], c.get("limits"))
    got, _ = C.run_c(c["program"], c["input"], c.get("limits"), extra_flags=SAN)
    if {k: ref[k] for k in K} != {k: got.get(k) for k in K} or got.get("backend_stderr"):
        bad.append((c["name"], got.get("status"), (got.get("backend_stderr") or "")[:300]))
rep = compare_str(partial(C.run_c, extra_flags=SAN), per_op=4)
print(cc, "corpus v0.3", len(cases) - len(bad), "/", len(cases), "| str difftest", rep["runs"], "runs,", len(rep["diffs"]), "diffs")
for b in bad[:5]: print(" ", b)
for d in rep["diffs"][:5]: print(" ", d["op"], d["input"], d["backend"], (d["stderr"] or "")[:300])
sys.exit(1 if bad or rep["diffs"] else 0)
