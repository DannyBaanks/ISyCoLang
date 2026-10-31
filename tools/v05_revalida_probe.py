"""Sonda de revalidación de CORE v0.5 (V1 `len` de arreglos, V2 azúcar `for`).

La pregunta: ¿los casos 401..410 del corpus v0.5 hacen lo que su `expected` escrito a mano
dice, en la referencia Y en cada backend, sin mover ningún programa anterior?

Hace cuatro cosas, en este orden:

1. **Tres vías** por caso: `expected` (a mano) ↔ referencia ↔ cada backend instalado.
   EQUIV exige coincidir con las dos primeras.
2. **Gemelos**: el mismo programa con la forma larga escrita a mano (para V1, la capacidad
   literal en lugar de `len(a)`; para V2, el `while` equivalente). Los `steps` tienen que
   coincidir: es la prueba de que el azúcar es estático y no una operación nueva.
3. **No regresión**: la misma fuente recabezada a 0.1..0.4 tiene que seguir siendo
   `INVALID_PROGRAM`. `steps` y códigos se registran, no se embellecen.
4. **Intenta falsarse a sí misma**: si el V1/V2 simulado se apaga (el `has(...,"v05")` del
   checker devolviendo False para esa familia, que es exactamente el estado previo), los
   casos tienen que rechazoarse de verdad — si ejecutaran, el PASS de arriba sería vacuo.
   Y una variante del programa (capacidad 5 -> 6, o el `for` con un elemento más) tiene que
   mover la salida: el valor sale del tipo, no de un constante escrita en el sonda.

Un PASS con el árbol sucio de código es `EVIDENCE_ONLY`, nunca gate de release.

    python3 tools/v05_revalida_probe.py --casos 401,406            # tabla por stdout
    python3 tools/v05_revalida_probe.py --casos 401,406 --write    # sella evidencia
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import isyco.checker as checker_mod                                   # noqa: E402
from isyco import run                                                 # noqa: E402
from isyco.backends import available                                  # noqa: E402
from isyco.conformance import COMPARED, load_corpus                   # noqa: E402
from isyco.errors import InvalidProgram                               # noqa: E402
from isyco.ir_interp import compile_ir                                # noqa: E402

KEYS = COMPARED
V05 = ROOT / "programs" / "conformance_v0.5"
VIEJAS = ("0.1", "0.2", "0.3", "0.4")

#: número -> (caso, gemelo, variante). El gemelo es la forma larga SIN el azúcar;
#: la variante cambia la capacidad declarada y tiene que mover la salida.
ESPECIFICACION = {
    "401": {
        "gemelo": ("inline", """isyco 0.5

fn cuanto(a: [i32; 5]) -> i64 {
    return 5;
}

fn main() -> i64 !emit {
    let xs: [i32; 5] = [1, 2, 3, 4, 5];
    emit cuanto(xs);
    return 5;
}
"""),
        "variante": ("inline", """isyco 0.5

fn cuanto(a: [i32; 6]) -> i64 {
    return len(a);
}

fn main() -> i64 !emit {
    let xs: [i32; 6] = [1, 2, 3, 4, 5, 6];
    emit cuanto(xs);
    return len(xs);
}
"""),
        "variante_esperada": {"emits": ["6"], "return": "6"},
    },
    "406": {
        "gemelo": ("inline", """isyco 0.5

fn suma(a: [i32; 6]) -> i32 {
    let i: i64 = 0;
    let total: i32 = 0;
    while i < 6 {
        total = total + a[i];
        i = i + 1;
    }
    return total;
}

fn main() -> i32 {
    let xs: [i32; 6] = [1, 2, 3, 4, 5, 6];
    return suma(xs);
}
"""),
        "variante": ("inline", """isyco 0.5

fn suma(a: [i32; 7]) -> i32 {
    let i: i64 = 0;
    let total: i32 = 0;
    while i < len(a) {
        total = total + a[i];
        i = i + 1;
    }
    return total;
}

fn main() -> i32 {
    let xs: [i32; 7] = [1, 2, 3, 4, 5, 6, 7];
    return suma(xs);
}
"""),
        "variante_esperada": {"emits": [], "return": "28"},
    },
}


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
        ruta = linea[3:] if len(linea) > 3 else ""
        partes = [p.strip() for p in ruta.split("->")]
        if all(p.startswith("evidence/") for p in partes):
            continue
        return True
    return False


def fuente(entrada) -> bytes:
    modo, texto = entrada
    return (V05 / texto).read_bytes() if modo == "archivo" else texto.encode("utf-8")


def recabezar(codigo: bytes, version: str) -> bytes:
    lineas = codigo.decode("utf-8").split("\n")
    assert lineas[0].startswith("isyco "), lineas[0]
    lineas[0] = f"isyco {version}"
    return "\n".join(lineas).encode("utf-8")


def observado(res: dict) -> dict:
    return {k: res.get(k) for k in KEYS}


def clasificar(expected: dict, ref: dict, got: dict | None, excepcion: str | None) -> str:
    """EQUIV exige coincidir con la referencia Y con el esperado escrito a mano."""
    if excepcion is not None:
        return "BUILD_FAIL"
    if got.get("status") == "UNSUPPORTED":
        return "UNSUPPORTED"
    if got.get("status") in ("BACKEND_CRASH", "TIMEOUT") or got.get("backend_stderr"):
        return "RUNTIME_FAIL"
    if observado(got) == ref and observado(got) == expected:
        return "EQUIV"
    return "DIVERGENT"


def referenciar(codigo: bytes):
    """(observado, pasos, rechazo) de la referencia.

    La referencia no lanza: un programa rechazado vuelve como resultado
    `INVALID_PROGRAM(code)`, así que ahí —y no en una excepción— se lee el rechazo.
    """
    try:
        res, _ = run(codigo, [], None)
    except InvalidProgram as exc:
        return None, None, f"INVALID_PROGRAM({exc.code})"
    if res["status"] == "INVALID_PROGRAM":
        return None, None, f"INVALID_PROGRAM({res['code']})"
    return observado(res), res["steps"], None


def tres_vias(casos: list[dict], backends: dict) -> list[dict]:
    filas = []
    for case in casos:
        ref, pasos_ref, exc_ref = referenciar(case["program"])
        fila = {"caso": case["name"], "claim": case["claim"], "expected": case["expected"],
                "referencia": ref, "pasos_referencia": pasos_ref,
                "rechazo_referencia": exc_ref, "backends": {}}
        if exc_ref is not None:
            filas.append(fila)
            continue
        for name, backend in sorted(backends.items()):
            try:
                got, _ = backend.run(case["program"], case["input"], case.get("limits"))
                detalle = None
            except Exception as exc:            # noqa: BLE001 - un fallo real se registra
                got, detalle = None, f"{type(exc).__name__}: {str(exc)[:160]}"
            fila["backends"][name] = {
                "clasificacion": clasificar(case["expected"], ref, got, detalle),
                "estado": (f"{got.get('status')}" + (f"({got.get('code')})" if got.get("code")
                                                     else "")) if got else detalle,
                "pasos": got.get("steps") if got else None,
                "excepcion": detalle,
            }
        filas.append(fila)
    return filas


def gemelos(casos: list[dict]) -> list[dict]:
    """El azúcar no puede costar ni un paso: el gemelo escrito a mano da lo mismo, mismo paso."""
    filas = []
    for case in casos:
        numero = case["name"].split("_")[0]
        espe = ESPECIFICACION.get(numero)
        if not espe:
            filas.append({"caso": case["name"], "estado": "SIN_GEMELO", "pasos": None})
            continue
        obs_a, pasos_a, _ = referenciar(case["program"])
        obs_g, pasos_g, exc_g = referenciar(fuente(espe["gemelo"]))
        if exc_g:
            estado = "FALTA_GEMELO"
        elif obs_a != obs_g:
            estado = "SALIDA_DIFIERE"
        elif pasos_a != pasos_g:
            estado = "PASOS_DIFIEREN"
        else:
            estado = "IGUAL"
        filas.append({"caso": case["name"], "estado": estado,
                      "pasos": {"azucar": pasos_a, "gemelo": pasos_g},
                      "salidas": {"azucar": obs_a, "gemelo": obs_g},
                      "rechazo_gemelo": exc_g})
    return filas


def no_regresion(casos: list[dict]) -> list[dict]:
    filas = []
    for case in casos:
        linea = {}
        for version in VIEJAS:
            try:
                compile_ir(recabezar(case["program"], version))
                linea[version] = "ACEPTADO"
            except InvalidProgram as exc:
                linea[version] = f"INVALID_PROGRAM({exc.code})"
        filas.append({"caso": case["name"], "rechazos": linea})
    return filas


def brazo_viejo(casos: list[dict]) -> list[dict]:
    """V1/V2 apagados: el checker ve la familia v05 como antes. Si ejecutara, el PASS es vacuo."""
    real = checker_mod.has
    filas = []
    try:
        checker_mod.has = lambda version, family: (
            False if family == "v05" and version in ("0.5",) else real(version, family))
        for case in casos:
            _, _, exc = referenciar(case["program"])
            filas.append({"caso": case["name"], "sin_la_regla": exc or "EJECUTA"})
    finally:
        checker_mod.has = real
    return filas


def hace_el_trabajo(casos: list[dict]) -> list[dict]:
    """Cambiar la capacidad declarada mueve la salida: el valor viene del tipo, no de la sonda.

    La salida esperada de la variante está escrita a mano abajo, en `ESPECIFICACION`, antes
    de correr: 1+2+..+7 = 28 y la capacidad de `[i32; 6]` es 6.
    """
    filas = []
    for case in casos:
        numero = case["name"].split("_")[0]
        espe = ESPECIFICACION.get(numero)
        if not espe:
            continue
        obs_v, pasos_v, exc_v = referenciar(fuente(espe["variante"]))
        obs_base, _, _ = referenciar(case["program"])
        esperado = {"status": "HALTED", "code": None, **espe["variante_esperada"]}
        filas.append({"caso": case["name"], "observado": obs_v, "pasos": pasos_v,
                      "esperado": esperado, "rechazo": exc_v,
                      "coincide_con_lo_predicho": obs_v == esperado,
                      "mueve_la_salida": obs_v != obs_base})
    return filas


def ir_sin_nuevos_nodos(casos: list[dict]) -> dict:
    """V1 dice 'la IR no cambia': ningún `len` de arreglo llega a bajar, y `len(s)` sí."""
    out = {"casos": [], "control_len_de_str": None}
    for case in casos:
        try:
            modulo = compile_ir(case["program"])
        except InvalidProgram:
            continue
        texto = json.dumps(modulo)
        out["casos"].append({"caso": case["name"], "nodos_len": texto.count('"k": "len"'),
                             "schema": modulo["schema"]})
    control = ('isyco 0.3\nfn main() -> i64 {\n    let s: str<8> = "hola";\n'
               '    return len(s);\n}\n').encode()
    out["control_len_de_str"] = json.dumps(compile_ir(control)).count('"k": "len"')
    return out


def main(argv: list[str]) -> int:
    write = "--write" in argv
    if "--casos" not in argv:
        print("falta --casos 401,406 (sin población explícita la sonda no corre)")
        return 1
    numeros = [n for n in argv[argv.index("--casos") + 1].split(",") if n]
    todas = load_corpus(V05)
    casos = [c for n in numeros for c in todas if c["name"].startswith(f"{n}_")]
    if len(casos) != len(numeros):
        print(f"--casos {numeros}: algunos no están en {V05} (encontrados "
              f"{[c['name'] for c in casos]})")
        return 1
    backends = available()
    filas = tres_vias(casos, backends)
    gem = gemelos(casos)
    regres = no_regresion(casos)
    viejo = brazo_viejo(casos)
    trabajo = hace_el_trabajo(casos)
    ir = ir_sin_nuevos_nodos(casos)

    sucio = dirty_codigo()
    rec = {"comando": " ".join(argv), "utc": datetime.now(timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%SZ"), "git_head": git_head(),
           "arbol_sucio_codigo": sucio,
           "veredicto_arbol": "EVIDENCE_ONLY" if sucio else "RELEASE_GATE",
           "python": platform.python_version(), "corpus": str(V05.relative_to(ROOT)),
           "casos": numeros, "backends": sorted(backends)}
    documento = {"schema": "isyco.evidence/0.1",
                 "milestone": "Revalidación CORE v0.5 (V1/V2) — corpus 401..410",
                 "receipt": rec, "tres_vias": filas, "gemelos": gem,
                 "no_regresion": regres, "brazo_viejo": viejo,
                 "hace_el_trabajo": trabajo, "ir": ir}

    conteo: dict[str, int] = {}
    for fila in filas:
        for nombre, dato in fila["backends"].items():
            conteo[f"{nombre}:{dato['clasificacion']}"] = \
                conteo.get(f"{nombre}:{dato['clasificacion']}", 0) + 1

    lineas = [
        "Revalidación CORE v0.5 — tres vías, gemelos estáticos, no regresión, auto-falsación",
        f"utc={rec['utc']}  git_head={rec['git_head']}  arbol={rec['veredicto_arbol']} "
        f"(sucio_codigo={rec['arbol_sucio_codigo']})",
        f"comando: {rec['comando']}   casos={numeros}   backends={rec['backends']}",
        "",
        "1) tres vias (expected a mano <-> referencia <-> backend)",
    ]
    for fila in filas:
        lineas.append(f"   {fila['caso']}  claim={fila['claim'][:58]}")
        lineas.append(f"     esperado: {fila['expected']}")
        lineas.append(f"     referencia: {fila['referencia']}  pasos={fila['pasos_referencia']}"
                      + (f"  RECHAZO={fila['rechazo_referencia']}" if fila["rechazo_referencia"]
                         else ""))
        for nombre, dato in fila["backends"].items():
            lineas.append(f"     {nombre:9s} {dato['clasificacion']:12s} {dato['estado']}"
                          f"  pasos={dato['pasos']}")
    lineas += ["", "2) gemelos estaticos (los mismos pasos que la forma larga a mano)"]
    for fila in gem:
        lineas.append(f"   {fila['caso']:28s} {fila['estado']:12s} {fila['pasos']}")
    lineas += ["", "3) no regresion (la misma fuente recabezada a versiones anteriores)"]
    for fila in regres:
        lineas.append(f"   {fila['caso']:28s} " + "  ".join(
            f"{v}={c}" for v, c in sorted(fila["rechazos"].items())))
    lineas += ["", "4) brazo viejo (la regla v05 apagada en el checker)"]
    for fila in viejo:
        lineas.append(f"   {fila['caso']:28s} {fila['sin_la_regla']}")
    lineas += ["", "5) el valor viene del tipo (variante de capacidad)"]
    for fila in trabajo:
        lineas.append(f"   {fila['caso']:28s} observado={fila['observado']}")
        lineas.append(f"   {'':28s} predicho={fila['esperado']} "
                      f"coincide={fila['coincide_con_lo_predicho']} "
                      f"mueve_la_salida={fila['mueve_la_salida']} pasos={fila['pasos']}"
                      + (f"  RECHAZO={fila['rechazo']}" if fila["rechazo"] else ""))
    lineas += ["", "6) la IR no gana nodos nuevos (V1: len de arreglo es const)"]
    for fila in ir["casos"]:
        lineas.append(f"   {fila['caso']:28s} nodos_len={fila['nodos_len']} "
                      f"schema={fila['schema']}")
    lineas.append(f"   control len(str) = {ir['control_len_de_str']} nodos_len (debe ser 1)")
    lineas += ["", f"conteo por clase: {conteo or 'ningun backend instalado'}"]

    # ---- auto-falsación: cualquier grieta impide sellar
    falsos = []
    for fila in filas:
        if fila["rechazo_referencia"]:
            falsos.append(f"{fila['caso']}: la referencia rechaza un caso que debe ejecutar")
        for nombre, dato in fila["backends"].items():
            if dato["clasificacion"] in ("DIVERGENT", "BUILD_FAIL", "RUNTIME_FAIL"):
                falsos.append(f"{fila['caso']} en {nombre}: {dato['clasificacion']} "
                              f"({dato['estado']})")
    for fila in gem:
        if fila["estado"] == "PASOS_DIFIEREN":
            falsos.append(f"{fila['caso']}: el azúcar cuesta pasos de más {fila['pasos']}")
        elif fila["estado"] == "SALIDA_DIFIERE":
            falsos.append(f"{fila['caso']}: el gemelo a mano da otra salida {fila['salidas']}")
        elif fila["estado"] == "FALTA_GEMELO":
            falsos.append(f"{fila['caso']}: el gemelo no baja o falla "
                          f"({fila['rechazo_gemelo']})")
    for fila in regres:
        for version, code in fila["rechazos"].items():
            if code == "ACEPTADO":
                falsos.append(f"{fila['caso']} se acepta con cabecera {version}: "
                              f"un programa anterior cambió de significado")
    for fila in viejo:
        if fila["sin_la_regla"] == "EJECUTA":
            falsos.append(f"{fila['caso']} ejecuta sin la regla de v0.5: el PASS es vacuo")
    for fila in trabajo:
        if not fila["coincide_con_lo_predicho"]:
            falsos.append(f"variante de {fila['caso']}: {fila['observado']} != "
                          f"predicho a mano {fila['esperado']}")
        if not fila["mueve_la_salida"]:
            falsos.append(f"variante de {fila['caso']} no mueve la salida: "
                          f"la capacidad no viene del tipo")
    if ir["control_len_de_str"] != 1:
        falsos.append(f"control len(str): {ir['control_len_de_str']} nodos, se esperaba 1")
    for fila in ir["casos"]:
        if fila["nodos_len"]:
            falsos.append(f"{fila['caso']}: la IR lleva {fila['nodos_len']} nodos len "
                          f"(V1/V2 prometen const, no una operación nueva)")
    for mensaje in falsos:
        print(f"CONTROL FALSO: {mensaje}")
    if write and falsos:
        print("no se sella: hay controles falsos")
        return 1
    print("\n".join(lineas))
    if not write:
        return 0
    stamp = rec["utc"].replace(":", "").replace("-", "")
    destino = ROOT / "evidence" / "v05_revalida"
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
