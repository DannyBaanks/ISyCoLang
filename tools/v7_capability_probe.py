"""Sonda del milestone V7 (CORE v0.5): capacidades por contenido, no por cabecera.

La pregunta que mide es una sola: ¿`UNSUPPORTED` señala una capacidad que el programa
realmente exige, o señala el número de schema con el que bajó la IR?

Hace tres cosas, en este orden:

1. **Cuenta** los dos conjuntos sobre el corpus congelado (170 casos) y sobre los canarios
   439..442 escritos A MANO antes de implementar: `SCHEMA_CAN_EXPRESS` es `module["schema"]`,
   `PROGRAM_REQUIRES` es `features_of`. Son 60 contra 46: 14 programas pedían `ir0.2` sin
   usar ningún tipo 0.2.
2. **Ejecuta** el experimento comparativo: el brazo `etiqueta` (la regla que había antes de
   V7) y el brazo `contenido` (la regla actual) sobre los mismos casos, en COBOL, que es el
   único backend instalado que declara no saber nada de 0.2. Para que el brazo viejo no sea
   un espantajo, se reconstruye desde el blob de git del commit previo y se verifica que la
   simulación coincide con ese código caso por caso.
3. **Intenta falsarse a sí misma**: si a `emit_array` se le da la capacidad que niega (el
   artefacto que V7 nombra), el resultado tiene que ser un fallo real del emitter y no una
   coincidencia; y el sabotaje declarado por COBOL tiene que romperse contra sí mismo o
   declararse VACÍO.

Un PASS con el árbol sucio de código es `EVIDENCE_ONLY`, nunca gate de release.

    python3 tools/v7_capability_probe.py            # tabla por stdout
    python3 tools/v7_capability_probe.py --write    # sella evidence/v05_v7/run_<UTC>.{json,txt}
"""
from __future__ import annotations

import ast
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import isyco.backends.base as base                                   # noqa: E402
from isyco import run                                                 # noqa: E402
from isyco.backends import available                                  # noqa: E402
from isyco.backends.base import features_of, missing_features         # noqa: E402
from isyco.conformance import COMPARED, load_all, load_corpus         # noqa: E402
from isyco.errors import InvalidProgram                               # noqa: E402
from isyco.ir_validate import SCHEMA_V2                               # noqa: E402

KEYS = COMPARED
V05 = ROOT / "programs" / "conformance_v0.5"
CANARIOS = ("439", "440", "441", "442")
# Estado del engine ANTES de V7: el commit del gate sellado de V6-bis.
REF_ETIQUETA = "f856d55"
# (caso, (fragmento del fuente, sustituto)) — dos variantes para ver mover la salida.
TRABAJO = (("442_nucleo_03_sin_str", ("while k < 3", "while k < 4")),
           ("248_array_equality", ("b[0] = 5", "b[0] = 1")))


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


def observed_of(row: dict) -> dict:
    return {k: row.get(k) for k in KEYS}


def classify(expected: dict, ref: dict, got: dict | None, excepcion: str | None) -> str:
    """EQUIV exige coincidir con la referencia Y con el esperado escrito a mano."""
    if excepcion is not None:
        return "BUILD_FAIL"
    if got.get("status") == "UNSUPPORTED":
        return "UNSUPPORTED"
    if got.get("status") in ("BACKEND_CRASH", "TIMEOUT") or got.get("backend_stderr"):
        return "RUNTIME_FAIL"
    if observed_of(got) == ref and observed_of(got) == expected:
        return "EQUIV"
    return "DIVERGENT"


# --- las dos reglas -------------------------------------------------------------------
def features_etiqueta(module: dict) -> set[str]:
    """Reconstrucción de lo que `features_of` devolvía antes de V7.

    Dos diferencias con el código actual, y las dos son la hipotesis: la cabecera 0.2
    regalaba `ir0.2` a cualquier programa bajado en ese contenedor, y emitir un arreglo
    no existía como capacidad (`emit_array` nace en V7 porque COBOL falla al hacerlo).
    """
    out = set(features_of(module)) - {"emit_array"}
    if module.get("schema") == SCHEMA_V2:
        out.add("ir0.2")
    return out


def features_etiqueta_desde_git() -> tuple[object | None, str]:
    """El `features_of` real del commit previo, ejecutado en un espacio propio.

    Devuelve (callable|None, nota). Si el blob o sus privados ya no están, el control de
    fidelidad se declara INCONCLUSIVE en vez de silenciarse.
    """
    try:
        source = subprocess.run(["git", "show", f"{REF_ETIQUETA}:isyco/backends/base.py"],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return None, f"blob no disponible: {type(exc).__name__}"
    tree = ast.parse(source)
    nodo = next((n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "features_of"), None)
    if nodo is None:
        return None, f"{REF_ETIQUETA}:isyco/backends/base.py no define features_of"
    ns = {"ty_from_json": base.ty_from_json, "_type_features": base._type_features,
          "_walk": base._walk, "SCHEMA_V2": SCHEMA_V2}
    exec(compile(ast.get_source_segment(source, nodo), "<git:features_of>", "exec"), ns)
    return ns["features_of"], f"features_of leido de {REF_ETIQUETA} (isyco/backends/base.py)"


# --- población ------------------------------------------------------------------------
def modulos() -> list[dict]:
    """Todos los programas que bajan a IR: corpus congelado + canarios V7."""
    casos = list(load_all(ROOT)) + [next(c for c in load_corpus(V05)
                                         if c["name"].startswith(f"{n}_")) for n in CANARIOS]
    congelado = {c["name"] for c in load_all(ROOT)}
    out = []
    for case in casos:
        module = compile_ir_safe(case["program"])
        if module is not None:
            out.append({"case": case, "module": module, "congelado": case["name"] in congelado})
    return out


def compile_ir_safe(data: bytes):
    """IR del programa, o None si el frontend lo rechaza (sin IR no hay capacidades)."""
    from isyco.ir_interp import compile_ir
    try:
        return compile_ir(data)
    except InvalidProgram:
        return None


def cobol_de(regla, nombre: str):
    """Instancia de COBOL que decide sus capacidades con `regla` (el brazo del experimento).

    `name` distinto ⇒ caché de compilación distinta: los dos brazos nunca comparten binario,
    y un binario construido bajo una regla no puede contaminar la lectura de la otra.
    """
    from isyco.backends.cobol import BACKEND
    cls = type(BACKEND)

    class Brazo(cls):
        name = nombre
        features = cls.features

        def _features(self, data, module):
            return regla(module)

    return Brazo()


# --- mediciones -----------------------------------------------------------------------
def conteos(poblacion: list[dict], backends: dict) -> dict:
    """Dónde viven las dos preguntas, y a qué backend le cambia algo (solo aritmética)."""
    def triple(sub: list[dict]) -> tuple[int, int, list[str]]:
        etiqueta = {m["case"]["name"] for m in sub if m["module"]["schema"] == SCHEMA_V2}
        contenido = {m["case"]["name"] for m in sub if "ir0.2" in features_of(m["module"])}
        return len(etiqueta), len(contenido), sorted(etiqueta - contenido)
    por_etiqueta, por_contenido, solo = triple(poblacion)
    congelada = [m for m in poblacion if m["congelado"]]
    e_c, c_c, solo_c = triple(congelada)
    por_backend = {}
    for name, backend in sorted(backends.items()):
        viejo = nuevo = 0
        for m in poblacion:
            faltan_viejo = features_etiqueta(m["module"]) - set(backend.features)
            faltan_nuevo = features_of(m["module"]) - set(backend.features)
            viejo += bool(faltan_viejo)
            nuevo += bool(faltan_nuevo)
        por_backend[name] = {"declara_0_2": "ir0.2" in set(backend.features),
                             "unsupported_etiqueta": viejo, "unsupported_contenido": nuevo,
                             "cambia": viejo != nuevo}
    return {"total": len(poblacion), "por_etiqueta": por_etiqueta,
            "por_contenido": por_contenido, "solo_etiqueta": solo,
            "congelado": {"total": len(congelada), "por_etiqueta": e_c,
                          "por_contenido": c_c, "solo_etiqueta": solo_c},
            "por_backend": por_backend}


def brazo_a_brazo(nombres: list[str], backends: dict) -> list[dict]:
    """Ejecuta los casos donde las dos reglas difieren, una vez por brazo."""
    rows = []
    viejo = cobol_de(features_etiqueta, "cobol_etiqueta")
    for name in nombres:
        case = next(c for c in cases_all() if c["name"] == name)
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        row = {"name": name, "programa": "INVALID_PROGRAM" if ref["status"] == "INVALID_PROGRAM"
               else "IR", "referencia": observed_of(ref), "pasos_referencia": ref.get("steps")}
        for etiqueta, backend in (("etiqueta", viejo), ("contenido", backends["cobol"])):
            try:
                got, _ = backend.run(case["program"], case["input"], case.get("limits"))
                row[etiqueta] = {"clasificacion": classify(case["expected"], observed_of(ref),
                                                            got, None),
                                 "estado": f"{got.get('status')}"
                                           + (f"({got.get('code')})" if got.get("code") else ""),
                                 "pasos": got.get("steps"),
                                 "missing": got.get("code")
                                            if got.get("status") == "UNSUPPORTED" else None}
            except Exception as exc:                     # noqa: BLE001 — se registra, no se silencia
                row[etiqueta] = {"clasificacion": "BUILD_FAIL",
                                 "excepcion": f"{type(exc).__name__}: {str(exc)[:200]}"}
        row["pasos_iguales"] = (row.get("contenido", {}).get("pasos") == row["pasos_referencia"])
        rows.append(row)
    return rows


_ALL_CASES: list[dict] | None = None


def cases_all() -> list[dict]:
    global _ALL_CASES
    if _ALL_CASES is None:
        _ALL_CASES = list(load_all(ROOT)) + load_corpus(V05)
    return _ALL_CASES


def canarios(backends: dict) -> list[dict]:
    """Los cuatro casos escritos a mano antes de implementar, contra la referencia real."""
    rows = []
    for numero in CANARIOS:
        case = next(c for c in load_corpus(V05) if c["name"].startswith(f"{numero}_"))
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        module = compile_ir_safe(case["program"])
        pasos = None
        try:
            got, _ = backends["cobol"].run(case["program"], case["input"], case.get("limits"))
            clase = classify(case["expected"], observed_of(ref), got, None)
            estado = f"{got.get('status')}" + (f"({got.get('code')})" if got.get("code") else "")
            pasos = got.get("steps")
        except Exception as exc:                         # noqa: BLE001
            clase, estado = "BUILD_FAIL", f"{type(exc).__name__}: {str(exc)[:160]}"
        rows.append({"name": case["name"], "claim": case["claim"], "schema": module["schema"],
                     "ir0.2_por_contenido": "ir0.2" in features_of(module),
                     "capacidades": sorted(features_of(module)),
                     "esperado": case["expected"], "referencia": observed_of(ref),
                     "referencia_ok": observed_of(ref) == case["expected"],
                     "pasos_referencia": ref.get("steps"), "pasos_cobol": pasos,
                     "cobol": clase, "estado": estado})
    return rows


def hace_falta_emit_array(caso_253: dict, caso_441: dict, cobol) -> dict:
    """El artefacto nuevo tiene que nombrar un hueco real, no cosmético.

    Se le da a COBOL la capacidad que V7 dice que le falta. Si el emitter supiera imprimir
    arreglos, el resultado sería EQUIV y `emit_array` sería una etiqueta vacía; lo que pasa
    es que el emisor revienta, y eso es exactamente lo que la capacidad nombra.
    """
    from isyco.backends.cobol import BACKEND

    class ConAtomos(type(BACKEND)):
        name = "cobol_con_emit_array"
        features = frozenset(set(BACKEND.features) | {"emit_array"})

    con = ConAtomos()
    out = {}
    for etiqueta, case in (("253_congelado", caso_253), ("441_canario", caso_441)):
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        try:
            got, _ = con.run(case["program"], case["input"], case.get("limits"))
            clasificacion = classify(case["expected"], observed_of(ref), got, None)
            detalle = observed_of(got)
        except Exception as exc:                         # noqa: BLE001
            clasificacion = "BUILD_FAIL"
            detalle = f"{type(exc).__name__}: {str(exc)[:200]}"
        out[etiqueta] = {"clasificacion": clasificacion, "detalle": detalle,
                         "missing_cobol_real": missing_features(cobol, case["program"]),
                         "con_la_capacidad_de_claro_no_es_EQUIV": clasificacion != "EQUIV"}
    out["hueco_real"] = all(v["con_la_capacidad_de_claro_no_es_EQUIV"]
                            for k, v in out.items() if isinstance(v, dict))
    return out


def hace_el_trabajo(cobol) -> dict:
    """El COBOL recuperado ejecuta de verdad: cambiar el programa cambia la salida del binario.

    Dos variantes, cada una escrita sobre el fuente del caso (no sobre la salida). El control
    clásico de este repo —«la salida esperada no aparece escrita en el fuente generado»— se
    aplica donde puede nombrarse sin ambigüedad: en `442` la salida de la variante es `12`, un
    valor que se arma en el bucle, así que se busca como `DISPLAY "12"`. En `248` la salida son
    `"true"`/`"false"`, que el preámbulo del runtime de COBOL ya escribe como parte del
    formateo de booleanos: ahí el control es **NO_APLICABLE** y se declara, no se cuenta verde.
    """
    from isyco.ir_interp import compile_ir
    out = {"variantes": [], "literal_no_escrito": None, "ok": False}
    for nombre, (viejo, nuevo) in TRABAJO:
        case = next(c for c in cases_all() if c["name"].startswith(nombre))
        fuente = case["program"].decode("utf-8")
        if viejo not in fuente:
            out["variantes"].append({"caso": nombre, "error": f"«{viejo}» ya no está en el fuente"})
            continue
        variante = fuente.replace(viejo, nuevo).encode("utf-8")
        limpio, _ = cobol.run(case["program"], case["input"], case.get("limits"))
        ref_v, _ = run(variante, case["input"], case.get("limits"))
        got_v, _ = cobol.run(variante, case["input"], case.get("limits"))
        source_v = cobol.emit(compile_ir(variante))
        emitidos_v = [e for e in (ref_v.get("emits") or [])]
        escritos = [e for e in emitidos_v if f'DISPLAY "{e}"' in source_v]
        out["variantes"].append({
            "caso": nombre, "variante": nuevo, "salida_original": limpio.get("emits"),
            "salida_variante": got_v.get("emits"),
            "coincide_referencia_variante": observed_of(got_v) == observed_of(ref_v),
            "la_salida_cambia": got_v.get("emits") != limpio.get("emits"),
            "salidas_escritas_en_el_fuente_de_la_variante": escritos})
        if nombre.startswith("442"):
            out["literal_no_escrito"] = not escritos
    out["control_de_literales_248"] = (
        "NO_APLICABLE: el runtime de COBOL ya escribe \"true\"/\"false\" al formatear "
        "booleanos, así que buscar la salida en el fuente no distingue calculado de escrito")
    buenas = [v for v in out["variantes"] if "error" not in v]
    out["ok"] = bool(buenas) and all(
        v["coincide_referencia_variante"] and v["la_salida_cambia"] for v in buenas) \
        and out["literal_no_escrito"] is True
    return out


def _nodos(node):
    if isinstance(node, dict):
        yield node
        for valor in node.values():
            yield from _nodos(valor)
    elif isinstance(node, list):
        for valor in node:
            yield from _nodos(valor)


def rasgos(module: dict) -> set[str]:
    """Rasgos del programa que cada sabotaje declarado necesita para ser medible."""
    out: set[str] = set()
    for fn in module["functions"]:
        for node in _nodos(fn["body"]):
            k, op = node.get("k"), node.get("op")
            if k == "concat":
                out.add("str_concat")
            if k != "bin":
                continue
            lados = [node.get("a") or {}, node.get("b") or {}]
            ts = [(lado.get("ty") or {}).get("t") for lado in lados]
            ts.append((node.get("ty") or {}).get("t"))
            if "dec" in ts:
                out.add("dec")
            if op in ("div", "rem") and "int" in ts and "dec" not in ts:
                out.add("idiv")
    return out


NECESITA = {"half_even_as_half_up": "dec", "div_floor": "idiv", "str_concat_truncates": "str_concat"}


def ultima_evidencia_gate() -> dict:
    """El gate F5 sellado más reciente: dónde SÍ se mide el sabotaje, con su hash."""
    archivos = sorted((ROOT / "evidence" / "backends").glob("gate_*.json"))
    if not archivos:
        return {"hay": False, "nota": "no hay evidence/backends/gate_*.json"}
    ultimo = archivos[-1]
    data = json.loads(ultimo.read_text(encoding="utf-8"))
    cobol = data.get("backends", {}).get("cobol", {})
    return {"hay": True, "archivo": ultimo.name,
            "sha256": hashlib.sha256(ultimo.read_bytes()).hexdigest(),
            "git_head": data.get("git_head"),
            "cobol_corpus": {k: cobol.get("corpus", {}).get(k) for k in ("cases", "passed")},
            "cobol_unsupported": len(cobol.get("corpus", {}).get("unsupported", [])),
            "cobol_sabotaje": cobol.get("sabotage", {})}


def sabotaje(cobol, casos_hojas: list[dict], gate: dict) -> dict:
    """El sabotaje declarado se compara contra el mismo backend limpio, no contra la referencia.

    La población recuperada por V7 no es el lugar donde se mide un sabotaje numérico: es
    población de capacidades, elegida por su schema, no por sus operadores. Se reporta lo que
    hay (casos con el rasgo y lo que realmente observan) y se remite al gate F5 sellado, que
    barre el corpus completo y el diferencial. Un cascos nunca cuenta como detección.
    """
    out = {}
    for s in cobol.sabotages:
        necesario = NECESITA.get(s)
        rotas, cascos, ejercibles, observados = [], [], [], []
        for case in casos_hojas:
            module = compile_ir_safe(case["program"])
            if module is None or (necesario and necesario not in rasgos(module)):
                continue
            ejercibles.append(case["name"])
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            observados.append({"caso": case["name"], "observado": observed_of(ref)})
            try:
                got, _ = cobol.run(case["program"], case["input"], case.get("limits"),
                                   sabotage=s)
                base, _ = cobol.run(case["program"], case["input"], case.get("limits"))
            except Exception as exc:                     # noqa: BLE001
                cascos.append(f"{case['name']}:{type(exc).__name__}")
                continue
            if observed_of(got) != observed_of(base):
                rotas.append(case["name"])
        out[s] = {"necesita": necesario, "casos_con_el_rasgo": ejercibles,
                  "observados": observados,
                  "divergen": len(rotas), "casos_rotos": rotas, "cascos": cascos,
                  "lectura": ("DETECTADO" if rotas else "NO_MIDE_EN_ESTA_POBLACION"),
                  "por_que_no_FALSO": (None if rotas else
                        "un rasgo presente no es un observable que lo distinga: ver «observados» "
                        "(los operandos deciden) y el barrido completo del gate"),
                  "se_mide_en": (f"{gate.get('archivo')} (sha {str(gate.get('sha256'))[:12]}) "
                                 f"con {json.dumps(gate.get('cobol_sabotaje', {}).get(s))}"
                                 if gate.get("hay") else "sin gate sellado: INCONCLUSIVE")}
    return out


def fidelidad(poblacion: list[dict]) -> dict:
    """La simulación del brazo viejo tiene que ser EL código viejo, caso por caso."""
    vieja, nota = features_etiqueta_desde_git()
    if vieja is None:
        return {"estado": "INCONCLUSIVE", "nota": nota, "divergencias": None}
    diffs = [m["case"]["name"] for m in poblacion if set(vieja(m["module"])) !=
             features_etiqueta(m["module"])]
    return {"estado": "FIEL" if not diffs else "DIVERGE", "nota": nota,
            "modulos_comparados": len(poblacion), "divergencias": diffs[:12]}


def receipt(comando: str, rec: dict) -> dict:
    sucio_codigo = dirty_codigo()
    return {
        "schema": "isyco.evidence/0.1",
        "milestone": "V7 (CORE v0.5) — capacidades derivadas del contenido del programa",
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "comando": comando,
        "git_head": git_head(),
        "arbol_sucio_codigo": sucio_codigo,
        "veredicto_arbol": "EVIDENCE_ONLY" if sucio_codigo else "RELEASE_GATE",
        "python": platform.python_version(),
        "corpus": ("programs/conformance_v0.1..v0.4 (congelado) + canarios V7 "
                   "439..442 en programs/conformance_v0.5"),
        "corpus_hash": rec["corpus_hash"],
        "brazo_viejo_desde": REF_ETIQUETA,
        "backends_disponibles": sorted(available()),
        "casos": rec["casos"],
    }


def tabla(rec: dict, cont: dict, fieles: dict, brazos: list[dict], can: list[dict],
          atomos: dict, trabajo: dict, sab: dict) -> list[str]:
    lineas = [
        "V7 (CORE v0.5) — UNSUPPORTED por capacidad exigida, no por etiqueta de schema",
        f"utc={rec['utc']}  git_head={rec['git_head']}  arbol={rec['veredicto_arbol']}"
        f"  (sucio_codigo={rec['arbol_sucio_codigo']})",
        f"comando: {rec['comando']}",
        f"corpus={rec['corpus']}  casos_con_IR={rec['casos']}  corpus_hash={rec['corpus_hash']}",
        f"python={rec['python']}  backends={','.join(rec['backends_disponibles'])}",
        "",
        "1) SCHEMA_CAN_EXPRESS vs PROGRAM_REQUIRES",
        f"   congelado (v0.1..v0.4, {cont['congelado']['total']} programas con IR): "
        f"por etiqueta = {cont['congelado']['por_etiqueta']}   "
        f"por contenido (ir0.2) = {cont['congelado']['por_contenido']}   "
        f"solo por etiqueta = {len(cont['congelado']['solo_etiqueta'])}",
        f"   + canarios V7 ({cont['total']} programas con IR): "
        f"por etiqueta = {cont['por_etiqueta']}   por contenido = {cont['por_contenido']}   "
        f"solo por etiqueta = {len(cont['solo_etiqueta'])}",
        f"   {cont['solo_etiqueta']}",
        "   por backend (UNSUPPORTED antes -> despues, sin compilar: aritmetica de conjuntos):",
    ]
    for name, dato in cont["por_backend"].items():
        lineas.append(f"     {name:9s} {dato['unsupported_etiqueta']:4d} -> "
                      f"{dato['unsupported_contenido']:4d}   "
                      + ("CAMBIA" if dato["cambia"]
                         else "no cambia (declara ir0.2 y las capacidades 0.2)"))
    lineas += ["", f"2) brazo viejo reconstruido desde git: {fieles['estado']} "
                   f"({fieles.get('nota')}; {fieles.get('modulos_comparados')} modulos, "
                   f"divergencias {fieles.get('divergencias')})"]
    lineas.append("   ejecucion de los casos donde las dos reglas difieren:")
    for row in brazos:
        lineas.append(f"     {row['name']:28s} ref={row['referencia']['status']:15s}"
                      f" pasos={row['pasos_referencia']}  "
                      f"etiqueta={row['etiqueta']['clasificacion']}"
                      f"{'' if not row['etiqueta'].get('missing') else '(' + row['etiqueta']['missing'] + ')'}"
                      f"  ->  contenido={row['contenido']['clasificacion']}"
                      f"{'' if not row['contenido'].get('missing') else '(' + row['contenido']['missing'] + ')'}"
                      + ("" if row["contenido"].get("pasos") is None else
                         f" pasos={row['contenido']['pasos']}"
                         f" {'PASOS_IGUAL' if row['pasos_iguales'] else 'PASOS_DIFIERE'}")
                      + (f"  EXCEPCION {row['contenido'].get('excepcion')}"
                         if row['contenido'].get('excepcion') else ""))
    lineas.append("")
    lineas.append("3) canarios V7 (esperado escrito a mano antes de implementar):")
    for row in can:
        lineas.append(f"     {row['name']:28s} schema={row['schema'].split('/')[-1]}"
                      f" ir0.2por_contenido={str(row['ir0.2_por_contenido']):5s}"
                      f" ref={'OK' if row['referencia_ok'] else 'DIFIERE'}"
                      f" pasos ref={row['pasos_referencia']} cobol={row['pasos_cobol']}"
                      f"  cobol={row['cobol']} {row['estado']}")
        lineas.append(f"     {'':28s} capacidades={row['capacidades']}")
    lineas += ["", "4) ¿hace falta el atomo nuevo? (COBOL con `emit_array` regalada):"]
    for k, v in atomos.items():
        if isinstance(v, dict):
            lineas.append(f"     {k:15s} {v['clasificacion']}  "
                          f"missing_cobol_real={v['missing_cobol_real']}  {v['detalle']}")
    lineas.append(f"   hueco_real={atomos['hueco_real']}")
    lineas += ["", "5) el engine hace el trabajo (variantes del programa, no de la salida):"]
    for v in trabajo.get("variantes", []):
        if "error" in v:
            lineas.append(f"     {v['caso']:28s} ERROR {v['error']}")
        else:
            lineas.append(f"     {v['caso']:28s} {v['salida_original']} --[{v['variante']}]--> "
                          f"{v['salida_variante']}  coincide_ref={v['coincide_referencia_variante']}"
                          f"  cambia={v['la_salida_cambia']}"
                          f"  escritas_en_fuente={v['salidas_escritas_en_el_fuente_de_la_variante']}")
    lineas.append(f"   {trabajo.get('control_de_literales_248')}")
    lineas.append(f"   ok={trabajo.get('ok')}")
    lineas.append("6) sabotajes de COBOL sobre la población recuperada (mide capacidades, no operadores):")
    for s, v in sab.items():
        lineas.append(f"     {s:22s} {v['lectura']}  casos con el rasgo={v['casos_con_el_rasgo']}"
                      f"  observados={json.dumps(v['observados'], ensure_ascii=False)}")
        lineas.append(f"     {'':22s} se mide en: {v['se_mide_en']}")
    return lineas


def main(argv: list[str]) -> int:
    write = "--write" in argv
    backends = available()
    poblacion = modulos()
    cont = conteos(poblacion, backends)
    fieles = fidelidad(poblacion)
    nombres = cont["solo_etiqueta"]
    brazos = brazo_a_brazo(nombres, backends) if "cobol" in backends else []
    can = canarios(backends) if "cobol" in backends else []
    # Testigos del sabotaje: solo cuentan los casos que bajo la regla nueva ejecutan y
    # coinciden (un UNSUPPORTED o un DIVERGENT no puede detectar nada).
    vistos = {row["name"] for row in brazos if row["contenido"]["clasificacion"] == "EQUIV"}
    vistos |= {row["name"] for row in can if row["cobol"] == "EQUIV"}
    hojas = [c for c in cases_all() if c["name"] in vistos]
    atomos = hace_falta_emit_array(
        next(c for c in cases_all() if c["name"] == "253_emit_array"),
        next(c for c in cases_all() if c["name"].startswith("441_")),
        backends["cobol"]) if "cobol" in backends else {}
    trabajo = hace_el_trabajo(backends["cobol"]) if "cobol" in backends else {}
    gate = ultima_evidencia_gate()
    sab = sabotaje(backends["cobol"], hojas, gate) if "cobol" in backends else {}
    corpus_hash = hashlib.sha256(json.dumps(
        [{"name": m["case"]["name"], "expected": m["case"]["expected"]} for m in poblacion],
        sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    rec = receipt(" ".join(["python3", "tools/v7_capability_probe.py"] + argv),
                  {"corpus_hash": corpus_hash, "casos": len(poblacion)})
    documento = {"receipt": rec, "conteos": cont, "fidelidad_brazo_viejo": fieles,
                 "brazos": brazos, "canarios": can, "emit_array": atomos,
                 "hace_el_trabajo": trabajo, "sabotaje": sab, "gate_f5": gate}
    lineas = tabla(rec, cont, fieles, brazos, can, atomos, trabajo, sab)
    for linea in lineas:
        print(linea)

    conteo_por_clase = {}
    for row in brazos:
        conteo_por_clase[row["contenido"]["clasificacion"]] = \
            conteo_por_clase.get(row["contenido"]["clasificacion"], 0) + 1
    print(f"\nbrazo contenido sobre los {len(brazos)} casos que solo pedian la etiqueta: "
          f"{conteo_por_clase}")
    pasos_malos = [row["name"] for row in brazos
                   if row["contenido"]["clasificacion"] == "EQUIV" and not row["pasos_iguales"]]
    trampa = [row["name"] for row in brazos if row["contenido"]["clasificacion"]
              in ("DIVERGENT", "BUILD_FAIL", "RUNTIME_FAIL", "INCONCLUSIVE")]
    can_trampa = [row["name"] for row in can
                  if not row["referencia_ok"] or row["cobol"]
                  in ("DIVERGENT", "BUILD_FAIL", "RUNTIME_FAIL")]
    print(f"fallos reales en brazos (no UNSUPPORTED): {trampa or 'ninguno'}")
    print(f"fallos reales en canarios: {can_trampa or 'ninguno'}")
    print(f"recuperados con pasos distintos de la referencia: {pasos_malos or 'ninguno'}")
    falsos = []
    if fieles["estado"] != "FIEL":
        falsos.append(f"el brazo viejo no reproduce el código de {REF_ETIQUETA}"
                      f" ({fieles['estado']})")
    if not atomos.get("hueco_real", True):
        falsos.append("emit_array regalado produce EQUIV: la capacidad no nombra nada")
    if not trabajo.get("ok", True):
        falsos.append("la salida no se mueve con el programa, o la variante no coincide")
    sin_deteccion = [s for s, v in (gate.get("cobol_sabotaje") or {}).items()
                     if isinstance(v, dict) and not v.get("detected")]
    if sin_deteccion:
        print(f"AVISO (estado previo del gate sellado, no de V7): sabotajes sin detección "
              f"en {gate.get('archivo')}: {sin_deteccion}")
    if not gate.get("hay"):
        falsos.append("sin gate F5 sellado: la remisión del sabotaje queda INCONCLUSIVE")
    for mensaje in falsos:
        print(f"CONTROL FALSO/INCONCLUSIVE: {mensaje}")
    if write and (trampa or can_trampa or pasos_malos or falsos):
        print("no se sella: hay fallos reales o controles falsos")
        return 1

    if not write:
        return 0
    stamp = rec["utc"].replace(":", "").replace("-", "")
    destino = ROOT / "evidence" / "v05_v7"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"run_{stamp}.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (destino / f"run_{stamp}.json").write_text(
        json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    archivos = sorted(p for p in destino.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (destino / "SHA256SUMS.txt").write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in archivos),
        encoding="utf-8")
    print(f"\nsellado en evidence/v05_v7/run_{stamp}.{{txt,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
