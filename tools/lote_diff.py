"""Coteja dos lotes de gates hoja por hoja: qué cambió entre un recibo y el siguiente.

Los lotes de 216, 218 y 224 se cotejaron así a mano y la cifra quedó en prosa
(`spec/CORE_v0.5.md` §9). Esta herramienta hace la misma cuenta y la sella, para que «no
regresión contra el lote anterior» sea un recibo y no una frase.

Qué mide, por gate (F2, F3, F4, F5):

- aplana los dos JSON a hojas `ruta -> valor`. Los renglones de una lista que llevan nombre
  se indexan por **identidad** —el caso, y caso más nivel de traza en F3— y no por posición:
  un caso nuevo en medio no desplaza a los demás;
- cuenta hojas compartidas, distintas, altas (solo en el lote nuevo) y bajas (solo en el viejo);
- **veredicto**: `SIN_REGRESION` si no hay bajas y toda hoja distinta es sello, contador,
  costo o toolchain (`PERMITIDAS`). Una hoja distinta fuera de esa lista —el `status` de un
  caso, un `emit`, un paso— es `REGRESION` y se lista entera.

Control anti-fake: antes de cotejar se sabotea una copia del lote nuevo de F2 (se cambia el
resultado de un caso y se borra otro) y el cotejo tiene que salir `REGRESION` con una hoja
prohibida y bajas. Si el sabotaje pasa, la herramienta no sirve y lo dice.

Uso:
    python3 tools/lote_diff.py --viejo 2026-11-03T232115Z,2026-11-03T232115Z,2026-11-03T232116Z,2026-11-03T232750Z \
                               --nuevo 2026-11-12T042323Z,2026-11-12T042323Z,2026-11-12T042330Z,2026-11-12T042934Z \
                               [--write]

Los cuatro sellos van en el orden F2, F3, F4, F5.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _gate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "isyco-lote-diff/1"

GATES = (("F2", "conformance", "run_"), ("F3", "ir", "gate_"),
         ("F4", "c", "gate_"), ("F5", "backends", "gate_"))

#: Campo final de una hoja que puede cambiar entre lotes sin ser regresión.
PERMITIDAS = {
    "sello": {"generated_utc", "git_head", "git_head_end"},
    "contador": {"total", "passed", "equal", "comparisons", "programs_lowered_to_ir",
                 "cases", "intentados", "reference_vs_backend_ok", "expected_vs_reference_ok"},
    "costo": {"wall_ms_total", "user_ms_total", "sys_ms_total", "max_rss_kb_max",
              "rss_measured_runs", "runs_measured"},
    "toolchain": {"python", "toolchain"},
}
CLASE = {campo: clase for clase, campos in PERMITIDAS.items() for campo in campos}


def hojas(o, ruta=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from hojas(v, ruta + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            clave = i
            if isinstance(v, dict):
                nombre = v.get("name") or v.get("case")
                if nombre is not None:
                    clave = f"{nombre}|{v.get('trace') or v.get('level') or v.get('trace_level') or ''}"
            yield from hojas(v, ruta + (clave,))
    else:
        yield ruta, o


def campo(ruta) -> str:
    """El nombre de campo de la hoja: el último tramo que no es índice de lista."""
    for tramo in reversed(ruta):
        if isinstance(tramo, str) and "|" not in tramo:
            return tramo
    return ""


def cotejar(viejo: dict, nuevo: dict) -> dict:
    a, b = dict(hojas(viejo)), dict(hojas(nuevo))
    compartidas = set(a) & set(b)
    distintas = sorted((r for r in compartidas if a[r] != b[r]), key=repr)
    clases = Counter(CLASE.get(campo(r), "PROHIBIDA") for r in distintas)
    prohibidas = [{"ruta": list(r), "viejo": a[r], "nuevo": b[r]}
                  for r in distintas if campo(r) not in CLASE]
    bajas = sorted((list(r) for r in set(a) - set(b)), key=repr)
    return {
        "compartidas": len(compartidas), "distintas": len(distintas),
        "altas": len(set(b) - set(a)), "bajas": len(bajas),
        "distintas_por_clase": dict(sorted(clases.items())),
        "distintas_por_campo": dict(sorted(Counter(campo(r) for r in distintas).items())),
        "prohibidas": prohibidas, "bajas_rutas": bajas[:50],
        "veredicto": "SIN_REGRESION" if not prohibidas and not bajas else "REGRESION",
    }


def sabotear(nuevo: dict) -> dict:
    """Cambia el resultado de un caso y borra otro: lo que el cotejo tiene que ver."""
    roto = copy.deepcopy(nuevo)
    lista = next(v for v in roto.values()
                 if isinstance(v, list) and v and isinstance(v[0], dict) and "name" in v[0])
    victima = next(k for k, v in lista[0].items()
                   if k not in ("name",) and k not in CLASE and not isinstance(v, (dict, list)))
    lista[0][victima] = "SABOTEADO"
    del lista[1]
    return roto


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--viejo", required=True, help="cuatro sellos F2,F3,F4,F5 del lote viejo")
    ap.add_argument("--nuevo", required=True, help="cuatro sellos F2,F3,F4,F5 del lote nuevo")
    ap.add_argument("--write", action="store_true", help="sella en evidence/lotes/")
    args = ap.parse_args(argv)
    viejos, nuevos = args.viejo.split(","), args.nuevo.split(",")
    if len(viejos) != 4 or len(nuevos) != 4:
        ap.error("cada lote son cuatro sellos: F2,F3,F4,F5")

    stamp = _gate.stamp()
    procedencia = _gate.arbol()
    lineas = []

    def di(texto=""):
        print(texto)
        lineas.append(texto)

    gates, cargados = {}, {}
    for (gate, carpeta, prefijo), sv, sn in zip(GATES, viejos, nuevos):
        par = {}
        for lado, sello in (("viejo", sv), ("nuevo", sn)):
            ruta = _gate.EVIDENCE / carpeta / f"{prefijo}{sello}.json"
            datos = ruta.read_bytes()
            par[lado] = {"recibo": f"evidence/{carpeta}/{ruta.name}",
                         "sha256": hashlib.sha256(datos).hexdigest()}
            cargados[gate, lado] = json.loads(datos)
        resultado = cotejar(cargados[gate, "viejo"], cargados[gate, "nuevo"])
        gates[gate] = {**par, **resultado}
        di(f"{gate}: {resultado['veredicto']} — compartidas {resultado['compartidas']}, "
           f"distintas {resultado['distintas']} {resultado['distintas_por_clase']}, "
           f"altas {resultado['altas']}, bajas {resultado['bajas']}")
        for p in resultado["prohibidas"][:10]:
            di(f"    PROHIBIDA {p['ruta']}: {p['viejo']!r} -> {p['nuevo']!r}")

    control = cotejar(cargados["F2", "viejo"], sabotear(cargados["F2", "nuevo"]))
    detectado = (control["veredicto"] == "REGRESION" and bool(control["prohibidas"])
                 and control["bajas"] > 0)
    di(f"sabotaje (un resultado cambiado y un caso borrado en F2): "
       f"{'DETECTADO' if detectado else 'NO DETECTADO'} — {len(control['prohibidas'])} "
       f"prohibidas, {control['bajas']} bajas")

    ok = detectado and all(g["veredicto"] == "SIN_REGRESION" for g in gates.values())
    di(f"veredicto: {'PASS' if ok else 'FAIL'} ({procedencia['veredicto_arbol']})")

    documento = {
        "schema": SCHEMA, "generated_utc": stamp, "git_head": _gate.git_head(), **procedencia,
        "permitidas": {k: sorted(v) for k, v in PERMITIDAS.items()},
        "gates": gates,
        "sabotaje": {"detectado": detectado, "prohibidas": len(control["prohibidas"]),
                     "bajas": control["bajas"]},
        "verdict": "PASS" if ok else "FAIL",
        "no_mide": ["que los dos lotes salieran del mismo anfitrión ni del mismo toolchain: "
                    "las hojas `python` y `toolchain` lo registran cuando difieren",
                    "nada que el recibo no guarde: F4 no lleva renglones por caso"],
    }
    if args.write:
        res = _gate.sellar(documento, "\n".join(lineas) + "\n", _gate.EVIDENCE / "lotes",
                           f"run_{stamp}")
        print(f"sellado: {res['out']} sha256={res['sha256']} ({res['sumados']} archivos sumados)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
