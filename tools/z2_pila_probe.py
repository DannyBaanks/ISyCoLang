"""Z2-b: mide que la pila que trae quien llama ya no decide si un programa legal baja.

`tools/z2_guard_probe.py` dejó sellado el límite de la cota (C8 de
`evidence/z2_guard/run_2026-11-04T001913Z.json`): el fuente del tope legal —64 niveles— moría por
`RecursionError` si quien llamaba traía 300 frames. `isyco/pila.py` reserva la pila del paquete
contada **desde el llamante**, y esta sonda mide el estado después:

* P1: el tope legal de cinco caras recorre todo el camino (bajar, validar, censar capacidades,
  emitir por cada backend que lo declara, ejecutar por las dos rutas) con 0, 300 y 3 000 frames
  de un llamante que llega con 40 de aire;
* P2: el nivel 65 sigue siendo `SPEC_LIMIT` con esos mismos llamantes;
* P3: sabotaje — con el presupuesto en 0 vuelve el muro, y no solo en el frontend: también en el
  censo de capacidades y en los cinco emisores, que recorren la IR;
* P4: el coste real por cara (bisección del límite con la reserva apagada) contra el presupuesto;
* P5: el límite de recursión del llamante queda como estaba, salga el paquete como salga;
* P6: la ejecución también cuenta desde el llamante (`50 * max_call_depth + 1000` era absoluto);
* P7: el caso exacto de C8 —límite de fábrica, 300 frames— hoy baja;
* P8: lo que **no** cierra — el anidamiento de sentencias (`if` dentro de `if`) no tiene cota
  nombrada: su borde es un `RecursionError` cuyo número lo pone el presupuesto, no el idioma.

Todo lo que puede agotar la pila corre en un proceso hijo. No invoca ningún toolchain: emitir es
generar texto. `--write` sella en `evidence/z2_pila/` y se niega si algún control sale `FALSO`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[1]))
import _gate  # noqa: E402
from isyco import ast as A  # noqa: E402
from isyco import pila  # noqa: E402

ROOT = _gate.ROOT
COTA = A.MAX_EXPR_DEPTH
AIRE = 40
RECIBO_C8 = "evidence/z2_guard/run_2026-11-04T001913Z.json"

# argv: raíz, fuente, frames del llamante, límite ("aire" = profundidad + frames + AIRE, o un
# número absoluto), qué recorrer, sabotaje ("", "presupuesto0", "absoluto"), límites de ejecución.
HIJO = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
ruta, previos, limite, que, sabotaje, limites = (sys.argv[2], int(sys.argv[3]), sys.argv[4],
                                                 sys.argv[5], sys.argv[6], json.loads(sys.argv[7]))
from isyco import pila
from isyco.backends import registry
from isyco.backends.base import features_of
from isyco.interp import run
from isyco.ir_interp import compile_ir, run_via_ir
if sabotaje == "presupuesto0":
    pila.FRAMES_POR_NIVEL = 0
elif sabotaje == "absoluto":
    pila.profundidad = lambda: 0
data = open(ruta, "rb").read()
modulo = None
if que not in ("todo", "ir", "run"):          # un recorrido de la IR, aislado: se baja antes,
    real = pila.FRAMES_POR_NIVEL              # con pila limpia y la reserva puesta
    pila.FRAMES_POR_NIVEL = 32
    modulo = compile_ir(data)
    pila.FRAMES_POR_NIVEL = real

def trabajo():
    if que == "ir":
        return {"schema": compile_ir(data)["schema"]}
    if que == "run":
        doc = run(data, [], limites or None)[0]
        return {"status": doc["status"], "code": doc["code"], "emits": doc["emits"]}
    if que == "features_of":
        return {"capacidades": len(features_of(modulo))}
    if que != "todo":
        return {"bytes": len(registry()[que].emit(modulo))}
    m = compile_ir(data)
    emitidos = sorted(n for n, b in registry().items() if features_of(m) <= set(b.features)
                      and b.emit(m))
    a, b = run(data, [])[0], run_via_ir(data, [])[0]
    return {"status": a["status"], "code": a["code"], "via_ir": b["status"], "emitidos": emitidos}

def baja(n):
    return baja(n - 1) if n else trabajo()

antes = sys.getrecursionlimit()
sys.setrecursionlimit(pila.profundidad() + previos + int(limite[4:]) if limite.startswith("aire")
                      else int(limite))
durante = sys.getrecursionlimit()
try:
    r = {"resultado": "OK", **baja(previos)}
except RecursionError:
    r = {"resultado": "RecursionError"}
except Exception as exc:
    r = {"resultado": type(exc).__name__, "code": getattr(exc, "code", None)}
r["limite_restaurado"] = sys.getrecursionlimit() == durante
sys.setrecursionlimit(antes)
print(json.dumps(r))
'''


def terminos(k: int, ter: str = "1") -> str:
    return " + ".join([ter] * k)


def _main(cuerpo: str, antes: str = "") -> str:
    return (f"isyco 0.5\n\n{antes}fn main() -> i64 !emit {{\n"
            f"    let x: i64 = {cuerpo};\n    emit x;\n    return x;\n}}\n")


def fuente_parentesis(k: int) -> str:
    return _main(f"{'(' * k}1{')' * k}")


def fuente_prefijo(k: int) -> str:
    return _main(f"{'-' * k}1")


def fuente_cadena(k: int) -> str:
    return _main(terminos(k))


def fuente_pelada(k: int) -> str:
    return (f'isyco 0.5\n\nfn cuanto(s: str) -> i64 {{\n    return {terminos(k, "len(s)")};\n}}\n\n'
            f'fn main() -> i64 !emit {{\n    emit cuanto("hola");\n'
            f'    return {4 * k};\n}}\n')


def fuente_llamadas(k: int) -> str:
    return _main(f"{'f(' * k}1{')' * k}", "fn f(a: i64) -> i64 {\n    return a;\n}\n\n")


def fuente_recursiva(hondo: int) -> str:
    return (f"isyco 0.5\n\nfn baja(n: i64) -> i64 {{\n    if n == 0 {{\n        return 0;\n    }}\n"
            f"    return 1 + baja(n - 1);\n}}\n\n"
            f"fn main() -> i64 !emit {{\n    emit baja({hondo});\n    return 0;\n}}\n")


def fuente_bloques(k: int) -> str:
    cuerpo = "    let x: i64 = 1;\n"
    cuerpo += "".join("    " * (i + 1) + "if true {\n" for i in range(k))
    cuerpo += "    " * (k + 1) + "emit x;\n"
    cuerpo += "".join("    " * (i + 1) + "}\n" for i in reversed(range(k)))
    return f"isyco 0.5\n\nfn main() -> i64 !emit {{\n{cuerpo}    return 0;\n}}\n"


#: `(fuente(k), k en el tope legal)`; un `k` más es el nivel 65. Las cuatro de la sonda de la
#: guarda más `llamadas`, que resultó la más cara y aquella sonda no medía.
CARAS = {"parentesis": (fuente_parentesis, COTA - 1), "prefijo": (fuente_prefijo, COTA),
         "cadena": (fuente_cadena, COTA), "pelada": (fuente_pelada, COTA - 1),
         "llamadas": (fuente_llamadas, COTA - 1)}
LLAMANTES = (0, 300, 3000)


def ejecutar(camino: Path, previos: int = 0, limite: str = f"aire{AIRE}", que: str = "todo",
             sabotaje: str = "", limites: dict | None = None) -> dict:
    proc = subprocess.run([sys.executable, "-c", HIJO, str(ROOT), str(camino), str(previos),
                           limite, que, sabotaje, json.dumps(limites or {})],
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        return {"resultado": f"MUERTE_DEL_HIJO rc={proc.returncode}",
                "detalle": (proc.stderr or "")[-200:]}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"resultado": "ERROR_HARNESS", "detalle": (proc.stderr or proc.stdout)[-300:]}


def coste(camino: Path, que: str = "todo") -> int | None:
    """Mínimo de frames por debajo del llamante con que `que` todavía pasa, sin reserva."""
    lo, hi = 5, 4 * pila.frames_frontend()
    if ejecutar(camino, limite=f"aire{hi}", que=que, sabotaje="presupuesto0")["resultado"] != "OK":
        return None
    while lo + 1 < hi:
        medio = (lo + hi) // 2
        if ejecutar(camino, limite=f"aire{medio}", que=que,
                    sabotaje="presupuesto0")["resultado"] == "OK":
            hi = medio
        else:
            lo = medio
    return hi


def main(argv) -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--write", action="store_true", help="sella en evidence/z2_pila/")
    args = parser.parse_args(argv)
    stamp = _gate.stamp()
    procedencia = _gate.arbol()
    lineas, claims, falsos = [], {}, []

    def claim(identidad, afirmacion, estado, observado):
        claims[identidad] = {"id": identidad, "afirmacion": afirmacion, "estado": estado,
                             "observado": observado}
        print(f"  [{identidad}] {estado}", flush=True)
        if estado == "FALSO":
            falsos.append(f"{identidad}: {afirmacion} — observado {json.dumps(observado)[:200]}")

    def estado(ok: bool) -> str:
        return "DEMONSTRADO" if ok else "FALSO"

    presupuesto = pila.frames_frontend()
    lineas.append(f"python: {sys.version.split()[0]}  cota nombrada: {COTA}  "
                  f"presupuesto: {pila.FRAMES_POR_NIVEL} x {COTA} = {presupuesto} frames  "
                  f"aire del llamante: {AIRE}")

    with tempfile.TemporaryDirectory(prefix="isyco_z2p_") as t:
        tmp = Path(t)
        fuentes: dict[str, Path] = {}

        def escribir(nombre: str, texto: str) -> Path:
            fuentes[nombre] = tmp / f"{nombre}.isy"
            fuentes[nombre].write_text(texto, encoding="utf-8")
            return fuentes[nombre]

        topes = {n: escribir(f"tope_{n}_{k}", hacer(k)) for n, (hacer, k) in CARAS.items()}
        pasados = {n: escribir(f"pasa_{n}_{k + 1}", hacer(k + 1))
                   for n, (hacer, k) in CARAS.items()}

        # --- P1 ------------------------------------------------------------------------------
        p1 = {n: {str(f): ejecutar(c, previos=f) for f in LLAMANTES} for n, c in topes.items()}
        claim("P1", f"el fuente del tope legal ({COTA} niveles) baja, se valida, se emite y "
                    f"ejecuta por las dos rutas con {', '.join(map(str, LLAMANTES))} frames de un "
                    f"llamante que llega con {AIRE} de aire, en las cinco caras",
              estado(all(r["resultado"] == "OK" and r.get("status") == "HALTED"
                         and r.get("via_ir") == "HALTED" and len(r.get("emitidos", [])) >= 4
                         for cara in p1.values() for r in cara.values())), p1)

        # --- P2 ------------------------------------------------------------------------------
        p2 = {n: {str(f): ejecutar(c, previos=f, que="run") for f in LLAMANTES}
              for n, c in pasados.items()}
        claim("P2", "el nivel 65 sigue siendo `INVALID_PROGRAM`/`SPEC_LIMIT` con esos mismos "
                    "llamantes: la reserva no mueve el borde del idioma",
              estado(all(r["resultado"] == "OK" and r.get("code") == "SPEC_LIMIT"
                         for cara in p2.values() for r in cara.values())), p2)

        # --- P3 ------------------------------------------------------------------------------
        recorridos = ["features_of", "c", "rust", "zig", "pydecimal", "cobol"]
        p3 = {"frontend": {n: {"sin_reserva": ejecutar(c, previos=300, que="ir",
                                                        sabotaje="presupuesto0")["resultado"],
                               "con_reserva": ejecutar(c, previos=300, que="ir")["resultado"]}
                           for n, c in topes.items()},
              "recorridos_de_la_ir": {
                  q: {"sin_reserva": ejecutar(topes["cadena"], previos=300, que=q,
                                              sabotaje="presupuesto0")["resultado"],
                      "con_reserva": ejecutar(topes["cadena"], previos=300, que=q)["resultado"]}
                  for q in recorridos}}
        claim("P3", "sabotaje: con el presupuesto en 0 y 300 frames del llamante vuelve el "
                    "`RecursionError` —en el frontend para las cinco caras y, sobre la cadena "
                    "izquierda, en el censo de capacidades y en los cinco emisores—; con la "
                    "reserva puesta los mismos once pasan. Es la reserva la que lo consigue",
              estado(all(v == {"sin_reserva": "RecursionError", "con_reserva": "OK"}
                         for grupo in p3.values() for v in grupo.values())), p3)

        # --- P4 ------------------------------------------------------------------------------
        p4 = {n: coste(c) for n, c in topes.items()}
        p4_ir = {q: coste(topes["cadena"], q) for q in recorridos}
        caro = max(p4, key=lambda n: p4[n] or 0)
        claim("P4", f"la cara legal más cara es `{caro}` y gasta {p4[caro]} frames en todo el "
                    f"camino ({round((p4[caro] or 0) / COTA, 1)} por nivel): menos de la mitad "
                    f"del presupuesto de {presupuesto}",
              estado(all(p4.values()) and all(p4_ir.values())
                     and 2 * max(p4.values()) <= presupuesto and caro == "llamadas"),
              {"todo_el_camino": p4, "recorridos_de_la_ir_sobre_cadena": p4_ir,
               "presupuesto": presupuesto, "frames_por_nivel_medido": round(p4[caro] / COTA, 2)
               if p4[caro] else None})

        # --- P5 ------------------------------------------------------------------------------
        p5 = {"sale_bien": ejecutar(topes["llamadas"], previos=300),
              "sale_por_spec_limit": ejecutar(pasados["parentesis"], previos=300, que="run"),
              "sale_por_recursion_error": ejecutar(topes["parentesis"], previos=300, que="ir",
                                                   sabotaje="presupuesto0")}
        claim("P5", "el límite de recursión del llamante queda como estaba, salga el paquete "
                    "bien, por rechazo del idioma o por `RecursionError`",
              estado(all(r.get("limite_restaurado") is True for r in p5.values())
                     and p5["sale_por_recursion_error"]["resultado"] == "RecursionError"), p5)

        # --- P6 ------------------------------------------------------------------------------
        rec = escribir("ejecucion_recursiva_200", fuente_recursiva(200))
        lim = {"max_call_depth": 256}
        absoluto = 50 * lim["max_call_depth"] + 1000
        p6 = {"llamante": absoluto + 200, "limite_absoluto_anterior": absoluto,
              "limpio": ejecutar(rec, que="run", limites=lim),
              "hondo": ejecutar(rec, previos=absoluto + 200, que="run", limites=lim),
              "hondo_contando_en_absoluto": ejecutar(rec, previos=absoluto + 200, que="run",
                                                     sabotaje="absoluto", limites=lim)}
        claim("P6", f"la ejecución también cuenta desde el llamante: un programa que recursiona "
                    f"200 veces da lo mismo con pila limpia y con {absoluto + 200} frames encima "
                    f"—más que el `50 * max_call_depth + 1000` = {absoluto} que antes era el "
                    f"límite absoluto—, y contando en absoluto (sabotaje) muere",
              estado(p6["limpio"].get("emits") == ["200"] and p6["hondo"].get("emits") == ["200"]
                     and p6["hondo_contando_en_absoluto"]["resultado"] == "RecursionError"), p6)

        # --- P7 ------------------------------------------------------------------------------
        viejo = json.loads((ROOT / RECIBO_C8).read_text(encoding="utf-8"))
        antes = {p: viejo["muro_sin_guarda"][p]["tope_con_guarda"] for p in ("0", "300")}
        ahora = {p: ejecutar(topes["parentesis"], previos=int(p), limite="1000",
                             que="ir")["resultado"] for p in ("0", "300")}
        claim("P7", "el caso exacto de C8 —63 pares de paréntesis, límite de fábrica 1000, 300 "
                    "frames del llamante— era `RecursionError` en el recibo de la guarda y hoy "
                    "baja",
              estado(antes == {"0": "OK", "300": "RecursionError"}
                     and ahora == {"0": "OK", "300": "OK"}),
              {"recibo": RECIBO_C8, "antes": antes, "ahora": ahora})

        # --- P8 ------------------------------------------------------------------------------
        def borde_bloques(previos: int, sabotaje: str = "", limite: str = f"aire{AIRE}") -> dict:
            def pasa(k: int) -> dict:
                return ejecutar(escribir(f"bloques_{k}", fuente_bloques(k)), previos=previos,
                                limite=limite, sabotaje=sabotaje)
            lo, hi = 8, 4000
            if pasa(lo)["resultado"] != "OK":
                return {"ok": None, "fallo": lo, "señal_fallo": pasa(lo)["resultado"]}
            while lo + 1 < hi:
                medio = (lo + hi) // 2
                if pasa(medio)["resultado"] == "OK":
                    lo = medio
                else:
                    hi = medio
            return {"ok": lo, "fallo": hi, "señal_ok": pasa(lo).get("status"),
                    "señal_fallo": pasa(hi)["resultado"]}

        p8 = {"llamante_0": borde_bloques(0), "llamante_300": borde_bloques(300),
              "llamante_0_sin_reserva": borde_bloques(0, "presupuesto0", "1000")}
        b0, b3, bs = p8["llamante_0"], p8["llamante_300"], p8["llamante_0_sin_reserva"]
        claim("P8", f"LÍMITE, medido: el anidamiento de **sentencias** no tiene cota nombrada. "
                    f"{b0['ok']} bloques `if` anidados bajan y {b0['fallo']} mueren por "
                    f"`{b0['señal_fallo']}`; el borde ya no se mueve con el llamante (igual con "
                    f"300 frames) pero lo pone el presupuesto y no el idioma (sin reserva y con "
                    f"el límite de fábrica: {bs['ok']}/{bs['fallo']})",
              estado(b0 == b3 and b0["señal_ok"] == "HALTED"
                     and b0["señal_fallo"] == "RecursionError" and bs != b0), p8)
        for nombre in [n for n in fuentes if n.startswith("bloques_")
                       and n not in (f"bloques_{b0['ok']}", f"bloques_{b0['fallo']}")]:
            del fuentes[nombre]                 # solo se sellan las dos fuentes del borde

        selladas = {n: c.read_bytes() for n, c in fuentes.items()}

    documento = {"schema": "isycolang.z2_pila_probe/1", "generated_utc": stamp,
                 "git_head": _gate.git_head(), **procedencia,
                 "python": sys.version.split()[0], "cota_nombrada": COTA,
                 "frames_por_nivel": pila.FRAMES_POR_NIVEL, "presupuesto_frontend": presupuesto,
                 "aire_del_llamante": AIRE, "llamantes": list(LLAMANTES),
                 "fuentes_sha256": {n: hashlib.sha256(d).hexdigest()
                                    for n, d in sorted(selladas.items())},
                 "continuidad": {"sonda_anterior": "tools/z2_guard_probe.py",
                                 "recibo_anterior": RECIBO_C8,
                                 "decision": "docs/decisions/Z2B_PILA_PROPIA.md"},
                 "claims": list(claims.values()),
                 "veredicto": "FALSO" if falsos else "DEMONSTRADO"}

    for c in claims.values():
        lineas.append(f"{c['id']:>3} {c['estado']:<12} {c['afirmacion']}")
        lineas.append(f"      observado: {json.dumps(c['observado'], ensure_ascii=False)[:260]}")
    for mensaje in falsos:
        lineas.append(f"CONTROL FALSO: {mensaje}")
    print("\n".join(lineas), flush=True)

    if not args.write:
        return 1 if falsos else 0
    if falsos:
        print("no se sella: hay controles falsos", file=sys.stderr)
        return 1
    destino = _gate.EVIDENCE / "z2_pila"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in selladas.items():
        (destino / f"run_{stamp}_{nombre}.isy").write_bytes(datos)
    res = _gate.sellar(documento, "\n".join(lineas) + "\n", destino, f"run_{stamp}")
    print(f"sellado en {destino}/run_{stamp}.{{json,txt}} mas {len(selladas)} fuentes "
          f"(sha {res['sha256'][:8]})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
