"""Sonda de Z1: el techo de comptime de Zig era forma del emisor, no frontera del idioma.

Z1 preguntaba si un programa legal de v0.5 puede compilar en C y Rust y no en Zig, o si el
idioma hereda el techo del toolchain más débil. La respuesta medida es que el techo lo ponía
`isyco/backends/zig.py` en dos sitios, y ninguno es semántica:

1. **el cuerpo**: Zig cuesta **una** rama de evaluación por instanciación de `str` —dos antes
   del alias, cuando cada sitio instanciaba además su tipo—, así que la cuota de fábrica de
   1000 se agotaba alrededor de mil copias. El emisor ahora se concede `1000 + 8·sitios`
   dentro de cada función: ocho veces el coste medido, finito, y crece solo con lo que el
   emisor genera de verdad;
2. **la firma**: evaluar la cabecera de un clone con 1024 parámetros `IsyStr(2)` agota el
   marco de la *declaración*, y ninguna cuota escrita dentro de un cuerpo lo alcanza. El
   emisor declara el tipo una vez por ancho (`const Str2 = IsyStr(2);`) y usa el alias.

Los dos mecanismos se miden **por separado**: la frontera de 500/504 que P4 selló con el
emisor anterior hoy cabe *sin la cuota*, o sea que la movió el alias; y 1024 instanciaciones
siguen muriendo sin la cuota aunque el alias esté puesto, o sea que la cuota sostiene el
resto. Sin esa separación la sonda afirmaría que el arreglo es uno cuando son dos.

Y un hallazgo que no es ni del idioma ni del emisor: la ruta de frontend (`compile_ir`)
tiene un techo de **profundidad** de expresión —`RecursionError` a los 242 niveles, mientras
un árbol de 2000 términos pasa—, artefacto del anfitrión sin guarda nombrada que queda
abierto como issue Z2 en `docs/OPEN_QUESTIONS_P1_P4.md`.

Cada claim de «compila» tiene su variante saboteada al revés (sin la cuota, la cuota a nivel
de archivo, sin el alias) medida con el compilador muriendo de verdad, y todo programa que
compila se coteja con la referencia normativa y con el binario C.

    python3 tools/z1_ceiling_probe.py            # corre y muestra la tabla
    python3 tools/z1_ceiling_probe.py --write    # sella evidence/z1_ceiling/run_<UTC>.{json,txt}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
from isyco.backends.base import ToolchainBuildFailure  # noqa: E402
from isyco.backends.zig import CUOTA_BASE, CUOTA_SITIO  # noqa: E402
from isyco.conformance import COMPARED  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402
from v05_p4_probe import fuente_ranuras, fuente_ranuras_parciales  # noqa: E402

KEYS = COMPARED + ("steps",)
DIGITOS = "0123456789abcdefghijklmnopqrstuvwxyz"
# Los dos puntos sellados de la bisección de P4 (evidence/v05_p4/run_20261102T085025Z.json):
# 500 instanciaciones cabían y 504 no, con el emisor anterior. Aquí se re-miden con el de hoy.
P4_OK, P4_FALLO = 500, 504
SHA_EXTRA_CASE = "52a2803975adf30db03bdb6cd975b4dc724faa5ebfdeddc21e5f90fc5e98c9b5"
RAMA_QUE_FALTA = "backwards branches"
# Control de la zona sin `str`: ni cuota ni alias deben aparecer en un programa que no los usa.
FUENTE_SIN_STR = (b'isyco 0.5\n\nfn m(a: i64) -> i64 { return a; }\n'
                  b'fn main() -> i64 !emit {\n    emit m(1);\n    return 0;\n}\n')


def b36(i: int, n: int) -> str:
    s = ""
    for _ in range(n):
        s = DIGITOS[i % 36] + s
        i //= 36
    return s


def ranuras_de_ancho(a: int, largo: int) -> bytes:
    """`a` instanciaciones de `str`, todas de `largo` caracteres y todas distintas.

    Con una sola llamada la aridad y el número de instanciaciones crecen juntos: es la forma
    de separar coste por instanciación de coste por ancho del literal (ancho 2 y ancho 64 dan
    la misma cuota y mueren igual), y también la única que llega a 2048 instanciaciones sin
    pasarse de la cota de resoluciones de P4.
    """
    firma = ", ".join(f"p{i}: str" for i in range(1, a + 1))
    args = ", ".join('"%s"' % b36(i, largo) for i in range(a))
    return (f'isyco 0.5\n\nfn m({firma}) -> i64 {{ return len(p1); }}\n'
            f'fn main() -> i64 !emit {{\n    emit m({args});\n    return 0;\n}}\n').encode()


def sitios_puros(u: int) -> bytes:
    """`32u` instanciaciones con una firma de cuatro parámetros: el sitio solo, sin aridad.

    `fuente_ranuras_parciales(4, 2, u)` son `8u` clones de una definición de cuatro ranuras
    (los tres primeros anchos fijos en {1,2}, el último barre 1..u): en u=32 se planta en los
    256 clones que deja P4 y da 1024 instanciaciones con solo cuatro parámetros de firma. Así
    la cota que se biseca es de instanciaciones y no de instanciaciones *más* parámetros.
    """
    return fuente_ranuras_parciales(4, 2, u)


def cuota_de(texto: str) -> list[int]:
    return [int(m) for m in re.findall(r"@setEvalBranchQuota\((\d+)\)", texto)]


def sin_cuota(texto: str) -> str:
    return "\n".join(l for l in texto.splitlines() if "setEvalBranchQuota" not in l) + "\n"


def cuota_en_fichero(texto: str) -> str:
    """La misma cuota a nivel de archivo: autoriza otro marco y no sirve (C2)."""
    valor = cuota_de(texto)[0]
    lineas = [l for l in texto.splitlines() if "setEvalBranchQuota" not in l]
    i = next(n for n, l in enumerate(lineas) if l.startswith("fn isy_flush"))
    lineas.insert(i, f"comptime {{ @setEvalBranchQuota({valor}); }}")
    return "\n".join(lineas) + "\n"


def sin_alias(texto: str) -> str:
    """Expande los alias: cada uso del tipo vuelve a ser una instancia `IsyStr(N)`."""
    sin_decls = "\n".join(l for l in texto.splitlines() if not l.startswith("const Str"))
    return re.sub(r"\bStr(\d+)\b", r"IsyStr(\1)", sin_decls) + "\n"


VARIANTES = {"emisor": lambda t: t, "sin_cuota": sin_cuota,
             "cuota_en_fichero": cuota_en_fichero, "sin_alias": sin_alias}

# Lo que se compila, y en qué orden. `emisor` es el fuente tal cual lo escribe el backend;
# las demás son saboteadas al revés para que el arreglo tenga su contrafactual medido.
PLAN = [("512x2", "emisor"), ("512x2", "sin_cuota"),
        ("sitios_960", "emisor"), ("sitios_960", "sin_cuota"),
        ("aridad_1024", "emisor"), ("aridad_1024", "sin_cuota"),
        ("aridad_1024", "cuota_en_fichero"), ("aridad_1024", "sin_alias"),
        ("1024x64", "emisor"), ("1024x64", "sin_cuota"),
        ("aridad_2048", "emisor"), ("aridad_2048", "sin_cuota"),
        ("P4_500", "emisor"), ("P4_500", "sin_cuota"),
        ("P4_504", "emisor"), ("P4_504", "sin_cuota"),
        ("extra_case", "emisor"), ("extra_case", "sin_cuota")]


def compilar(zig, texto: str) -> dict:
    """`build-exe` con las banderas del backend, en un directorio propio, sin caché en medio."""
    with tempfile.TemporaryDirectory(prefix="isyco_z1_") as tmp:
        carpeta = Path(tmp)
        src = carpeta / "sonda.zig"
        src.write_text(texto, encoding="utf-8")
        inicio = time.perf_counter()
        proc = subprocess.run(zig.compile_cmd(src, carpeta / "sonda", ()),
                              capture_output=True, text=True, cwd=carpeta)
        error = next((l.strip() for l in (proc.stderr or proc.stdout).splitlines()
                      if "error:" in l), "")
        return {"exit": proc.returncode, "s": round(time.perf_counter() - inicio, 1),
                "error": error, "sha256": hashlib.sha256(texto.encode()).hexdigest(),
                "sitios": texto.count("= isy_str("),
                "aliases": sum(1 for l in texto.splitlines() if l.startswith("const Str"))}


def ejecutar(backend, fuente: bytes) -> dict:
    """La ruta real del contrato: construye, ejecuta y devuelve las claves comparadas."""
    try:
        doc, _ = backend.run(fuente, [], None)
    except ToolchainBuildFailure as e:
        return {"fallo_build": str(e).splitlines()[0][:160]}
    return {k: doc.get(k) for k in KEYS}


def cadena(k: int) -> str:
    """`k` términos `len(s)` sumados por la izquierda: la expresión tiene profundidad k."""
    e = "len(s)"
    for _ in range(k - 1):
        e = f"{e} + len(s)"
    return e


def arbol(k: int) -> str:
    """Los mismos `k` términos en árbol binario balanceado: profundidad ~log2(k)."""
    if k == 1:
        return "len(s)"
    izq = k // 2
    return f"({arbol(izq)} + {arbol(k - izq)})"


HIJO = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from isyco.ir_interp import compile_ir
try:
    compile_ir(open(sys.argv[2], "rb").read())
    print(json.dumps({"resultado": "OK"}))
except RecursionError:
    print(json.dumps({"resultado": "RecursionError",
                      "detalle": "limite de recursion = %d" % sys.getrecursionlimit()}))
except Exception as exc:
    print(json.dumps({"resultado": type(exc).__name__, "detalle": str(exc)[:200]}))
'''


def frontend(expr: str) -> tuple[dict, bytes]:
    """La fuente se prueba en un proceso hijo, y se devuelve para que se pueda sellar.

    El límite de recursión es por interpretación y una `RecursionError` capturada deja el stack
    de la sonda en un estado que no se quiere medir: aquí el que se desborda es el hijo.
    """
    fuente = (f'isyco 0.5\n\nfn m(s: str) -> i64 {{ return {expr}; }}\n'
              f'fn main() -> i64 !emit {{\n    emit m("x");\n    return 0;\n}}\n').encode()
    with tempfile.TemporaryDirectory(prefix="isyco_z1_front_") as tmp:
        camino = Path(tmp) / "sonda.isy"
        camino.write_bytes(fuente)
        proc = subprocess.run([sys.executable, "-c", HIJO, str(ROOT), str(camino)],
                              capture_output=True, text=True, timeout=600)
    try:
        d = json.loads(proc.stdout)
    except Exception:
        d = {"resultado": "ERROR_HARNESS", "detalle": (proc.stderr or proc.stdout)[-300:]}
    d["fuente_bytes"] = len(fuente)
    d["fuente_sha256"] = hashlib.sha256(fuente).hexdigest()
    return d, fuente


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="sella en evidence/z1_ceiling/")
    args = parser.parse_args(argv)
    stamp = _gate.stamp()
    backends = available()
    if "zig" not in backends or "c" not in backends:
        print("hacen falta zig y c instalados: NOTHING DEMOSTRABLE", file=sys.stderr)
        return 1
    zig, ce = backends["zig"], backends["c"]
    falsos, lineas, claims = [], [], {}

    def claim(identidad, afirmacion, estado, observado):
        claims[identidad] = {"id": identidad, "afirmacion": afirmacion, "estado": estado,
                             "observado": observado}
        if estado == "FALSO":
            falsos.append(f"{identidad}: {afirmacion} — observado {json.dumps(observado)[:160]}")
        print(f"  [{identidad}] {estado}", flush=True)

    def muere(res) -> bool:
        return res["exit"] != 0 and RAMA_QUE_FALTA in res["error"]

    # --- las formas que se miden ------------------------------------------------------
    formas = {
        "512x2": ranuras_de_ancho(512, 2),
        "1024x64": ranuras_de_ancho(1024, 64),
        "aridad_1024": ranuras_de_ancho(1024, 2),
        "aridad_2048": ranuras_de_ancho(2048, 3),
        "sitios_960": sitios_puros(30),
        # `fuente_ranuras_parciales(2, 2, u)` hace 2u clones de 2 ranuras: 4u instanciaciones.
        "P4_500": fuente_ranuras_parciales(2, 2, P4_OK // 4),
        "P4_504": fuente_ranuras_parciales(2, 2, P4_FALLO // 4),
        "extra_case": fuente_ranuras(4, 4),
    }
    emitido = {n: zig.emit(compile_ir(f)) for n, f in formas.items()}

    # --- la tabla de compilaciones, en crudo y sin caché -------------------------------
    med = {}
    for forma, variante in PLAN:
        texto = VARIANTES[variante](emitido[forma])
        med[f"{forma}|{variante}"] = compilar(zig, texto)
        fila = med[f"{forma}|{variante}"]
        print(f"  {forma:12} {variante:17} sitios={fila['sitios']:5} "
              f"alias={fila['aliases']:4} exit={fila['exit']} {fila['s']:6}s "
              f"{fila['error'][:60]}", flush=True)

    def m(forma, variante):
        return med[f"{forma}|{variante}"]

    # --- C1: el coste es por instanciación, y no por ancho ni por arreglo --------------
    # Bajo el emisor anterior la frontera sellada estaba en 500 OK / 504 FALLO, con cada sitio
    # pagando su tipo además de su llamada. Con el alias puesto la cota se corre a ~1000: los
    # puntos de abajo la acotan por debajo (960 sitios con firma corta caben) y por arriba
    # (1024 sitios mueran con firma de 4 parámetros o de 1024, y con literal de 2 o de 64).
    caben = [f for f in ("512x2", "sitios_960", "P4_500", "P4_504")
             if m(f, "sin_cuota")["exit"] == 0]
    mueren = [f for f in ("aridad_1024", "1024x64", "aridad_2048", "extra_case")
              if muere(m(f, "sin_cuota"))]
    viven = sorted(f for f in formas if m(f, "emisor")["exit"] == 0)

    def mensaje(res) -> str:
        """Solo el texto del compilador, sin la posición del fuente (cambia con el ancho)."""
        return res["error"].split("error:")[-1].strip()

    mismo_error = (mensaje(m("aridad_1024", "sin_cuota"))
                    == mensaje(m("1024x64", "sin_cuota"))
                    == mensaje(m("extra_case", "sin_cuota")))
    claim("C1", f"el presupuesto de comptime de Zig cuesta una rama por instanciación de "
                f"`str`: sin la línea del emisor caben {sorted(caben)} y mueren {sorted(mueren)} "
                f"(la cota no depende del ancho del literal ni de si los sitios vienen de una "
                f"firma gorda o de 256 clones), y con la línea del emisor compilan las "
                f"{len(formas)} formas",
          "DEMONSTRADO" if (sorted(caben) == sorted(["512x2", "sitios_960", "P4_500", "P4_504"])
                            and sorted(mueren) == sorted(["aridad_1024", "1024x64", "aridad_2048",
                                                           "extra_case"])
                            and viven == sorted(formas) and mismo_error) else "FALSO",
          {"caben_sin_cuota": sorted(caben), "mueren_sin_cuota": sorted(mueren),
           "sitios_sin_cuota": {f: m(f, "sin_cuota")["sitios"] for f in sorted(formas)},
           "compilan_con_cuota": viven, "error_igual": mismo_error,
           "frontera_anterior_P4": f"{P4_OK} OK / {P4_FALLO} FALLO con el emisor anterior"})

    # --- C2: la posición de la cuota no es opcional -----------------------------------
    fichero = m("aridad_1024", "cuota_en_fichero")
    claim("C2", "la misma cuota puesta a nivel de archivo no arregla nada: un `comptime` de "
                "archivo es su propio marco (sabotaje medido, no supuesto)",
          "DEMONSTRADO" if muere(fichero) else "FALSO",
          {"error": fichero["error"][:120], "s": fichero["s"], "sitios": fichero["sitios"]})

    # --- C3: la firma es un marco aparte y el alias la abarata ------------------------
    sin_al = m("aridad_1024", "sin_alias")
    con_al = m("aridad_1024", "emisor")
    claim("C3", "la cabecera de un clone con 1024 parámetros agota el marco de la "
                "declaración aunque el cuerpo traiga su cuota; con el tipo declarado una vez "
                "por ancho compila",
          "DEMONSTRADO" if (muere(sin_al) and con_al["exit"] == 0 and con_al["aliases"] == 1
                            and sin_al["aliases"] == 0) else "FALSO",
          {"sin_alias": {"error": sin_al["error"][:120], "s": sin_al["s"]},
           "con_alias": {"exit": con_al["exit"], "s": con_al["s"], "aliases": con_al["aliases"],
                         "cuota": cuota_de(emitido["aridad_1024"])}})

    # --- C4: qué arreglo movió cada frontera ------------------------------------------
    # La frontera de P4 (500 OK / 504 FALLO) se selló con el emisor anterior, donde cada sitio
    # pagaba dos ramas. Hoy 504 cabe SIN cuota: eso lo movió el alias. Y 1024 sitios sin cuota
    # siguen muriendo con el alias puesto: eso lo tiene que sostener la cuota. Los dos
    # mecanismos por separado o la sonda vende uno como el otro.
    antes = {f: m(f, "sin_cuota")["exit"] == 0 for f in ("P4_500", "P4_504")}
    despues = {f: muere(m(f, "sin_cuota")) for f in ("aridad_1024", "extra_case")}
    claim("C4", f"los {P4_FALLO} instanciaciones que P4 selló como FALLO con el emisor anterior "
                f"compilan hoy sin la cuota (el alias bajó el coste de dos ramas a una), y "
                f"1024 instanciaciones siguen muriendo sin ella aunque el alias esté puesto: "
                f"la cuota no es el adorno que arregló P4, es lo que sostiene el resto",
          "DEMONSTRADO" if all(antes.values()) and all(despues.values()) else "FALSO",
          {"p4_sin_cuota_compila": antes, "frontera_alias_sin_cuota": despues,
           "sitios": {f: m(f, "sin_cuota")["sitios"] for f in ("P4_500", "P4_504",
                                                               "aridad_1024", "extra_case")}})

    # --- C5: los dos bordes de P4, con el emisor de hoy -------------------------------
    # El lado OK se re-mide aunque ya cupiera: un arreglo que arregla 504 y rompe 500 es una
    # regresión, y la bisección sólo vale como frontera si los dos bordes siguen en su lado.
    esperado_5 = {}
    for nombre in ("P4_500", "P4_504"):
        ref, _ = run(formas[nombre], [])
        esperado_5[nombre] = {k: ref[k] for k in KEYS}
        z, c = ejecutar(zig, formas[nombre]), ejecutar(ce, formas[nombre])
        esperado_5[nombre + "_medido"] = {"zig": z, "c": c}
    claim("C5", f"los dos puntos sellados de la bisección de P4 ({P4_OK} y {P4_FALLO} "
                f"instanciaciones) compilan en Zig con el emisor de hoy y coinciden con la "
                f"referencia y con C: la frontera ya no corta por debajo de lo que acepta el idioma",
          "DEMONSTRADO" if all(esperado_5[n + "_medido"][b] == esperado_5[n]
                               for n in ("P4_500", "P4_504") for b in ("zig", "c")) else "FALSO",
          esperado_5)

    # --- C6: el caso extra que rompió F5 es el mismo programa y ahora compila ---------
    sha_extra = hashlib.sha256(formas["extra_case"]).hexdigest()
    ref_extra, _ = run(formas["extra_case"], [])
    z_extra, c_extra = ejecutar(zig, formas["extra_case"]), ejecutar(ce, formas["extra_case"])
    esperado_extra = {k: ref_extra[k] for k in KEYS}
    claim("C6", "el caso extra de F5 (256 clones de cuatro ranuras, 1024 instanciaciones) "
                "compila en Zig, coincide con la referencia y con C, y su program_sha256 es "
                "el mismo del recibo FAIL gate_2026-11-02T235456Z.json",
          "DEMONSTRADO" if (sha_extra == SHA_EXTRA_CASE and z_extra == esperado_extra
                            and c_extra == esperado_extra) else "FALSO",
          {"program_sha256": sha_extra, "igual_al_recibo": sha_extra == SHA_EXTRA_CASE,
           "sitios": m("extra_case", "emisor")["sitios"],
           "aliases": m("extra_case", "emisor")["aliases"],
           "esperado": esperado_extra, "zig": z_extra, "c": c_extra})

    # --- C7: la cuota es proporcional al cuerpo, no un número mágico ------------------
    # Se coteja contra las constantes del emisor, no contra un literal de la sonda: si alguien
    # mueve `CUOTA_SITIO`, la afirmación tiene que moverse con él o decir FALSO.
    relacion = {n: (emitido[n].count("= isy_str("), cuota_de(emitido[n])) for n in formas}
    proporcion = all(c == CUOTA_BASE + CUOTA_SITIO * s
                     for s, cs in relacion.values() for c in cs)
    cuerpo = all(emitido[n].splitlines()[i - 1].startswith("fn ")
                 for n in formas
                 for i, _ in [(k, l) for k, l in enumerate(emitido[n].splitlines())
                              if "setEvalBranchQuota" in l])
    plano = zig.emit(compile_ir(FUENTE_SIN_STR))
    sin_guarda = (not any(l.startswith("const Str") for l in plano.splitlines())
                  and "setEvalBranchQuota" not in plano)
    claim("C7", f"en las {len(formas)} formas la cuota del emisor vale exactamente {CUOTA_BASE} + "
                f"{CUOTA_SITIO}·(instanciaciones de la propia función) y es la primera "
                f"sentencia de la función que instancia `str`; un programa sin `str` no "
                f"escribe ni cuota ni alias",
          "DEMONSTRADO" if (proporcion and cuerpo and sin_guarda
                            and all(cs for s, cs in relacion.values())) else "FALSO",
          {"proporcion": proporcion, "primera_sentencia": cuerpo, "sin_str_limpio": sin_guarda,
           "sitios_y_cuota": {n: [s, cs] for n, (s, cs) in relacion.items()}})

    # --- C8: el extremo de aridad que la cuota sola no alcanzaba ----------------------
    ref_2048, _ = run(formas["aridad_2048"], [])
    z_2048, c_2048 = ejecutar(zig, formas["aridad_2048"]), ejecutar(ce, formas["aridad_2048"])
    esperado_2048 = {k: ref_2048[k] for k in KEYS}
    claim("C8", "una definición legal de 2048 parámetros de `str` (2048 instanciaciones y "
                "la firma más grande que se ha probado) compila en Zig y coincide con la "
                "referencia y con C",
          "DEMONSTRADO" if z_2048 == esperado_2048 and c_2048 == esperado_2048 else "FALSO",
          {"esperado": esperado_2048, "zig": z_2048, "c": c_2048})

    # --- C9: el arreglo no es gratis: coste pared medido ------------------------------
    tiempos = {f: m(f, "emisor")["s"] for f in ("512x2", "aridad_1024", "extra_case")}
    claim("C9", "compilar estas formas sigue costando decenas de segundos en Zig: la cuota "
                "levanta el techo, no acelera el compilador (dato para F6, que mide costes)",
          "DEMONSTRADO" if all(v > 1 for v in tiempos.values()) else "FALSO",
          {"s_por_forma": tiempos})

    # --- C10: el otro techo que apareció midiendo, y de quién es ----------------------
    # No es del emisor ni del idioma: es de Python. Se mide aquí porque la sonda es el
    # recibo, y un número que vive en /tmp no es evidencia.
    prof, fuentes_front = {}, {}
    for nombre, expr in (("cadena_241", cadena(241)), ("cadena_242", cadena(242)),
                         ("arbol_2000", arbol(2000))):
        prof[nombre], fuentes_front[nombre] = frontend(expr)
    claim("C10", "la ruta de frontend (`compile_ir`) tiene un techo de **profundidad** de "
                 "expresión, no de tamaño: 241 términos `len(s)` sumados por la izquierda se "
                 "aceptan y 242 sueltan `RecursionError` contra el límite de fábrica de Python, "
                 "mientras un árbol de 2000 términos (profundidad 12, fuente 8 veces más "
                 "grande) se acepta — es artefacto del anfitrión y no tiene guarda nombrada: "
                 "queda como issue Z2",
          "DEMONSTRADO" if (prof["cadena_241"]["resultado"] == "OK"
                            and prof["cadena_242"]["resultado"] == "RecursionError"
                            and prof["arbol_2000"]["resultado"] == "OK"
                            and prof["arbol_2000"]["fuente_bytes"]
                            > prof["cadena_242"]["fuente_bytes"] * 4) else "FALSO",
          prof)

    lineas.append(f"zig: {zig.toolchain()}   gcc: {ce.toolchain()}")
    for nombre, fuente in formas.items():
        lineas.append(f"{nombre:12} {len(fuente):8} bytes   "
                      f"{m(nombre, 'emisor')['sitios']:5} instanciaciones   "
                      f"{m(nombre, 'emisor')['aliases']:4} alias   "
                      f"cuota {cuota_de(emitido[nombre])}")
    lineas.append("")
    for clave in sorted(med):
        v = med[clave]
        lineas.append(f"{clave:38} exit={v['exit']} {v['s']:6}s {v['error'][:70]}")
    lineas.append("")
    for c in claims.values():
        lineas.append(f"{c['id']:>3} {c['estado']:<15} {c['afirmacion']}")
        lineas.append(f"      observado: {json.dumps(c['observado'], ensure_ascii=False)[:220]}")
    for mensaje in falsos:
        lineas.append(f"CONTROL FALSO: {mensaje}")

    documento = {"schema": "isycolang.z1_ceiling_probe/2", "generated_utc": stamp,
                 "git_head": _gate.git_head(), **_gate.arbol(),
                 "toolchains": {"zig": zig.toolchain(), "c": ce.toolchain()},
                 "regla": {"coste_por_instanciacion": "1 rama (acotado por C1: 960 sitios con "
                                                      "firma corta caben en 1000 y 1024 revientan)",
                           "coste_antes_del_alias": "2 ramas: la cota sellada de P4 estaba en "
                                                    f"{P4_OK} OK / {P4_FALLO} FALLO",
                           "margen": f"CUOTA_SITIO={CUOTA_SITIO}, ocho veces el coste medido",
                           "cuota_del_emisor": f"{CUOTA_BASE} + {CUOTA_SITIO}*sitios por cuerpo",
                           "alias": "un `const StrN = IsyStr(N);` por ancho, usado en todo el "
                                    "codigo generado"},
                 "formas": {n: {"fuente_bytes": len(f),
                                "fuente_sha256": hashlib.sha256(f).hexdigest(),
                                "emitido_sha256": hashlib.sha256(emitido[n].encode()).hexdigest(),
                                "instanciaciones": emitido[n].count("= isy_str("),
                                "cuota": cuota_de(emitido[n])}
                            for n, f in formas.items()},
                 "continuidad": {"extra_case_sha256_recibo_F5": SHA_EXTRA_CASE,
                                 "biseccion_P4": {"max_ok_sitios": P4_OK,
                                                  "min_fallo_sitios": P4_FALLO,
                                                  "recibo": "evidence/v05_p4/run_20261102T085025Z.json"},
                                 "gate_previo": "evidence/backends/gate_2026-11-02T235456Z.json"},
                 "mediciones": med,
                 "frontend_profundidad": prof,
                 "claims": list(claims.values()),
                 "veredicto": "FALSO" if falsos else "DEMONSTRADO"}
    print("\n".join(lineas))
    if not args.write:
        return 1 if falsos else 0
    if falsos:
        print("no se sella: hay controles falsos", file=sys.stderr)
        return 1
    destino = _gate.EVIDENCE / "z1_ceiling"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, fuente in formas.items():
        (destino / f"run_{stamp}_{nombre}.isy").write_bytes(fuente)
    for nombre, fuente in fuentes_front.items():
        (destino / f"run_{stamp}_front_{nombre}.isy").write_bytes(fuente)
    # El fuente emitido del caso extra es el artefacto del que dependen las filas del gate:
    # `build/` esta fuera del repo, así que sin esta copia el sha del fuente no recomponen nada.
    (destino / f"run_{stamp}_extra_case_emitido.zig").write_text(emitido["extra_case"],
                                                                 encoding="utf-8")
    _gate.sellar(documento, "\n".join(lineas) + "\n", destino, f"run_{stamp}")
    print(f"sellado en {destino}/run_{stamp}.{{json,txt}} mas las "
          f"{len(formas) + len(fuentes_front)} fuentes y el .zig emitido del caso extra")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
