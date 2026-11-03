"""Z2 ya decidida: mide que la cota de anidamiento la pone el idioma, no el anfitrión.

`tools/z2_depth_probe.py` respondió la pregunta de Z2 —el frontend tenía techo, era de
profundidad y era de Python (`evidence/z2_depth/run_2026-11-03T074629Z.json`)— y con la guarda
puesta (`isyco/ast.py:MAX_EXPR_DEPTH`) sus claims sobre la bajada ya no son la pregunta. Esta
sonda mide el estado **después** de la decisión, sobre el mismo material:

* dónde cae el borde en cada una de las cuatro caras del anidar, y con qué señal;
* si el borde sigue moviéndose con la pila que trae quien llama (antes: 241 → 166);
* cuántos frames pide la forma legal más cara y con cuántos frames llega quien llama de verdad;
* que la población del repo queda lejos, con la misma regla de censo que la sonda vieja;
* que el `deepcopy` del clon de V6 (`specialize.py:55`) ya no se alcanza por esta vía;
* sabotaje: mover la constante mueve el borde, así que rechaza la guarda y no el anfitrión.

Corre todo lo que puede agotar la pila en un proceso hijo, como su predecesora. `--write` sella
en `evidence/z2_guard/` y se niega si algún control sale `FALSO`.
"""
from __future__ import annotations

import hashlib
import json
import re
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[1]))
import _gate  # noqa: E402
from isyco import ast as A  # noqa: E402

ROOT = _gate.ROOT
LIMITE_FABRICA = 1000
COTA = A.MAX_EXPR_DEPTH

# El hijo baja el fuente y reporta: sin excepciones de la sonda, con el código y el `at` del
# rechazo, y con el conteo de frames cuando la señal sigue siendo `RecursionError`.
HIJO = r'''
import json, resource, sys, time, traceback
ruta, limite, previos, modo, cota = (sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
                                     sys.argv[5], sys.argv[6])
sys.setrecursionlimit(limite)
if cota != "0":
    import isyco.ast as A
    A.MAX_EXPR_DEPTH = int(cota)          # sabotaje: la cota se mueve desde fuera del idioma

def bajar(m, data):
    if m == "ir":
        from isyco.ir_interp import compile_ir
        return compile_ir(data)
    if m == "interp":
        from isyco.interp import run
        return run(data, [])[0]
    raise ValueError(m)

def hondo(n, expr):
    if n == 0:
        t0 = time.time()
        try:
            res = bajar(modo, open(expr, "rb").read())
            r = {"resultado": "OK", "s": round(time.time() - t0, 3)}
            if isinstance(res, dict) and "status" in res:
                r["status"] = res["status"]
                r["code"] = res.get("code")
            return r
        except RecursionError:
            tb = traceback.extract_tb(sys.exc_info()[2])
            return {"resultado": "RecursionError", "frames": len(tb),
                    "frames_copy": sum(1 for f in tb if f.filename.endswith("copy.py")),
                    "s": round(time.time() - t0, 3)}
        except Exception as exc:
            return {"resultado": type(exc).__name__, "code": getattr(exc, "code", None),
                    "at": getattr(exc, "at", None), "detalle": str(exc)[:240],
                    "s": round(time.time() - t0, 3)}
    return hondo(n - 1, expr)

r = hondo(previos, ruta)
r["rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
print(json.dumps(r))
'''

#: las cuatro caras del anidar: `(nombre, fuente(k, expr), expr(k), nivel esperado en k)`
#: - parentesis y prefijos los cuenta el **parser** (un nivel por par o por signo, más el 1 de
#:   la expresión); el AST se queda en 1 y 2;
#: - la cadena izquierda y la cadena sobre `str` pelado las cuenta el **AST**: la del pelado
#:   suma el nivel de su propio operando, así que llega al tope un término antes.
def terminos(k: int, ter: str = "1") -> str:
    return " + ".join([ter] * k)


def fuente_parentesis(k: int) -> str:
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {'(' * k}1{')' * k};\n"
            f"    emit x;\n    return x;\n}}\n")


def fuente_prefijo(k: int) -> str:
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {'-' * k}1;\n"
            f"    emit x;\n    return x;\n}}\n")


def fuente_cadena(k: int) -> str:
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {terminos(k)};\n"
            f"    emit x;\n    return x;\n}}\n")


def fuente_pelada(k: int) -> str:
    return (f'isyco 0.5\n\nfn cuanto(s: str) -> i64 {{\n    return {terminos(k, "len(s)")};\n}}\n\n'
            f'fn main() -> i64 !emit {{\n    emit cuanto("hola");\n'
            f'    return {4 * k};\n}}\n')


def arbol(k: int, ter: str = "1") -> str:
    """Los mismos `k` términos en árbol binario balanceado: profundidad ~log2(k)."""
    if k == 1:
        return ter
    izq = k // 2
    return f"({arbol(izq, ter)} + {arbol(k - izq, ter)})"


def fuente_arbol(k: int) -> str:
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {arbol(k)};\n"
            f"    emit x;\n    return x;\n}}\n")


CARAS = {"parentesis": (fuente_parentesis, COTA - 1),     # k pares -> nivel k+1
         "prefijo": (fuente_prefijo, COTA),               # el último `-` se colapsa en el literal
         "cadena": (fuente_cadena, COTA),                 # k términos -> AST k
         "pelada": (fuente_pelada, COTA - 1)}             # k términos -> AST k+1 (el operando)


def ejecutar(camino: Path, limite: int = LIMITE_FABRICA, previos: int = 0,
             modo: str = "ir", cota: int = 0) -> dict:
    proc = subprocess.run([sys.executable, "-c", HIJO, str(ROOT), str(camino), str(limite),
                           str(previos), modo, str(cota)],
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        return {"resultado": f"MUERTE_DEL_HIJO rc={proc.returncode}",
                "detalle": (proc.stderr or "")[-200:]}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"resultado": "ERROR_HARNESS", "detalle": (proc.stderr or proc.stdout)[-300:]}


def paso(res: dict) -> bool:
    return res.get("resultado") == "OK" and res.get("status", "HALTED") == "HALTED"


def escribir(tmp: Path, nombre: str, texto: str, prefijado: dict) -> Path:
    camino = tmp / nombre
    camino.write_text(texto, encoding="utf-8")
    prefijado[nombre] = camino
    return camino


def borde(tmp: Path, nombre: str, hacer, k_ok: int, k_fallo: int, guardados: dict) -> dict:
    """El par exacto `(tope, un nivel más)`: no una bisección, sino el borde que nombra la spec."""
    a = escribir(tmp, f"cota_{nombre}_ok_{k_ok}.isy", hacer(k_ok), guardados)
    b = escribir(tmp, f"cota_{nombre}_fallo_{k_fallo}.isy", hacer(k_fallo), guardados)
    return {"ok": k_ok, "fallo": k_fallo, "medido_ok": ejecutar(a), "medido_fallo": ejecutar(b),
            "fuente_ok_sha256": hashlib.sha256(a.read_bytes()).hexdigest(),
            "fuente_fallo_sha256": hashlib.sha256(b.read_bytes()).hexdigest()}


def limite_minimo(tmp: Path, nombre: str, hacer, k: int, guardados: dict,
                  hi: int = LIMITE_FABRICA - 1) -> dict:
    """Mínimo `setrecursionlimit` con el que la forma de `k` niveles todavía baja: su precio."""
    camino = escribir(tmp, f"precio_{nombre}_{k}.isy", hacer(k), guardados)
    lo, tope = 40, hi
    if not paso(ejecutar(camino, limite=tope)):
        return {"ok": False, "frames": None, "medido": ejecutar(camino, limite=tope)}
    while lo + 1 < tope:
        mid = (lo + tope) // 2
        if paso(ejecutar(camino, limite=mid)):
            tope = mid
        else:
            lo = mid
    return {"ok": True, "frames": tope, "medido": ejecutar(camino, limite=tope)}


def frames_quien_llama(tmp: Path, guardados: dict) -> dict:
    """Cuántos frames trae el proceso que llama al frontend, por las dos rutas reales del paquete."""
    sonda = r'''
import inspect, io, json, runpy, sys, unittest
ruta = sys.argv[2]
medido = {}
import isyco.ir_interp as II
original = II.compile_ir
def spy(data, *a, **k):
    medido.setdefault("ir", len(inspect.stack()))
    return original(data, *a, **k)
II.compile_ir = spy
import isyco.interp as IN
base = IN.run
def spy_run(data, *a, **k):
    medido.setdefault("run", len(inspect.stack()))
    return base(data, *a, **k)
IN.run = spy_run
sys.argv = ["isyco", "ir", ruta]
try:
    runpy.run_module("isyco", run_name="__main__")
except SystemExit:
    pass
from tests import test_depth                     # la ruta real: un test del paquete, no un eco
corrido = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.TestLoader().loadTestsFromTestCase(test_depth.CotaNombrada))
print(json.dumps({"medido": medido, "tests": [corrido.testsRun, len(corrido.failures),
                                               len(corrido.errors)]}))
'''
    camino = escribir(tmp, "frames_quien_llama.isy", fuente_cadena(4), guardados)
    proc = subprocess.run([sys.executable, "-c", sonda, str(ROOT), str(camino)],
                          capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    try:
        visto = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        visto = {"error": (proc.stderr or proc.stdout)[-300:]}
    return {"frames": visto.get("medido", visto), "tests": visto.get("tests"),
            "crudo": visto, "rc": proc.returncode}


def profundidad(node) -> int:
    """Máxima cadena de nodos de expresión dentro de un módulo ISY-IR: la regla del censo viejo."""
    mejor, pila = 0, [(node, 0)]
    while pila:
        o, d = pila.pop()
        if isinstance(o, dict):
            nd = d + 1 if "k" in o else d
            mejor = max(mejor, nd)
            for v in o.values():
                if isinstance(v, (dict, list)):
                    pila.append((v, nd))
        elif isinstance(o, list):
            for v in o:
                if isinstance(v, (dict, list)):
                    pila.append((v, d))
    return mejor


def censo_poblacion() -> dict:
    """El mismo censo de `z2_depth_probe.py`: todas las fuentes de `programs/`, misma regla."""
    from isyco.errors import InvalidProgram
    from isyco.ir_interp import compile_ir
    bajan, no_bajan = [], []
    for ruta in sorted(ROOT.glob("programs/**/*.isy")):
        try:
            bajan.append((profundidad(compile_ir(ruta.read_bytes())),
                          str(ruta.relative_to(ROOT))))
        except InvalidProgram as exc:
            no_bajan.append((str(ruta.relative_to(ROOT)), exc.code))
        except RecursionError:
            no_bajan.append((str(ruta.relative_to(ROOT)), "RecursionError"))
    bajan.sort(reverse=True)
    casos_z2 = tuple(f"{n}_" for n in range(449, 455))
    reales = [x for x in bajan if not x[1].rsplit("/", 1)[-1].startswith(casos_z2)]
    return {"fuentes_que_bajan": len(bajan), "rechazadas": len(no_bajan),
            "max_profundidad": bajan[0][0] if bajan else 0,
            "max_fuente": bajan[0][1] if bajan else "",
            "max_sin_casos_z2": reales[0][0] if reales else 0,
            "max_fuente_sin_casos_z2": reales[0][1] if reales else "",
            "top": [{"profundidad": d, "fuente": n} for d, n in bajan[:8]],
            "biblioteca_texto": [{"profundidad": d, "fuente": n} for d, n in bajan
                                 if "06_biblioteca_texto" in n],
            "rechazos_por_codigo": sorted({c for _, c in no_bajan})}


def main(argv) -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--write", action="store_true", help="sella en evidence/z2_guard/")
    args = parser.parse_args(argv)
    stamp = _gate.stamp()
    lineas, claims, falsos = [], {}, []

    def claim(identidad, afirmacion, estado, observado):
        claims[identidad] = {"id": identidad, "afirmacion": afirmacion, "estado": estado,
                             "observado": observado}
        print(f"  [{identidad}] {estado}", flush=True)
        if estado == "FALSO":
            falsos.append(f"{identidad}: {afirmacion} — observado {json.dumps(observado)[:160]}")

    lineas.append(f"python: {sys.version.split()[0]}  limite de fabrica: {LIMITE_FABRICA}"
                  f"  cota nombrada: {COTA}"
                  f"  rss sonda: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB")

    with tempfile.TemporaryDirectory(prefix="isyco_z2g_") as t:
        tmp = Path(t)
        guardados: dict[str, Path] = {}

        # --- C1: el borde nombrado, en las cuatro caras, con la señal del idioma -----------
        bordes = {}
        for nombre, (hacer, k_ok) in CARAS.items():
            bordes[nombre] = borde(tmp, nombre, hacer, k_ok, k_ok + 1, guardados)
            print(f"  {nombre:10} borde {bordes[nombre]['ok']} OK / {bordes[nombre]['fallo']}"
                  f" -> {bordes[nombre]['medido_fallo'].get('code')}", flush=True)
        rechazo = bordes["cadena"]["medido_fallo"]
        niveles = {n: (re.search(r"anida (\d+) niveles", b["medido_fallo"].get("detalle", ""))
                       or [None, "sin número"])[1] for n, b in bordes.items()}
        bien = (all(paso(b["medido_ok"]) for b in bordes.values())
                and all(b["medido_fallo"].get("code") == "SPEC_LIMIT" for b in bordes.values())
                and all(str(v) == str(COTA + 1) for v in niveles.values()))
        claim("C1", f"la cota nombrada es **{COTA}** y el borde cae en el **mismo nivel** en las "
                    "cuatro caras del anidar (parentesis y prefijo los cuenta el parser; cadena "
                    "y cadena con clon los cuenta el AST), siempre con `INVALID_PROGRAM` / "
                    "`SPEC_LIMIT` nombrando el nivel "
                    f"{COTA + 1} y la cota en el mensaje, en lugar de "
                    "`RecursionError`",
              "DEMONSTRADO" if bien else "FALSO",
              {n: {"ok": b["ok"], "fallo": b["fallo"],
                   "resultado_fallo": b["medido_fallo"].get("code")
                   or b["medido_fallo"].get("resultado"),
                   "nivel_nombrado": niveles[n],
                   "sha_ok": b["fuente_ok_sha256"][:8], "sha_fallo": b["fuente_fallo_sha256"][:8]}
               for n, b in bordes.items()}
              | {"mensaje": rechazo.get("detalle"), "at": rechazo.get("at")})

        # --- C2: el borde ya no depende de la pila que trae quien llama --------------------
        # Por la ruta de la referencia (`interp.run`), que es la normativa de F2.
        por_previos = {}
        cadena_fallo = guardados[f"cota_cadena_fallo_{COTA + 1}.isy"]
        cadena_ok = guardados[f"cota_cadena_ok_{COTA}.isy"]
        for previos in (0, 50, 100, 150, 200, 300):
            por_previos[previos] = [
                ejecutar(cadena_fallo, previos=previos, modo="interp").get("code"),
                ejecutar(cadena_ok, previos=previos, modo="interp").get("status")]
        estable = all(v == ["SPEC_LIMIT", "HALTED"] for v in por_previos.values())
        claim("C2", "el borde es del idioma y no de la pila: con 0, 50, 100, 150, 200 y 300 "
                    "frames previos del llamante, los "
                    f"{COTA + 1} niveles siguen dando `SPEC_LIMIT` y los {COTA} siguen "
                    "`HALTED` (antes de la guarda el mismo fuente cortaba en 241 con pila "
                    "limpia y en 166 con 300 frames encima, "
                    "`evidence/z2_depth/run_2026-11-03T074629Z.json` §pila_del_llamante)",
              "DEMONSTRADO" if estable else "FALSO", por_previos)

        # --- C3: precio en frames de la forma legal más cara --------------------------------
        precios = {n: limite_minimo(tmp, n, hacer, k_ok, guardados)
                   for n, (hacer, k_ok) in CARAS.items()}
        caras = [p["frames"] for p in precios.values() if p["ok"]]
        claim("C3", "la forma legal más cara cabe en el límite de fábrica con holgura: el precio "
                    "de cada cara al tope es el mínimo `setrecursionlimit` con el que todavía "
                    "baja (bisecado entre 40 y 999)",
              "DEMONSTRADO" if len(caras) == len(precios) and max(caras) < LIMITE_FABRICA - 1
              else "FALSO",
              {"frames_minimos": precios, "margen_con_999": LIMITE_FABRICA - 1 - max(caras)
               if caras else None})

        # --- C4: cuánta pila traen los caminos reales del paquete ---------------------------
        llamante = frames_quien_llama(tmp, guardados)
        traidos = [v for v in llamante["frames"].values() if isinstance(v, int)]
        verde = llamante["tests"] and llamante["tests"][1:] == [0, 0]
        aire = LIMITE_FABRICA - 1 - max(caras) if caras else 0
        claim("C4", "quien llama al frontend desde los caminos del paquete llega con poca pila "
                    "gastada: medido `len(inspect.stack())` en la primera línea de `compile_ir` "
                    "por la ruta `python3 -m isyco ir`, y en la primera línea de `interp.run` "
                    "por la ruta de un test del paquete (`tests/test_depth.py`, corrido en verde "
                    "dentro de la sonda). El número se compara con el aire que deja la forma "
                    "legal más cara",
              "DEMONSTRADO" if len(traidos) == 2 and max(traidos) < aire and verde
              else "FALSO", {"frames_del_llamante": llamante["frames"],
                             "tests_de_la_sonda": llamante["tests"], "aire_restante": aire})

        # --- C5: la población queda lejos ----------------------------------------------------
        cen = censo_poblacion()
        claim("C5", "ninguna fuente del repo roza la cota: con la misma regla de censo que "
                    "`tools/z2_depth_probe.py` (cadena de nodos `k` en la IR) la población sigue "
                    "en el número medido el 2026-11-03, y los únicos que llegan a "
                    f"{COTA} son los seis casos que fijan el borde (`449`–`454`)",
              "DEMONSTRADO" if (cen["max_sin_casos_z2"] <= 8
                                and cen["fuentes_que_bajan"] >= 150
                                and "RecursionError" not in cen["rechazos_por_codigo"])
              else "FALSO", cen)

        # --- C6: el clon ya no se alcanza por esta vía ---------------------------------------
        # Los dos lados de la frontera vieja: 241 términos **bajaban** (AST 242) y 242 reventaban.
        # Hoy se rechazan los dos: el precio de nombrar el borde es dejar fuera lo que el
        # anfitrión toleraba por casualidad.
        antes = {"frontera_con_clon": [241, 242], "frames_de_copy": "985 de 999",
                 "recibo": "evidence/z2_depth/run_2026-11-03T074629Z.json"}
        tolerada = ejecutar(escribir(tmp, "clon_241_terminos.isy", fuente_pelada(241), guardados))
        muerta = ejecutar(escribir(tmp, "clon_242_terminos.isy", fuente_pelada(242), guardados))
        ahora = {"241_terminos_antes_bajaba": tolerada, "242_terminos_antes_reventaba": muerta}
        grande = escribir(tmp, "arbol_2000.isy", fuente_arbol(2000), guardados)
        r_grande = ejecutar(grande)
        chiquita = escribir(tmp, "pelada_64.isy", fuente_pelada(64), guardados)
        r_chiquita = ejecutar(chiquita)
        claim("C6", "la guarda corta **antes** de que el clon exista: el fuente que moría a los "
                    "242 términos `len(s)` —985 de 999 frames del traceback eran de `copy.py` "
                    f"por el `deepcopy` de `specialize.py:55`— hoy se rechaza con `SPEC_LIMIT` "
                    f"en {muerta.get('s')} s, y con él el de 241 términos que antes **bajaba** "
                    f"({tolerada.get('code')} en {tolerada.get('s')} s): nombrar el borde cuesta "
                    "dejar fuera fuentes que el anfitrión toleraba. Y el techo sigue siendo de "
                    "**profundidad**, no de tamaño: 2 000 términos en árbol balanceado "
                    f"(12 niveles, {len(grande.read_bytes())} bytes) bajan, los mismos 64 en "
                    f"cadena izquierda sobre `str` pelado ({len(chiquita.read_bytes())} bytes) no",
              "DEMONSTRADO" if (paso(r_grande) and tolerada.get("code") == "SPEC_LIMIT"
                                and muerta.get("code") == "SPEC_LIMIT"
                                and r_chiquita.get("code") == "SPEC_LIMIT"
                                and "RecursionError" not in
                                [tolerada.get("resultado"), muerta.get("resultado"),
                                 r_chiquita.get("resultado")])
              else "FALSO",
              {"antes": antes, "ahora": ahora,
               "arbol_2000": {"bytes": len(grande.read_bytes()), "medido": r_grande},
               "pelada_64": {"bytes": len(chiquita.read_bytes()), "medido": r_chiquita}})

        # --- C7: sabotaje — mover la constante mueve el borde --------------------------------
        sab_lejos = ejecutar(guardados[f"cota_cadena_fallo_{COTA + 1}.isy"], cota=200,
                             modo="interp")
        sab_pelada = ejecutar(escribir(tmp, "sab_pelada_120.isy", fuente_pelada(120), guardados),
                              cota=200, modo="interp")
        sab_corta = ejecutar(escribir(tmp, "sab_cadena_6.isy", fuente_cadena(6), guardados),
                             cota=5, modo="interp")
        claim("C7", "es la guarda lo que rechaza: con `MAX_EXPR_DEPTH` subido a 200 desde fuera "
                    "del idioma, los "
                    f"{COTA + 1} niveles se aceptan y una cadena de 121 niveles sobre `str` "
                    "pelado baja y corre; con la constante bajada a 5, una cadena de 6 se "
                    f"rechaza con `SPEC_LIMIT`. El anfitrión no decide el borde en ninguno de "
                    "los tres controles",
              "DEMONSTRADO" if (sab_lejos.get("status") == "HALTED"
                                and sab_pelada.get("status") == "HALTED"
                                and sab_corta.get("code") == "SPEC_LIMIT")
              else "FALSO",
              {"cota_200_cadena_65": sab_lejos, "cota_200_pelada_120": sab_pelada,
               "cota_5_cadena_6": sab_corta})

        # --- C8: el muro que la guarda reemplaza, medido con la guarda levantada -------------
        def borde_anfitrion(previos: int, hi: int = 199) -> dict:
            # La última bisección no es el borde: se vuelven a correr `lo`, `hi` y la cota.
            lo = 1
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                camino = escribir(tmp, f"anfitrion_{previos}_bis_{mid}.isy",
                                  fuente_parentesis(mid), guardados)
                if paso(ejecutar(camino, cota=200, previos=previos)):
                    lo = mid
                else:
                    hi = mid
            extremo = {k: ejecutar(escribir(tmp, f"anfitrion_{previos}_{k}.isy",
                                            fuente_parentesis(k), guardados),
                                    cota=200, previos=previos) for k in (lo, hi, COTA - 1)}
            # Y con la guarda **puesta** (cota real): un fuente legal de 64 niveles puede
            # seguir muriendo si quien llama trae mucha pila. Es el límite honesto de la cota.
            real = ejecutar(escribir(tmp, f"anfitrion_{previos}_guarda.isy",
                                      fuente_parentesis(COTA - 1), guardados), previos=previos)
            return {"ok": lo, "fallo": hi,
                    "señal_ok": extremo[lo].get("resultado"),
                    "señal_fallo": extremo[hi].get("resultado"),
                    "frames": extremo[hi].get("frames"),
                    "al_tope": extremo[COTA - 1].get("resultado"),
                    "tope_con_guarda": real.get("resultado")}

        anfitrion = {p: borde_anfitrion(p) for p in (0, 300)}
        a0, a3 = anfitrion[0], anfitrion[300]
        claim("C8", "el muro que la guarda reemplaza era del anfitrión y estaba **por debajo** "
                    "de la cota: con `MAX_EXPR_DEPTH` levantada a 200 para que la guarda no "
                    f"estorbe, la cadena de paréntesis se estrella contra `RecursionError` en "
                    f"{a0['fallo']} pares con pila limpia y en {a3['fallo']} pares con 300 "
                    f"frames encima —el muro se mueve {a0['ok'] - a3['ok']} niveles según "
                    f"quien llama—. El fuente que hoy es el tope legal ({COTA - 1} pares, "
                    f"{COTA} niveles) bajaba con pila limpia (`{a0['al_tope']}`) y moría con 300 "
                    f"frames encima (`{a3['al_tope']}`): sin la guarda decidía el anfitrión. Con "
                    f"la guarda **puesta** el mismo fuente baja limpio "
                    f"(`{a0['tope_con_guarda']}`) y sigue muriendo con 300 frames "
                    f"(`{a3['tope_con_guarda']}`): la cota deja el borde del idioma por debajo "
                    "del muro medido, no borra el muro",
              "DEMONSTRADO" if (a0["señal_fallo"] == a3["señal_fallo"] == "RecursionError"
                                and a0["señal_ok"] == a3["señal_ok"] == "OK"
                                and a0["al_tope"] == "OK" and a3["al_tope"] == "RecursionError"
                                and a0["tope_con_guarda"] == "OK"
                                and a3["tope_con_guarda"] == "RecursionError"
                                and a0["ok"] - a3["ok"] >= 20) else "FALSO",
              anfitrion)

        selladas = {n: c.read_bytes() for n, c in guardados.items()
                    if n.startswith(("cota_", "clon_", "arbol_", "pelada_"))}

    documento = {"schema": "isycolang.z2_guard_probe/1", "generated_utc": stamp,
                 "git_head": _gate.git_head(), **_gate.arbol(),
                 "python": sys.version.split()[0], "limite_de_fabrica": LIMITE_FABRICA,
                 "cota_nombrada": COTA, "constante": "isyco/ast.py:MAX_EXPR_DEPTH",
                 "caras": {n: {"quien_cuenta": "parser" if n in ("parentesis", "prefijo")
                               else "AST", "borde_ok": b["ok"], "borde_fallo": b["fallo"],
                               "señal": b["medido_fallo"].get("code")}
                           for n, b in bordes.items()},
                 "bordes": bordes, "pila_del_llamante": por_previos,
                 "precio_en_frames": precios, "frames_quien_llama": llamante,
                 "muro_sin_guarda": anfitrion,
                 "censo_poblacion": cen, "clon_inalcanzable": ahora,
                 "continuidad": {"sonda_pre_decision": "tools/z2_depth_probe.py",
                                 "recibo_pre_decision":
                                     "evidence/z2_depth/run_2026-11-03T074629Z.json",
                                 "decision": "docs/decisions/Z2_MAX_EXPR_DEPTH.md",
                                 "casos": "programs/conformance_v0.5/449..454"},
                 "claims": list(claims.values()),
                 "veredicto": "FALSO" if falsos else "DEMONSTRADO"}

    for c in claims.values():
        lineas.append(f"{c['id']:>3} {c['estado']:<15} {c['afirmacion']}")
        lineas.append(f"      observado: {json.dumps(c['observado'], ensure_ascii=False)[:220]}")
    for mensaje in falsos:
        lineas.append(f"CONTROL FALSO: {mensaje}")
    print("\n".join(lineas), flush=True)

    if not args.write:
        return 1 if falsos else 0
    if falsos:
        print("no se sella: hay controles falsos", file=sys.stderr)
        return 1
    destino = _gate.EVIDENCE / "z2_guard"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in selladas.items():
        (destino / f"run_{stamp}_{nombre.removesuffix('.isy')}.isy").write_bytes(datos)
    res = _gate.sellar(documento, "\n".join(lineas) + "\n", destino, f"run_{stamp}")
    print(f"sellado en {destino}/run_{stamp}.{{json,txt}} mas {len(selladas)} fuentes "
          f"(sha {res['sha256'][:8]})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
