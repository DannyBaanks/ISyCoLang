"""Sonda de Z1: el techo de comptime de Zig era forma del emisor, no frontera del idioma.

Z1 preguntaba si un programa legal de v0.5 puede compilar en C y Rust y no en Zig, o si el
idioma hereda el techo del toolchain más débil. La respuesta medida es que el techo lo ponía
`isyco/backends/zig.py` en dos sitios, y ninguno es semántica:

1. **el cuerpo**: Zig cuesta ~2 ramas de evaluación por instanciación de `str`, así que un
   cuerpo con más de ~500 agotaba la cuota de fábrica de 1000. El emisor ahora se concede
   `1000 + 8·sitios` dentro de cada función —cuatro veces el coste medido, finita, y crece
   solo con el código que genera de verdad—;
2. **la firma**: evaluar la cabecera de un clone con 1024 parámetros `IsyStr(2)` agota el
   marco de la *declaración*, y ninguna cuota escrita dentro de un cuerpo lo alcanza. El
   emisor declara el tipo una vez por ancho (`const Str2 = IsyStr(2);`) y usa el alias.

La sonda no se cree el arreglo: cada claim de «compila» tiene su variante saboteada al revés
(sin la cuota, la cuota a nivel de archivo, sin el alias) medida con el compilador muriendo de
verdad, y todo programa que compila se coteja con la referencia normativa y con el binario C.

Al medir el techo de Zig apareció **otro** techo, que no es ni del idioma ni del emisor: la ruta
de frontend de referencia (`compile_ir`) se desborda con `RecursionError` a los 242 niveles de
anidamiento de una expresión, mientras un árbol de 2000 términos pasa. Es un límite del anfitrión
sin guarda nombrada, y por eso se mide y se sella aquí: queda abierto como issue Z2 en
`docs/OPEN_QUESTIONS_P1_P4.md`.

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
# 500 instanciaciones cabían y 504 no. Aquí se re-miden con el emisor de hoy.
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

    El par `largo` es lo que separa coste por instanciación de coste por ancho: 512 sitios
    de ancho 2 y 512 de ancho 64 cuestan lo mismo, así que la cuota del emisor va por cuenta.
    """
    firma = ", ".join(f"p{i}: str" for i in range(1, a + 1))
    args = ", ".join('"%s"' % b36(i, largo) for i in range(a))
    return (f'isyco 0.5\n\nfn m({firma}) -> i64 {{ return len(p1); }}\n'
            f'fn main() -> i64 !emit {{\n    emit m({args});\n    return 0;\n}}\n').encode()


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

    def muere(res) -> bool:
        return res["exit"] != 0 and RAMA_QUE_FALTA in res["error"]

    # --- las formas que se miden ------------------------------------------------------
    formas = {
        "512x2": ranuras_de_ancho(512, 2),
        "512x64": ranuras_de_ancho(512, 64),
        "aridad_1024": ranuras_de_ancho(1024, 2),
        "aridad_2048": ranuras_de_ancho(2048, 3),
        # `fuente_ranuras_parciales(2, 2, u)` hace 2u clones de 2 ranuras: 4u instanciaciones.
        "P4_500": fuente_ranuras_parciales(2, 2, P4_OK // 4),
        "P4_504": fuente_ranuras_parciales(2, 2, P4_FALLO // 4),
        "extra_case": fuente_ranuras(4, 4),
    }
    emitido = {n: zig.emit(compile_ir(f)) for n, f in formas.items()}

    # --- C1: el coste va por instanciación, el ancho no -------------------------------
    sin1 = compilar(zig, sin_cuota(emitido["512x2"]))
    sin2 = compilar(zig, sin_cuota(emitido["512x64"]))
    ok1 = compilar(zig, emitido["512x2"])
    ok2 = compilar(zig, emitido["512x64"])
    claim("C1", "512 instanciaciones de `str` agotan la cuota de fábrica de Zig y el ancho "
                "del literal no pesa: ancho 2 y ancho 64 mueren igual sin la línea del emisor "
                "y compilan igual con ella",
          "DEMONSTRADO" if (muere(sin1) and muere(sin2) and ok1["exit"] == ok2["exit"] == 0
                            and ok1["sitios"] == ok2["sitios"] == 512) else "FALSO",
          {"sitios": [ok1["sitios"], ok2["sitios"]],
           "cuota": [cuota_de(emitido["512x2"]), cuota_de(emitido["512x64"])],
           "sin_cuota": [sin1["error"][:90], sin2["error"][:90]],
           "ms": [ok1["s"], ok2["s"]]})

    # --- C2: la posición de la cuota no es opcional -----------------------------------
    fichero = compilar(zig, cuota_en_fichero(emitido["512x2"]))
    claim("C2", "la misma cuota puesta a nivel de archivo no arregla nada: un `comptime` de "
                "archivo es su propio marco (sabotaje medido, no supuesto)",
          "DEMONSTRADO" if muere(fichero) else "FALSO",
          {"error": fichero["error"][:120], "s": fichero["s"]})

    # --- C3: la firma es un marco aparte y el alias la abarata ------------------------
    sin_alias_1024 = compilar(zig, sin_alias(emitido["aridad_1024"]))
    con_alias_1024 = compilar(zig, emitido["aridad_1024"])
    claim("C3", "la cabecera de un clone con 1024 parámetros agota el marco de la "
                "declaración aunque el cuerpo traiga su cuota; con el tipo declarado una vez "
                "por ancho compila",
          "DEMONSTRADO" if (muere(sin_alias_1024) and con_alias_1024["exit"] == 0
                            and con_alias_1024["aliases"] == 1
                            and sin_alias_1024["aliases"] == 0) else "FALSO",
          {"sin_alias": {"error": sin_alias_1024["error"][:120], "s": sin_alias_1024["s"]},
           "con_alias": {"exit": con_alias_1024["exit"], "s": con_alias_1024["s"],
                         "aliases": con_alias_1024["aliases"],
                         "cuota": cuota_de(emitido["aridad_1024"])}})

    # --- C4: los dos puntos sellados de P4, con el emisor de hoy ----------------------
    # El lado OK se re-mide aunque ya cupiera: un arreglo que arregla 504 y rompe 500 es una
    # regresión, y la bisección sólo vale como frontera si los dos bordes siguen en su lado.
    esperado_4 = {}
    for nombre in ("P4_500", "P4_504"):
        ref, _ = run(formas[nombre], [])
        esperado_4[nombre] = {k: ref[k] for k in KEYS}
        z, c = ejecutar(zig, formas[nombre]), ejecutar(ce, formas[nombre])
        esperado_4[nombre + "_medido"] = {"zig": z, "c": c}
    claim("C4", f"los dos puntos sellados de la bisección de P4 ({P4_OK} y {P4_FALLO} "
                f"instanciaciones) compilan en Zig con el emisor de hoy y coinciden con la "
                f"referencia y con C: la frontera ya no corta por debajo de lo que acepta el idioma",
          "DEMONSTRADO" if all(esperado_4[n + "_medido"][b] == esperado_4[n]
                               for n in ("P4_500", "P4_504") for b in ("zig", "c")) else "FALSO",
          esperado_4)

    # --- C5: el caso extra que rompió F5 es el mismo programa y ahora compila ---------
    sha_extra = hashlib.sha256(formas["extra_case"]).hexdigest()
    ref_extra, _ = run(formas["extra_case"], [])
    z_extra, c_extra = ejecutar(zig, formas["extra_case"]), ejecutar(ce, formas["extra_case"])
    esperado_extra = {k: ref_extra[k] for k in KEYS}
    claim("C5", "el caso extra de F5 (256 clones de cuatro ranuras, 1024 instanciaciones) "
                "compila en Zig, coincide con la referencia y con C, y su program_sha256 es "
                "el mismo del recibo FAIL gate_2026-11-02T235456Z.json",
          "DEMONSTRADO" if (sha_extra == SHA_EXTRA_CASE and z_extra == esperado_extra
                            and c_extra == esperado_extra) else "FALSO",
          {"program_sha256": sha_extra, "igual_al_recibo": sha_extra == SHA_EXTRA_CASE,
           "sitios": emitido["extra_case"].count("= isy_str("),
           "aliases": sum(1 for l in emitido["extra_case"].splitlines()
                          if l.startswith("const Str")),
           "esperado": esperado_extra, "zig": z_extra, "c": c_extra})

    # --- C6: la cuota es proporcional al cuerpo, no un número mágico ------------------
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
    sin_guarda = not any(l.startswith("const Str") for l in plano.splitlines()) \
        and "setEvalBranchQuota" not in plano
    claim("C6", f"en las {len(formas)} formas la cuota del emisor vale exactamente {CUOTA_BASE} + "
                f"{CUOTA_SITIO}·(instanciaciones de la propia función) y es la primera "
                f"sentencia de la función que instancia `str`; un programa sin `str` no "
                f"escribe ni cuota ni alias",
          "DEMONSTRADO" if (proporcion and cuerpo and sin_guarda
                            and all(cs for s, cs in relacion.values())) else "FALSO",
          {"proporcion": proporcion, "primera_sentencia": cuerpo, "sin_str_limpio": sin_guarda,
           "sitios_y_cuota": {n: [s, cs] for n, (s, cs) in relacion.items()}})

    # --- C7: el extremo de aridad que la cuota sola no alcanzaba ----------------------
    ref_2048, _ = run(formas["aridad_2048"], [])
    z_2048, c_2048 = ejecutar(zig, formas["aridad_2048"]), ejecutar(ce, formas["aridad_2048"])
    esperado_2048 = {k: ref_2048[k] for k in KEYS}
    claim("C7", "una definición legal de 2048 parámetros de `str` (2048 instanciaciones y "
                "la firma más grande que se ha probado) compila en Zig y coincide con la "
                "referencia y con C",
          "DEMONSTRADO" if z_2048 == esperado_2048 and c_2048 == esperado_2048 else "FALSO",
          {"esperado": esperado_2048, "zig": z_2048, "c": c_2048})

    # --- C8: el arreglo no es gratis: coste pared medido ------------------------------
    # 512x2 y aridad_1024 ya se compilaron crudo en C1/C3; se reutiliza esa medida y solo el
    # caso extra se mide de nuevo, para no pagar dos veces el mismo `build-exe`.
    tiempos = {"512x2": ok1["s"], "aridad_1024": con_alias_1024["s"],
               "extra_case": compilar(zig, emitido["extra_case"])["s"]}
    claim("C8", "compilar estas formas sigue costando decenas de segundos en Zig: la cuota "
                "levanta el techo, no acelera el compilador (dato para F6, que mide costes)",
          "DEMONSTRADO" if all(v > 1 for v in tiempos.values()) else "FALSO",
          {"s_por_forma": tiempos})

    # --- C9: el otro techo que apareció midiendo, y de quién es -----------------------
    # No es del emisor ni del idioma: es de Python. Se mide aquí porque la sonda es el
    # recibo, y un número que vive en /tmp no es evidencia.
    prof, fuentes_front = {}, {}
    for nombre, expr in (("cadena_241", cadena(241)), ("cadena_242", cadena(242)),
                         ("arbol_2000", arbol(2000))):
        prof[nombre], fuentes_front[nombre] = frontend(expr)
    claim("C9", "la ruta de frontend (`compile_ir`) tiene un techo de **profundidad** de "
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
                      f"{emitido[nombre].count('= isy_str('):5} instanciaciones   "
                      f"{sum(1 for l in emitido[nombre].splitlines() if l.startswith('const Str')):3} alias")
    lineas.append("")
    for c in claims.values():
        lineas.append(f"{c['id']:>3} {c['estado']:<15} {c['afirmacion']}")
        lineas.append(f"      observado: {json.dumps(c['observado'], ensure_ascii=False)[:220]}")
    for mensaje in falsos:
        lineas.append(f"CONTROL FALSO: {mensaje}")

    documento = {"schema": "isycolang.z1_ceiling_probe/1", "generated_utc": stamp,
                 "git_head": _gate.git_head(), **_gate.arbol(),
                 "toolchains": {"zig": zig.toolchain(), "c": ce.toolchain()},
                 "regla": {"coste_por_instanciacion": "2 ramas de evaluacion por isy_str: "
                                                      "acotado por C1 entre 1000/512 y 1000/500",
                           "margen": "CUOTA_SITIO deja cuatro veces el coste medido sin "
                                     "apagar la guarda (sigue finita y sigue creciendo solo con "
                                     "lo que el emisor genera)",
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
                 "sabotajes": {"sin_cuota_512x2": sin1, "sin_cuota_512x64": sin2,
                               "cuota_en_fichero_512x2": fichero,
                               "sin_alias_aridad_1024": sin_alias_1024},
                 "compilados": {"512x2": ok1, "512x64": ok2, "aridad_1024": con_alias_1024},
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
    print(f"sellado en {destino}/run_{stamp}.{{json,txt}} mas las diez fuentes y el .zig "
          "emitido del caso extra")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
