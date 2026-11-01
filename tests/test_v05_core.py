"""V1 (CORE v0.5): `len` de un arreglo lo resuelve el frontend, y la IR no se entera.

Lo que se comprueba es la forma de la decisión, no solo el resultado: `len(a)` con
`a: [T; N]` se reemplaza por el entero `N` en el AST, así que no hay nodo `len` nuevo en
la IR, ninguna capacidad nueva en `features_of`, y el programa gasta exactamente los
mismos pasos que su gemelo escrito a mano (`spec/CORE_v0.5_propuesta.md` §2 V1). `len(s)`
de v0.3 sigue siendo una operación, y en 0.1–0.4 `len` de un arreglo sigue siendo
`TYPE_MISMATCH`: ningún programa existente cambia de significado.

V2 (CORE v0.5): `for x in a { … }` es azúcar del parser. La comprobación es de forma, no de
resultado: el AST que recibe la referencia es el `while` gemelo escrito a mano, así que la IR
es la misma salvo las posiciones y el nombre del índice sintético, los `steps` son los del
gemelo (23 / 38 / 20, exigidos por el gate F2.4) y `features_of` no gana ningún átomo. `for`
queda reservada solo desde `0.5`; `in` sigue siendo contextual (V3).
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
from isyco.backends.base import features_of, missing_features  # noqa: E402
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


def ejecuta(codigo: bytes, entrada: list | None = None) -> dict:
    got, _ = run(codigo, entrada or [], None)
    return got


def clave(codigo: str | bytes, entrada: list | None = None) -> dict:
    dato = codigo if isinstance(codigo, bytes) else codigo.encode()
    got = ejecuta(dato, entrada)
    return {k: got[k] for k in KEYS}


def caso(numero: str) -> dict:
    return next(c for c in load_corpus(V05) if c["name"].startswith(f"{numero}_"))


#: número -> forma larga del `for`. Los tres archivos corren HOY con cabecera `0.4` y son
#: la predicción medida de los `steps`; el de 402 está aquí porque el corpus congeló solo
#: los gemelos que ya se habían medido el 2026-10-30.
GEMELOS = {
    "402": ("inline", """isyco 0.5

struct Item { nombre: str<8>, precio: dec<8,2> }

fn main(items: [Item; 3]) -> dec<8,2> {
    let total: dec<8,2> = 0.00;
    let i: i64 = -1;
    while i + 1 < len(items) {
        i = i + 1;
        let it: Item = items[i];
        total = total + it.precio;
    }
    return total;
}
"""),
    "403": ("archivo", "gemelos/403_while.isy"),
    "404": ("archivo", "gemelos/404_while_incremento_arriba.isy"),
    "405": ("archivo", "gemelos/405_while.isy"),
}

#: pasos de los gemelos medidos con la forma larga a mano: gate F2.4, ítem 2
PASOS_EXIGIDOS = {"403": 23, "404": 38, "405": 20}


def fuente_gemelo(numero: str) -> bytes:
    modo, texto = GEMELOS[numero]
    return (V05 / texto).read_bytes() if modo == "archivo" else texto.encode("utf-8")


def podar(nodo):
    """IR sin posiciones y sin el nombre de la tabla de locales: queda solo la forma."""
    if isinstance(nodo, dict):
        return {k: podar(v) for k, v in nodo.items()
                if k not in ("at", "source_sha256")
                and not (k == "name" and set(nodo) == {"name", "ty"})}
    if isinstance(nodo, list):
        return [podar(v) for v in nodo]
    return nodo


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


class ForAzucar(unittest.TestCase):
    def test_for_coincide_con_su_expected(self):
        """Los cuatro casos del corpus contra su expected, escrito a mano el 2026-10-30."""
        esperados = {"402": {"status": "HALTED", "code": None, "emits": [], "return": "3.85"},
                     "403": {"status": "HALTED", "code": None, "emits": [], "return": "17"},
                     "404": {"status": "HALTED", "code": None, "emits": ["2", "3", "7"],
                             "return": "3"},
                     "405": {"status": "HALTED", "code": None, "emits": ["1", "3"],
                             "return": "2"}}
        for numero, esperado in esperados.items():
            case = caso(numero)
            with self.subTest(caso=case["name"]):
                self.assertEqual({k: ejecuta(case["program"], case["input"])[k]
                                  for k in COMPARED}, esperado, case["name"])
                self.assertEqual(case["expected"], esperado, "el expected se movió")

    def test_el_for_gasta_los_pasos_del_while_gemelo(self):
        """Misma salida y mismos pasos que la forma larga: el azúcar no es una operación."""
        for numero in GEMELOS:
            case = caso(numero)
            azucar = clave(case["program"], case["input"])
            gemelo = clave(fuente_gemelo(numero), case["input"])
            with self.subTest(caso=case["name"]):
                self.assertEqual(azucar, gemelo, "azúcar y gemelo divergen")
                if numero in PASOS_EXIGIDOS:
                    self.assertEqual(gemelo["steps"], PASOS_EXIGIDOS[numero])

    def test_el_control_negativo_sigue_siendo_negativo(self):
        """El incremento abajo —la forma intuitiva— no es un gemelo: el `continue` salta el
        avance y el bucle se queda girando sobre el 5. Por eso el azúcar incrementa arriba."""
        got = ejecuta((V05 / "gemelos" / "404_while_incremento_abajo.isy").read_bytes(), [])
        self.assertEqual((got["status"], got["code"], got["emits"]),
                         ("LIMIT_REACHED", "max_steps", ["2", "3"]))

    def test_la_ir_del_for_es_la_ir_del_gemelo(self):
        """El azúcar no introduce forma nueva. Este control cazó que construir `-1` con
        `Unary` restaba un nodo `neg` que el `while` escrito a mano no tiene."""
        for numero in GEMELOS:
            with self.subTest(caso=numero):
                self.assertEqual(podar(compile_ir(caso(numero)["program"])),
                                 podar(compile_ir(fuente_gemelo(numero))))

    def test_el_for_no_pide_ninguna_capacidad_nueva(self):
        """V2 es frontend puro: lo que exige el `for` es lo mismo que exige su `while`."""
        for numero in GEMELOS:
            with self.subTest(caso=numero):
                self.assertEqual(features_of(compile_ir(caso(numero)["program"])),
                                 features_of(compile_ir(fuente_gemelo(numero))))

    def test_for_es_reservada_solo_desde_05(self):
        """En 0.4 `for` sigue siendo un nombre normal; en 0.5 ya no se puede declarar."""
        codigo = ("isyco {version}\nfn main() -> i32 {{\n"
                  "    let for: i32 = 5;\n    return for;\n}}\n")
        self.assertEqual(ejecuta(codigo.format(version="0.4").encode())["return"], "5")
        with self.assertRaises(InvalidProgram) as raised:
            compile_ir(codigo.format(version="0.5").encode())
        self.assertEqual(raised.exception.code, "SYNTAX")

    def test_in_sigue_siendo_contextual(self):
        """V3: `in` no se reserva. Aquí es a la vez una variable y el separador del `for`."""
        codigo = ("isyco 0.5\nfn main() -> i32 {\n    let in: i32 = 7;\n"
                  "    let xs: [i32; 2] = [1, 2];\n    for x in xs { in = in + x; }\n"
                  "    return in;\n}\n")
        self.assertEqual(ejecuta(codigo.encode())["return"], "10")

    def test_la_variable_del_for_no_sale_del_bucle(self):
        codigo = ("isyco 0.5\nfn main() -> i32 {\n    let xs: [i32; 2] = [1, 2];\n"
                  "    for x in xs { }\n    return x;\n}\n")
        self.assertEqual(ejecuta(codigo.encode())["code"], "UNKNOWN_NAME")

    def test_dos_for_seguidos_reutilizan_el_nombre(self):
        """El índice sintético es distinto en cada `for`, y `x` muere con su cuerpo."""
        codigo = ("isyco 0.5\nfn main() -> i32 !emit {\n    let xs: [i32; 2] = [1, 2];\n"
                  "    let ys: [i32; 3] = [10, 20, 30];\n    let s: i32 = 0;\n"
                  "    for x in xs { s = s + x; }\n    for x in ys { s = s + x; }\n"
                  "    emit s;\n    return s;\n}\n")
        got = clave(codigo)
        self.assertEqual((got["status"], got["emits"], got["return"]),
                         ("HALTED", ["63"], "63"))

    def test_for_anidado(self):
        codigo = ("isyco 0.5\nfn main() -> i32 {\n    let xs: [i32; 2] = [3, 4];\n"
                  "    let ys: [i32; 2] = [10, 20];\n    let s: i32 = 0;\n"
                  "    for a in xs {\n        for b in ys { s = s + a * b; }\n    }\n"
                  "    return s;\n}\n")
        self.assertEqual(ejecuta(codigo.encode())["return"], "210")

    def test_for_sobre_un_campo(self):
        """El lugar puede estar calificado por un campo: `for n in c.cosas`."""
        codigo = ("isyco 0.5\nstruct Caja { cosas: [i32; 3] }\nfn main() -> i32 {\n"
                  "    let c: Caja = Caja { cosas: [1, 2, 4] };\n    let s: i32 = 0;\n"
                  "    for n in c.cosas { s = s + n; }\n    return s;\n}\n")
        self.assertEqual(ejecuta(codigo.encode())["return"], "7")

    def test_for_no_acepta_una_expresion(self):
        """P2, medido: la cota y el índice evalúan el lugar dos veces, así que se rechaza
        antes de chequear — ni un literal sin tipo esperado, ni una llamada con efectos."""
        literal = ("isyco 0.5\nfn main() -> i32 {\n"
                   "    for x in [1, 2, 3] { }\n    return 0;\n}\n")
        llamada = ("isyco 0.5\nfn xs() -> [i32; 2] { return [1, 2]; }\n"
                   "fn main() -> i32 {\n    for x in xs() { }\n    return 0;\n}\n")
        for nombre, codigo in (("literal", literal), ("llamada", llamada)):
            with self.subTest(forma=nombre):
                with self.assertRaises(InvalidProgram) as raised:
                    compile_ir(codigo.encode())
                self.assertEqual(raised.exception.code, "SYNTAX")

    def test_return_dentro_del_for_vale_lo_que_en_el_while(self):
        """`always_returns` no conoce el `for`: un `return` en el cuerpo no garantiza nada."""
        codigo = ("isyco 0.5\nfn main() -> i32 {\n    let xs: [i32; 2] = [1, 2];\n"
                  "    for x in xs { return x; }\n}\n")
        with self.assertRaises(InvalidProgram) as raised:
            compile_ir(codigo.encode())
        self.assertEqual(raised.exception.code, "MISSING_RETURN")

    def test_break_fuera_del_for_sigue_prohibido(self):
        codigo = "isyco 0.5\nfn main() -> i32 {\n    break;\n    return 0;\n}\n"
        with self.assertRaises(InvalidProgram) as raised:
            compile_ir(codigo.encode())
        self.assertEqual(raised.exception.code, "BAD_LOOP_CONTROL")

    def test_for_en_versions_anteriores_sigue_rechazado(self):
        """No regresión: antes de 0.5 el azúcar no existe y la fuente se rechaza igual."""
        program = caso("403")["program"].decode("utf-8")
        for version in ("0.1", "0.2", "0.3", "0.4"):
            recabezado = program.replace("isyco 0.5", f"isyco {version}", 1).encode()
            with self.subTest(version=version):
                with self.assertRaises(InvalidProgram) as raised:
                    compile_ir(recabezado)
                self.assertEqual(raised.exception.code, "SYNTAX")

    def test_los_canones_coinciden_en_cada_backend(self):
        """Diferencial de V2: referencia == expected == cada backend instalado, pasos incluidos."""
        for numero in ("402", "403", "404", "405"):
            case = caso(numero)
            ref = ejecuta(case["program"], case["input"])
            for name, backend in sorted(AVAILABLE.items()):
                got, _ = backend.run(case["program"], case["input"], case.get("limits"))
                with self.subTest(caso=case["name"], backend=name):
                    if got["status"] == "UNSUPPORTED":
                        continue    # dominio declarado del backend, no una diferencia
                    self.assertEqual({k: got[k] for k in KEYS},
                                     {k: ref[k] for k in KEYS}, f"{case['name']} en {name}")
                    self.assertEqual({k: ref[k] for k in COMPARED}, case["expected"],
                                     f"{case['name']} contra el expected escrito a mano")

    def test_cobol_rechaza_402_por_contenido_no_por_el_for(self):
        """El único UNSUPPORTED de V2 es la regla de V7: a COBOL le falta el contenido
        `str`/`struct`/`ir0.2`, no el azúcar — el gemelo de 402 exige los mismos átomos y
        403/404/405, que no usan `str`, se ejecutan."""
        if "cobol" not in AVAILABLE:
            self.skipTest("no hay cobc")
        case = caso("402")
        faltan = missing_features(AVAILABLE["cobol"], case["program"])
        self.assertEqual(faltan, ["ir0.2", "str", "struct"])
        got, _ = AVAILABLE["cobol"].run(case["program"], case["input"], case.get("limits"))
        self.assertEqual((got["status"], got["code"]), ("UNSUPPORTED", ",".join(faltan)))
        for numero in ("403", "404", "405"):
            otro = caso(numero)
            salida = AVAILABLE["cobol"].run(otro["program"], otro["input"],
                                            otro.get("limits"))[0]
            with self.subTest(caso=otro["name"]):
                self.assertNotEqual(salida["status"], "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
