"""Gate F5: conformidad ISY_BACKEND/1 de cada backend instalado, con evidencia.

Uso: python3 tools/backend_gate.py [--pairs N] [--only c,rust,zig] [--extra-case ruta.isy]

Por backend (spec/BACKEND.md §5):
1. corpus v0.1–v0.4: mismo status/code/emits/return/steps que la referencia;
2. casos fuera de capacidades -> UNSUPPORTED (se cuentan aparte);
3. diferencial por tipo numérico (isyco/difftest.py) contra la referencia;
4. el engine hace el trabajo: el fuente generado no contiene las salidas
   esperadas y otra entrada da otra salida;
5. cada sabotaje declarado por el backend es detectado (corpus y diferencial);
   si el backend declara `str`, también corre el diferencial de strings;
6. costo medido (spec/BACKEND.md §3.1): resumen por backend, informativo.

Durante 21 recibos este gate abortaba a mitad si un toolchain moría: `backend.run` se
llamaba sin guarda y el JSON se escribía solo al final, así que no quedaba recibo ni para
los casos anteriores (hallazgo 13). Ahora hay tres capas y un sellado que corre aunque
la corrida reviente:
- **caso** — `isyco/harness` alrededor de cada llamada al backend, dentro de `corpus`,
  `does_the_work` y las piernas diferenciales: el fallo se anota en la lista hermana
  `harness` y la pierna continúa;
- **pierna** — lo que la capa 1 no atrapó deja la pierna como `not_run` y el gate pasa al
  backend siguiente;
- **corrida** — cualquier otra excepción se registra en `abortado` con su traceback, y aun
  así `_gate.sellar` escribe el recibo y su stdout.
Un fallo del toolchain **no** es una diferencia semántica: `failures` y `diffs` siguen
midiendo solo desacuerdos con la referencia (la semántica normativa, spec/BACKEND.md), y
`conformant` se pliega sobre las dos cosas. Escribe `evidence/backends/gate_<UTC>.json`,
nunca sobrescribe, y rehace el `SHA256SUMS.txt` del directorio.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _gate  # noqa: E402
from isyco import run  # noqa: E402
from isyco.backends import available, registry  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.difftest import compare, compare_str  # noqa: E402
from isyco.harness import CODES, SCHEMA, intento  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402
from isyco.source import program_sha256  # noqa: E402

KEYS = COMPARED + ("steps",)


def firmar(filas: list, nombre: str, version: str) -> list:
    """Cada fila del arnés dice de qué backend y de qué toolchain es.

    Con cinco backends en la corrida, una fila que solo dice «pierna corpus» no permite ni
    reproducir el fallo ni descartar que sea la misma fuente muerta en dos patas distintas.
    """
    for fila in filas:
        fila.setdefault("backend", nombre)
        fila.setdefault("toolchain", version)
    return filas


def corpus(backend, cases, sabotage=None) -> dict:
    """Corpus contra la referencia. Un caso que revienta el toolchain se anota y no se cuenta.

    `passed + unsupported + fallas` puede ser menor que `cases`: la diferencia son los casos
    que no llegaron a medirse, y `no_medidos` lo dice explícito en vez de inflar un cero. La
    referencia se llama sin guarda: si ella explota, el bug es del idioma y tiene que subir.
    """
    passed, unsupported, failures, costs, filas = 0, [], [], [], []
    for case in cases:
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        contexto = {"leg": "corpus", "case": case["name"], "sabotage": sabotage,
                    # `program_sha256` y no `hashlib`: en v0.5 el programa es un Bundle y
                    # hashear sus bytes crudos revienta aquí, antes de llamar al backend.
                    "program_sha256": program_sha256(case["program"])}
        got, fr = intento(backend.run, case["program"], case["input"], case.get("limits"),
                          fase="corpus", contexto=contexto, sabotage=sabotage)
        if fr is not None:
            filas.append(fr)
            continue
        got = got[0]                                 # el contrato del backend es (resultado, traza)
        if got.get("cost"):
            costs.append(got["cost"])
        if got.get("status") == "UNSUPPORTED":
            unsupported.append({"name": case["name"], "missing": got["code"]})
        elif {k: ref[k] for k in KEYS} == {k: got.get(k) for k in KEYS} \
                and not got.get("backend_stderr"):
            passed += 1
        else:
            failures.append({"name": case["name"], "reference": {k: ref[k] for k in KEYS},
                             "backend": {k: got.get(k) for k in KEYS},
                             "stderr": got.get("backend_stderr")})
    return {"cases": len(cases), "passed": passed, "unsupported": unsupported,
            "failures": failures, "cost": cost_summary(costs), "harness": filas,
            "no_medidos": len(filas)}


def cost_summary(costs: list) -> dict:
    """Resumen del costo medido en las corridas del corpus (no semántico)."""
    rss = [c["max_rss_kb"] for c in costs if c.get("max_rss_kb") is not None]
    return {"runs_measured": len(costs),
            "wall_ms_total": round(sum(c["wall_ms"] for c in costs), 3),
            "user_ms_total": round(sum(c["user_ms"] for c in costs), 3),
            "sys_ms_total": round(sum(c["sys_ms"] for c in costs), 3),
            "max_rss_kb_max": max(rss) if rss else None,
            "rss_measured_runs": len(rss)}


def sabotages(backend, cases, pairs) -> dict:
    """Cada sabotaje declarado debe ser detectado; un crash de la pierna NO es detección.

    `corpus_failures` y `difftest_diffs` siguen siendo solo divergencia semántica y valen
    `None` cuando la pierna murió antes de medir: escribir 0 diría «no detectó nada», y ese
    cero es exactamente el blanco que no puede heredar un verde.
    """
    version = backend.toolchain() or "?"
    out = {}
    for sabotage in backend.sabotages:
        contexto = {"leg": f"sabotage:{sabotage}", "sabotage": sabotage, "backend": backend.name}
        filas, c_fail, d_fail, s_fail = [], None, None, None
        corre_str = "str" in backend.features
        cuerpo, fr = intento(corpus, backend, cases, fase="sabotage.corpus",
                             contexto=contexto, sabotage=sabotage)
        if fr is not None:
            filas.append(fr)
        else:
            filas += firmar(cuerpo["harness"], backend.name, version)
            c_fail = len(cuerpo["failures"])
        dif, fr = intento(compare, partial(backend.run, sabotage=sabotage),
                          fase="sabotage.difftest", contexto=contexto, pairs=pairs)
        if fr is None:
            filas += firmar(dif["harness"], backend.name, version)
            d_fail = len(dif["diffs"])
        else:
            filas.append(fr)
        if corre_str:
            sd, fr = intento(compare_str, partial(backend.run, sabotage=sabotage),
                             fase="sabotage.difftest_str", contexto=contexto, per_op=4)
            if fr is None:
                filas += firmar(sd["harness"], backend.name, version)
                s_fail = len(sd["diffs"])
            else:
                filas.append(fr)
        medido = c_fail is not None and d_fail is not None and (s_fail is not None or not corre_str)
        fila = {"corpus_failures": c_fail, "difftest_diffs": d_fail,
                "detected": bool(medido and c_fail and (d_fail + (s_fail or 0)) and not filas),
                "harness": filas}
        if corre_str:
            fila["difftest_str_diffs"] = s_fail
        out[sabotage] = fila
    return out


def does_the_work(backend, cases) -> dict:
    """El engine hace el trabajo: el fuente no contiene las salidas y otra entrada da otra.

    Si el toolchain muere aquí no se midió nada: `ok` en falso y las dos cifras en `None`,
    nunca un `[]` que se lea como «no se filtró nada».
    """
    case = next(c for c in cases if c["name"] == "027_interes")
    contexto = {"leg": "does_the_work", "case": case["name"], "backend": backend.name,
                "toolchain": backend.toolchain() or "?"}
    filas = []
    fuente, fr = intento(backend.emit, compile_ir(case["program"]), fase="does_the_work.emit",
                         contexto=contexto)
    leaked = None if fr is not None else [v for v in case["expected"]["emits"] if v in fuente]
    if fr is not None:
        filas.append(fr)
    other, fr = intento(backend.run, case["program"], ["2000.00", "0.0525"],
                        fase="does_the_work.run", contexto=contexto)
    emites = None if fr is not None else other[0].get("emits")
    if fr is not None:
        filas.append(fr)
    return {"leaked_outputs": leaked, "other_input_emits": emites, "harness": filas,
            "ok": not filas and not leaked and emites == ["8.22", "16.44", "24.66"]}


def esqueleto(nombre: str, backend, version: str, seleccionado: bool = True) -> dict:
    """Entrada completa ANTES de correr nada: un backend que no arranca también deja recibo.

    `tests/test_evidence.py` pliega todos los recibos con `newest.update(gate["backends"])`;
    sin esta fila, un backend ausente de este recibo heredaría la entrada del anterior y la
    suite quedaría verde sobre una corrida abortada. Las piernas sin correr se escriben
    `{"not_run": true}` y SIN campos numéricos: un `diff_count: 0` pasaría la aserción.

    `seleccionado` separa las dos cosas que antes se confundían: `--only c` deja a los demás
    marcados como «hoy no tocaba correrlos» (un gate parcial sigue pudiendo decir PASS, que
    es el uso declarado de la bandera), mientras que un backend seleccionado que no terminó
    fuerza FAIL.
    """
    return {"toolchain": version, "features": sorted(backend.features), "completado": False,
            "corpus": {"not_run": True}, "difftest": {"not_run": True},
            "does_the_work": {"not_run": True}, "sabotage": {}, "conformant": False,
            "seleccionado": seleccionado}


def correr_backend(report, backend, cases, args) -> bool:
    """Las cinco piernas de un backend. La capa 2 (`capa`) es la que deja `not_run`."""
    nombre = backend.name
    version = backend.toolchain() or "?"
    entry = report["backends"][nombre]
    ok = True

    def capa(legible, f, *a, **kw):
        res, fr = intento(f, *a, fase=f"pierna:{legible}",
                          contexto={"leg": legible, "backend": nombre}, **kw)
        if fr is not None:
            return {"not_run": True, "harness": firmar([fr], nombre, version)}
        if isinstance(res, dict):
            firmar(res.get("harness", []), nombre, version)
        return res

    cuerpo = capa("corpus", corpus, backend, cases)
    if cuerpo.get("not_run"):
        ok = False
    entry["corpus"] = cuerpo
    print(f"  corpus: {cuerpo.get('passed', 0)}/{cuerpo.get('cases', 0)} "
          f"(unsupported {len(cuerpo.get('unsupported', []))}, fallas "
          f"{len(cuerpo.get('failures', []))}, arnés {len(cuerpo.get('harness', []))})",
          flush=True)

    dif = capa("difftest", compare, backend.run, pairs=args.pairs)
    if dif.get("not_run"):
        ok = False
        entry["difftest"] = dif
    else:
        entry["difftest"] = {"runs": dif["runs"], "seed": dif["seed"],
                             "diff_count": len(dif["diffs"]), "diffs": dif["diffs"][:30],
                             "harness": dif["harness"], "types_aborted": dif["types_aborted"],
                             "omitted": sum(t["omitted"] for t in dif["types"])}
    print(f"  difftest: {entry['difftest'].get('runs', 0)} corridas, "
          f"{entry['difftest'].get('diff_count', 0)} diferencias, "
          f"{len(entry['difftest'].get('harness', []))} filas del arnés", flush=True)

    if "str" in backend.features:
        sd = capa("difftest_str", compare_str, backend.run)
        if sd.get("not_run"):
            ok = False
            entry["difftest_str"] = sd
        else:
            entry["difftest_str"] = {"runs": sd["runs"], "seed": sd["seed"],
                                     "diff_count": len(sd["diffs"]), "diffs": sd["diffs"][:30],
                                     "harness": sd["harness"], "omitted": sd["omitted"],
                                     "aborted": sd["aborted"]}
            print(f"  difftest str: {sd['runs']} corridas, {len(sd['diffs'])} diferencias, "
                  f"{len(sd['harness'])} filas del arnés", flush=True)

    trabajo = capa("does_the_work", does_the_work, backend, cases)
    if trabajo.get("not_run"):
        trabajo = {"not_run": True, "ok": False, "harness": trabajo["harness"],
                   "leaked_outputs": None, "other_input_emits": None}
        ok = False
    entry["does_the_work"] = trabajo
    print(f"  engine hace el trabajo: {trabajo['ok']}", flush=True)

    sab = capa("sabotage", sabotages, backend, cases, min(args.pairs, 4))
    if sab.get("not_run"):
        sab = {"abortado": {"not_run": True, "detected": False, "harness": sab["harness"]}}
        ok = False
    entry["sabotage"] = sab
    for clave, res in entry["sabotage"].items():
        print(f"  sabotaje {clave}: detectado={res.get('detected')} "
              f"(corpus {res.get('corpus_failures')}, diferencial "
              f"{res.get('difftest_diffs')}, arnés {len(res.get('harness', []))})", flush=True)

    piernas = [entry["corpus"], entry["difftest"], entry["does_the_work"]]
    if "difftest_str" in entry:
        piernas.append(entry["difftest_str"])
    piernas += list(entry["sabotage"].values())
    entry["completado"] = not any(leg.get("not_run") for leg in piernas)
    entry["conformant"] = _gate.es_conforme(entry)
    return entry["conformant"]


def extra_case(ruta: Path) -> dict:
    """Un caso fuera del corpus congelado.

    No hace falta un `.expect.json`: `corpus()` compara el backend contra la referencia, no
    contra un `expected`, así que la única pieza que aporta el archivo es el programa.
    """
    return {"name": f"extra_{ruta.stem}", "program": ruta.read_bytes(), "input": [],
            "limits": None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--only", default="")
    parser.add_argument("--extra-case", default="",
                        help="fuente .isy que se corre como caso adicional (no entra al corpus)")
    args = parser.parse_args()
    only = set(filter(None, args.only.split(",")))
    sello = _gate.stamp()
    destino = _gate.EVIDENCE / "backends"
    nombre_recibo = f"gate_{sello}"

    with _gate.captura_stdout() as transcripcion:
        report = {"schema": "isycolang.backend_gate/1", "pairs_per_op": args.pairs,
                  "git_head": _gate.git_head(), **_gate.arbol(),
                  "harness": {"guarda": SCHEMA, "codigos": list(CODES),
                              "capas": ["caso", "pierna", "corrida"]},
                  "registered": sorted(registry()), "backends": {},
                  "generated_utc": sello}
        ok = True
        try:
            cases = load_all(ROOT)
            if args.extra_case:
                ruta = Path(args.extra_case)
                fuente = ruta.read_bytes()
                cases = cases + [extra_case(ruta)]
                report["extra_case"] = {"ruta": str(ruta),
                                        "program_sha256": program_sha256(fuente)}
                destino.mkdir(parents=True, exist_ok=True)
                copia = destino / f"{nombre_recibo}_extra_case.isy"
                if copia.exists():
                    raise FileExistsError(f"{copia} ya existe: una ruta de evidencia reutilizada")
                copia.write_bytes(fuente)
            todos = available()
            for nombre, backend in todos.items():
                report["backends"][nombre] = esqueleto(
                    nombre, backend, backend.toolchain() or "?",
                    seleccionado=not only or nombre in only)
            for nombre, backend in todos.items():
                if only and nombre not in only:
                    continue
                print(f"[{nombre}] {backend.toolchain()}", flush=True)
                ok &= correr_backend(report, backend, cases, args)
        except Exception as exc:                     # noqa: BLE001 — capa 3: abortar también sella
            report["abortado"] = {"exception": type(exc).__name__, "excerpt": str(exc)[:400],
                                  "traceback": traceback.format_exc()[-2000:]}
            ok = False
            print(f"ABORTADO: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
        report["missing_toolchains"] = sorted(set(registry()) - set(available()))
        conformes = all(b["conformant"] for b in report["backends"].values()
                        if b.get("seleccionado", True))
        report["verdict"] = ("PASS" if ok and conformes and report["backends"]
                             and not report.get("abortado") else "FAIL")
        try:
            recibo = _gate.sellar(report, transcripcion.texto, destino, nombre_recibo)
        except FileExistsError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(json.dumps({"out": recibo["out"], "verdict": report["verdict"],
                          "sha256": recibo["sha256"], "sumados": recibo["sumados"]}))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
