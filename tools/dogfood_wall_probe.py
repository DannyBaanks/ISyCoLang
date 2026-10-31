"""Sonda del muro de cabecera (docs/DOGFOOD_2026-10-30.md §7).

Pregunta: ¿los rechazos `ir0.2` de COBOL son víctimas de la etiqueta del header o
de contenido que el propio frontend exige en 0.3/0.4? Método: copiar cada
programa reescribiendo SOLO su primera línea con `isyco 0.2` y mirar tres cosas:
si el frontend aún lo acepta, qué schema produce y si COBOL lo ejecuta igual que
la referencia.

Corrida: python3 tools/dogfood_wall_probe.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from isyco.backends import available              # noqa: E402
from isyco.interp import DEFAULT_LIMITS, run      # noqa: E402
from isyco.ir_interp import compile_ir            # noqa: E402

KEYS = ("status", "code", "emits", "return")
# (etiqueta, [archivos .isy relativos a programs/], principal, entradas)
MODULAR = [("301_basic", "conformance_v0.4/301_basic"),
           ("313_same_names", "conformance_v0.4/313_same_names"),
           ("314_runtime_error_in_module", "conformance_v0.4/314_runtime_error_in_module"),
           ("318_recursion_in_module", "conformance_v0.4/318_recursion_in_module"),
           ("321_limit_across_modules", "conformance_v0.4/321_limit_across_modules"),
           ("324_module_main", "conformance_v0.4/324_module_main"),
           ("326_pub_in_main", "conformance_v0.4/326_pub_in_main"),
           ("327_qualified_call_stmt", "conformance_v0.4/327_qualified_call_stmt"),
           ("328_private_helper_inside", "conformance_v0.4/328_private_helper_inside")]

CASES = [("248_array_equality", ["conformance_v0.3/248_array_equality.isy"],
          "248_array_equality.isy", []),
         ("253_emit_array", ["conformance_v0.3/253_emit_array.isy"], "253_emit_array.isy", [])] + [
        (name, [str(p.relative_to(ROOT / "programs"))
                for p in (ROOT / "programs" / folder).rglob("*.isy")], "main.isy", [])
        for name, folder in MODULAR] + [
        ("03_criba (sin str/struct/import)", ["dogfood/03_criba.isy"], "03_criba.isy", ["100"])]
def relabel(scratch, label, files, main_name, ver):
    """Copia el programa entero con la cabecera puesta a `ver` en todos sus archivos."""
    out = scratch / label.split(" ")[0]
    out.mkdir(parents=True, exist_ok=True)
    for rel in files:
        src = ROOT / "programs" / rel
        txt = src.read_text(encoding="utf-8")
        (out / src.name).write_text("\n".join([f"isyco {ver}"] + txt.splitlines()[1:]) + "\n",
                                    encoding="utf-8")
    return out / main_name


def main() -> int:
    print("== ¿etiqueta o contenido? cada programa reescrito con `isyco 0.2` ==")
    scratch = Path(tempfile.mkdtemp(prefix="dogfood_wall_probe_"))
    try:
        for label, files, main_name, inputs in CASES:
            data = relabel(scratch, label, files, main_name, "0.2").read_bytes()
            ref, _ = run(data, inputs, DEFAULT_LIMITS)
            if ref["status"] == "INVALID_PROGRAM":
                # El rechazo viene del lexer/checker con la cabecera bajada: es una
                # regla de contenido (import, pub, == entre arreglos, emit de arreglo),
                # no la etiqueta del schema.
                print(f"{label:34s} RECHAZADO por contenido: INVALID_PROGRAM({ref['code']})")
                continue
            got, _ = available()["cobol"].run(data, inputs, DEFAULT_LIMITS)
            same = {k: ref[k] for k in KEYS} == {k: got.get(k) for k in KEYS}
            print(f"{label:34s} aceptado: schema={compile_ir(data)['schema']} "
                  f"ref={ref['status']}/{ref['code']} cobol={got.get('status')}/{got.get('code')} "
                  f"igual={same} emits={got.get('emits')}")
    finally:
        shutil.rmtree(scratch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
