"""V1 (CORE v0.5): `len` de un arreglo lo resuelve el frontend, y la IR no se entera.

Lo que se comprueba es la forma de la decisión, no solo el resultado: `len(a)` con
`a: [T; N]` se reemplaza por el entero `N` en el AST, así que no hay nodo `len` nuevo en
la IR, ninguna capacidad nueva en `features_of`, y el programa gasta exactamente los
mismos pasos que su gemelo escrito a mano (`spec/CORE_v0.5_propuesta.md` §2 V1). `len(s)`
de v0.3 sigue siendo una operación, y en 0.1–0.4 `len` de un arreglo sigue siendo
`TYPE_MISMATCH`: ningún programa existente cambia de significado.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends import available  # noqa: E402
from isyco.backends.base import features_of  # noqa: E402
from isyco.conformance import COMPARED, load_corpus  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

V05 = ROOT / "programs" / "conformance_v0.5"
KEYS = COMPARED + ("steps",)
AVAILABLE = available()
if os.environ.get("ISYCO_TEST_BACKENDS"):
    AVAILABLE = {k: v for k, v in AVAILABLE.items()
                 if k in os.environ["ISYCO_TEST_BACKENDS"].split(",")}

# `len(a)` como cota del while, con su gemelo literal escrito a mano: misma salida, mismo paso.
SUMA = """isyco {version}
fn suma(a: [i32; 6]) -> i32 {{
    let i: i64 = 0;
    let total: i32 = 0;
    while i < {cota} {{
        total = total + a[i];
        i = i + 1;
    }}
    return total;
}}

fn main() -> i32 {{
    let xs: [i32; 6] = [1, 2, 3, 4, 5, 6];
    return suma(xs);
}}
"""


def resultado(codigo: str) -> dict:
    got, _ = run(codigo.encode(), [], None)
    return got


def clave(codigo: str) -> dict:
    got = resultado(codigo)
    return {k: got[k] for k in KEYS}


def caso(numero: str) -> dict:
    return next(c for c in load_corpus(V05) if c["name"].startswith(f"{numero}_"))


class LenArreglo(unittest.TestCase):
    def test_len_de_arreglo_devuelve_su_capacidad(self):
        for numero, esperado in (("401", {"status": "HALTED", "code": None,
                                          "emits": ["5"], "return": "5"}),
                                 ("406", {"status": "HALTED", "code": None,
                                          "emits": [], "return": "21"})):
            case = caso(numero)
            got, _ = run(case["program"], case["input"], case.get("limits"))
            with self.subTest(caso=case["name"]):
                self.assertEqual({k: got[k] for k in COMPARED}, esperado, case["name"])
                self.assertEqual(case["expected"], esperado, "el expected se movió")

    def test_es_estatico_no_cuenta_paso(self):
        """El gemelo con el 6 escrito a mano da exactamente los mismos pasos (medido)."""
        con_len = clave(SUMA.format(version="0.5", cota="len(a)"))
        literal = clave(SUMA.format(version="0.5", cota="6"))
        self.assertEqual(con_len, literal)

    def test_la_ir_no_lleva_nodo_len_de_arreglo(self):
        """El `len` desaparece del AST antes de bajar: la IR lleva un `const`, no un `len`."""
        modulo = compile_ir(caso("401")["program"])
        cuanto = next(f for f in modulo["functions"] if f["name"] == "cuanto")
        retorno = cuanto["body"][0]["value"]
        self.assertEqual((retorno["k"], retorno["v"]), ("const", "5"))
        self.assertEqual(retorno["ty"], {"t": "int", "bits": 64, "signed": True, "ovf": "trap"})
        self.assertNotIn('"k": "len"', json.dumps(modulo))

    def test_len_de_arreglo_no_pide_ninguna_capacidad_nueva(self):
        """V1 es frontend puro: `features_of` no gana átomo con los canarios."""
        for numero in ("401", "406"):
            f = features_of(compile_ir(caso(numero)["program"]))
            with self.subTest(caso=numero):
                self.assertNotIn("ir0.2", f)
                self.assertNotIn("emit_array", f)

    def test_len_de_str_sigue_siendo_operacion(self):
        """Lo que no se tocó: `len(s)` de v0.3 §2.4 baja a su nodo y su tipo es i64."""
        codigo = ('isyco 0.3\nfn main() -> i64 {\n    let s: str<8> = "hola";\n'
                  '    return len(s);\n}\n')
        self.assertEqual(resultado(codigo)["return"], "4")
        modulo = compile_ir(codigo.encode())
        main = next(f for f in modulo["functions"] if f["name"] == "main")
        self.assertEqual(main["body"][-1]["value"]["k"], "len")

    def test_no_se_estrecha_solo(self):
        """`len` es i64 (coherencia con `len(s)`); un i8 sigue siendo TYPE_MISMATCH."""
        self.assertEqual(resultado('isyco 0.5\nfn main() -> i64 {\n'
                                   '    let xs: [i64; 3] = [1, 2, 3];\n'
                                   '    let n: i8 = len(xs);\n    return 0;\n}\n')["code"],
                         "TYPE_MISMATCH")

    def test_dentro_de_un_literal_de_struct(self):
        """El reemplazo camina también las tuplas (nombre, expr, at) de un literal de struct."""
        codigo = ('isyco 0.5\nstruct Par { x: i64, ys: [i64; 3] }\n'
                  'fn main() -> i64 !emit {\n    let xs: [i64; 4] = [1, 2, 3, 4];\n'
                  '    let p: Par = Par { x: len(xs), ys: [7, 8, 9] };\n    emit p.x;\n'
                  '    return len(p.ys);\n}\n')
        self.assertEqual(clave(codigo), {"status": "HALTED", "code": None,
                                         "emits": ["4"], "return": "3", "steps": 5})

    def test_arreglo_de_structs_tambien(self):
        codigo = ('isyco 0.5\nstruct Punto { x: i64 }\nfn main() -> i64 {\n'
                  '    let ps: [Punto; 3] = [Punto { x: 1 }, Punto { x: 2 }, Punto { x: 3 }];\n'
                  '    return len(ps);\n}\n')
        self.assertEqual(resultado(codigo)["return"], "3")

    def test_en_versions_anteriores_sigue_rechazado(self):
        """No regresión: el mismo cuerpo con cabecera vieja sigue siendo INVALID_PROGRAM.

        Motos distintos, y medidos: en 0.1/0.2 `len` ni siquiera es palabra clave
        (`KEYWORDS_V03` la trae en 0.3), así que `len(a)` es una llamada desconocida; en
        0.3/0.4 `len` existe pero es de strings, y un arreglo es TYPE_MISMATCH.
        """
        for version, code in (("0.1", "UNKNOWN_NAME"), ("0.2", "UNKNOWN_NAME"),
                              ("0.3", "TYPE_MISMATCH"), ("0.4", "TYPE_MISMATCH")):
            codigo = SUMA.format(version=version, cota="len(a)")
            with self.subTest(version=version):
                with self.assertRaises(InvalidProgram) as raised:
                    compile_ir(codigo.encode())
                self.assertEqual(raised.exception.code, code)

    def test_los_canones_coinciden_en_cada_backend(self):
        """Diferencial de V1: referencia == expected == cada backend instalado, pasos incluidos."""
        for numero in ("401", "406"):
            case = caso(numero)
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            for name, backend in sorted(AVAILABLE.items()):
                got, _ = backend.run(case["program"], case["input"], case.get("limits"))
                with self.subTest(caso=case["name"], backend=name):
                    if got["status"] == "UNSUPPORTED":
                        continue    # dominio declarado del backend, no una diferencia
                    self.assertEqual({k: got[k] for k in KEYS},
                                     {k: ref[k] for k in KEYS}, f"{case['name']} en {name}")
                    self.assertEqual({k: ref[k] for k in COMPARED}, case["expected"],
                                     f"{case['name']} contra el expected escrito a mano")


if __name__ == "__main__":
    unittest.main()
