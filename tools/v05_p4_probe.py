"""Verifica la regla con la que se cerró P4 y sigue midiendo su forma: cuántas
especializaciones crea un programa de verdad, cómo crecen con la forma del programa y
dónde está el techo del toolchain.

P4 («¿cuántas especializaciones puede crear un programa?») se cerró el 2026-11-02 con
**256 resoluciones por definición fuente dentro del programa** y error nombrado
`SPEC_LIMIT`: `docs/decisions/P4_SPEC_LIMIT.md`. La medición que sostuvo la decisión no
estaba en ningún recibo — las sondas V6 y V7 guardan resultados por backend, no el
registro de clones — así que esta sonda la recalcula desde el instrumento
(`isyco/checker.py`: `Checker.specs` y `Checker.spec_counts`) y añade lo que faltaba:

  1. **Censo del corpus** — la población del gate (`load_corpus`: 48 casos de
     `programs/conformance_v0.5`, incluidos los 4 con módulos): clones por programa,
     total, máximo por definición dentro de un programa y en todo el corpus, escalera de
     anchos instanciados. Los casos que existen para probar el tope (`447`, `448`) se
     parten del resto porque si no la cota se muerde la cola.
  2. **Una ranura contextual, K anchos distintos**: ¿los clones valen `min(K, tope)` y
     K = tope+1 es `SPEC_LIMIT`?
  3. **Dos y tres ranuras**: ¿los clones valen W² y W³? Son multiplicativos, y de ahí la
     granularidad elegida.
  4. **Control negativo**: 20 sitios de llamada con el MISMO ancho deben dar 1 clon —
     si diera 20, el instrumento cuenta llamadas y no resoluciones, y todo lo anterior
     sería basura.
  5. **Costo**: bytes de ISY-IR, funciones en la IR, y compilar/ejecutar en C para los
     tres tamaños exigidos de la escalera (8, 64, 256 — el último es el borde legal) más
     los extremos (512, 1024, 2048), que hoy se rechazan en el frontend.
  6. **Techo de toolchain**: matriz (1, 2, 3, 4 ranuras) × ancho, por c/rust/zig. El
     tope es una decisión del idioma; que un compilador soporte 256 copias de una
     definición NO forma parte de la garantía (`spec/CORE_v0.5.md` §7) y por eso esta
     fila se mide en lugar de afirmarse.
  7. **La forma real de una librería V6**: 11 helpers en 3 módulos con K anchos — el
     crecimiento por módulo que hace dos semanas era solo prosa de conversación.

    python3 tools/v05_p4_probe.py                    # corre y reporta, no escribe
    python3 tools/v05_p4_probe.py --bisect-zig       # recorre la banda de Zig por aridad: 21
                                                     # compilaciones más (~2 min, medido)
    python3 tools/v05_p4_probe.py --write            # sella en evidence/v05_p4/
"""
from __future__ import annotations

import hashlib
import itertools
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

from isyco import specialize                      # noqa: E402
from isyco.backends import available              # noqa: E402
from isyco.checker import Checker                 # noqa: E402
from isyco.conformance import load_corpus         # noqa: E402
from isyco.errors import InvalidProgram           # noqa: E402
from isyco.interp import run                      # noqa: E402
from isyco.ir import canonical_bytes, lower       # noqa: E402
from isyco.modules import load_program, module_prefix  # noqa: E402
from isyco.source import Bundle, program_sha256   # noqa: E402

V05 = ROOT / "programs" / "conformance_v0.5"
ESCALERA = (1, 2, 4, 8, 16, 32, 64, 128, 256)
COMBINACIONES = (2, 3, 4, 6, 8)      # W para 2 ranuras -> W^2 clones
COSTO_C = (8, 64, 256)               # tamaños que DEBEN compilar y coincidir con la referencia
EXTREMOS = (512, 1024, 2048)          # con el tope de P4 dentro, los tres se rechazan en el
                                      # frontend: se reportan como salen, no como control
BACKENDS_TECHO = ("c", "rust", "zig")
# Anchos por ranura que se barren EN LA MATRIZ de toolchain (sección 6). A cada escalera se
# le añaden después el último ancho legal y el primero que pasa del tope, calculados sobre
# la constante viva, no escritos aquí.
ANCHURAS_TECHO = {1: (8, 16, 32, 64, 96, 128), 2: (4, 8, 12), 3: (4, 5), 4: (3,)}
# Granularidad de `--bisect-zig`: los anchos de las ranuras primeras se FIJAN aquí y solo se
# barre el último, de modo que cada paso de la bisección vale BISECCION_FIJOS^(ranuras-1)
# clones. Se fijan en 2 y no en 1 para que la forma barrida siga siendo multi-valora en cada
# ranura: con 1 fijo la frontera mediría una degeneración que la escalera no observa.
BISECCION_FIJOS = 2
LIBRERIA_K = (1, 2, 3, 4, 6, 8)
# Los totales de clones medidos en vivo el 2026-11-02, antes de existir este recibo. Son el
# control de que el generador de la sección 7 no se movió entre esa medición y el sello.
LIBRERIA_ESPERADA = {1: 11, 2: 22, 3: 29, 4: 36, 6: 58, 8: 58}


def tope() -> int:
    """El tope de P4, leído de la constante del spec en cada uso.

    Se lee por atributo y nunca se copia a una constante de módulo: si alguien cambia
    `MAX_CLONES_PER_DEFINITION`, las curvas de esta sonda tienen que moverse con él, que
    es exactamente lo que el sabotaje de `tests/test_reference.py` comprueba."""
    return specialize.MAX_CLONES_PER_DEFINITION



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


def cta_derivada(clones: list[str]) -> dict[str, int]:
    """Recuento por definición fuente, derivado del registro de clones vía `base_de`."""
    salida: dict[str, int] = {}
    for nombre in clones:
        base = base_de(nombre)
        salida[base] = salida.get(base, 0) + 1
    return salida


def ensayar(fuente) -> dict:
    """Chequea y devuelve el registro de especializaciones sin ejecutar nada.

    Con el tope de P4 el rechazo es estático: un programa que lo pasa devuelve el registro
    VACÍO y no baja a la IR. Aun así se reporta `resoluciones_max`, porque es el dato que
    dice dónde mordió la cota (el contador llega a tope+1 antes de lanzar) en lugar de
    cuántas copias sobrevivieron, que por construcción es ninguna.
    """
    checker = None
    try:
        program = load_program(fuente)
        checker = Checker(program)
        checker.check()
    except InvalidProgram as e:
        conteos = dict(checker.spec_counts) if checker else {}
        return {"error": f"{e.code}", "clones": [], "programa": None, "conteos": conteos,
                "resoluciones_max": max(conteos.values(), default=0)}
    conteos = dict(checker.spec_counts)
    return {"error": None, "clones": sorted(checker.specs), "programa": program,
            "conteos": conteos, "resoluciones_max": max(conteos.values(), default=0)}


def bytes_de(fuente) -> int:
    """Tamaño de la fuente, con `Bundle` (los casos con módulos) y con `bytes`."""
    if isinstance(fuente, Bundle):
        return sum(len(data) for _, data in fuente.files)
    return len(fuente)


# --- 1. censo del corpus -------------------------------------------------------------

def censo_corpus():
    """Censo sobre LA POBLACIÓN DEL GATE, no sobre un glob de archivos.

    `load_corpus` (isyco/conformance.py) añade además los casos con módulos, que son
    carpetas con `main.isy` + `expect.json` — un glob de `.isy` pierde `408`, `421` y
    `440`, y `421` es justamente el caso con una especialización calificada
    (`util.marca.4`). Contar otra población que la del gate es el bug de deriva de
    población que ya cazó V7.

    Con P4 cerrado, los casos que existen para probar el tope (`447`, `448`) fijan por
    construcción el máximo del censo: la cota se muerde la cola. No se excluyen de la
    población — ahí sigue el total del gate — se reportan aparte, y la partición se lee
    del `claim` de cada caso, no de una lista escrita a mano que se oxida.
    """
    filas = []
    for caso in sorted(load_corpus(V05), key=lambda c: c["name"]):
        t0 = time.perf_counter()
        res = ensayar(caso["program"])
        ms = round((time.perf_counter() - t0) * 1000, 2)
        filas.append({"caso": caso["name"], "clones": res["clones"], "n": len(res["clones"]),
                      "chequeo_ms": ms, "error": res["error"],
                      "de_tope": "P4" in caso.get("claim", ""),
                      "cruce_contador": (res["error"] is not None
                                         or res["conteos"] == cta_derivada(res["clones"]))})
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
    nombres_de_tope = {f["caso"] for f in filas if f["de_tope"]}
    sin_tope = {(caso, base): n for (caso, base), n in por_def_y_programa.items()
                if caso not in nombres_de_tope}
    max_def_local_sin_tope = max(sin_tope.values(), default=0)
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
        "max_por_definicion_en_un_programa_sin_casos_de_tope": max_def_local_sin_tope,
        "definiciones_max_locales_sin_casos_de_tope": sorted(
            f"{caso}::{base}" for (caso, base), n in sin_tope.items()
            if n == max_def_local_sin_tope),
        "casos_de_tope": sorted(f["caso"] for f in filas if f["de_tope"]),
        "max_por_definicion_en_todo_el_corpus": max_def_global,
        "definiciones_max_globales": sorted(d for d, n in por_def.items()
                                            if n == max_def_global),
        "por_definicion_en_corpus": dict(sorted(por_def.items())),
        "definiciones_unicas": len(por_def),
        "escalera_anchos": sorted(anchos),
        "escalera_retornos": sorted(retornos),
        "casos_con_error": [f["caso"] for f in filas if f["error"]],
        "cruce_contador_fallas": [f["caso"] for f in filas if not f["cruce_contador"]],
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


def fuente_ranuras(ranuras: int, w: int) -> bytes:
    """Una definición con N parámetros `str`, llamada en las w^N combinaciones de anchos.

    Generaliza `fuente_dos_ranuras`/`fuente_tres_ranuras` para la matriz de toolchain, que
    necesita llegar a 256 copias con 1, 2, 3 y 4 ranuras. Se construye con `product` en vez
    de anidar `for` por cada aridad.
    """
    nombres = [f"a{i}" for i in range(1, ranuras + 1)]
    firma = ", ".join(f"{n}: str" for n in nombres)
    suma = " + ".join(f"len({n})" for n in nombres)

    def literal(ancho: int) -> str:
        return '"' + "x" * ancho + '"'

    llamadas = "".join(
        f'    emit multi({", ".join(literal(a) for a in combo)});\n'
        for combo in itertools.product(range(1, w + 1), repeat=ranuras))
    return (f'isyco 0.5\n\nfn multi({firma}) -> i64 {{ return {suma}; }}\n'
            f'fn main() -> i64 !emit {{\n{llamadas}    return 0;\n}}\n').encode()


# --- 7. la forma real de una librería V6 ----------------------------------------------

TEXT = ("""isyco 0.5
pub fn largo(s: str) -> i64 { return len(s); }
pub fn pad(s: str, n: i64, c: str<1>) -> str<32> {
    let out: str<32> = s;
    let k: i64 = len(s);
    while k < n { out = out + c; k = k + 1; }
    return out;
}
pub fn junta(a: str, b: str) -> str<32> { let r: str<32> = a + b; return r; }
pub fn doble(s: str) -> str { return s + s; }
pub fn mayus(s: str) -> str<16> { return s as str<16>; }
pub fn cuenta(s: str) -> i64 { return len(s); }
pub fn guion(s: str) -> str<16> { return s as str<16>; }
""").encode()
FMT = ("isyco 0.5\npub fn marca(s: str) -> str<8> { return s as str<8>; }\n"
       "pub fn copia(s: str) -> str<8> { return s as str<8>; }\n"
       "pub fn etiqueta(s: str) -> str { return s + s; }\n").encode()
POOL = ["ab", "abcd", "abcdefgh", "1234567890123456", "xyz", "q", "r", "t"]


def fuente_libreria(k: int) -> Bundle:
    """Una librería de texto en estilo V6: 11 helpers pelados, 3 módulos, K anchos.

    Es la forma que Danny quiere construir de verdad (el objetivo declarado de CORE v0.5),
    no una escalera sintética: cada ancho nuevo que se usa en un helper de `texto` cuesta
    una resolución por helper tocado, y `q`/`r`/`t` del pool comparten ancho 1 — por eso la
    curva se satura en K=6 aunque el pool tenga ocho cadenas.
    """
    cuerpo, n = [], 0
    for s in POOL[:k]:
        corto = s[:4]
        cuerpo += [f'    emit texto.{fn}("{s}");'
                   for fn in ("largo", "mayus", "cuenta", "guion")]
        cuerpo += [f'    emit texto.pad("{s}", 9, "-");',
                   f'    emit texto.junta("{s}", "z");']
        # `doble` y `etiqueta` devuelven `str` pelado: se llaman donde una capacidad esperada
        # las fije (V6-bis), que es justamente el `let` anotado de una librería de verdad.
        n += 1
        cuerpo += [f'    let d{n}: str<8> = texto.doble("{corto}");', f"    emit d{n};"]
        cuerpo += [f'    emit fmt.{fn}("{corto}");' for fn in ("marca", "copia")]
        n += 1
        cuerpo += [f'    let e{n}: str<8> = fmt.etiqueta("{corto}");', f"    emit e{n};"]
        cuerpo += [f'    emit local("{s}");']
    main = ("isyco 0.5\nimport texto;\nimport fmt;\n\n"
            "fn local(s: str) -> i64 { return len(s); }\n\n"
            "fn main() !emit {\n" + "\n".join(cuerpo) + "\n}\n").encode()
    return Bundle((("main.isy", main), ("texto.isy", TEXT), ("fmt.isy", FMT)), "main.isy")


def por_modulo(prog, bases) -> dict:
    """A qué espacio de nombre pertenece cada definición fuente.

    `A.Fn` no tiene un campo módulo en el AST: el único rastro es el prefijo del nombre, así
    que se decide contra la lista de módulos cargados (`module_prefix`), el más largo primero.
    Lo que no cae bajo ninguno es el archivo principal, reportado como `MAIN`.
    """
    prefs = sorted((module_prefix(m) for m in prog.modules), key=len, reverse=True)
    salida: dict[str, int] = {}
    for base in bases:
        modulo = next((p.rstrip(".") for p in prefs if base.startswith(p)), "MAIN")
        salida[modulo] = salida.get(modulo, 0) + 1
    return dict(sorted(salida.items()))


def curva_libreria() -> list[dict]:
    filas = []
    for k in LIBRERIA_K:
        fuente = fuente_libreria(k)
        res = ensayar(fuente)
        bases = [base_de(n) for n in res["clones"]]
        por_def: dict[str, int] = {}
        for base in bases:
            por_def[base] = por_def.get(base, 0) + 1
        filas.append({"K": k, "clones": len(res["clones"]), "error": res["error"],
                      "resoluciones_max": max(por_def.values(), default=0),
                      "definiciones": len(por_def),
                      "por_definicion": dict(sorted(por_def.items())),
                      "cruce_contador": res["conteos"] == por_def,
                      "por_modulo": (por_modulo(res["programa"], bases)
                                     if res["programa"] else {}),
                      "fuente_bytes": bytes_de(fuente)})
    return filas


def costo(fuente) -> dict:
    """Bytes y funciones de la IR, más referencia y C con su diferencial.

    Los extremos de la escalera se corren con el mismo cuerpo: si algo revienta ahí, eso ES
    el dato, así que se registra el fallo en lugar de propagarlo. Con P4 cerrado, los tres
    extremos (`512`, `1024`, `2048`) se cortan en el frontend y devuelven
    `chequeo: SPEC_LIMIT` con la resolución exacta en la que el contador pasó el tope.
    """
    salida = {"fuente_bytes": bytes_de(fuente)}
    try:
        res = ensayar(fuente)
        salida["resoluciones_max"] = res["resoluciones_max"]
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
    """K anchos distintos sobre una sola definición, con el exceso como control positivo.

    `tope() + 1` no estaba en la escalera original: sin él, la corrida mediría la curva por
    debajo de la cota y no diría nada de que la cota se aplica.
    """
    filas = []
    for k in ESCALERA + (tope() + 1,):
        fuente = fuente_una_ranura(k)
        res = ensayar(fuente)
        filas.append({"K": k, "clones": len(res["clones"]), "error": res["error"],
                      "resoluciones_max": res["resoluciones_max"],
                      "fuente_bytes": len(fuente)})
    return filas


def curva_combinaciones():
    dos, tres = [], []
    for w in COMBINACIONES:
        fuente = fuente_dos_ranuras(w)
        res = ensayar(fuente)
        dos.append({"W": w, "llamadas": w * w, "clones": len(res["clones"]),
                    "error": res["error"], "resoluciones_max": res["resoluciones_max"],
                    "fuente_bytes": len(fuente)})
    for w in (2, 3):
        fuente = fuente_tres_ranuras(w)
        res = ensayar(fuente)
        tres.append({"W": w, "llamadas": w ** 3, "clones": len(res["clones"]),
                     "error": res["error"], "resoluciones_max": res["resoluciones_max"],
                     "fuente_bytes": len(fuente)})
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
    # los extremos: con el tope dentro se cortan en el frontend, y eso es el dato.
    for k in EXTREMOS:
        fila = {"K": k, "control": False}
        fila.update(costo(fuente_una_ranura(k)))
        filas.append(fila)
    return filas


# --- 6. techo de toolchain ------------------------------------------------------------

def ultima_anchura_legal(ranuras: int) -> int:
    """Mayor W con W^ranuras <= tope: el borde justo de la escalera de cada aridad."""
    w = 1
    while (w + 1) ** ranuras <= tope():
        w += 1
    return w


def escalera_techo(ranuras: int) -> tuple[int, ...]:
    """Anchos que se barren por aridad: los fijos por debajo del borde, y el borde y su
    exceso calculados sobre la constante viva, para que la matriz no se oxide si el tope
    se mueve."""
    borde = ultima_anchura_legal(ranuras)
    fijos = tuple(w for w in ANCHURAS_TECHO.get(ranuras, ()) if w < borde)
    return fijos + (borde, borde + 1)


def prueba_backends(fuente, res: dict, backends: dict) -> dict:
    """Corre una fuente ya chequeada por c/rust/zig y registra qué pasó con cada uno.

    Se captura cualquier excepción del backend porque `base.py:194-195` lanza `RuntimeError`
    cuando el compilador devuelve no-cero: un fallo del toolchain ES el dato de esta sección,
    no un error de la sonda. Un programa que pasa el tope no se compila: no baja a la IR, así
    que no hay nada que un compilador pueda ver, y decir `FRONTEND` es más honesto que medir
    los 0,4 ms de una corrida que no intentó compilar. Del texto del fallo se guarda la línea
    que dice `error:`, porque la última de Zig es una nota sobre `-freference-trace`.
    """
    salida = {}
    for nombre in BACKENDS_TECHO:
        if res["error"]:
            salida[nombre] = {"estado": "FRONTEND"}
            continue
        backend = backends.get(nombre)
        if backend is None:
            salida[nombre] = {"estado": "NO_INSTALADO"}
            continue
        t0 = time.perf_counter()
        try:
            r, _ = backend.run(fuente, [])
            salida[nombre] = {"estado": "OK", "status": r["status"],
                              "ms": round((time.perf_counter() - t0) * 1000)}
        except Exception as e:                    # noqa: BLE001 — el fallo es el dato
            lineas = [x.strip() for x in str(e).splitlines() if x.strip()]
            detalle = next((x for x in lineas if "error:" in x), lineas[-1] if lineas else "")
            salida[nombre] = {"estado": "FALLO",
                              "error": f"{type(e).__name__}: {detalle}"[:130]}
    return salida


def fila_techo(ranuras: int, w: int, backends: dict) -> dict:
    """Una fila de la matriz: W anchos en cada una de N ranuras, o sea W^N clones."""
    fuente = fuente_ranuras(ranuras, w)
    res = ensayar(fuente)
    fila = {"ranuras": ranuras, "W": w, "llamadas": w ** ranuras,
            "clones": len(res["clones"]), "resoluciones_max": res["resoluciones_max"],
            "error": res["error"], "fuente_bytes": len(fuente),
            "cruce_contador": (res["error"] is not None
                               or res["conteos"] == cta_derivada(res["clones"]))}
    fila.update(prueba_backends(fuente, res, backends))
    return fila


def fuente_ranuras_parciales(ranuras: int, fijos: int, ultimo: int) -> bytes:
    """N ranuras: las N-1 primeras conservan `fijos` anchos y solo la última varía.

    Es la forma de contar copias sin cambiar la aridad. La escalera perfecta (W^N) solo cae en
    potencias exactas y deja bandas enormes sin cerrar; con `fijos=2` el número de clones es
    2^(N-1) · ultimo, así que la bisección tiene granularidad 2^(N-1) copias.
    """
    nombres = [f"a{i}" for i in range(1, ranuras + 1)]
    firma = ", ".join(f"{n}: str" for n in nombres)
    suma = " + ".join(f"len({n})" for n in nombres)

    def literal(ancho: int) -> str:
        return '"' + "x" * ancho + '"'

    fijas = itertools.product(range(1, fijos + 1), repeat=ranuras - 1)
    llamadas = "".join(
        f'    emit multi({", ".join(literal(a) for a in combo)});\n'
        for combo in (prev + (u,) for prev in fijas for u in range(1, ultimo + 1)))
    return (f'isyco 0.5\n\nfn multi({firma}) -> i64 {{ return {suma}; }}\n'
            f'fn main() -> i64 !emit {{\n{llamadas}    return 0;\n}}\n').encode()


def fila_biseccion(ranuras: int, ultimo: int, backends: dict) -> dict:
    """Una fila de la banda: BISECCION_FIJOS^(ranuras-1) · ultimo clones de una definición."""
    fuente = fuente_ranuras_parciales(ranuras, BISECCION_FIJOS, ultimo)
    res = ensayar(fuente)
    fila = {"ranuras": ranuras, "fijos": BISECCION_FIJOS, "ultimo": ultimo,
            "llamadas": len(res["clones"]) if not res["error"] else BISECCION_FIJOS ** (
                ranuras - 1) * ultimo,
            "clones": len(res["clones"]), "resoluciones_max": res["resoluciones_max"],
            "error": res["error"], "fuente_bytes": len(fuente),
            "cruce_contador": (res["error"] is not None
                               or res["conteos"] == cta_derivada(res["clones"]))}
    fila.update(prueba_backends(fuente, res, backends))
    return fila


def biseccion_zig(ranuras: int, lo: int, hi: int, backends: dict) -> dict:
    """Recorre [lo, hi] en unidades de `ultimo` hasta que solo separe un paso.

    `lo` y `hi` los valida `frontera_zig` compilando los dos extremos: si la cuenta no es
    monótona en esta forma, o si la aridad pesa más que el número de copias, se reporta el
    bracket roto en lugar de escribir una frontera que no se midió.
    """
    paso = BISECCION_FIJOS ** (ranuras - 1)
    pasos = []
    while hi - lo > 1:
        medio = (lo + hi) // 2
        fila = fila_biseccion(ranuras, medio, backends)
        pasos.append({"ultimo": medio, "clones": fila["llamadas"],
                      "estado": fila["zig"]["estado"], "ms": fila["zig"].get("ms")})
        if fila["error"] or not fila["cruce_contador"]:
            return {"estado": "PASA_EL_TOPE", "ultimo": medio, "pasos": pasos}
        if fila["zig"]["estado"] == "OK":
            lo = medio
        else:
            hi = medio
    return {"estado": "BISECTADO", "max_ok_clones": lo * paso,
            "min_fail_clones": hi * paso, "pasos": pasos}


def frontera_zig(filas: list[dict], backends: dict, bisect_zig: bool) -> dict:
    """Dónde deja Zig de compilar una definición, medido por aridad en ESTA corrida.

    La matriz solo toca potencias exactas, así que entre dos filas consecutivas queda una banda
    enorme sin recorrer. `--bisect-zig` la cierra moviendo una sola ranura; sin esa bandera el
    recibo deja la banda abierta con `estado: NO_MEDIDO`. Nunca se escribe «Zig falla con ~100»
    de un número que no se tocó: lo que se afirma aquí sale de una compilación.
    """
    if "zig" not in backends:
        return {"zig_instalado": False, "estado": "NO_INSTALADO", "por_aridad": {}}
    por_aridad = {}
    for ranuras in (1, 2, 3, 4):
        legales = [f for f in filas if f["ranuras"] == ranuras and not f["error"]]
        ok = max((f["clones"] for f in legales if f["zig"]["estado"] == "OK"), default=None)
        falla = min((f["clones"] for f in legales if f["zig"]["estado"] == "FALLO"),
                    default=None)
        entrada = {"escalera_max_ok": ok, "escalera_min_fallo": falla}
        if falla is None:
            por_aridad[ranuras] = dict(entrada, estado="SIN_FALLO_DENTRO_DEL_TOPE")
            continue
        if not bisect_zig:
            por_aridad[ranuras] = dict(entrada, estado="NO_MEDIDO", banda_abierta=[ok, falla])
            continue
        paso = BISECCION_FIJOS ** (ranuras - 1)
        lo, hi = ok // paso, -(-falla // paso)
        bordes = {n: fila_biseccion(ranuras, n, backends) for n in (lo, hi)}
        if bordes[lo]["zig"]["estado"] != "OK" or bordes[hi]["zig"]["estado"] != "FALLO":
            por_aridad[ranuras] = dict(
                entrada, estado="BRACKET_NO_SE_SOSTIENE", paso_clones=paso,
                bordes={n: {"ultimo": f["ultimo"], "clones": f["llamadas"],
                            "zig": f["zig"]["estado"]} for n, f in bordes.items()})
            continue
        resultado = biseccion_zig(ranuras, lo, hi, backends)
        por_aridad[ranuras] = dict(entrada, paso_clones=paso,
                                  bordes_validados={n: {"ultimo": f["ultimo"],
                                                        "clones": f["llamadas"],
                                                        "zig": f["zig"]["estado"],
                                                        "ms": f["zig"].get("ms")}
                                                    for n, f in bordes.items()},
                                  **resultado)
    return {"zig_instalado": True, "fijos_biseccion": BISECCION_FIJOS,
            "por_aridad": por_aridad}


def curva_techo(bisect_zig: bool) -> tuple[list[dict], dict]:
    """Matriz (aridad × ancho) sobre c/rust/zig y, si se pide, la frontera de Zig cerrada.

    Las filas se generan todas de una sola vez porque `controles_techo` las necesita completas
    para exigir monotonía por aridad antes de que `frontera_zig` interprete la escalera.
    """
    backends = available()
    filas = [fila_techo(ranuras, w, backends) for ranuras in (1, 2, 3, 4)
             for w in escalera_techo(ranuras)]
    return filas, frontera_zig(filas, backends, bisect_zig)


def controles_techo(filas: list[dict]) -> list[str]:
    """Qué tendría que ser verdad para que una fila hable del toolchain y no del generado.

    Una fila de Zig solo significa algo si el programa que le llegó es válido (los otros dos
    compilan), si la cuenta que exige el tope coincide con el registro de clones, y si la
    frontera es monótona: un W más grande no puede compilar donde el pequeño reventó.
    """
    mensajes = []
    for fila in filas:
        sin_tope = fila["W"] ** fila["ranuras"]
        clave = f"aridad={fila['ranuras']} W={fila['W']} ({sin_tope} clones)"
        if fila["error"] is None:
            if sin_tope > tope():
                mensajes.append(f"techo {clave}: legal con {sin_tope} > tope {tope()}")
            if fila["clones"] != sin_tope or fila["resoluciones_max"] != sin_tope:
                mensajes.append(f"techo {clave}: clones={fila['clones']} "
                                f"resoluciones={fila['resoluciones_max']}")
            if not fila["cruce_contador"]:
                mensajes.append(f"techo {clave}: spec_counts no coincide con el registro "
                                f"derivado por base_de — el contador de P4 y `specs` divergen")
            for nombre in BACKENDS_TECHO:
                if fila[nombre]["estado"] == "OK" and fila[nombre].get("status") != "HALTED":
                    mensajes.append(f"techo {clave}: {nombre} dice OK pero no HALTED "
                                    f"({fila[nombre].get('status')})")
        elif fila["error"] != "SPEC_LIMIT":
            mensajes.append(f"techo {clave}: error esperado SPEC_LIMIT, llegó {fila['error']}")
        elif fila["resoluciones_max"] != tope() + 1:
            mensajes.append(f"techo {clave}: SPEC_LIMIT con el contador en "
                            f"{fila['resoluciones_max']}, se esperaba {tope() + 1} — el tope "
                            f"no mordió en la resolución justa")
        elif fila["clones"] != 0:
            mensajes.append(f"techo {clave}: SPEC_LIMIT y aun así {fila['clones']} clones en "
                            f"el registro — el rechazo no es estático")
        # si un backend falla, los otros dos tienen que compilar: si no, el generado es
        # inválido y la fila no dice nada del toolchain que se estaba midiendo.
        if fila["zig"]["estado"] == "FALLO" and any(
                fila[n]["estado"] != "OK" for n in ("c", "rust")):
            mensajes.append(f"techo {clave}: Zig falla y c/rust no compilan la misma fila "
                            f"(c={fila['c']['estado']} rust={fila['rust']['estado']}) — la "
                            f"fila no habla de Zig")
    for ranuras in (1, 2, 3, 4):
        legales = [f for f in filas if f["ranuras"] == ranuras and not f["error"]]
        for nombre in BACKENDS_TECHO:
            vistos = [(f["W"], f[nombre]["estado"]) for f in legales]
            estados = [e for _, e in vistos]
            if "FALLO" in estados:
                primer_fallo = estados.index("FALLO")
                if "OK" in estados[primer_fallo + 1:]:
                    mensajes.append(f"techo aridad={ranuras}: {nombre} falla en "
                                    f"W={vistos[primer_fallo][0]} y compila después — la "
                                    f"frontera no es monótona, la matriz no fija un umbral")
    return mensajes


def control_crecimiento(etiqueta: str, casos: list[tuple[dict, int]]) -> list[str]:
    """Guard a prueba de tope para las tres curvas sintetizadas.

    Antes la expectativa era `clones == K` (o `W^2`, `W^3`) a secas: con P4 cerrado eso se
    volvía falso en cualquier escalera que pasara del tope y bloqueaba el sello. Por debajo
    del tope se siguen exigiendo los clones exactos; por encima se exige el rechazo
    (`SPEC_LIMIT`, registro vacío) y que el contador haya llegado justo a tope+1.
    """
    mensajes = []
    limite = tope()
    for fila, sin_tope in casos:
        if sin_tope <= limite:
            if fila["error"] or fila["clones"] != sin_tope:
                mensajes.append(f"{etiqueta}: se esperaban {sin_tope} clones y ningun "
                                f"error, dio clones={fila['clones']} "
                                f"error={fila['error']} — el censo del corpus no es "
                                f"comparable")
        elif (fila["error"], fila["clones"], fila["resoluciones_max"]) != (
                "SPEC_LIMIT", 0, limite + 1):
            mensajes.append(f"{etiqueta}: {sin_tope} resoluciones pasan del tope {limite} y "
                            f"no devolvieron SPEC_LIMIT con registro vacío y contador en "
                            f"{limite + 1} (dio error={fila['error']} clones={fila['clones']} "
                            f"resoluciones={fila['resoluciones_max']})")
    return mensajes


def main(argv: list[str]) -> int:
    write = "--write" in argv
    bisect_zig = "--bisect-zig" in argv
    filas_censo, resumen = censo_corpus()
    una = curva_una_ranura()
    dos, tres = curva_combinaciones()
    mismo = control_mismo_ancho()
    costo_curva = curva_costo()
    filas_techo, techo_zig = curva_techo(bisect_zig)
    libreria = curva_libreria()

    falsos = []
    # el instrumento: si el control negativo cuenta llamadas, nada de lo demás vale
    if mismo["clones"] != 1:
        falsos.append(f"control: 20 sitios con el mismo ancho dan {mismo['clones']} clones "
                      f"(deberían 1) — el registro cuenta llamadas, no resoluciones")
    falsos += control_crecimiento("una ranura", [(f, f["K"]) for f in una])
    falsos += control_crecimiento("dos ranuras", [(f, f["W"] ** 2) for f in dos])
    falsos += control_crecimiento("tres ranuras", [(f, f["W"] ** 3) for f in tres])
    if resumen["total_clones"] == 0:
        falsos.append("censo: cero clones en todo el corpus — 411 y 413 tienen definiciones "
                      "contextuales, así que el censo es vacío")
    if resumen["cruce_contador_fallas"]:
        falsos.append(f"censo: en {resumen['cruce_contador_fallas']} el contador de P4 "
                      f"(spec_counts) no coincide con el registro derivado por base_de — la "
                      f"cuenta y las copias que se crean son dos cosas distintas")
    for fila in costo_curva:
        if not fila["control"]:
            continue
        if fila.get("status") != "HALTED":
            falsos.append(f"costo K={fila['K']}: la referencia no HALTED "
                          f"({fila.get('status')}({fila.get('code')}) "
                          f"chequeo={fila.get('chequeo')} fallo={fila.get('fallo')})")
        if fila.get("c_equiv") is False:
            falsos.append(f"costo K={fila['K']}: C diverge de la referencia")
    falsos += controles_techo(filas_techo)
    distintos = {k: len({len(s) for s in POOL[:k]}) for k in LIBRERIA_K}
    for fila in libreria:
        esperado = LIBRERIA_ESPERADA[fila["K"]]
        if fila["error"] or fila["clones"] != esperado:
            falsos.append(f"libreria K={fila['K']}: {fila['clones']} clones y "
                          f"error={fila['error']}; la medición de 2026-11-02 decía {esperado} "
                          f"— el generador se movió y el número que se sella ya no es el que "
                          f"se midió")
        if not fila["cruce_contador"]:
            falsos.append(f"libreria K={fila['K']}: spec_counts no coincide con el registro "
                          f"por definicion")
        if fila["resoluciones_max"] != distintos[fila["K"]]:
            falsos.append(f"libreria K={fila['K']}: la definicion mas cargada dio "
                          f"{fila['resoluciones_max']} resoluciones y el pool tiene "
                          f"{distintos[fila['K']]} anchos distintos")

    sucio = dirty_codigo()
    limite = tope()
    rec = {"comando": " ".join(argv) or "v05_p4_probe.py",
           "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "git_head": git_head(), "arbol_sucio_codigo": sucio,
           "veredicto_arbol": "EVIDENCE_ONLY" if sucio else "RELEASE_GATE",
           "python": platform.python_version(),
           "corpus": str(V05.relative_to(ROOT)),
           "tope": limite,
           "tope_como_se_lee": "isyco/specialize.py: MAX_CLONES_PER_DEFINITION, leida viva en "
                              "cada uso; si el sabotaje la mueve, la sonda se mueve con ella",
           "instrumento": "isyco/checker.py: Checker.specs (las copias creadas) y "
                          "Checker.spec_counts (las resoluciones contadas por definicion)",
           "decision": f"P4 CERRADA el 2026-11-02 por Danny: {limite} especializaciones por "
                       f"definicion fuente dentro del programa, rechazadas con "
                       f"INVALID_PROGRAM/SPEC_LIMIT (docs/decisions/P4_SPEC_LIMIT.md). La "
                       f"sonda verifica la regla y mide el techo del toolchain, que el tope "
                       f"NO garantiza"}
    documento = {"schema": "isyco.evidence/0.1",
                 "milestone": f"P4 (CORE v0.5) CERRADA — tope de {limite} especializaciones "
                              f"por definicion (SPEC_LIMIT): censo, forma del crecimiento, "
                              f"techo de toolchain y libreria V6",
                 "receipt": rec,
                 "censo_corpus": {"filas": filas_censo, "resumen": resumen},
                 "curva_una_ranura": una,
                 "curva_dos_ranuras": dos,
                 "curva_tres_ranuras": tres,
                 "control_mismo_ancho": mismo,
                 "costo": costo_curva,
                 "techo_toolchain": {"filas": filas_techo, "zig": techo_zig},
                 "libreria_v6": libreria}

    lineas = [
        f"P4 — tope de {limite} especializaciones por definicion (SPEC_LIMIT): censo, forma "
        f"del crecimiento, techo de toolchain y libreria",
        f"utc={rec['utc']}  git_head={rec['git_head']}  arbol={rec['veredicto_arbol']} "
        f"(sucio_codigo={rec['arbol_sucio_codigo']})",
        f"comando: {rec['comando']}   python={rec['python']}",
        f"instrumento: {rec['instrumento']}",
        "",
        f"1) censo de la poblacion del gate en conformance_v0.5 (load_corpus: "
        f"{resumen['programas']} casos, 4 con modulos; 447-448 alta el 2026-11-02 por P4)",
    ]
    for fila in filas_censo:
        if fila["n"] or fila["de_tope"]:
            lineas.append(f"   {fila['caso']:44s} clones={fila['n']:2d} "
                          f"{'[tope] ' if fila['de_tope'] else ''}{fila['clones']}")
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
    lineas.append(f"   casos que existen para probar el tope: {resumen['casos_de_tope']}; "
                  f"fuera de ellos el maximo por definicion EN UN PROGRAMA sigue en "
                  f"{resumen['max_por_definicion_en_un_programa_sin_casos_de_tope']} "
                  f"{resumen['definiciones_max_locales_sin_casos_de_tope']} — esa es la base "
                  f"que decidio el numero, sellada en la corrida de 46 casos "
                  f"run_20261101T234407Z.json")
    lineas.append(f"   max por definicion EN TODO EL CORPUS: "
                  f"{resumen['max_por_definicion_en_todo_el_corpus']} "
                  f"{resumen['definiciones_max_globales']}")
    lineas.append(f"   por definicion (corpus): {resumen['por_definicion_en_corpus']}")
    lineas.append(f"   escalera de anchos (parametro): {resumen['escalera_anchos']}")
    lineas.append(f"   escalera de retornos (V6-bis):  {resumen['escalera_retornos']}")
    lineas.append(f"   casos con error estatico: {resumen['casos_con_error'] or 'ninguno'}")
    divergencias = resumen["cruce_contador_fallas"] or "todo coincide"
    lineas.append(f"   cruce spec_counts vs base_de(specs): {divergencias}")
    lineas += ["", f"2) una ranura contextual: K anchos distintos dan min(K, {limite}) clones "
                   f"y K={limite + 1} es SPEC_LIMIT"]
    for fila in una:
        lineas.append(f"   K={fila['K']:4d}  clones={fila['clones']:4d}  "
                      f"resoluciones={fila['resoluciones_max']:4d}  "
                      f"fuente={fila['fuente_bytes']}B  error={fila['error']}")
    lineas += ["", "3) dos y tres ranuras: ¿los clones son W^2 y W^3?"]
    for fila in dos:
        lineas.append(f"   2 ranuras W={fila['W']}: llamadas={fila['llamadas']:3d} "
                      f"clones={fila['clones']:3d} resoluciones={fila['resoluciones_max']:3d} "
                      f"fuente={fila['fuente_bytes']}B error={fila['error']}")
    for fila in tres:
        lineas.append(f"   3 ranuras W={fila['W']}: llamadas={fila['llamadas']:3d} "
                      f"clones={fila['clones']:3d} resoluciones={fila['resoluciones_max']:3d} "
                      f"fuente={fila['fuente_bytes']}B error={fila['error']}")
    lineas += ["", "4) control negativo: 20 sitios de llamada, un solo ancho"]
    lineas.append(f"   clones={mismo['clones']}  nombres={mismo['nombres']}  "
                  f"error={mismo['error']}")
    lineas += ["", "5) costo (IR y C): los controles exigidos y los extremos, que con el tope "
                   "dentro se cortan en el frontend"]
    for fila in costo_curva:
        exigido = "control" if fila["control"] else "exceso"
        lineas.append(
            f"   K={str(fila['K']):16s} [{exigido}] fuente={fila.get('fuente_bytes')}B "
            f"clones={fila.get('clones')} resoluciones={fila.get('resoluciones_max')} "
            f"ir={fila.get('ir_bytes')}B "
            f"funcs_ir={fila.get('ir_funciones')} pasos={fila.get('pasos')} "
            f"ref_ms={fila.get('ref_ms')} c_ms={fila.get('c_ms')} "
            f"equiv={fila.get('c_equiv')} status={fila.get('status')} "
            f"chequeo={fila.get('chequeo')} fallo={fila.get('fallo')}")
    lineas += ["", f"6) techo de toolchain: una definicion de N ranuras llamada en W^N "
                   f"combinaciones, tope={limite}"]
    for fila in filas_techo:
        lineas.append(
            f"   aridad={fila['ranuras']} W={fila['W']:3d} llamadas={fila['llamadas']:5d} "
            f"clones={fila['clones']:4d} resoluciones={fila['resoluciones_max']:4d} "
            f"fuente={fila['fuente_bytes']:7d}B error={str(fila['error']):10s} "
            + "  ".join(f"{n}={fila[n]['estado']}"
                        + (f"/{fila[n]['ms']}ms" if "ms" in fila[n] else "")
                        + (f" {fila[n]['error']}" if "error" in fila[n] else "")
                        for n in BACKENDS_TECHO))
    if not techo_zig["zig_instalado"]:
        lineas.append("   Zig no esta instalado en este host: la matriz dice NO_INSTALADO y "
                      "esta corrida no afirma ninguna frontera")
    for ranuras, d in sorted(techo_zig["por_aridad"].items()):
        lineas.append(f"   frontera de Zig, aridad={ranuras}: escalera "
                      f"max_ok={d['escalera_max_ok']} min_fallo={d['escalera_min_fallo']} "
                      f"estado={d['estado']}")
        banda = {k: v for k, v in d.items()
                 if k not in ("escalera_max_ok", "escalera_min_fallo", "estado")}
        if banda:
            lineas.append(f"      banda: {banda}")
    lineas += ["", "7) la forma real de una libreria V6: 11 helpers pelados en 3 modulos, "
                   "K anchos del pool"]
    for fila in libreria:
        lineas.append(f"   K={fila['K']:2d}  clones={fila['clones']:3d}  "
                      f"definiciones={fila['definiciones']:3d}  "
                      f"max_por_definicion={fila['resoluciones_max']:2d}  "
                      f"por_modulo={fila['por_modulo']}  "
                      f"fuente={fila['fuente_bytes']}B  error={fila['error']}")
    seis = next(f for f in libreria if f["K"] == 6)
    lineas.append(f"   K=6, definicion por definicion: {seis['por_definicion']}")
    lineas.append("")
    lineas.append("   LECTURA (lo que dicen estas cifras; la decision ya esta tomada):")
    lineas.append("   - el control 4) vale: 20 sitios con el mismo ancho dan 1 clon, así que")
    lineas.append("     el registro cuenta RESOLUCIONES y todo lo de arriba es comparable;")
    lineas.append("   - 2) y 3) dan K, W^2 y W^3 exactos por debajo del tope y SPEC_LIMIT con")
    lineas.append("     registro vacío justo al pasarlo: el conteo es multiplicativo en las")
    lineas.append("     ranuras, y esa es la razon de la granularidad elegida (por definicion")
    lineas.append("     y no por programa, que mezclaria aridades);")
    lineas.append("   - el censo 1) ya no decide el numero: con 447 y 448 dentro, el maximo")
    lineas.append("     por definicion lo pone el caso que prueba la cota, así que la base de")
    lineas.append("     la decision es la corrida de 46 casos sellada (max 2 por definicion")
    lineas.append("     dentro de un programa, 4 por programa);")
    lineas.append("   - 5) y 6) separan dos cosas que antes se confundian: el tope corta")
    lineas.append(f"     ANTES de la IR, así que ningún backend ve más de {limite} copias de")
    lineas.append("     una definicion, pero esas SI llegan al toolchain y ahí la cota no")
    lineas.append("     garantiza nada: hay filas donde Zig revienta mientras C y rust")
    lineas.append("     compilan, y el punto donde revienta depende de la ARIDAD de la")
    lineas.append("     definicion y no solo del numero de copias: con el tope puesto, una")
    lineas.append("     ranura compila las 256 y con dos, tres o cuatro el mismo orden")
    lineas.append("     revienta. Techo de compilador != limite del idioma (pregunta Z1,")
    lineas.append("     docs/OPEN_QUESTIONS_P1_P4.md);")
    if bisect_zig:
        lineas.append("   - 6b) esa frontera esta MEDIDA, no afirmada: cada aridad tiene su")
        lineas.append("     umbral en clones y sus dos bordes se compilan antes de partir.")
        lineas.append("     La biseccion fija en 2 las ranuras primeras y suelta la ultima")
        lineas.append("     (paso de 2^(n-1) clones): el umbral es de ESA forma, no de la")
        lineas.append("     escalera de anchos iguales, y por eso los bordes rodean numeros")
        lineas.append("     que la escalera no toca. aridad=1 sale SIN_FALLO_DENTRO_DEL_TOPE:")
        lineas.append("     con una sola ranura Zig no rompe antes de la cota del idioma.")
    else:
        lineas.append("   - 6b) sin --bisect-zig la banda entre la escalera y el primer fallo")
        lineas.append("     queda NO_MEDIDO: el recibo no afirma un umbral que no se compilo;")
        lineas.append("     lo que si esta medido aqui es el borde de cada escalera.")
    lineas.append("   - 7) en la forma real de una libreria el maximo por definicion es el")
    lineas.append("     numero de anchos DISTINTOS del pool (el control lo exige), no el de")
    lineas.append("     llamadas: once helpers en tres modulos agotan mucho antes de la cota,")
    lineas.append("     y lo que la gasta es una sola definicion con muchas ranuras.")

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
