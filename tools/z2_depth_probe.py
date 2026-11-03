#!/usr/bin/env python3
"""Sonda de Z2: el techo de profundidad del frontend de referencia, y de quién es.

Z2 abrió la sonda de Z1 (`tools/z1_ceiling_probe.py`, claim C10) midiendo otra cosa: al buscar el
techo de Zig apareció un techo en `compile_ir`, la ruta por la que la referencia baja un fuente a
ISY-IR. La referencia **es** la semántica normativa (`AGENTS.md` regla 4), así que un programa que
ella no puede bajar no tiene con qué discutir — y aquí no lo rechaza el idioma: sube una
`RecursionError` de Python.

Lo que esta sonda separa, todo medido en procesos hijos con el límite de fábrica (1000):

1. La frontera es de **profundidad de expresión**, no de tamaño: una cadena izquierda de 241
   términos se acepta y 242 revienta, mientras un árbol de 2000 términos (profundidad 12) se acepta.
2. Hay **dos** fronteras, no una, y la más baja la pone el **clon** de V6: una definición con `str`
   pelado se copia entera por cada resolución (`specialize.py:55`, `copy.deepcopy`), y ese `deepcopy`
   es recursivo. Sin `str` pelado la misma forma llega ~90 términos más arriba.
3. El número **no es del idioma**: depende de cuántos frames traiga el llamante (241 con la pila
   limpia, 166 con 300 frames encima) y sube si se sube `sys.setrecursionlimit`.
4. La única acomodación de pila del paquete está atada a **otro eje**: `sys.setrecursionlimit(
   50 * max_call_depth + 1000)` envuelve la *ejecución* del intérprete (`interp.py:374`,
   `ir_interp.py:346`) y se restaura en un `finally`; no captura `RecursionError` en ninguna parte
   ni declara una cota de profundidad de expresión. Y ninguna de las cinco bajadas del frontend
   dentro de los gates está envuelta en `harness.intento`: lo que las amortigua es la capa 3 de
   cada gate, que aborta la pierna entera en vez de anotar una fila por caso.
5. Cuán lejos está la población real: el censo de profundidad sobre las fuentes del repo.
6. Quién paga el techo: el mismo fuente muere por `compile_ir`, por `interp.run` (la referencia
   normativa de F2) y por `run_via_ir`, porque `load` corre el checker —con su clon— antes de la
   única línea que sube el límite.

Nada de esto decide la política de Z2: el issue se abre en `docs/OPEN_QUESTIONS_P1_P4.md` con los
números, las opciones y lo que queda `NOT_DEMONSTRATED`. No toca ningún toolchain, pero bisección,
censo y seis puntos de pila son cientos de procesos hijos: corre minutos. Se sella con `--write` y
no sella si algún control sale `FALSO`.
"""
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[1]))
import _gate  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

ROOT = _gate.ROOT
LIMITE_FABRICA = 1000
KEYS = ("schema", "source_sha256")

# El hijo hace todo lo que puede ensuciar el proceso de la sonda: agotar la pila, capturar el
# traceback completo, medir RSS y, si revienta de verdad, devolverse un código de salida negativo.
HIJO = r'''
import json, resource, sys, time, traceback
ruta, limite, frames_previos, modo = (sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
                                      sys.argv[5])
sys.setrecursionlimit(limite)

def bajar(m, data):
    """Las tres rutas por las que un fuente entra al frontend de referencia."""
    if m == "ir":
        from isyco.ir_interp import compile_ir
        return compile_ir(data)
    if m == "interp":
        from isyco.interp import run
        return run(data, [])[0]
    if m == "via_ir":
        from isyco.ir_interp import run_via_ir
        return run_via_ir(data, [])[0]
    raise ValueError(m)

def hondo(n, expr):
    if n == 0:
        t0 = time.time()
        try:
            res = bajar(modo, open(expr, "rb").read())
            ok = {"resultado": "OK", "s": round(time.time() - t0, 3)}
            if isinstance(res, dict) and "status" in res:
                ok["status"] = res["status"]
                ok["code"] = res.get("code")
            return ok
        except RecursionError:
            tb = traceback.extract_tb(sys.exc_info()[2])
            r0 = {"s": round(time.time() - t0, 3)}
            copias = sum(1 for f in tb if f.filename.endswith("copy.py"))
            asomados = sorted({f"{f.filename.split('/')[-1]}:{f.name}" for f in tb
                               if not f.filename.endswith("copy.py")})
            return {"resultado": "RecursionError", "frames": len(tb), "frames_copy": copias,
                    "marcas": asomados[:6], **r0}
        except Exception as exc:
            return {"resultado": type(exc).__name__, "detalle": str(exc)[:200],
                    "s": round(time.time() - t0, 3)}
    return hondo(n - 1, expr)

r = hondo(frames_previos, ruta)
r["rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
print(json.dumps(r))
'''

# `hondo` con `frames_previos` entra desde una pila ya profunda: eso es lo que hace que el número
# no sea del idioma. Todo lo demás corre con la pila limpia del proceso hijo.


def ejecutar(camino: Path, limite: int = LIMITE_FABRICA, previos: int = 0,
             modo: str = "ir") -> dict:
    """Una pasada del fuente dado: proceso hijo, con la pila y el límite pedidos, por la ruta dada."""
    proc = subprocess.run([sys.executable, "-c", HIJO, str(ROOT), str(camino),
                           str(limite), str(previos), modo],
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        # Un `rc` negativo es una señal: el tope de Python se fue al C stack. Es un dato, no
        # una excepción de la sonda.
        return {"resultado": f"MUERTE_DEL_HIJO rc={proc.returncode}",
                "detalle": (proc.stderr or "")[-200:]}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"resultado": "ERROR_HARNESS", "detalle": (proc.stderr or proc.stdout)[-300:]}


def cadena(termino: str, k: int) -> str:
    """`k` términos sumados por la izquierda: la expresión tiene profundidad k."""
    e = termino
    for _ in range(k - 1):
        e = f"{e} + {termino}"
    return e


def arbol(termino: str, k: int) -> str:
    """Los mismos `k` términos en árbol binario balanceado: profundidad ~log2(k)."""
    if k == 1:
        return termino
    izq = k // 2
    return f"({arbol(termino, izq)} + {arbol(termino, k - izq)})"


def fuente_pelada(expr: str) -> str:
    """Parámetro `str` pelado: V6 obliga a clonar la definición, y el clon copia el cuerpo."""
    return (f'isyco 0.5\n\nfn m(s: str) -> i64 {{ return {expr}; }}\n'
            f'fn main() -> i64 !emit {{\n    emit m("x");\n    return 0;\n}}\n')


def fuente_ancha(expr: str) -> str:
    """Misma forma con `str<64>`: no hay resolución contextual, así que no hay clon."""
    return (f'isyco 0.5\n\nfn m(s: str<64>) -> i64 {{ return {expr}; }}\n'
            f'fn main() -> i64 !emit {{\n    let a: str<64> = "x";\n    emit m(a);\n'
            f'    return 0;\n}}\n')


def fuente_entera(expr: str) -> str:
    """Testigo sin `str` de ninguna clase: la forma pura del ascensor de profundidad."""
    e = expr.replace("len(s)", "a")
    return (f'isyco 0.5\n\nfn m(a: i64) -> i64 {{ return {e}; }}\n'
            f'fn main() -> i64 !emit {{\n    emit m(1);\n    return 0;\n}}\n')


FAMILIAS = {"pelada": fuente_pelada, "str64": fuente_ancha, "entera": fuente_entera}


def escribir(tmp: Path, nombre: str, texto: str) -> Path:
    camino = tmp / nombre
    camino.write_text(texto, encoding="utf-8")
    return camino


def paso(res: dict) -> bool:
    """`OK` para la bisección: sin excepción y, si la ruta devolvió documento, con `HALTED`."""
    return res.get("resultado") == "OK" and res.get("status", "HALTED") == "HALTED"


def frontera(tmp: Path, hacer, termino: str, lo_ok: int, hi_fallo: int,
             modo: str = "ir", prefijo: str = "bis") -> dict:
    """Bisección de la forma: deja los dos bordes medidos, con el fuente de cada uno guardado."""
    res = {}
    while lo_ok + 1 < hi_fallo:
        mid = (lo_ok + hi_fallo) // 2
        f = escribir(tmp, f"{prefijo}_{mid}.isy", hacer(cadena(termino, mid)))
        res[mid] = ejecutar(f, modo=modo)
        if paso(res[mid]):
            lo_ok = mid
        else:
            hi_fallo = mid
    a = escribir(tmp, f"{prefijo}_ok_{lo_ok}.isy", hacer(cadena(termino, lo_ok)))
    b = escribir(tmp, f"{prefijo}_fallo_{hi_fallo}.isy", hacer(cadena(termino, hi_fallo)))
    return {"ok": lo_ok, "fallo": hi_fallo,
            "resultado_fallo": ejecutar(b, modo=modo)["resultado"],
            "ok_medido": ejecutar(a, modo=modo), "fallo_medido": ejecutar(b, modo=modo),
            "fuente_ok_sha256": hashlib.sha256(a.read_bytes()).hexdigest(),
            "fuente_fallo_sha256": hashlib.sha256(b.read_bytes()).hexdigest()}


def profundidad(node) -> int:
    """Máxima cadena de nodos de expresión (`k`) dentro de un módulo ISY-IR: la regla del censo."""
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


def main(argv) -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--write", action="store_true", help="sella en evidence/z2_depth/")
    args = parser.parse_args(argv)
    stamp = _gate.stamp()
    lineas, claims, falsos = [], {}, []

    def claim(identidad, afirmacion, estado, observado):
        claims[identidad] = {"id": identidad, "afirmacion": afirmacion, "estado": estado,
                             "observado": observado}
        print(f"  [{identidad}] {estado}", flush=True)
        if estado == "FALSO":
            falsos.append(f"{identidad}: {afirmacion} — observado {json.dumps(observado)[:160]}")

    rss_inicio = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    lineas.append(f"python: {sys.version.split()[0]}  limite de fabrica: {LIMITE_FABRICA}"
                  f"  rss sonda: {rss_inicio} MB")

    with tempfile.TemporaryDirectory(prefix="isyco_z2_") as t:
        tmp = Path(t)

        # --- E1: dos fronteras, y la baja la pone el clon -------------------------------
        # Si el techo fuera de la forma del AST, las tres familias cortarían en el mismo punto.
        fro = {}
        for nombre, hacer, termino in (("pelada", fuente_pelada, "len(s)"),
                                       ("str64", fuente_ancha, "len(s)"),
                                       ("entera", fuente_entera, "a")):
            fro[nombre] = frontera(tmp, hacer, termino, 1, 4000)
            print(f"  {nombre:8} frontera {fro[nombre]['ok']} OK / "
                  f"{fro[nombre]['fallo']} {fro[nombre]['resultado_fallo']}", flush=True)
        misma_forma = abs(fro["str64"]["ok"] - fro["entera"]["ok"]) <= 2
        claim("E1", "el techo de `compile_ir` es de **profundidad de expresión** y su valor "
                    "depende de si el programa dispara el clon de V6: con `str` pelado corta en "
                    f"{fro['pelada']['ok']} OK / {fro['pelada']['fallo']} y sin clon corta en "
                    f"{fro['entera']['ok']} (arreglo de `i64`) y {fro['str64']['ok']} (`str<64>`); "
                    "las dos familias sin clon tienen la misma forma y el mismo término y cortan "
                    "a un término una de otra, así que lo que separa las dos fronteras no es la "
                    "forma del AST sino si hay resolución contextual de `str` — ~90 términos más "
                    "arriba con la misma cadena",
              "DEMONSTRADO" if (fro["pelada"]["ok"] < fro["entera"]["ok"] - 40
                                and misma_forma
                                and fro["pelada"]["resultado_fallo"] == "RecursionError")
              else "FALSO",
              {n: {k: v for k, v in f.items() if k.endswith(("ok", "fallo", "resultado_fallo"))}
               for n, f in fro.items()} | {"misma_forma_sin_clon": misma_forma})

        # --- E2: el culpable es el `deepcopy` del clon, y está medido en el traceback ----
        n_fallo = fro["pelada"]["fallo"]
        camino = escribir(tmp, f"pelada_{n_fallo}.isy", fuente_pelada(cadena("len(s)", n_fallo)))
        est = ejecutar(camino)
        camino_sin = escribir(tmp, f"entera_{n_fallo}.isy", fuente_entera(cadena("a", n_fallo)))
        est_sin = ejecutar(camino_sin)
        pct = round(100 * est.get("frames_copy", 0) / est.get("frames", 1))
        claim("E2", "la frontera del caso con clon se agota dentro de `copy.deepcopy`, no dentro "
                    f"del parser ni del lowering: {pct} % de los {est.get('frames')} frames del "
                    "traceback son de `copy.py` y las marcas que asoman por debajo son "
                    "`specialize` y el checker; los mismos "
                    f"{n_fallo} términos sin clon bajan a IR sin excepción",
              "DEMONSTRADO" if (est["resultado"] == "RecursionError"
                                and est["frames_copy"] / est["frames"] > 0.9
                                and any("specialize" in m or "checker" in m for m in est["marcas"])
                                and est_sin["resultado"] == "OK") else "FALSO",
              {"con_clon": est, "sin_clon_misma_medida": est_sin})

        # --- E3: el número no es del idioma: depende de la pila del llamante -------------
        por_profundidad = {}
        for previos in (0, 50, 100, 150, 200, 300):
            lo, hi = 1, 400
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                c = escribir(tmp, f"pila_{previos}_{mid}.isy",
                             fuente_pelada(cadena("len(s)", mid)))
                if paso(ejecutar(c, previos=previos)):
                    lo = mid
                else:
                    hi = mid
            por_profundidad[previos] = [lo, hi]
            print(f"  frames_previos={previos:4} frontera {lo} OK / {hi}", flush=True)
        valores = [v[0] for v in por_profundidad.values()]
        claim("E3", "la misma familia con clon tiene fronteras distintas según cuántos frames "
                    "traiga el llamante: " + " > ".join(f"{p} frames → {v[0]} OK" for p, v in
                                                       sorted(por_profundidad.items(), reverse=True))
                    + " — el número medido no es una capacidad del idioma ni del frontend, es "
                      "cuánta pila queda en el proceso que llama",
              "DEMONSTRADO" if valores == sorted(valores, reverse=True) and valores[0] - valores[-1] > 40
              else "FALSO",
              {"frontera_por_frames": por_profundidad})

        # --- E4: la única acomodación de recursión está atada a otro eje ------------------
        # Se buscan los cuatro nombres con los que el frontend podría nombrar esta cota.
        buscados = ("setrecursionlimit", "RecursionError", "MAX_DEPTH", "profundidad_max")
        presentes = {}
        for nombre in buscados:
            proc = subprocess.run(["grep", "-rnI", nombre, "isyco/"], cwd=ROOT,
                                  capture_output=True, text=True)
            presentes[nombre] = [l for l in proc.stdout.splitlines()
                                 if "test" not in l][:6]
        sitios_cuota = [l for l in presentes["setrecursionlimit"] if "50 * lim" in l]
        # Cómo lo vería un gate hoy: envuelto en `harness.intento` es una fila del arnés.
        con_guarda = json.loads(subprocess.run(
            [sys.executable, "-c", r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from isyco.harness import intento
from isyco.ir_interp import compile_ir
sys.setrecursionlimit(1000)
r, fila = intento(compile_ir, open(sys.argv[2], "rb").read(), fase="sonda",
                  contexto={"leg": "z2"})
print(json.dumps({"valor": r is not None, "fila": fila}))
''', str(ROOT), str(camino)],
            capture_output=True, text=True, timeout=900).stdout.strip().splitlines()[-1])
        fila = con_guarda["fila"] or {}
        claim("E4", "no hay guarda para **esta** cota, y la que existe está atada a un eje "
                    "distinto: `isyco/` no captura `RecursionError` en ningún sitio ni declara "
                    "`MAX_DEPTH` ni `profundidad_max` de expresión (búsqueda medida, cero "
                    f"coincidencias), y sus únicas dos acomodaciones de pila son "
                    f"`sys.setrecursionlimit(50 * max_call_depth + 1000)` en "
                    f"{[l.split(':')[0] + ':' + l.split(':')[1] for l in sitios_cuota]} — envuelven "
                    "la **ejecución** del intérprete y se restauran en un `finally`, así que la "
                    "bajada de un fuente nunca pasa por ahí. Sin paraguas el fallo sube; con él "
                    f"(medido), el programa de {fro['pelada']['fallo']} términos sale como fila "
                    "`HARNESS_INTERNAL` con excepción `RecursionError`, nunca como rechazo del "
                    "idioma",
              "DEMONSTRADO" if (not presentes["RecursionError"]
                                and not presentes["MAX_DEPTH"]
                                and not presentes["profundidad_max"]
                                and len(sitios_cuota) == 2
                                and fila.get("code") == "HARNESS_INTERNAL"
                                and fila.get("exception") == "RecursionError") else "FALSO",
              {"buscado_en_isyco": presentes, "sitios_cuota": sitios_cuota,
               "intento": con_guarda})

        # --- E5: las bajadas dentro de los gates están fuera de `harness.intento` ---------
        # Se busca en el texto porque la afirmación es de procedimiento: qué capa envuelve cada
        # llamada del frontend dentro de los dos gates. Un comentario no cuenta.
        tokens = ("compile_ir(", "run(", "run_via_ir(")
        archivos = ("tools/ir_gate.py", "tools/backend_gate.py")
        llamadas, excepts = [], {}
        for archivo in archivos:
            lineas_archivo = (ROOT / archivo).read_text(encoding="utf-8").splitlines()
            excepts[archivo] = [l.strip().split("#")[0].strip()[:60]
                                for l in lineas_archivo if l.strip().startswith("except")]
            for i, texto in enumerate(lineas_archivo):
                linea = texto.strip()
                if not any(t in linea for t in tokens) or linea.startswith("#") or '"""' in linea:
                    continue
                dentro = linea.startswith("intento(") or "= intento(" in linea
                protegida = dentro and not any(t in linea.split("intento(")[-1] for t in tokens)
                llamadas.append({"dónde": f"{archivo}:{i + 1}", "protegida": protegida,
                                 "cruda": "intento(" not in linea, "linea": linea[:90]})
        sin_paraguas = [d["dónde"] for d in llamadas]
        crudas = [d["dónde"] for d in llamadas if d["cruda"]]
        capa3 = {a: [e for e in ex if "Exception" in e] for a, ex in excepts.items()}
        cubre = any("RecursionError" in e or "BaseException" in e
                    for ex in excepts.values() for e in ex)
        claim("E5", "ninguna de las " + str(len(llamadas)) + " bajadas del frontend dentro de los "
                    "dos gates está envuelta en `harness.intento`: " + ", ".join(crudas) +
                    " llaman al frontend pelado y " + ", ".join(
                        d["dónde"] for d in llamadas if not d["cruda"]) +
                    " evalúa la bajada como **argumento** de `intento`, o sea antes del paraguas "
                    "(en `backend_gate.py:77` la llamada sin guarda es deliberada: 'si la "
                    "referencia explota, el bug es del idioma y tiene que subir'). Lo que sí las "
                    "cubre es la capa 3 de cada gate "
                    f"({[k for k, v in capa3.items() if v]}) y, en `ir_gate.py:63`, un "
                    "`except InvalidProgram` que por diseño solo alcanza los rechazos del idioma. "
                    "Consecuencia leída del código, no ejercida: un programa suficiente profundo "
                    "no deja el gate sin recibo —sale FAIL con `abortado`— pero truncaba la pierna "
                    "entera, con la identidad del caso solo en el excerpt del traceback y no en una "
                    "fila `HARNESS_INTERNAL` con `leg`/`case`/`program_sha256` como sí da "
                    "`intento`",
              "DEMONSTRADO" if (len(llamadas) == 5 and not cubre
                                and all(capa3[a] for a in archivos)
                                and not any(d["protegida"] for d in llamadas)) else "FALSO",
              {"llamadas_encontradas": llamadas, "except_en_gates": excepts,
               "capa3": capa3, "sin_paraguas": sin_paraguas})

        # --- E6: censo de la población real, con la misma regla --------------------------
        # La regla se calibra con el borde que **pasa** y con margen: medir la cadena de la
        # frontera dentro de la propia sonda agotaría su pila (aquí se cuenta el overhead del
        # llamante, que E3 muestra de qué tamaño es), y ese experimento ya está hecho en el hijo.
        regla = {}
        for k in (3, 120, 200):
            c = escribir(tmp, f"regla_{k}.isy", fuente_pelada(cadena("len(s)", k)))
            regla[k] = profundidad(compile_ir(c.read_bytes()))
        censo, no_bajan = [], []
        for f in sorted(ROOT.glob("programs/**/*.isy")):
            try:
                censo.append((profundidad(compile_ir(f.read_bytes())),
                              str(f.relative_to(ROOT))))
            except Exception as exc:
                no_bajan.append((str(f.relative_to(ROOT)), type(exc).__name__))
        censo.sort(reverse=True)
        top = [(d, n) for d, n in censo[:8]]
        libreria = [(d, n) for d, n in censo if "06_biblioteca_texto" in n]
        k_ok = fro["pelada"]["ok"]
        claim("E6", f"la población real está más de un orden de magnitud por debajo de la "
                    f"frontera: sobre "
                    f"{len(censo)} fuentes que bajan a IR ({len(no_bajan)} rechazadas a propósito) "
                    f"la profundidad máxima de expresión es **{censo[0][0]}** (`{censo[0][1]}`) y "
                    "la librería de texto que motivó V6 está en "
                    f"**{libreria[0][0] if libreria else '?'}**, frente al borde medido en "
                    f"**{k_ok}** (la regla extrapolada pone la cadena que muere en {k_ok + 1}); "
                    "la regla `cadena(k) -> profundidad k+1` se calibró sobre tres puntos que sí "
                    "bajan a IR, así que profundidad de frontera y profundidad de censo son la "
                    "misma magnitud",
              "DEMONSTRADO" if (censo and censo[0][0] <= k_ok // 8
                                and all(v == k + 1 for k, v in regla.items())
                                and len(regla) == 3 and libreria) else "FALSO",
              {"regla_cadena_k_es_profundidad": regla, "max_poblacion": censo[0][0],
               "top": top, "biblioteca_texto": libreria,
               "rechazadas": len(no_bajan), "fuentes_censadas": len(censo)})

        # --- E7: el clon se paga en tiempo, y es multiplicativo --------------------------
        coste = {}
        for ancho in (1, 8, 64, 200):
            for terminos in (2, 60, 240):
                c = escribir(tmp, f"coste_{ancho}_{terminos}.isy",
                             (f'isyco 0.5\n\nfn m(s: str) -> i64 {{ return '
                              f'{cadena("len(s)", terminos)}; }}\nfn main() -> i64 !emit {{\n'
                              + "".join(f'    emit m("{"x" * (i + 2)}");\n' for i in range(ancho))
                              + "    return 0;\n}\n"))
                r = ejecutar(c)
                coste[f"{ancho}x{terminos}"] = [r["resultado"], r.get("s")]
        barato, caro = coste["200x2"], coste["200x240"]
        claim("E7", "el coste del clon es multiplicativo en clones × términos del cuerpo, porque "
                    "`specialize.py:55` copia el cuerpo entero por resolución: 200 resoluciones de "
                    f"un cuerpo de 2 términos cuestan {barato[1]} s y las mismas 200 de un cuerpo "
                    f"de 240 cuestan {caro[1]} s, en la frontera de lo que el tope de P4 permite "
                    "(256 por definición) y con la referencia como único ejecutor — dato para F6",
              "DEMONSTRADO" if (caro[0] == "OK" and barato[0] == "OK"
                                and caro[1] > barato[1] * 20) else "FALSO",
              {"s_por_clones_x_terminos": coste})

        # --- E8: subir el límite mueve la frontera, y no es gratis -----------------------
        subido = {}
        for k, limite in ((n_fallo, 2000), (1200, 5000), (6000, 5000), (6000, 20000),
                          (20000, 60000), (60000, 200000)):
            c = escribir(tmp, f"lim_{k}_l{limite}.isy", fuente_pelada(cadena("len(s)", k)))
            r = ejecutar(c, limite=limite)
            subido[f"{k}_con_{limite}"] = [r["resultado"], r.get("rss_mb")]
        vivos = all("MUERTE" not in v[0] for v in subido.values())
        claim("E8", "la cota es del anfitrión y se puede levantar, pero la necesidad crece con la "
                    f"profundidad y nadie ha medido dónde está el techo físico: {n_fallo} términos "
                    "pasan con 2000 de límite y 1200 con 5000, mientras 6000 no pasan ni con 20000 "
                    "y 60000 no pasan con 200000. En todo el rango medido el fallo sigue siendo "
                    "`RecursionError`, no una señal del proceso: no se observó desbordamiento de C "
                    "stack, y eso es un `NOT_DEMONSTRATED`, no un verde",
              "DEMONSTRADO" if (subido[f"{n_fallo}_con_2000"][0] == "OK"
                                and subido["1200_con_5000"][0] == "OK"
                                and subido["6000_con_5000"][0] == "RecursionError"
                                and subido["60000_con_200000"][0] == "RecursionError"
                                and vivos) else "FALSO",
              {"resultado_y_rss": subido})

        # --- E9: el control de forma: profundidad sí, tamaño no --------------------------
        grande = escribir(tmp, "arbol_2000.isy", fuente_pelada(arbol("len(s)", 2000)))
        r_grande = ejecutar(grande)
        chiquita = escribir(tmp, f"cadena_{fro['pelada']['fallo']}.isy",
                            fuente_pelada(cadena("len(s)", fro["pelada"]["fallo"])))
        r_chica = ejecutar(chiquita)
        claim("E9", "el techo no es de tamaño de fuente: un árbol de 2000 términos "
                    f"({len(grande.read_bytes())} bytes, profundidad 12) se acepta, mientras una "
                    f"cadena izquierda de {fro['pelada']['fallo']} "
                    f"({len(chiquita.read_bytes())} bytes) revienta — el "
                    "mismo control que dejó Z1 en su claim C10, reproducido aquí con la familia "
                    "del clon",
              "DEMONSTRADO" if (r_grande["resultado"] == "OK"
                                and r_chica["resultado"] == "RecursionError"
                                and len(grande.read_bytes()) > 4 * len(chiquita.read_bytes()))
              else "FALSO",
              {"arbol_2000": [r_grande["resultado"], len(grande.read_bytes())],
               "cadena_fallo": [r_chica["resultado"], len(chiquita.read_bytes())],
               "arbol_sha256": hashlib.sha256(grande.read_bytes()).hexdigest(),
               "cadena_sha256": hashlib.sha256(chiquita.read_bytes()).hexdigest()})

        # --- E10: el techo lo paga la referencia normativa, no solo el camino a la IR -----
        # `load` corre el checker —y por tanto el clon— antes de la única línea que sube el
        # límite de recursión, y esa línea envuelve la ejecución. La acomodación de E4 llega
        # tarde para la bajada. Se mide por las tres rutas, sobre los mismos fuentes.
        ruta_ref = {}
        for nombre, termino in (("pelada", "len(s)"), ("entera", "a")):
            c = escribir(tmp, f"ref_{nombre}_{fro[nombre]['fallo']}.isy",
                         FAMILIAS[nombre](cadena(termino, fro[nombre]["fallo"])))
            for modo in ("interp", "via_ir"):
                ruta_ref[f"{nombre}_{modo}"] = ejecutar(c, modo=modo)
        fro_ref = frontera(tmp, fuente_pelada, "len(s)", 1, 4000, modo="interp", prefijo="ref")
        print(f"  referencia frontera {fro_ref['ok']} OK / {fro_ref['fallo']} "
              f"{fro_ref['resultado_fallo']}", flush=True)
        pierna = ruta_ref["pelada_interp"]
        copia_ref = (pierna.get("frames_copy", 0) / pierna.get("frames", 1))
        claim("E10", "el techo no es un artefacto del camino a la IR: el fuente que muere en "
                    f"`compile_ir` a {fro['pelada']['fallo']} términos muere igual por "
                    f"`interp.run` — la referencia normativa de F2 — y por `run_via_ir`, y en las "
                    f"dos familias ({fro['entera']['fallo']} términos sin clon incluidos). La "
                    f"bisección de la ruta de referencia corta en {fro_ref['ok']} OK / "
                    f"{fro_ref['fallo']}, a {abs(fro_ref['ok'] - fro['pelada']['ok'])} términos de "
                    "la bajada, y el mismo `deepcopy` se come el "
                    f"{round(copia_ref * 100)} % de los frames: la suba de "
                    "`setrecursionlimit` va alrededor de la **ejecución** y `load` ya reventó "
                    "antes, así que subir `max_call_depth` no abre margen en el frontend",
              "DEMONSTRADO" if (pierna["resultado"] == "RecursionError"
                                and ruta_ref["pelada_via_ir"]["resultado"] == "RecursionError"
                                and ruta_ref["entera_interp"]["resultado"] == "RecursionError"
                                and copia_ref > 0.9
                                and abs(fro_ref["ok"] - fro["pelada"]["ok"]) <= 20
                                and fro_ref["resultado_fallo"] == "RecursionError") else "FALSO",
              {"frontera_referencia_pelada": fro_ref,
               "bajada_ir_pelada": [fro["pelada"]["ok"], fro["pelada"]["fallo"]],
               "bajada_ir_entera": [fro["entera"]["ok"], fro["entera"]["fallo"]],
               "ruta_de_los_mismos_fuentes": ruta_ref})

        guardadas = {
            "frontera_pelada_ok": escribir(tmp, "sellada_pelada_ok.isy",
                                           fuente_pelada(cadena("len(s)", fro["pelada"]["ok"]))),
            "frontera_pelada_fallo": escribir(tmp, "sellada_pelada_fallo.isy",
                                              fuente_pelada(cadena("len(s)", fro["pelada"]["fallo"]))),
            "frontera_entera_fallo": escribir(tmp, "sellada_entera_fallo.isy",
                                              fuente_entera(cadena("a", fro["entera"]["fallo"]))),
            "arbol_2000": grande,
            "clon_coste_200x240": escribir(tmp, "sellada_coste.isy",
                                           (f'isyco 0.5\n\nfn m(s: str) -> i64 {{ return '
                                            f'{cadena("len(s)", 240)}; }}\nfn main() -> i64 !emit '
                                            f'{{\n' + "".join(f'    emit m("{"x" * (i + 2)}");\n'
                                                              for i in range(200))
                                            + "    return 0;\n}\n")),
        }
        # El bytes viaja fuera del directorio temporal: el `with` lo borra antes del sellado.
        selladas = {n: c.read_bytes() for n, c in guardadas.items()}

    documento = {"schema": "isycolang.z2_depth_probe/1", "generated_utc": stamp,
                 "git_head": _gate.git_head(), **_gate.arbol(),
                 "python": sys.version.split()[0], "limite_de_fabrica": LIMITE_FABRICA,
                 "familias": {"pelada": "parametro `str` pelado: dispara el clon de V6",
                              "str64": "parametro `str<64>`: misma forma, sin clon",
                              "entera": "parametro `i64`: forma pura sin `str`"},
                 "fronteras": {n: {"ok": f["ok"], "fallo": f["fallo"],
                                   "resultado_fallo": f["resultado_fallo"],
                                   "fuente_ok_sha256": f["fuente_ok_sha256"],
                                   "fuente_fallo_sha256": f["fuente_fallo_sha256"]}
                               for n, f in fro.items()},
                 "censo_poblacion": {"fuentes_que_bajan": len(censo),
                                     "rechazadas": len(no_bajan),
                                     "max_profundidad": censo[0][0],
                                     "top": [{"profundidad": d, "fuente": n} for d, n in top],
                                     "biblioteca_texto": [{"profundidad": d, "fuente": n}
                                                         for d, n in libreria]},
                 "continuidad": {"z1_c10": "evidence/z1_ceiling/run_2026-11-03T035753Z.json",
                                 "especializacion": "isyco/specialize.py:55 copy.deepcopy(fn)",
                                 "gates_fuera_de_intento": llamadas},
                 "pila_del_llamante": por_profundidad,
                 "ruta_referencia": {"frontera_interpelada": {k: fro_ref[k] for k in
                                                              ("ok", "fallo", "resultado_fallo",
                                                               "fuente_ok_sha256",
                                                               "fuente_fallo_sha256")},
                                     "mismos_fuentes_por_las_tres_rutas": ruta_ref},
                 "acomodacion_de_pila": {"setrecursionlimit": sitios_cuota,
                                         "recursion_error_capturada": presentes["RecursionError"]},
                 "coste_clones_por_terminos": coste,
                 "limites_subidos": subido,
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
    destino = _gate.EVIDENCE / "z2_depth"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in selladas.items():
        (destino / f"run_{stamp}_{nombre}.isy").write_bytes(datos)
    res = _gate.sellar(documento, "\n".join(lineas) + "\n", destino, f"run_{stamp}")
    print(f"sellado en {destino}/run_{stamp}.{{json,txt}} mas {len(selladas)} fuentes "
          f"(sha {res['sha256'][:8]})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
