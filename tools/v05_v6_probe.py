"""Sonda del milestone V6+V6-bis (CORE v0.5): capacidad diferida en parámetros y retornos.

Corre los casos V6 de `programs/conformance_v0.5/` contra las tres rutas —intérprete de
referencia, ISY-IR (ida y vuelta por JSON) y cada backend instalado— y compara con los
`expected`, que están escritos A MANO antes de implementar (rito del repo: esperado
independiente + backends como testigos).

Clasifica cada backend como EQUIV / DIVERGENT / UNSUPPORTED / BUILD_FAIL / RUNTIME_FAIL /
INCONCLUSIVE: un fallo de compilación nunca se reescribe como «no soportado» y una
excepción nunca se convierte en IR vacía y sigo.

También mide, sin fijar límites (es la base de P4): cuántas especializaciones crea cada
programa y cuántas funciones llegan a la IR. Y lleva el control anti-fake de todo
diferencial de este repo: un backend saboteado tiene que romper algo.

    python3 tools/v05_v6_probe.py            # tabla por stdout
    python3 tools/v05_v6_probe.py --write    # sella evidence/v05_v6/run_<UTC>.{json,txt}
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

from isyco import checker, modules                                    # noqa: E402
from isyco.backends import available, registry                        # noqa: E402
from isyco.conformance import COMPARED, load_corpus                   # noqa: E402
from isyco.errors import InvalidProgram                               # noqa: E402
from isyco.interp import run                                          # noqa: E402
from isyco.ir_interp import compile_ir, run_via_ir                    # noqa: E402
from isyco.source import program_sha256                               # noqa: E402

CORPUS_DIR = ROOT / "programs" / "conformance_v0.5"
V6 = tuple(f"{n:03d}" for n in range(411, 439))     # V6 (411–428) + V6-bis (429–438)
CASO_ENTRADA = "428_str_pelado_desde_stdin"          # el único con entrada por stdin
CASO_EMISION_LARGA = "423_ancho_grande_doble"        # emite 32 bytes que el fuente no contiene
CASO_RETORNO = "429_retorno_pelado_dos_expectativas"  # concatena y emite 8 bytes que el fuente no contiene
OTRA_ENTRADA = "adios"
KEYS = COMPARED


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dirty() -> bool:
    """Árbol sucio => la corrida es EVIDENCE_ONLY, nunca gate de release."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return True
    return bool(out.strip())


def dirty_codigo() -> bool:
    """Si hay código sin commitear, ignorando `evidence/`.

    El requisito del plan es «PASS con árbol sucio = EVIDENCE_ONLY» para que nada del
    compilador cambie entre la medición y el commit. Pero sellar SIEMPRE ensucia el árbol
    — escribe el propio archivo de evidencia —, así que el lectura útil es «¿hay algo del
    engine o del corpus sin commitear?». `arbol_sucio` sigue registrando la cruda: las dos
    banderas quedan en el recibo, no se esconde una detrás de la otra.
    """
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return True
    for linea in out.splitlines():
        if not linea.strip():
            continue
        ruta = linea[3:] if len(linea) > 3 else ""
        partes = [p.strip() for p in ruta.split("->")]     # un rename muestra «viejo -> nuevo»
        if all(p.startswith("evidence/") for p in partes):
            continue
        return True
    return False


def shape(row: dict) -> str:
    return f"{row.get('status')}" + (f"({row.get('code')})" if row.get("code") else "")


def observed_of(row: dict) -> dict:
    return {k: row.get(k) for k in KEYS}


def specializations(program) -> dict:
    """Nombres fuente vs clones que crea el checker (medición de P4, sin límite fijado)."""
    antes = set(program.fns)
    checker.check(program)
    despues = set(program.fns)
    return {"creadas": sorted(despues - antes), "descartadas": sorted(antes - despues)}


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


def probe_case(case: dict, backends: dict) -> dict:
    ref, _ = run(case["program"], case["input"], case.get("limits"))
    referencia = observed_of(ref)
    row = {"name": case["name"], "claim": case["claim"], "input": case["input"],
           "program_sha256": program_sha256(case["program"]), "expected": case["expected"],
           "reference": referencia, "reference_ok": referencia == case["expected"],
           "steps": ref["steps"]}
    try:
        module = compile_ir(case["program"])
        ir_result, _ = run_via_ir(case["program"], case["input"], case.get("limits"))
        observado_ir = observed_of(ir_result)
        row.update(ir=observado_ir, ir_schema=module["schema"],
                   ir_ok=observado_ir == case["expected"] and observado_ir == referencia,
                   funciones_ir=sorted(f["name"] for f in module["functions"]))
    except InvalidProgram as exc:      # rechazado en el chequeo: la IR tampoco existe, y eso es acuerdo
        de_acuerdo = (case["expected"]["status"] == "INVALID_PROGRAM"
                      and exc.code == case["expected"]["code"])
        row.update(ir=None, ir_ok=de_acuerdo, ir_rechazo=f"INVALID_PROGRAM({exc.code})")
    except Exception as exc:                         # noqa: BLE001 — se registra, no se silencia
        row.update(ir=None, ir_ok=False, excepcion_ir=f"{type(exc).__name__}: {exc}")
    fila = {}
    for name, backend in sorted(backends.items()):
        try:
            got, _ = backend.run(case["program"], case["input"], case.get("limits"))
            fila[name] = {"clasificacion": classify(case["expected"], referencia, got, None),
                          "estado": shape(got), "observed": observed_of(got),
                          "missing": got.get("code") if got.get("status") == "UNSUPPORTED" else None}
        except Exception as exc:                     # noqa: BLE001
            fila[name] = {"clasificacion": "BUILD_FAIL",
                          "excepcion": f"{type(exc).__name__}: {str(exc)[:300]}"}
    row["backends"] = fila
    try:
        row["especializaciones"] = specializations(modules.load_program(case["program"]))
    except InvalidProgram as exc:      # un programa rechazado en el chequeo no instancia nada
        row["especializaciones"] = {"creadas": [], "descartadas": [], "rechazado": exc.code}
    return row


def nodos(node):
    """Todos los dicts de un cuerpo de IR, sin depender de ningún privado del backend."""
    if isinstance(node, dict):
        yield node
        for valor in node.values():
            yield from nodos(valor)
    elif isinstance(node, list):
        for valor in node:
            yield from nodos(valor)


def rasgos(module: dict) -> set[str]:
    """Rasgos que el programa **usa**, leídos de la IR bajada (no de la cabecera).

    Sirve para una sola pregunta aquí: ¿este corpus puede ejercitar el sabotaje? Un
    programa sin decimales no puede detectar un cambio de redondeo por mucho que el
    texto generado cambie — el preámbulo del runtime se patchea en todos los casos.
    Medir el texto diría «en alcance» donde no hay nada que medir.
    """
    out: set[str] = set()
    for fn in module["functions"]:
        for node in nodos(fn["body"]):
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


def sabotage_control(backend, cases: list[dict]) -> dict:
    """Un backend saboteado tiene que romperse **contra sí mismo** en algún caso.

    Comparar el sabotaje contra la referencia es trampa: un backend que ya diferencia
    de la referencia —UNSUPPORTED en todo este corpus, p. ej. COBOL— «detectaría» el
    sabotaje sin tocarlo. La comparación es `saboteado vs sin sabotear` sobre los
    mismos datos.

    Dos refinamientos, porque la sonda no puede inflarse a sí misma:

    - un cascos NO cuenta como detección: contarse un crash como prueba de que el
      engine miró los datos es exactamente el modo en que un diferencial se vuelve falso;
    - un sabotaje cuyo rasgo no aparece en ningún programa del corpus está VACÍO. No es
      un fallo ni una cobertura: es un rasgo que este corpus no mide, y se dice.
    """
    hojas = []
    for case in cases:
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        base = None
        try:
            base, _ = backend.run(case["program"], case["input"], case.get("limits"))
        except Exception as exc:                       # noqa: BLE001
            base = {"excepcion": f"{type(exc).__name__}"}
        if observed_of(base) == observed_of(ref):
            hojas.append(case)
    # Un programa rechazado en el chequeo no tiene IR: lo que no baja tampoco se puede medir.
    def rasgos_de(case):
        try:
            return rasgos(compile_ir(case["program"]))
        except InvalidProgram:
            return set()
    out = {}
    for sabotage in backend.sabotages:
        necesario = NECESITA.get(sabotage)
        ejercibles = [c for c in hojas
                      if not necesario or necesario in rasgos_de(c)]
        rotas, cascos = [], []
        for case in ejercibles:
            try:
                got, _ = backend.run(case["program"], case["input"], case.get("limits"),
                                     sabotage=sabotage)
                base, _ = backend.run(case["program"], case["input"], case.get("limits"))
            except Exception as exc:                   # noqa: BLE001
                cascos.append(f"{case['name']}:{type(exc).__name__}")
                continue
            if observed_of(got) != observed_of(base):
                rotas.append(case["name"])
        if rotas:
            lectura = "DETECTADO"
        elif not ejercibles:
            lectura = ("VACÍO: ningún caso testigo de este corpus usa el rasgo "
                       f"{necesario or '?'}")
        else:
            lectura = "FALSO: hay casos que usan el rasgo y el sabotaje no los mueve"
        out[sabotage] = {"necesita": necesario, "ejercibles": len(ejercibles),
                         "casos_ejercibles": [c["name"] for c in ejercibles][:8],
                         "testigos": len(hojas),
                         "divergen": len(rotas), "detectado": bool(rotas),
                         "casos_rotos": rotas[:8], "cascos": cascos, "lectura": lectura}
    return out


def does_the_work(backend, caso_largo: dict, caso_entrada: dict, caso_retorno: dict) -> dict:
    """El engine hace el trabajo, no el generador. Tres controles, cada uno donde aplica:

    - `423` emite 32 bytes que el fuente NO contiene escritos (`abcde…` se arma con `s + s`);
    - `428` lee stdin: cambiar la entrada tiene que cambiar la salida;
    - `429` (V6-bis) emite `abcdabcd`, que tampoco está escrito en el fuente: lo arma
      la copia especializada del retorno pelado.
    """
    esperado_largo = caso_largo["expected"]["emits"][0]
    source = backend.emit(compile_ir(caso_largo["program"]))
    filtrada = esperado_largo in source
    esperado_ret = caso_retorno["expected"]["emits"][0]
    source_ret = backend.emit(compile_ir(caso_retorno["program"]))
    filtrada_ret = esperado_ret in source_ret
    esperado = caso_entrada["expected"]["return"]
    otra, _ = backend.run(caso_entrada["program"], [OTRA_ENTRADA], caso_entrada.get("limits"))
    return {"cadena_de_32_en_el_fuente": filtrada, "otra_entrada": OTRA_ENTRADA,
            "otra_salida": otra.get("return"), "esperada": esperado,
            "cadena_de_retorno_en_el_fuente": filtrada_ret,
            "ok": not filtrada and not filtrada_ret and otra.get("return") not in (None, esperado)}


def receipt(cases: list[dict], comando: str) -> dict:
    sucio = dirty()
    sucio_codigo = dirty_codigo()
    corpus_hash = hashlib.sha256(json.dumps(
        [{"name": c["name"], "input": c["input"], "expected": c["expected"]} for c in cases],
        sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "schema": "isyco.evidence/0.1",
        "milestone": "V6/V6-bis (CORE v0.5) — str contextual en parámetros y retornos",
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "comando": comando,
        "git_head": git_head(),
        "arbol_sucio": sucio,
        "arbol_sucio_codigo": sucio_codigo,
        "regla_veredicto": ("RELEASE_GATE solo si `arbol_sucio_codigo` es falsa: ni el "
                            "engine, ni el corpus, ni las pruebas están modificados. "
                            "`arbol_sucio` cruda casi siempre es verdadera porque sellar "
                            "escribe evidencia en el árbol."),
        "veredicto_arbol": "EVIDENCE_ONLY" if sucio_codigo else "RELEASE_GATE",
        "python": platform.python_version(),
        "semilla": "n/a — la sonda no genera valores aleatorios",
        "corpus": "programs/conformance_v0.5, casos 411..438",
        "corpus_hash": corpus_hash,
        "backends_disponibles": sorted(available()),
        "versiones_backends": {name: (available()[name].toolchain() if name in available() else None)
                               for name in sorted(registry())},
        "casos": len(cases),
    }


def tabla(rec: dict, rows: list[dict], controles: dict) -> list[str]:
    lineas = [
        "V6+V6-bis (CORE v0.5) — capacidad diferida en parámetros y retornos",
        f"utc={rec['utc']}  git_head={rec['git_head']}  arbol={rec['veredicto_arbol']}"
        f"  (sucio_codigo={rec['arbol_sucio_codigo']}  sucio_crudo={rec['arbol_sucio']})",
        f"comando: {rec['comando']}",
        f"corpus={rec['corpus']}  casos={rec['casos']}  corpus_hash={rec['corpus_hash']}",
        f"python={rec['python']}  backends={','.join(rec['backends_disponibles'])}",
        f"semilla: {rec['semilla']}",
        "",
        "Cada caso se compara contra el expected escrito a mano en tres rutas: referencia,",
        "ISY-IR (ida y vuelta por JSON) y cada backend instalado. UNSUPPORTED no es fallo:",
        "es el dominio declarado del backend. Un programa rechazado en el chequeo no tiene",
        "IR: la ruta IR coincide cuando rechaza el mismo código de error.",
    ]
    for row in rows:
        if row.get("ir_rechazo") and row["ir_ok"]:
            estado_ir = f"RECHAZADO IGUAL QUE LA REFERENCIA {row['ir_rechazo']}"
        else:
            estado_ir = "COINCIDE" if row["ir_ok"] else "DIFIERE"
        lineas += [
            "",
            f"{row['name']}  —  {row['claim']}",
            f"  esperado   {json.dumps(row['expected'], ensure_ascii=False)}",
            f"  referencia {json.dumps(row['reference'], ensure_ascii=False)}"
            f"  steps={row['steps']}  {'COINCIDE' if row['reference_ok'] else 'DIFIERE'}",
            f"  ir         {json.dumps(row.get('ir'), ensure_ascii=False)}"
            f"  schema={row.get('ir_schema')}  {estado_ir}"
            + (f"  EXCEPCION {row['excepcion_ir']}" if row.get("excepcion_ir") else ""),
            f"  especializaciones creadas {row['especializaciones']['creadas']}"
            f"  descartadas {row['especializaciones']['descartadas']}",
        ]
        for name, dato in row["backends"].items():
            detalle = (f"missing={dato['missing']}" if dato["clasificacion"] == "UNSUPPORTED"
                       else json.dumps(dato.get("observed"), ensure_ascii=False))
            lineas.append(f"  {name:10s} {dato['clasificacion']:14s} {dato['estado']:18s} {detalle}")
    lineas.append("")
    total = len(rows)
    for name, control in sorted(controles.items()):
        testigos = max((d["testigos"] for d in control["sabotaje"].values()), default=0)
        sabotajes = "  ".join(
            f"{s}: {d['divergen']} rotas de {d['ejercibles']} casos con «{d['necesita']}» "
            f"[{d['lectura'].split(':')[0]}]"
            for s, d in control["sabotaje"].items())
        lineas.append(f"control {name} (testigos propios: {testigos}/{total}): {sabotajes or '—'}")
        if control.get("hace_el_trabajo"):
            lineas.append(f"  hace_el_trabajo={control['hace_el_trabajo']}")
    return lineas


def main(argv: list[str]) -> int:
    write = "--write" in argv
    cases = [c for c in load_corpus(CORPUS_DIR) if c["name"].split("_")[0] in V6]
    backends = available()
    rec = receipt(cases, " ".join(["python3", "tools/v05_v6_probe.py"] + argv))
    rows = [probe_case(case, backends) for case in cases]
    controles = {}
    caso_largo = next(c for c in cases if c["name"] == CASO_EMISION_LARGA)
    caso_entrada = next(c for c in cases if c["name"] == CASO_ENTRADA)
    caso_retorno = next(c for c in cases if c["name"] == CASO_RETORNO)
    for name, backend in sorted(backends.items()):
        control = {"sabotaje": sabotage_control(backend, cases)}
        try:
            control["hace_el_trabajo"] = does_the_work(backend, caso_largo, caso_entrada,
                                                       caso_retorno)
        except Exception as exc:                     # noqa: BLE001
            control["hace_el_trabajo"] = {"no_aplicable": f"{type(exc).__name__}: {str(exc)[:160]}"}
        controles[name] = control
    documento = {"receipt": rec, "cases": rows, "controles": controles}
    lineas = tabla(rec, rows, controles)
    for linea in lineas:
        print(linea)

    falsos = {name: [s for s, d in c["sabotaje"].items() if d["lectura"] == "FALSO"]
              for name, c in controles.items()
              if any(d["lectura"] == "FALSO" for d in c["sabotaje"].values())}
    if falsos:
        print(f"\nCONTROL FALSO (cambia el código y ningún observable): {falsos}")
    vacios = {name: [s for s, d in c["sabotaje"].items() if d["lectura"].startswith("VACÍO")]
              for name, c in controles.items()
              if any(d["lectura"].startswith("VACÍO") for d in c["sabotaje"].values())}
    if vacios:
        print(f"CONTROLES VACÍOS (el corpus no ejercita ese rasgo; cobertura NO medida): "
              f"{json.dumps(vacios, ensure_ascii=False)}")
    cascos = {name: {s: d["cascos"] for s, d in c["sabotaje"].items() if d["cascos"]}
              for name, c in controles.items() if any(d["cascos"] for d in c["sabotaje"].values())}
    if cascos:
        print(f"sabotajes que cascan (no cuentan como detección): {json.dumps(cascos)[:400]}")
    trampa = [row["name"] for row in rows
              if any(d["clasificacion"] in ("BUILD_FAIL", "RUNTIME_FAIL", "INCONCLUSIVE")
                     or d["clasificacion"] == "DIVERGENT" for d in row["backends"].values())
              or not row["reference_ok"] or not row["ir_ok"]]
    print(f"casos con fallo real (no UNSUPPORTED): {trampa or 'ninguno'}")

    if not write:
        return 0
    stamp = rec["utc"].replace(":", "").replace("-", "")
    destino = ROOT / "evidence" / "v05_v6"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"run_{stamp}.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (destino / f"run_{stamp}.json").write_text(
        json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    archivos = sorted(p for p in destino.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (destino / "SHA256SUMS.txt").write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in archivos),
        encoding="utf-8")
    print(f"\nsellado en evidence/v05_v6/run_{stamp}.{{txt,json}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
