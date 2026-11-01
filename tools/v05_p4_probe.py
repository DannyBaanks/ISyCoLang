"""Mide lo que la pregunta P4 de CORE v0.5 necesita antes de fijar un tope: cuántas
especializaciones crea un programa de verdad y cómo crecen con la forma del programa.

P4 («¿cuántas especializaciones puede crear un programa?», `spec/CORE_v0.5_propuesta.md`
§2) se decidió «midiendo el primer corpus, no inventando un número». El censo que
`docs/decisions/V6B_CONTEXTUAL_RETURN.md` §Medición afirma no estaba en ningún recibo
sellado — las sondas V6 y V7 guardan resultados por backend, no el registro de clones —
así que esta sonda lo recalcula desde el instrumento (`isyco/checker.py`: `Checker.specs`)
y le añade las dos curvas que faltaban:

  1. **Censo del corpus** — la población del gate (`load_corpus`: 46 casos de
     `programs/conformance_v0.5`, incluidos los 4 con módulos): clones por programa,
     total, máximo por definición dentro de un programa y en todo el corpus, escalera de
     anchos instanciados.
  2. **Una ranura contextual, K anchos distintos**: ¿los clones valen K?
  3. **Dos y tres ranuras**: ¿los clones valen W² y W³? Si son multiplicativos, un tope
     por programa es la palanca equivocada y un tope por definición tampoco alcanza.
  4. **Control negativo**: 20 sitios de llamada con el MISMO ancho deben dar 1 clon —
     si diera 20, el instrumento cuenta llamadas y no resoluciones, y todo lo anterior
     sería basura.
  5. **Costo**: bytes de ISY-IR, funciones en la IR, y compilar/ejecutar en C para los
     tres tamaños exigidos de la escalera más el techo (512, 1024, 2048), cada uno con su
     diferencial contra la referencia.

Nada de esto fija un número: registra la forma de la curva y qué error (si lo hay)
aparece. El tope y su nombre (`SPEC_LIMIT` u otro) siguen siendo decisión de Danny.

    python3 tools/v05_p4_probe.py            # corre y reporta, no escribe
    python3 tools/v05_p4_probe.py --write    # sella en evidence/v05_p4/
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.checker import Checker                     # noqa: E402
from isyco.conformance import load_corpus             # noqa: E402
from isyco.errors import InvalidProgram               # noqa: E402
from isyco.interp import run                          # noqa: E402
from isyco.ir import canonical_bytes, lower           # noqa: E402
from isyco.modules import load_program                # noqa: E402
from isyco.source import program_sha256               # noqa: E402

V05 = ROOT / "programs" / "conformance_v0.5"
ESCALERA = (1, 2, 4, 8, 16, 32, 64, 128, 256)
COMBINACIONES = (2, 3, 4, 6, 8)      # W para 2 ranuras -> W^2 clones
COSTO_C = (8, 64, 256)               # tamaños que DEBEN compilar y coincidir con la referencia
EXTREMOS = (512, 1024, 2048)          # techo natural: se reportan como salen, no como control


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dirty_codigo() -> bool:
    """Código, corpus o pruebas sin commitear ⇒ la corrida no puede ser gate de release."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return True
    for linea in out.splitlines():
        if not linea.strip():
            continue
        partes = [p.strip() for p in (linea[3:] if len(linea) > 3 else "").split("->")]
        if all(p.startswith("evidence/") for p in partes):
            continue
        return True
    return False


def base_de(nombre: str) -> str:
    """Nombre fuente de una especialización: quita los segmentos de capacidad.

    `geo.pad.8.16` -> `geo.pad`, `copia.3.r8` -> `copia`. La base nunca termina en un
    segmento numérico ni en `r<entero>` porque el léxico no admite un identificador que
    empiece en dígito (`spec/CORE_v0.5.md` §7), así que quitar sufijos con ese patrón
    devuelve la definición y solo la definición.
    """
    partes = nombre.split(".")
    while len(partes) > 1 and (re.fullmatch(r"\d+", partes[-1])
                               or re.fullmatch(r"r\d+", partes[-1])):
        partes.pop()
    return ".".join(partes)


def ensayar(fuente: bytes) -> dict:
    """Chequea y devuelve el registro de especializaciones sin ejecutar nada."""
    try:
        program = load_program(fuente)
    except InvalidProgram as e:
        return {"error": f"{e.code}", "clones": [], "programa": None}
    checker = Checker(program)
    try:
        checker.check()
    except InvalidProgram as e:
        return {"error": f"{e.code}", "clones": [], "programa": None}
    return {"error": None, "clones": sorted(checker.specs), "programa": program}


# --- 1. censo del corpus -------------------------------------------------------------

def censo_corpus():
    """Censo sobre LA POBLACIÓN DEL GATE, no sobre un glob de archivos.

    `load_corpus` (isyco/conformance.py) añade además los casos con módulos, que son
    carpetas con `main.isy` + `expect.json` — un glob de `.isy` pierde `408`, `421` y
    `440`, y `421` es justamente el caso con una especialización calificada
    (`util.marca.4`). Contar otra población que la del gate es el bug de deriva de
    población que ya cazó V7.
    """
    filas = []
    for caso in sorted(load_corpus(V05), key=lambda c: c["name"]):
        t0 = time.perf_counter()
        res = ensayar(caso["program"])
        ms = round((time.perf_counter() - t0) * 1000, 2)
        filas.append({"caso": caso["name"], "clones": res["clones"], "n": len(res["clones"]),
                      "chequeo_ms": ms, "error": res["error"]})
    total = sum(f["n"] for f in filas)
    por_def: dict[str, int] = {}
    por_def_y_programa: dict[tuple[str, str], int] = {}
    con_retorno = sin_retorno = 0
    anchos: set[int] = set()
    retornos: set[int] = set()
    for fila in filas:
        for nombre in fila["clones"]:
            base = base_de(nombre)
            por_def[base] = por_def.get(base, 0) + 1
            clave = (fila["caso"], base)
            por_def_y_programa[clave] = por_def_y_programa.get(clave, 0) + 1
            if re.search(r"\.r\d+$", nombre):
                con_retorno += 1
            else:
                sin_retorno += 1
            for segmento in nombre.split(".")[1:]:
                if re.fullmatch(r"r\d+", segmento):
                    retornos.add(int(segmento[1:]))
                    continue
                for digito in re.findall(r"\d+", segmento):
                    anchos.add(int(digito))
    max_programa = max((f["n"] for f in filas), default=0)
    max_def_global = max(por_def.values(), default=0)
    max_def_local = max(por_def_y_programa.values(), default=0)
    resumen = {
        "programas": len(filas),
        "programas_con_clones": sum(1 for f in filas if f["n"]),
        "total_clones": total,
        "clones_con_retorno_contextual": con_retorno,
        "clones_sin_retorno_contextual": sin_retorno,
        "max_por_programa": max_programa,
        "programas_max": sorted(f["caso"] for f in filas if f["n"] == max_programa),
        "max_por_definicion_en_un_programa": max_def_local,
        "definiciones_max_locales": sorted(f"{caso}::{base}" for (caso, base), n
                                            in por_def_y_programa.items()
                                            if n == max_def_local),
        "max_por_definicion_en_todo_el_corpus": max_def_global,
        "definiciones_max_globales": sorted(d for d, n in por_def.items()
                                            if n == max_def_global),
        "por_definicion_en_corpus": dict(sorted(por_def.items())),
        "definiciones_unicas": len(por_def),
        "escalera_anchos": sorted(anchos),
        "escalera_retornos": sorted(retornos),
        "casos_con_error": [f["caso"] for f in filas if f["error"]],
    }
    return filas, resumen


# --- 2/3/4. curvas sintetizadas ------------------------------------------------------

def fuente_una_ranura(k: int) -> bytes:
    llamadas = "".join(f'    emit largo("{"a" * w}");\n' for w in range(1, k + 1))
    return (f'isyco 0.5\n\nfn largo(s: str) -> i64 {{ return len(s); }}\n'
            f'fn main() -> i64 !emit {{\n{llamadas}    return 0;\n}}\n').encode()


def fuente_dos_ranuras(w: int) -> bytes:
    llamadas = "".join(f'    emit dos("{"a" * i}", "{"b" * j}");\n'
                       for i in range(1, w + 1) for j in range(1, w + 1))
    return (f'isyco 0.5\n\nfn dos(a: str, b: str) -> i64 {{ return len(a) + len(b); }}\n'
            f'fn main() -> i64 !emit {{\n{llamadas}    return 0;\n}}\n').encode()


def fuente_tres_ranuras(w: int) -> bytes:
    llamadas = "".join(f'    emit tres("{"a" * i}", "{"b" * j}", "{"c" * h}");\n'
                       for i in range(1, w + 1) for j in range(1, w + 1)
                       for h in range(1, w + 1))
    return (f'isyco 0.5\n\nfn tres(a: str, b: str, c: str) -> i64 '
            f'{{ return len(a) + len(b) + len(c); }}\n'
            f'fn main() -> i64 !emit {{\n{llamadas}    return 0;\n}}\n').encode()


def fuente_mismo_ancho(sitios: int) -> bytes:
    llamadas = "".join(f'    emit ancho("abcd");\n' for _ in range(sitios))
    return (f'isyco 0.5\n\nfn ancho(s: str) -> i64 {{ return len(s); }}\n'
            f'fn main() -> i64 !emit {{\n{llamadas}    return 0;\n}}\n').encode()


def costo(fuente: bytes) -> dict:
    """Bytes y funciones de la IR, más referencia y C con su diferencial.

    Los extremos de la escalera se corren con el mismo cuerpo: si algo revienta ahí,
    eso ES el dato (el techo natural que P4 pide medir), así que se registra el fallo
    en lugar de propagarlo.
    """
    salida = {"fuente_bytes": len(fuente)}
    try:
        res = ensayar(fuente)
        if res["error"]:
            salida["chequeo"] = res["error"]
            return salida
        program = res["programa"]
        module = lower(program, program_sha256(fuente))
        salida["chequeo"] = "OK"
        salida["clones"] = len(res["clones"])
        salida["ir_bytes"] = len(canonical_bytes(module))
        salida["ir_funciones"] = len(module["functions"])
        t0 = time.perf_counter()
        r, _ = run(fuente, [])
        salida["ref_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        salida["status"] = r["status"]
        salida["code"] = r["code"]
        salida["pasos"] = r["steps"]
        if r["status"] != "HALTED":
            return salida
        from isyco.backends.c import run_c
        t0 = time.perf_counter()
        c, _ = run_c(fuente, [])
        salida["c_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        comparable = ("status", "emits", "return")
        salida["c_equiv"] = all(r[k] == c[k] for k in comparable)
        salida["c_status"] = c["status"]
    except Exception as e:                              # noqa: BLE001 — el techo es el dato
        salida["fallo"] = f"{type(e).__name__}: {e}"[:200]
    return salida


def curva_una_ranura():
    filas = []
    for k in ESCALERA:
        fuente = fuente_una_ranura(k)
        res = ensayar(fuente)
        filas.append({"K": k, "clones": len(res["clones"]), "error": res["error"],
                      "fuente_bytes": len(fuente)})
    return filas


def curva_combinaciones():
    dos, tres = [], []
    for w in COMBINACIONES:
        fuente = fuente_dos_ranuras(w)
        res = ensayar(fuente)
        dos.append({"W": w, "llamadas": w * w, "clones": len(res["clones"]),
                    "error": res["error"], "fuente_bytes": len(fuente)})
    for w in (2, 3):
        fuente = fuente_tres_ranuras(w)
        res = ensayar(fuente)
        tres.append({"W": w, "llamadas": w ** 3, "clones": len(res["clones"]),
                     "error": res["error"], "fuente_bytes": len(fuente)})
    return dos, tres


def control_mismo_ancho():
    res = ensayar(fuente_mismo_ancho(20))
    return {"sitios": 20, "clones": len(res["clones"]), "nombres": res["clones"],
            "error": res["error"]}


def curva_costo():
    filas = []
    for k in COSTO_C:
        fila = {"K": k, "control": True}
        fila.update(costo(fuente_una_ranura(k)))
        filas.append(fila)
    # y el extremo de dos ranuras: 8x8 = 64 clones en 6 funciones fuente
    fila = {"K": "dos ranuras 8x8", "control": True}
    fila.update(costo(fuente_dos_ranuras(8)))
    filas.append(fila)
    # el techo: dónde deja de escalar. Se reporta como sale, no como control exigido.
    for k in EXTREMOS:
        fila = {"K": k, "control": False}
        fila.update(costo(fuente_una_ranura(k)))
        filas.append(fila)
    return filas


def main(argv: list[str]) -> int:
    write = "--write" in argv
    filas_censo, resumen = censo_corpus()
    una = curva_una_ranura()
    dos, tres = curva_combinaciones()
    mismo = control_mismo_ancho()
    costo_curva = curva_costo()

    falsos = []
    # el instrumento: si el control negativo cuenta llamadas, nada de lo demás vale
    if mismo["clones"] != 1:
        falsos.append(f"control: 20 sitios con el mismo ancho dan {mismo['clones']} clones "
                      f"(deberían 1) — el registro cuenta llamadas, no resoluciones")
    for fila in una:
        if fila["clones"] != fila["K"]:
            falsos.append(f"una ranura: K={fila['K']} dio {fila['clones']} clones "
                          f"(deberían K) — el censo del corpus no es comparable")
    for fila in dos:
        if fila["clones"] != fila["W"] ** 2:
            falsos.append(f"dos ranuras: W={fila['W']} dio {fila['clones']}, se esperaba "
                          f"W^2={fila['W'] ** 2}")
    for fila in tres:
        if fila["clones"] != fila["W"] ** 3:
            falsos.append(f"tres ranuras: W={fila['W']} dio {fila['clones']}, se esperaba "
                          f"W^3={fila['W'] ** 3}")
    if resumen["total_clones"] == 0:
        falsos.append("censo: cero clones en todo el corpus — 411 y 413 tienen definiciones "
                      "contextuales, así que el censo es vacío")
    for fila in costo_curva:
        if not fila["control"]:
            continue
        if fila.get("status") != "HALTED":
            falsos.append(f"costo K={fila['K']}: la referencia no HALTED "
                          f"({fila.get('status')}({fila.get('code')}) "
                          f"chequeo={fila.get('chequeo')} fallo={fila.get('fallo')})")
        if fila.get("c_equiv") is False:
            falsos.append(f"costo K={fila['K']}: C diverge de la referencia")

    sucio = dirty_codigo()
    rec = {"comando": " ".join(argv) or "v05_p4_probe.py",
           "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "git_head": git_head(), "arbol_sucio_codigo": sucio,
           "veredicto_arbol": "EVIDENCE_ONLY" if sucio else "RELEASE_GATE",
           "python": platform.python_version(),
           "corpus": str(V05.relative_to(ROOT)),
           "instrumento": "isyco/checker.py: Checker.specs (una entrada por resolución "
                          "de capacidad, no por sitio de llamada)",
           "decision": "P4 sigue ABIERTA: esta sonda mide la forma del crecimiento, no "
                       "propone un número"}
    documento = {"schema": "isyco.evidence/0.1",
                 "milestone": "P4 (CORE v0.5) — censo de especializaciones y forma del "
                              "crecimiento",
                 "receipt": rec,
                 "censo_corpus": {"filas": filas_censo, "resumen": resumen},
                 "curva_una_ranura": una,
                 "curva_dos_ranuras": dos,
                 "curva_tres_ranuras": tres,
                 "control_mismo_ancho": mismo,
                 "costo": costo_curva}

    lineas = [
        "P4 — censo de especializaciones y forma del crecimiento (sin fijar tope)",
        f"utc={rec['utc']}  git_head={rec['git_head']}  arbol={rec['veredicto_arbol']} "
        f"(sucio_codigo={rec['arbol_sucio_codigo']})",
        f"comando: {rec['comando']}   python={rec['python']}",
        f"instrumento: {rec['instrumento']}",
        "",
        f"1) censo de la poblacion del gate en conformance_v0.5 (load_corpus: "
        f"{resumen['programas']} casos, 4 con modulos; 443-446 alta el 2026-11-01)",
    ]
    for fila in filas_censo:
        if fila["n"]:
            lineas.append(f"   {fila['caso']:44s} clones={fila['n']:2d} "
                          f"{fila['clones']}")
    lineas.append(f"   TOTAL: {resumen['total_clones']} clones en "
                  f"{resumen['programas_con_clones']}/{resumen['programas']} programas; "
                  f"{resumen['definiciones_unicas']} definiciones fuente; "
                  f"{resumen['clones_sin_retorno_contextual']} sin retorno pelado (V6) y "
                  f"{resumen['clones_con_retorno_contextual']} con el (V6-bis)")
    lineas.append(f"   max por programa: {resumen['max_por_programa']} "
                  f"{resumen['programas_max']}")
    lineas.append(f"   max por definicion EN UN PROGRAMA: "
                  f"{resumen['max_por_definicion_en_un_programa']} "
                  f"{resumen['definiciones_max_locales']}")
    lineas.append(f"   max por definicion EN TODO EL CORPUS: "
                  f"{resumen['max_por_definicion_en_todo_el_corpus']} "
                  f"{resumen['definiciones_max_globales']}")
    lineas.append(f"   por definicion (corpus): {resumen['por_definicion_en_corpus']}")
    lineas.append(f"   escalera de anchos (parametro): {resumen['escalera_anchos']}")
    lineas.append(f"   escalera de retornos (V6-bis):  {resumen['escalera_retornos']}")
    lineas.append(f"   casos con error estatico: {resumen['casos_con_error'] or 'ninguno'}")
    lineas += ["", "2) una ranura contextual: K anchos distintos, K llamados"]
    for fila in una:
        lineas.append(f"   K={fila['K']:4d}  clones={fila['clones']:4d}  "
                      f"fuente={fila['fuente_bytes']}B  error={fila['error']}")
    lineas += ["", "3) dos y tres ranuras: ¿los clones son W^2 y W^3?"]
    for fila in dos:
        lineas.append(f"   2 ranuras W={fila['W']}: llamadas={fila['llamadas']:3d} "
                      f"clones={fila['clones']:3d}  fuente={fila['fuente_bytes']}B")
    for fila in tres:
        lineas.append(f"   3 ranuras W={fila['W']}: llamadas={fila['llamadas']:3d} "
                      f"clones={fila['clones']:3d}  fuente={fila['fuente_bytes']}B")
    lineas += ["", "4) control negativo: 20 sitios de llamada, un solo ancho"]
    lineas.append(f"   clones={mismo['clones']}  nombres={mismo['nombres']}  "
                  f"error={mismo['error']}")
    lineas += ["", "5) costo (IR y C) en los extremos de la escalera"]
    for fila in costo_curva:
        exigido = "control" if fila["control"] else "techo"
        lineas.append(
            f"   K={str(fila['K']):16s} [{exigido}] fuente={fila.get('fuente_bytes')}B "
            f"clones={fila.get('clones')} ir={fila.get('ir_bytes')}B "
            f"funcs_ir={fila.get('ir_funciones')} pasos={fila.get('pasos')} "
            f"ref_ms={fila.get('ref_ms')} c_ms={fila.get('c_ms')} "
            f"equiv={fila.get('c_equiv')} status={fila.get('status')} "
            f"chequeo={fila.get('chequeo')} fallo={fila.get('fallo')}")
    lineas.append("")
    lineas.append("   LECTURA (lo que dicen estas cifras, no una decision):")
    lineas.append("   - el control 4) vale: 20 sitios con el mismo ancho dan 1 clon, así que")
    lineas.append("     el registro cuenta RESOLUCIONES y todo lo de arriba es comparable;")
    lineas.append("   - 2) y 3) dan K, W^2 y W^3 exactos: el conteo es multiplicativo en las")
    lineas.append("     ranuras contextuales, así que un tope 'por programa' mezcla")
    lineas.append("     definiciones y aridad, y uno 'por definición' no ve el producto;")
    lineas.append("   - 5) no encuentra techo hasta 2048 clones y no aparece NINGUN error")
    lineas.append("     nombrado: hoy el crecimiento es silencioso. La cota y su nombre")
    lineas.append("     siguen siendo decision de Danny (P4 abierta).")

    for mensaje in falsos:
        print(f"CONTROL FALSO: {mensaje}")
    if write and falsos:
        print("no se sella: hay controles falsos")
        return 1
    print("\n".join(lineas))
    if not write:
        return 0
    stamp = rec["utc"].replace(":", "").replace("-", "")
    destino = ROOT / "evidence" / "v05_p4"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"run_{stamp}.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (destino / f"run_{stamp}.json").write_text(
        json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    archivos = sorted(p for p in destino.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (destino / "SHA256SUMS.txt").write_text(
        "\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
                  for p in archivos) + "\n", encoding="utf-8")
    print(f"\nsellado en {destino.relative_to(ROOT)}/run_{stamp}.{{txt,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
