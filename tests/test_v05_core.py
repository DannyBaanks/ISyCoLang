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

N1 (CORE v0.5 §4.4, adoptada el 2026-11-01): el mismo azúcar recorre un lugar de tipo `str` —
`len(s)` vueltas con variable `u8` copia, y la cota es la longitud del valor, no la capacidad—.
Casos `444`–`446` con sus gemelos en `GEMELOS` y su forma propia en `ForSobreStr`.
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


#: número -> forma larga del `for`. `403`, `404` y `405` corren HOY con cabecera `0.4` y son
#: la predicción medida de los `steps`; el de 402 está aquí porque el corpus congeló solo
#: los gemelos que ya se habían medido el 2026-10-30. Los tres de N1 (`444`–`446`) se
#: escribieron a mano el 2026-11-01 desde la regla de §4.4: `444` y `446` van en `0.4`
#: porque `len` de un `str` y `s[i]` son de v0.3, y `445` en `0.5` porque el `str` pelado es V6.
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
    "444": ("archivo", "gemelos/444_while.isy"),
    "445": ("archivo", "gemelos/445_while.isy"),
    "446": ("archivo", "gemelos/446_while.isy"),
}

#: pasos de los gemelos medidos con la forma larga a mano: gate F2.4, ítem 2
PASOS_EXIGIDOS = {"403": 23, "404": 38, "405": 20, "444": 22, "445": 27, "446": 22}


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


def traza_de(codigo: bytes, entrada: list | None, indice_sintetico: bool = False) -> list[str]:
    """Traza `stmt` sin posiciones, que es lo que el gate F2.4 ítem 2 compara línea a línea.

    Con `indice_sintetico` el índice del `for` se renombra al nombre que usa el gemelo: [P1]
    dice que el `at` de las sentencias generadas y el nombre elegido por el parser no forman
    parte del claim — lo que tiene que coincidir es la secuencia de eventos.
    """
    _, filas = run(codigo, entrada or [], None, trace="stmt")
    out = []
    for fila in filas:
        texto = json.dumps({k: v for k, v in fila.items() if k != "at"},
                           sort_keys=True, ensure_ascii=False, default=str)
        if indice_sintetico:
            for n in range(4):
                texto = texto.replace(f"foridx{n}", "i")
        out.append(texto)
    return out


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

    def test_la_traza_stmt_es_la_traza_del_gemelo(self):
        """La cola del ítem 2 del gate: no solo los pasos, la traza `stmt` evento por evento.

        Medido: 17, 22, 35 y 19 filas idénticas en `402`, `403`, `404` y `405`, una vez fuera
        las posiciones y con el índice sintético llamado como el gemelo ([P1]). Con los tres
        gemelos de N1, medidos el 2026-11-01: 21, 26 y 21 filas en `444`, `445` y `446`.
        """
        for numero in GEMELOS:
            case = caso(numero)
            with self.subTest(caso=case["name"]):
                azucar = traza_de(case["program"], case["input"], indice_sintetico=True)
                gemelo = traza_de(fuente_gemelo(numero), case["input"])
                self.assertGreater(len(azucar), 0, "un trazo vacío sería un pase vacuo")
                self.assertEqual(azucar, gemelo, "la secuencia de eventos no es la del gemelo")

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
        for numero in ("402", "403", "404", "405", "444", "445", "446"):
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


class ForSobreStr(unittest.TestCase):
    """N1 (CORE v0.5 §4.4, adoptada el 2026-11-01): `for c in s` sobre un `str`.

    Es la misma fórmula del azúcar V2 con un lugar de `str`: `len(s)` vueltas y variable `u8`
    copia. No es una operación nueva —`len(s)` y `s[i]` son de v0.3—, así que la igualdad de
    pasos, traza e IR con el gemelo la cubren los tests de `ForAzucar`, que iteran `GEMELOS`.
    Lo que se fija aquí es la forma propia del `str`: la cota es la LONGITUD del valor y no la
    capacidad declarada, la variable es `u8` y copia, y el lugar puede ser un campo, un `str`
    pelado de V6 o un arreglo de cadenas. Los números están medidos el 2026-11-01.
    """

    def fuente(self, capacidad: int) -> str:
        return ('isyco 0.5\nfn main() -> i64 !emit {\n'
                f'    let s: str<{capacidad}> = "hola";\n'
                '    for c in s { emit c; }\n    return len(s);\n}\n')

    def test_los_tres_casos_coinciden_con_su_expected(self):
        """El expected de `444`–`446` está transcrito de la regla, no del stdout."""
        esperados = {"444": {"status": "HALTED", "code": None,
                             "emits": ["104", "111", "108", "97"], "return": "4"},
                     "445": {"status": "HALTED", "code": None,
                             "emits": ["109", "117", "110", "100", "111"], "return": "5"},
                     "446": {"status": "HALTED", "code": None,
                             "emits": ["65", "65", "65", "97"], "return": "3"}}
        for numero, esperado in esperados.items():
            case = caso(numero)
            with self.subTest(caso=case["name"]):
                self.assertEqual({k: ejecuta(case["program"], case["input"])[k]
                                  for k in COMPARED}, esperado, case["name"])
                self.assertEqual(case["expected"], esperado, "el expected se movió")

    def test_la_cota_es_la_longitud_no_la_capacidad(self):
        """El corazón de N1: con `"hola"`, `str<4>`, `str<8>` y `str<16>` dan los mismos 4 bytes."""
        for capacidad in (4, 8, 16):
            with self.subTest(capacidad=capacidad):
                self.assertEqual(clave(self.fuente(capacidad)),
                                 {"status": "HALTED", "code": None,
                                  "emits": ["104", "111", "108", "97"],
                                  "return": "4", "steps": 22})

    def test_la_cadena_vacia_no_da_vueltas(self):
        got = clave('isyco 0.5\nfn main() -> i64 !emit {\n    let s: str<1> = "";\n'
                    '    for c in s { emit c; }\n    return len(s);\n}\n')
        self.assertEqual((got["status"], got["emits"], got["return"], got["steps"]),
                         ("HALTED", [], "0", 6))

    def test_la_variable_es_u8(self):
        """`c` es `u8`: sumarla a un `i64` sin cast es `TYPE_MISMATCH`; con `as i64` cierra 420."""
        codigo = ('isyco 0.5\nfn main() -> i64 {\n    let s: str<8> = "hola";\n'
                  '    let n: i64 = 0;\n    for c in s { n = n + c; }\n    return n;\n}\n')
        with self.assertRaises(InvalidProgram) as raised:
            compile_ir(codigo.encode())
        self.assertEqual(raised.exception.code, "TYPE_MISMATCH")
        self.assertEqual(ejecuta(codigo.replace("n + c", "n + (c as i64)").encode())["return"],
                         "420")

    def test_es_copia_y_ademas_el_lugar_no_se_puede_escribir(self):
        """Los dos filos de «`c` es copia» (§4.4), medidos el 2026-11-02 01:31 UTC.

        Hacia adentro: escribir `c` deja `s[0]` en `97` — es lo que fija `446`, y se repite
        aquí sin corpus por si el `expected` se moviera. Hacia afuera no hay forma de probar
        el alias inverso porque el lenguaje no lo permite: `s[0] = 66` es `NOT_ASSIGNABLE`
        desde v0.3 (los `str` son inmutables, `spec/CORE_v0.3.md:40`). O sea que la única
        direccionalidad que la regla tiene que garantizar es la primera.
        """
        copia = ('isyco 0.5\nfn main() -> i64 !emit {\n    let s: str<4> = "abc";\n'
                 '    for c in s { c = 65; emit c; }\n    emit s[0];\n    return 0;\n}\n')
        got = clave(copia)
        self.assertEqual((got["emits"], got["steps"]), (["65", "65", "65", "97"], 22))
        alias = ('isyco 0.5\nfn main() -> i64 !emit {\n    let s: str<4> = "abc";\n'
                 '    for c in s { s[0] = 66; emit c; }\n    return 0;\n}\n')
        got = ejecuta(alias.encode(), [])
        self.assertEqual((got["status"], got["code"], got["emits"]),
                         ("INVALID_PROGRAM", "NOT_ASSIGNABLE", []))

    def test_la_variable_no_escapa_del_bucle(self):
        codigo = ('isyco 0.5\nfn main() -> i64 {\n    let s: str<4> = "abc";\n'
                  '    for c in s { }\n    return c;\n}\n')
        self.assertEqual(ejecuta(codigo.encode())["code"], "UNKNOWN_NAME")

    def test_el_lugar_puede_ser_un_campo(self):
        got = clave('isyco 0.5\nstruct L { texto: str<6> }\nfn main() -> i64 !emit {\n'
                    '    let l: L = L { texto: "abc" };\n    for c in l.texto { emit c; }\n'
                    '    return len(l.texto);\n}\n')
        self.assertEqual((got["status"], got["emits"], got["return"], got["steps"]),
                         ("HALTED", ["97", "98", "99"], "3", 18))

    def test_arreglo_de_cadenas_anida_los_dos_azucares(self):
        """`for s in ss { for c in s { … } }`: el lugar del interior es un elemento de arreglo."""
        got = clave('isyco 0.5\nfn main() -> i64 !emit {\n'
                    '    let ss: [str<4>; 2] = ["ab", "cde"];\n'
                    '    for s in ss { for c in s { emit c; } }\n    return 0;\n}\n')
        self.assertEqual((got["status"], got["emits"], got["steps"]),
                         ("HALTED", ["97", "98", "99", "100", "101"], 38))

    def test_for_sobre_un_indice_de_str_sigue_sin_ser_lugar(self):
        with self.assertRaises(InvalidProgram) as raised:
            compile_ir(('isyco 0.5\nfn main() -> i64 {\n    let s: str<4> = "abc";\n'
                        '    for c in s[0] { }\n    return 0;\n}\n').encode())
        self.assertEqual(raised.exception.code, "SYNTAX")

    def test_con_cabecera_04_el_for_sobre_str_se_rechaza(self):
        """No regresión: `for` es reservada solo desde 0.5 (V3), también sobre un `str`."""
        with self.assertRaises(InvalidProgram) as raised:
            compile_ir(self.fuente(8).replace("isyco 0.5", "isyco 0.4", 1).encode())
        self.assertEqual(raised.exception.code, "SYNTAX")

    def test_poner_la_capacidad_como_cota_rompe_igual_que_en_el_gemelo(self):
        """Control de la regla: el `while` escrito a mano con `8` en vez de `len(s)` recorre los
        4 bytes y falla en el quinto — así se ve el sabotaje `test_len_de_str_se_hace_estatico`."""
        cap = ('isyco 0.4\nfn main() -> i64 !emit {\n    let s: str<8> = "hola";\n'
               '    let i: i64 = -1;\n    while i + 1 < 8 { i = i + 1; let c: u8 = s[i];'
               ' emit c; }\n    return len(s);\n}\n')
        got = ejecuta(cap.encode(), [])
        self.assertEqual((got["status"], got["code"], got["emits"], got["steps"]),
                         ("ERROR", "INDEX_OUT_OF_BOUNDS", ["104", "111", "108", "97"], 23))
        suelto = ejecuta(('isyco 0.5\nfn main() -> i64 !emit {\n    let s: str<8> = "hola";\n'
                          '    emit s[7];\n    return 0;\n}\n').encode(), [])
        self.assertEqual((suelto["status"], suelto["code"], suelto["steps"]),
                         ("ERROR", "INDEX_OUT_OF_BOUNDS", 3))

    def test_cobol_rechaza_los_tres_por_contenido_no_por_el_for(self):
        """El UNSUPPORTED de N1 es la regla de V7: a COBOL le falta `str`, no el azúcar."""
        if "cobol" not in AVAILABLE:
            self.skipTest("no hay cobc")
        for numero in ("444", "445", "446"):
            case = caso(numero)
            gemelo = fuente_gemelo(numero)
            faltan = missing_features(AVAILABLE["cobol"], case["program"])
            with self.subTest(caso=case["name"]):
                self.assertEqual(faltan, ["ir0.2", "str"])
                self.assertEqual(faltan, missing_features(AVAILABLE["cobol"], gemelo),
                                 "el azúcar exige un átomo que el gemelo no exige")
                got, _ = AVAILABLE["cobol"].run(case["program"], case["input"],
                                                case.get("limits"))
                self.assertEqual((got["status"], got["code"]),
                                 ("UNSUPPORTED", ",".join(faltan)))


if __name__ == "__main__":
    unittest.main()
