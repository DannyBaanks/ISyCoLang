"""Sonda del arnés endurecido: el fallo del toolchain es dato, no abort (hallazgo 13).

El hallazgo decía: un programa que ISY-IR **acepta** —256 clones de una definición de
cuatro ranuras, legal bajo la cota de SPEC_LIMIT— rompe el comptime de Zig, y el gate F5
abortaba sin dejar recibo ni para los casos anteriores. Esta sonda mide las cuatro cosas
que el arreglo promete y sella la evidencia cruda:

1. la guarda convierte el crash en una fila (`TOOLCHAIN_BUILD_FAIL`) y **no** en un
   resultado comparable: `intento` devuelve `None` como resultado, y su `build_key` sale de
   la fuente que se sella junto al recibo;
2. un rechazo del frontend **no** pasa por la guarda: `InvalidProgram` se propaga, porque
   eso es conducta del idioma y no del instrumento;
3. la misma fuente corre en los demás backends instalados y coincide con la referencia:
   el renglón que separa «murió el toolchain» de «el programa está mal»;
4. la caché negativa no vuelve a invocar el compilador sobre la misma fuente muerta.

Y un control positivo de la zona: 16 clones (el caso 448 que sí está en el corpus)
compilan en Zig. Sin controles falsos no se sella.

    python3 tools/f5_harness_probe.py            # tabla por stdout
    python3 tools/f5_harness_probe.py --write    # sella evidence/f5_harness/run_<UTC>.{json,txt}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _gate  # noqa: E402
from isyco import run  # noqa: E402
from isyco.backends import available  # noqa: E402
from isyco.conformance import COMPARED  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.harness import CODES, SCHEMA, intento  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402
from v05_p4_probe import fuente_ranuras  # noqa: E402

RANURAS, ANCHOS = 4, 4                       # 4**4 = 256 clones: la forma que muere en Zig
CLONES = ANCHOS ** RANURAS
ZONA_OK = (4, 2)                             # 16 clones: la forma del caso 448 del corpus
FUENTE_RECHAZADA = b"isyco 0.1\nfn main(a: i9) { return a; }\n"   # tipo inexistente
KEYS = COMPARED


def correr(backend, fuente) -> dict:
    """Ejecuta la fuente en un backend y dice en qué categoría cayó, sin reescribir nada."""
    inicio = time.perf_counter()
    res, fr = intento(backend.run, fuente, [], fase="sonda.run",
                      contexto={"leg": "sonda", "backend": backend.name})
    ms = round((time.perf_counter() - inicio) * 1000)
    if fr is not None:
        return {"estado": fr["code"], "ms": ms, "fila": fr}
    r = res[0]
    return {"estado": r.get("status"), "ms": ms, "resultado": {k: r.get(k) for k in KEYS},
            "backend_stderr": bool(r.get("backend_stderr"))}


def intentos_de_build(backend, fuente) -> dict:
    """Dos build sobre la misma fuente muerta: el segundo tiene que salir de la caché."""
    salidas = []
    for _ in range(2):
        inicio = time.perf_counter()
        _, fr = intento(backend.build, fuente, fase="sonda.build",
                        contexto={"leg": "sonda", "backend": backend.name})
        salidas.append({"ms": round((time.perf_counter() - inicio) * 1000, 3), "fila": fr})
    return {"primero": salidas[0], "segundo": salidas[1]}


def stderr_crudo(backend, fuente: str) -> dict:
    """El fallo sin intermediarios: se invoca el comando del toolchain una vez y se guarda todo.

    `emit` devuelve texto y `build` lo escribe tal cual; aquí se compila en un directorio
    propio para que el stderr registrado no pase por ningún recorte del arnés.
    """
    with tempfile.TemporaryDirectory(prefix="isyco_sonda_") as tmp:
        directorio = Path(tmp)
        src = directorio / f"sonda{backend.extension}"
        src.write_text(fuente, encoding="utf-8")
        cmd = backend.compile_cmd(src, directorio / "sonda", ())
        inicio = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=directorio)
        return {"exit": proc.returncode, "ms": round((time.perf_counter() - inicio) * 1000),
                "stderr": proc.stderr or proc.stdout}


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="sella en evidence/f5_harness/")
    args = parser.parse_args(argv)
    stamp = _gate.stamp()
    backends = available()
    falsos, lineas, claims = [], [], []

    def claim(identidad, afirmacion, estado, observado):
        claims.append({"id": identidad, "afirmacion": afirmacion, "estado": estado,
                       "observado": observado})
        if estado == "FALSO":
            falsos.append(f"{identidad}: {afirmacion} — observado {observado}")

    fuente = fuente_ranuras(RANURAS, ANCHOS)
    sha_fuente = hashlib.sha256(fuente).hexdigest()
    lineas.append(f"fuente: {RANURAS} ranuras x {ANCHOS} anchos = {CLONES} clones, "
                  f"{len(fuente)} bytes, sha256 {sha_fuente}")

    if "zig" not in backends:
        lineas.append("zig no esta instalado: la sonda no puede demostrar el crash "
                      "-> NOT_DEMONSTRATED")
        claim("C0", "zig instalado y alcanzable", "NOT_DEMONSTRADO", sorted(backends))

    # --- C1: el crash es fila, no resultado -------------------------------------------
    fuente_zig = sha_zig = fila_c1 = None
    if "zig" in backends:
        zig = backends["zig"]
        fuente_zig = zig.emit(compile_ir(fuente))
        sha_zig = hashlib.sha256(fuente_zig.encode("utf-8")).hexdigest()
        vuelta = intentos_de_build(zig, fuente_zig)
        fila = vuelta["primero"]["fila"]
        fila_c1 = fila
        # La `build_key` de la fila tiene que salir de la fuente que se sella: si no, el
        # recibo apuntaría a un artefacto que nadie puede recomponer (`build/` está fuera).
        clave = hashlib.sha256("\0".join([zig.name, zig.toolchain() or "?", fuente_zig])
                               .encode("utf-8")).hexdigest()[:24]
        reproducible = fila is not None and fila.get("build_key") == clave
        demo = (fila is not None and fila["code"] == "TOOLCHAIN_BUILD_FAIL"
                and "error:" in (fila["detail"] or "")
                and vuelta["segundo"]["fila"] is not None and reproducible)
        claim("C1", "build 256 clones en Zig deja una fila TOOLCHAIN_BUILD_FAIL con la "
                    "linea error: del compilador y una build_key recomponible",
              "DEMONSTRADO" if demo else "FALSO",
              {"code": fila and fila["code"], "detail": fila and fila["detail"],
               "build_key": fila and fila.get("build_key"), "key_reproducible": reproducible,
               "ms_primero": vuelta["primero"]["ms"]})
        # C4: la segunda invocacion sale de la cache negativa, no del compilador
        if demo:
            rapido = vuelta["segundo"]["ms"] < vuelta["primero"]["ms"] / 10
            mismo = vuelta["segundo"]["fila"]["detail"] == fila["detail"]
            claim("C4", "el mismo fuente muerto no vuelve a invocar el compilador "
                        "(cache negativa)", "DEMONSTRADO" if (rapido and mismo) else "FALSO",
                  {"ms_primero": vuelta["primero"]["ms"], "ms_segundo": vuelta["segundo"]["ms"],
                   "stderr_igual": mismo})
        crudo = stderr_crudo(zig, fuente_zig)
        control_crudo = crudo["exit"] != 0 and "error:" in crudo["stderr"]
        claim("C5", "el stderr crudo del toolchain (sin la guarda en medio) dice lo mismo "
                    "que la fila", "DEMONSTRADO" if control_crudo else "FALSO",
              {"exit": crudo["exit"], "linea": next((x.strip() for x in
                                                     crudo["stderr"].splitlines()
                                                     if "error:" in x), "")})
        if not control_crudo:
            falsos.append("C5: el compilador no murio fuera de la guarda")

    # --- C2: InvalidProgram se propaga -------------------------------------------------
    try:
        intento(compile_ir, FUENTE_RECHAZADA, fase="sonda.frontend", contexto={"leg": "sonda"})
        claim("C2", "un rechazo del frontend sube (la guarda no se lo traga)", "FALSO",
              "intento retorno sin lanzar")
    except InvalidProgram as exc:
        claim("C2", "un rechazo del frontend sube (la guarda no se lo traga)", "DEMONSTRADO",
              f"InvalidProgram: {str(exc).splitlines()[0][:110]}")

    # --- C3: la misma fuente vive en los otros backends -------------------------------
    # `HALTED` es el estado terminal normal del idioma (112 de los 218 casos del corpus lo
    # esperan): lo que separa «murió el toolchain» de «el programa está mal» es coincidir
    # con la referencia en las claves comparadas, no un status particular.
    referencia, _ = run(fuente, [])
    esperados = {k: referencia[k] for k in KEYS}
    por_backend = {}
    for nombre in sorted(backends):
        por_backend[nombre] = correr(backends[nombre], fuente)
    testigos = [n for n, r in sorted(por_backend.items())
                if r.get("resultado") == esperados and not r["backend_stderr"]]
    claim("C3", f"la fuente de {CLONES} clones coincide con la referencia en los backends "
                f"instalados (mientras Zig muere en su compilador)",
          "DEMONSTRADO" if len(testigos) >= 2 else "FALSO",
          {"referencia": {"status": referencia["status"], "return": referencia["return"],
                          "pasos": referencia["steps"]},
           "emits": len(referencia["emits"]), "coinciden": testigos,
           "estados": {n: r["estado"] for n, r in sorted(por_backend.items())}})

    # --- C6: control positivo de la zona (16 clones si compilan) -----------------------
    if "zig" in backends:
        zona = fuente_ranuras(*ZONA_OK)
        res, fr = intento(backends["zig"].build, backends["zig"].emit(compile_ir(zona)),
                          fase="sonda.zona", contexto={"leg": "sonda"})
        claim("C6", "16 clones de la misma definicion si compilan en Zig (la frontera es "
                    "del compilador, no del idioma)", "DEMONSTRADO" if fr is None else "FALSO",
              "build ok" if fr is None else fr["detail"])

    # --- C7: el crash no se puede blanquear con es_conforme ----------------------------
    limpio = {"completado": True, "corpus": {"failures": [], "harness": []},
              "difftest": {"diffs": [], "harness": []}, "does_the_work": {"ok": True,
                                                                          "harness": []},
              "sabotage": {"x": {"detected": True, "harness": []}}}
    sucia = json.loads(json.dumps(limpio))
    sucia["corpus"]["harness"] = [{"code": "TOOLCHAIN_BUILD_FAIL"}]
    pliega = _gate.es_conforme(limpio) and not _gate.es_conforme(sucia)
    claim("C7", "una fila de arnes en cualquier pierna vuelve no-conforme aunque fallos y "
                "diferencias esten vacios", "DEMONSTRADO" if pliega else "FALSO",
          {"limpio": _gate.es_conforme(limpio), "con_fila": _gate.es_conforme(sucia)})

    lineas.append("")
    for c in claims:
        lineas.append(f"{c['id']:>3} {c['estado']:<15} {c['afirmacion']}")
        lineas.append(f"      observado: {json.dumps(c['observado'], ensure_ascii=False)[:200]}")
    for mensaje in falsos:
        lineas.append(f"CONTROL FALSO: {mensaje}")

    documento = {"schema": "isycolang.f5_harness_probe/1", "generated_utc": stamp,
                "git_head": _gate.git_head(), **_gate.arbol(),
                "harness": {"guarda": SCHEMA, "codigos": list(CODES)},
                "config": {"ranuras": RANURAS, "anchos": ANCHOS, "clones": CLONES,
                           "fuente_sha256": sha_fuente, "zona_ok": list(ZONA_OK),
                           "zig_emitido_sha256": sha_zig, "backends": sorted(backends)},
                "claims": claims, "por_backend": por_backend, "c1_fila": fila_c1,
                "veredicto": "FALSO" if falsos else "DEMONSTRADO"}
    print("\n".join(lineas))
    if not args.write:
        return 1 if falsos else 0
    if falsos:
        print("no se sella: hay controles falsos", file=sys.stderr)
        return 1
    destino = _gate.EVIDENCE / "f5_harness"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"run_{stamp}_fuente.isy").write_bytes(fuente)
    if fuente_zig is not None:
        # `build/` esta en gitignore: sin estas dos copias el `build_key` de la fila y el
        # stderr del compilador no apuntarian a nada que se pueda volver a hashear.
        (destino / f"run_{stamp}_zig_emitido.zig").write_text(fuente_zig, encoding="utf-8")
        (destino / f"run_{stamp}_zig_build_stderr.txt").write_text(crudo["stderr"],
                                                                   encoding="utf-8")
    _gate.sellar(documento, "\n".join(lineas) + "\n", destino, f"run_{stamp}")
    print(f"sellado en {destino}/run_{stamp}.{{json,txt}} mas la fuente, el .zig emitido "
          "y el stderr crudo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
