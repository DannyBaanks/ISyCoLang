"""Gate F2.4, ítems 4 y 6 de `spec/CORE_v0.5_propuesta.md` §5, medidos tal como están escritos.

Al revisar el borrador para congelar (2026-11-12) los otros cuatro ítems tenían recibo y
estos dos no, en su forma literal:

- **Ítem 4** pide `programs/dogfood/03_criba.isy` **con cabecera `isyco 0.5`** y que COBOL lo
  ejecute igual que la referencia. Lo que había era el mismo hecho por otro camino (los
  canarios `439`–`442` y los casos numéricos `0.5` del corpus que COBOL pasa), no la criba
  recabezada. **El ítem, como lo escribió la propuesta, decía además «produce `isy-ir/0.1`», y
  eso no es lo que V7 implementó:** la etiqueta del contenedor la sigue poniendo la cabecera
  (`isy-ir/0.2` desde `0.3`) y lo que cambió es que la exigencia se deriva del contenido
  (`features_of` sin `ir0.2`). La sonda mide lo implementado y registra la etiqueta tal cual.
- **Ítem 6** pide `does_the_work` **sobre un caso `for`**. El gate de backends lo corre sobre
  `027_interes`, que no tiene `for`.

Los `expected` están escritos a mano aquí, antes de correr:

- criba con `n = 100`: hay 25 primos hasta 100, el mayor es 97 y mcd(1071, 462) = 21.
- `for` con entradas `1234 5678`: 1234·3 = 3702; + 5678·3 = 17034 → 20736; + 7·3 → 20757.
  Con `10 20`: 30, 90, 111.

Sabotajes (la sonda tiene que poder fallar):

- ítem 4: la criba recabezada con una línea que usa `str` tiene que pedir `ir0.2` y COBOL
  tiene que responder `UNSUPPORTED` — si no, «no pide `ir0.2`» no distingue nada;
- ítem 6: un fuente que lleva las salidas escritas (`emit 3702; emit 20736; emit 20757;`)
  tiene que salir como fuga y con la otra entrada tiene que dar lo mismo — si no, la prueba
  no ve a un backend que no hace el trabajo.

Uso: python3 tools/v05_gate_f24_probe.py [--write]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _gate  # noqa: E402
from isyco.backends import available  # noqa: E402
from isyco.backends.base import features_of  # noqa: E402
from isyco.interp import run  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

SCHEMA = "isyco-v05-gate-f24/1"
COMPARED = ("status", "code", "emits", "return")

CRIBA_ESPERADO = {"status": "HALTED", "code": None, "emits": ["25", "97", "21"], "return": "97"}

FOR_FUENTE = b"""isyco 0.5
fn main(a: i64, b: i64) -> i64 !emit {
    let xs: [i64; 3] = [a, b, 7];
    let total: i64 = 0;
    for x in xs {
        total = total + x * 3;
        emit total;
    }
    return total;
}
"""
FOR_ENTRADA, FOR_ESPERADO = ["1234", "5678"], {
    "status": "HALTED", "code": None, "emits": ["3702", "20736", "20757"], "return": "20757"}
FOR_OTRA, FOR_OTRA_EMITS = ["10", "20"], ["30", "90", "111"]

FOR_TRAMPOSO = b"""isyco 0.5
fn main(a: i64, b: i64) -> i64 !emit {
    let xs: [i64; 3] = [3702, 20736, 20757];
    for x in xs {
        emit x;
    }
    return 20757;
}
"""


def corta(doc: dict) -> dict:
    return {k: doc.get(k) for k in COMPARED}


def criba(version: str, con_str: bool = False) -> bytes:
    texto = (ROOT / "programs" / "dogfood" / "03_criba.isy").read_text(encoding="utf-8")
    assert texto.startswith("isyco 0.4\n")
    texto = f"isyco {version}\n" + texto[len("isyco 0.4\n"):]
    if con_str:
        texto = texto.replace("    emit cantidad;\n",
                              '    let s: str<4> = "hola";\n    emit len(s);\n    emit cantidad;\n')
        assert "hola" in texto
    return texto.encode("utf-8")


def item4(backends: dict) -> dict:
    fuente = criba("0.5")
    modulo = compile_ir(fuente)
    ref = corta(run(fuente, ["100"])[0])
    cobol = corta(backends["cobol"].run(fuente, ["100"])[0])
    saboteada = criba("0.5", con_str=True)
    modulo_s = compile_ir(saboteada)
    cobol_s = corta(backends["cobol"].run(saboteada, ["100"])[0])
    sabotaje = "ir0.2" in features_of(modulo_s) and cobol_s["status"] == "UNSUPPORTED"
    ok = ("ir0.2" not in features_of(modulo)
          and ref == CRIBA_ESPERADO and cobol == CRIBA_ESPERADO and sabotaje)
    return {"schema_ir": modulo["schema"], "features": sorted(features_of(modulo)),
            "esperado_a_mano": CRIBA_ESPERADO, "referencia": ref, "cobol": cobol,
            "etiqueta_que_pedia_la_propuesta": "isy-ir/0.1",
            "sabotaje_con_str": {"schema_ir": modulo_s["schema"],
                                 "features": sorted(features_of(modulo_s)), "cobol": cobol_s,
                                 "detectado": sabotaje},
            "ok": ok}


def hace_el_trabajo(backend, fuente: bytes) -> dict:
    emitido = backend.emit(compile_ir(fuente))
    fugas = [v for v in FOR_ESPERADO["emits"] if v in emitido]
    uno = corta(backend.run(fuente, FOR_ENTRADA)[0])
    otro = backend.run(fuente, FOR_OTRA)[0].get("emits")
    return {"fugas": fugas, "resultado": uno, "otra_entrada_emits": otro,
            "ok": not fugas and uno == FOR_ESPERADO and otro == FOR_OTRA_EMITS}


def item6(backends: dict) -> dict:
    ref = corta(run(FOR_FUENTE, FOR_ENTRADA)[0])
    filas = {nombre: hace_el_trabajo(b, FOR_FUENTE) for nombre, b in backends.items()}
    tramposo = hace_el_trabajo(backends["c"], FOR_TRAMPOSO)
    sabotaje = (bool(tramposo["fugas"]) and tramposo["otra_entrada_emits"] != FOR_OTRA_EMITS
                and not tramposo["ok"])
    return {"esperado_a_mano": FOR_ESPERADO, "otra_entrada": FOR_OTRA,
            "otra_entrada_emits_a_mano": FOR_OTRA_EMITS, "referencia": ref,
            "features": sorted(features_of(compile_ir(FOR_FUENTE))),
            "backends": filas,
            "sabotaje_fuente_tramposo": {"backend": "c", **tramposo, "detectado": sabotaje},
            "ok": ref == FOR_ESPERADO and sabotaje and all(f["ok"] for f in filas.values())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="sella en evidence/v05_gate_f24/")
    args = ap.parse_args(argv)
    stamp, procedencia = _gate.stamp(), _gate.arbol()
    backends = available()
    faltan = sorted({"c", "rust", "zig", "pydecimal", "cobol"} - set(backends))
    lineas = []

    def di(texto):
        print(texto)
        lineas.append(texto)

    if faltan:
        di(f"NO MEDIDO: faltan toolchains {faltan}")
        return 2
    r4, r6 = item4(backends), item6(backends)
    di(f"ítem 4 — criba con cabecera 0.5: etiqueta {r4['schema_ir']}, pide ir0.2: "
       f"{'ir0.2' in r4['features']}, referencia {r4['referencia']['emits']} "
       f"cobol {r4['cobol']['emits']} (a mano {CRIBA_ESPERADO['emits']}); sabotaje con str: "
       f"pide ir0.2: {'ir0.2' in r4['sabotaje_con_str']['features']}, cobol {r4['sabotaje_con_str']['cobol']['status']}"
       f"({r4['sabotaje_con_str']['cobol']['code']}) → {'PASS' if r4['ok'] else 'FAIL'}")
    for nombre, f in r6["backends"].items():
        di(f"ítem 6 — does_the_work sobre un `for`, {nombre}: fugas {f['fugas']}, "
           f"emits {f['resultado']['emits']}, otra entrada {f['otra_entrada_emits']} → "
           f"{'PASS' if f['ok'] else 'FAIL'}")
    t = r6["sabotaje_fuente_tramposo"]
    di(f"ítem 6 — sabotaje (fuente con las salidas escritas): fugas {t['fugas']}, otra entrada "
       f"{t['otra_entrada_emits']} → {'DETECTADO' if t['detectado'] else 'NO DETECTADO'}")
    ok = r4["ok"] and r6["ok"]
    di(f"veredicto: {'PASS' if ok else 'FAIL'} ({procedencia['veredicto_arbol']})")
    documento = {"schema": SCHEMA, "generated_utc": stamp, "git_head": _gate.git_head(),
                 **procedencia,
                 "toolchains": {n: b.toolchain() for n, b in backends.items()},
                 "item_4": r4, "item_6": r6, "verdict": "PASS" if ok else "FAIL",
                 "no_mide": ["los ítems 1, 2, 3 y 5 del gate: están en los recibos de F2–F5 y "
                             "en tests/test_v05_core.py",
                             "ningún anfitrión distinto del que corrió esta sonda"]}
    if args.write:
        res = _gate.sellar(documento, "\n".join(lineas) + "\n",
                           _gate.EVIDENCE / "v05_gate_f24", f"run_{stamp}")
        print(f"sellado: {res['out']} sha256={res['sha256']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
