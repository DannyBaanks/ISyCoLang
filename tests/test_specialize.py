"""V6 (CORE v0.5): la capacidad diferida en parámetros se resuelve en el frontend.

Lo que se comprueba aquí es la forma de la decisión, no solo sus resultados: una
definición con `str` pelado produce tantas copias acotadas como sitios de llamada,
ninguna capacidad «abierta» llega nunca a la IR (no hay centinela 0/-1/None/65536),
los nombres de las copias son inyectivos, y el azúcar no cambia ni un paso del
programa equivalente escrito a mano (el gemelo).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import checker, modules                            # noqa: E402
from isyco.backends.base import fn_ident                      # noqa: E402
from isyco.errors import InvalidProgram                       # noqa: E402
from isyco.interp import run                                  # noqa: E402
from isyco.ir import ty_from_json, ty_to_json                 # noqa: E402
from isyco.ir_interp import compile_ir                        # noqa: E402
from isyco.lexer import decode, tokenize                      # noqa: E402
from isyco.parser import parse                                # noqa: E402
from isyco.specialize import (contextual_slots, is_contextual, make_clone,   # noqa: E402
                              spec_name)
from isyco.types import ContextStrT, MAX_STR, StrT, type_size  # noqa: E402

V05 = ROOT / "programs" / "conformance_v0.5"
KEYS = ("status", "code", "emits", "return", "steps")
COMPARED = ("status", "code", "emits", "return")


def tipos_de(nodo):
    """Todo tipo str declarado en el módulo IR: la representación tiene que ser acotada."""
    if isinstance(nodo, dict):
        if nodo.get("t") == "str":
            yield ty_from_json(nodo)
        for valor in nodo.values():
            yield from tipos_de(valor)
    elif isinstance(nodo, list):
        for item in nodo:
            yield from tipos_de(item)


def bytes_de(nombre: str) -> bytes:
    return (V05 / f"{nombre}.isy").read_bytes()


def funciones(data: bytes) -> dict:
    return {f["name"]: f for f in compile_ir(data)["functions"]}


def capacidad(fn: dict, parametro: str):
    for local in fn["locals"]:
        if local["name"] == parametro:
            return ty_from_json(local["ty"])
    raise AssertionError(f"{fn['name']} no tiene el local {parametro!r}")


def ejecutar(data: bytes, entradas: list = ()) -> dict:
    resultado, _ = run(data, list(entradas))
    return {k: resultado[k] for k in KEYS}


class ReglaDePosicion(unittest.TestCase):
    """`str` sin capacidad solo existe en un parámetro (V6) o en el retorno (V6-bis),
    y solo a partir de 0.5."""

    def test_parametro_en_0_5_es_capacidad_diferida(self):
        program = parse(tokenize(decode(bytes_de("414_largo_ocho_y_dos"))))
        self.assertEqual(contextual_slots(program.fns["largo"]), [0])
        self.assertTrue(is_contextual(program.fns["largo"]))

    def test_retorno_pelado_es_un_molde_y_no_un_rechazo(self):
        """V6-bis: sin llamada que fije la expectativa no hay copia, y la definición
        desaparece; el programa sigue HALTED en vez de SYNTAX."""
        fuente = "isyco 0.5\nfn f() -> str {\n    return \"a\";\n}\nfn main() {\n}\n"
        self.assertEqual(ejecutar(fuente.encode())["status"], "HALTED")

    def test_pelado_rechazado_fuera_del_parametro_y_del_retorno(self):
        posiciones = {
            "let": "isyco 0.5\nfn main() {\n    let t: str = \"abc\";\n}\n",
            "cast": "isyco 0.5\nfn main() {\n    let t: str<4> = \"abc\" as str;\n}\n",
            "arreglo": "isyco 0.5\nfn main() {\n    let t: [str; 2] = [\"a\", \"b\"];\n}\n",
            "struct": "isyco 0.5\nstruct S {\n    c: str\n}\nfn main() {\n}\n",
        }
        for donde, fuente in posiciones.items():
            with self.subTest(posicion=donde):
                observe = ejecutar(fuente.encode())
                self.assertEqual((observe["status"], observe["code"]),
                                 ("INVALID_PROGRAM", "SYNTAX"))

    def test_pelado_rechazado_en_0_4(self):
        """La cabecera manda: V6/V6-bis no relajan ninguna 0.1–0.4 (propuesta §2)."""
        for version in ("0.3", "0.4"):
            posiciones = {
                "parametro": f"isyco {version}\nfn largo(s: str) -> i64 {{\n    return len(s);\n}}\n"
                             f"fn main() {{\n}}\n",
                "retorno": f"isyco {version}\nfn f() -> str {{\n    return \"a\";\n}}\n"
                           f"fn main() {{\n}}\n",
            }
            for donde, fuente in posiciones.items():
                with self.subTest(version=version, posicion=donde):
                    observe = ejecutar(fuente.encode())
                    self.assertEqual((observe["status"], observe["code"]),
                                     ("INVALID_PROGRAM", "SYNTAX"))


class Especializacion(unittest.TestCase):
    def test_dos_anchos_de_una_sola_definicion(self):
        fn = funciones(bytes_de("414_largo_ocho_y_dos"))
        self.assertIn("largo.8", fn)
        self.assertIn("largo.2", fn)
        self.assertNotIn("largo", fn)              # la definición pelada no se baja
        self.assertEqual(capacidad(fn["largo.8"], "s"), StrT(8))
        self.assertEqual(capacidad(fn["largo.2"], "s"), StrT(2))

    def test_invertir_las_llamadas_no_contamina(self):
        """Canario F: los dos órdenes dan los mismos valores, cada copia ve su ancho."""
        ocho_dos = ejecutar(bytes_de("414_largo_ocho_y_dos"))
        dos_ocho = ejecutar(bytes_de("415_largo_dos_y_ocho"))
        self.assertEqual(ocho_dos["emits"], list(reversed(dos_ocho["emits"])))
        self.assertEqual(sorted(funciones(bytes_de("414_largo_ocho_y_dos"))),
                         sorted(funciones(bytes_de("415_largo_dos_y_ocho"))))

    def test_la_copia_y_el_original_no_comparten_nada(self):
        program = modules.load_program(bytes_de("414_largo_ocho_y_dos"))
        original = program.fns["largo"]
        copia = make_clone(original, "largo.8", (8,), None)
        self.assertIsNot(copia.body, original.body)
        self.assertIsNot(copia.params, original.params)
        self.assertIsInstance(copia.params[0][1], StrT)
        self.assertIsInstance(original.params[0][1], ContextStrT)

    def test_definicion_sin_llamadas_se_descarta(self):
        self.assertEqual(list(funciones(bytes_de("419_definicion_sin_llamadas"))), ["main"])

    def test_recursion_se_instancia_una_vez_por_ancho(self):
        fn = funciones(bytes_de("420_recursion_contextual"))
        self.assertIn("cuenta.4", fn)
        self.assertIn("cuenta.1", fn)
        self.assertEqual(ejecutar(bytes_de("420_recursion_contextual"))["emits"], ["12", "2"])

    def test_propagacion_transitiva(self):
        """`envia` pelado llama a `copia` pelado: las dos cadenas se resuelven solas."""
        fn = funciones(bytes_de("413_encadenar_contextuales"))
        self.assertIn("envia.3", fn)
        self.assertIn("copia.3", fn)
        self.assertEqual(capacidad(fn["copia.8"], "s"), StrT(8))

    def test_dos_parametros_pelados_es_duplicado_en_posicional(self):
        fn = funciones(bytes_de("417_junta_dos_contextuales"))
        clave = [nombre for nombre in fn if nombre.startswith("junta")]
        self.assertEqual(clave, ["junta.3.2"])      # el orden de la clave es el posicional
        self.assertEqual(capacidad(fn["junta.3.2"], "a"), StrT(3))
        self.assertEqual(capacidad(fn["junta.3.2"], "b"), StrT(2))


class FailClosed(unittest.TestCase):
    def test_argumento_que_no_es_str_se_rechaza(self):
        self.assertEqual(ejecutar(bytes_de("427_argumento_no_str"))["status"], "INVALID_PROGRAM")
        self.assertEqual(ejecutar(bytes_de("427_argumento_no_str"))["code"], "TYPE_MISMATCH")

    def test_main_pelado_no_se_le_inventa_capacidad(self):
        self.assertEqual(ejecutar(bytes_de("424_main_contextual"))["code"], "TYPE_MISMATCH")

    def test_capacidad_que_el_cuerpo_no_acepta_es_estatico(self):
        """422: `let t: str<4> = s` con s instanciado en str<5> se rechaza antes de correr."""
        self.assertEqual(ejecutar(bytes_de("422_ancho_insuficiente_estatico"))["status"],
                         "INVALID_PROGRAM")

    def test_el_desborda_es_error_nunca_truncado(self):
        """418: 8 + 16 bytes en str<16> termina en ERROR(OVERFLOW) con cero salidas."""
        observe = ejecutar(bytes_de("418_junta_desborda"))
        self.assertEqual((observe["status"], observe["code"], observe["emits"]),
                         ("ERROR", "OVERFLOW", []))

    def test_contextual_nunca_llega_a_medirse_ni_bajarse(self):
        for fun in (type_size, ty_to_json):
            with self.subTest(funcion=fun.__name__):
                with self.assertRaises(AssertionError):
                    fun(ContextStrT())


class Nombres(unittest.TestCase):
    def test_espejo_de_representacion(self):
        self.assertEqual(str(ContextStrT()), "str")
        self.assertEqual(str(StrT(8)), "str<8>")

    def test_espejo_del_nombre(self):
        self.assertEqual(spec_name("pad", (8,), None), "pad.8")
        self.assertEqual(spec_name("geo.pad", (8, 16), None), "geo.pad.8.16")
        self.assertEqual(spec_name("pad", (8,), 16), "pad.8.r16")

    def test_inyectivo_entre_resoluciones(self):
        """Para una misma base, dos resoluciones distintas nunca comparten nombre.

        La base nunca termina en un segmento numérico (`test_un_fuente_no_puede_imitar_
        una_clave` y el prefijo de módulo), así que la secuencia de segmentos se lee
        sola: `pad.1.23` solo puede salir de (pad, [1, 23])."""
        bases = ("pad", "geo.pad", "punto1.pad", "textlib.pad")
        claves = [(b, w, r) for b in bases
                  for w, r in (((8,), None), ((1, 23), None), ((12, 3), None), ((123,), None),
                               ((2, 3), 1), ((23,), 1), ((2, 3), None))]
        ident = [fn_ident(spec_name(n, w, r)) for n, w, r in claves]
        self.assertEqual(len(set(ident)), len(claves), ident)
        self.assertEqual(len(set(spec_name(n, w, r) for n, w, r in claves)), len(claves))

    def test_un_fuente_no_puede_imitar_una_clave(self):
        """La clave añade segmentos numéricos; un nombre fuente no puede empezar en dígito."""
        with self.assertRaises(InvalidProgram):
            parse(tokenize(decode(b"isyco 0.5\nfn 8() {\n}\nfn main() {\n}\n")))


class NingunCentinela(unittest.TestCase):
    """Ninguna capacidad abierta se codifica como entero: 0, -1, None ni MAX son trampa."""

    def test_todas_las_capacidades_de_la_ir_estan_acotadas(self):
        for nombre in ("411_pad_dos_anchos", "413_encadenar_contextuales",
                       "417_junta_dos_contextuales", "420_recursion_contextual",
                       "423_ancho_grande_doble", "429_retorno_pelado_dos_expectativas",
                       "435_transmision_pelado_a_pelado", "438_retorno_pelado_desde_stdin"):
            modulo = compile_ir(bytes_de(nombre))
            for ty in tipos_de(modulo):
                with self.subTest(caso=nombre, ty=str(ty)):
                    self.assertIsInstance(ty, StrT)
                    self.assertTrue(1 <= ty.n <= MAX_STR)

    def test_sin_capacidades_nulas_en_los_locales(self):
        for nombre in ("411_pad_dos_anchos", "423_ancho_grande_doble"):
            for fn in funciones(bytes_de(nombre)).values():
                for local in fn["locals"]:
                    ty = ty_from_json(local["ty"])
                    with self.subTest(caso=nombre, fn=fn["name"], local=local["name"]):
                        if isinstance(ty, StrT):
                            self.assertGreaterEqual(ty.n, 1)


class Gemelo(unittest.TestCase):
    """El azúcar no cambia la semántica: el mismo programa con el ancho escrito a mano
    da el mismo resultado y el mismo número de pasos."""

    GEMELO_411 = (
        "isyco 0.4\n"
        "fn pad2(s: str<2>, n: i64, c: str<1>) -> str<32> {\n"
        "    let out: str<32> = s;\n    let k: i64 = len(s);\n"
        "    while k < n {\n        out = out + c;\n        k = k + 1;\n    }\n"
        "    return out;\n}\n"
        "fn pad7(s: str<7>, n: i64, c: str<1>) -> str<32> {\n"
        "    let out: str<32> = s;\n    let k: i64 = len(s);\n"
        "    while k < n {\n        out = out + c;\n        k = k + 1;\n    }\n"
        "    return out;\n}\n"
        'fn main() !emit {\n    emit pad2("hi", 5, "-");\n    emit pad7("unohola", 9, "!");\n}\n'
    ).encode()

    GEMELO_423 = (
        "isyco 0.4\n"
        "fn doble8(s: str<8>) -> str<64> {\n    let r: str<64> = s + s;\n    return r;\n}\n"
        "fn doble64(s: str<64>) -> str<64> {\n    let r: str<64> = s + s;\n    return r;\n}\n"
        'fn main() !emit {\n    let base: str<8> = "abcdefgh";\n'
        "    emit doble64(doble8(base));\n}\n"
    ).encode()

    def test_gemelos_mismo_resultado_y_mismos_pasos(self):
        parejas = {"411_pad_dos_anchos": self.GEMELO_411, "423_ancho_grande_doble": self.GEMELO_423}
        for nombre, gemelo in parejas.items():
            with self.subTest(caso=nombre):
                self.assertEqual(ejecutar(bytes_de(nombre)), ejecutar(gemelo))

    def test_el_gemelo_no_es_igual_a_una_sola_capacidad_fija(self):
        """Una sola definición con un ancho fijo NO sirve para dos anchos: por eso V6.

        El programa equivalente con `s: str<2>` se rechaza antes de correr, y el error
        es el más preciso que existe: el literal de 8 bytes no cabe en str<2>."""
        data = (V05 / "414_largo_ocho_y_dos.isy").read_text().replace(
            "fn largo(s: str)", "fn largo(s: str<2>)").replace("isyco 0.5", "isyco 0.4")
        observe = ejecutar(data.encode())
        self.assertEqual((observe["status"], observe["code"]),
                         ("INVALID_PROGRAM", "LITERAL_OUT_OF_RANGE"))


class RetornoPelado(unittest.TestCase):
    """V6-bis: `-> str` se resuelve con la capacidad esperada en el sitio de llamada.

    La clave de la copia lleva las dos orillas —capacidades de los argumentos y del
    retorno—, así que dos expectativas distintas conviven como dos copias. Una posición
    sin expectativa no tiene ancho por defecto: se rechaza, nunca se asume MAX_STR.
    """

    def test_dos_expectativas_son_dos_copias(self):
        fns = funciones(bytes_de("429_retorno_pelado_dos_expectativas"))
        self.assertEqual(set(fns), {"main", "doble.4.r8", "doble.2.r4"})
        self.assertEqual(ty_from_json(fns["doble.4.r8"]["ret"]), StrT(8))
        self.assertEqual(ty_from_json(fns["doble.2.r4"]["ret"]), StrT(4))
        self.assertEqual(ty_from_json(fns["doble.2.r4"]["locals"][0]["ty"]), StrT(2))

    def test_la_clave_lleva_las_dos_orillas(self):
        """El ancho del parámetro viene de stdin y el del retorno del `let`."""
        self.assertEqual(set(funciones(bytes_de("438_retorno_pelado_desde_stdin"))),
                         {"main", "doble.8.r16"})

    def test_transmision_de_expectativa(self):
        self.assertEqual(set(funciones(bytes_de("435_transmision_pelado_a_pelado"))),
                         {"main", "eco.4.r8", "doble.4.r8"})

    def test_desborde_es_overflow_y_no_emite(self):
        obs = ejecutar(bytes_de("430_retorno_pelado_desborda"))
        self.assertEqual((obs["status"], obs["code"], obs["emits"]),
                         ("ERROR", "OVERFLOW", []))

    def test_sin_expectativa_no_hay_ancho_por_defecto(self):
        for nombre in ("432_llamado_como_sentencia", "433_dentro_de_emit"):
            obs = ejecutar(bytes_de(nombre))
            with self.subTest(caso=nombre):
                self.assertEqual((obs["status"], obs["code"]),
                                 ("INVALID_PROGRAM", "TYPE_MISMATCH"))

    def test_el_ciclo_expectativa_parametro_pelado_se_rechaza(self):
        obs = ejecutar(bytes_de("434_expectativa_por_parametro_pelado"))
        self.assertEqual((obs["status"], obs["code"]), ("INVALID_PROGRAM", "TYPE_MISMATCH"))

    def test_estatico_mas_grande_que_la_expectativa(self):
        obs = ejecutar(bytes_de("431_expectativa_mas_chica"))
        self.assertEqual((obs["status"], obs["code"]), ("INVALID_PROGRAM", "TYPE_MISMATCH"))

    def test_main_y_la_cabecera_v04(self):
        esperado = {"436_retorno_pelado_en_main": "TYPE_MISMATCH",
                    "437_retorno_pelado_en_v04": "SYNTAX"}
        for nombre, codigo in esperado.items():
            obs = ejecutar(bytes_de(nombre))
            with self.subTest(caso=nombre):
                self.assertEqual((obs["status"], obs["code"]), ("INVALID_PROGRAM", codigo))

    def test_un_cast_fija_la_expectativa(self):
        data = (
            "isyco 0.5\n"
            "fn doble(s: str) -> str {\n    return s + s;\n}\n"
            'fn main() !emit {\n    emit doble("ab") as str<8>;\n}\n'
        ).encode()
        obs = ejecutar(data)
        self.assertEqual((obs["status"], obs["emits"]), ("HALTED", ["abab"]))

    def test_el_gemelo_escrito_a_mano_cuesta_dos_funciones(self):
        """Misma forma (let + emit) y mismo resultado con anchos fijos: el azúcar no
        añade pasos, solo evita escribir una definición por ancho."""
        gemelo = (
            "isyco 0.4\n"
            "fn doble4(s: str<4>) -> str<8> {\n    return s + s;\n}\n"
            "fn doble2(s: str<2>) -> str<4> {\n    return s + s;\n}\n"
            'fn main() !emit {\n'
            '    let ocho: str<8> = doble4("abcd");\n    emit ocho;\n'
            '    let cuatro: str<4> = doble2("ab");\n    emit cuatro;\n}\n'
        ).encode()
        self.assertEqual(ejecutar(gemelo),
                         ejecutar(bytes_de("429_retorno_pelado_dos_expectativas")))
