"""Z2 (CORE v0.5 §7): la cota de anidamiento de una expresión la pone el idioma, no el anfitrión.

Antes de nombrar el número se midieron las fronteras (Z2 en `docs/OPEN_QUESTIONS_P1_P4.md`):
sin guarda, la cadena de paréntesis moría por `RecursionError` en 89 pares con pila limpia y en
62 con 300 frames del llamante encima, y la cadena izquierda de `len(s)` agotaba la pila en el
`deepcopy` del clon de V6 (985 de 999 frames). En los dos casos la señal era `RecursionError`:
sin código, sin número y sin por qué, y la pagaba la referencia normativa (C6 y C8 de
`evidence/z2_guard/`, con la guarda levantada a 200 para que no estorbiera la medición).

La guarda se mide dos veces porque anidar tiene dos caras distintas:

* el **parser** cuenta los niveles que de verdad le bajan frames —paréntesis, argumentos de
  llamada, operadores prefijos—;
* el **checker** mide la cadena de nodos del AST, porque una suma izquierda de k términos se
  construye en un bucle y no hace bajar ni un frame al parser.

El `expected` de cada test está escrito sobre la regla, no copiado de una corrida.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import ast as A                                     # noqa: E402
from isyco.checker import expr_depth                           # noqa: E402
from isyco.errors import InvalidProgram                        # noqa: E402
from isyco.interp import run                                   # noqa: E402
from isyco.ir_interp import compile_ir                         # noqa: E402
from isyco.modules import load_program                         # noqa: E402

N = A.MAX_EXPR_DEPTH
KEYS = ("status", "code", "emits", "return")


def parentesis(pares: int) -> bytes:
    """`pares` anidados: el parser baja un nivel por par, el AST queda en profundidad 1."""
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {'(' * pares}1{')' * pares};\n"
            f"    emit x;\n    return x;\n}}\n").encode()


def cadena(terminos: int) -> bytes:
    """Suma izquierda de k términos: k niveles de AST sin que el parser recursione."""
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {' + '.join(['1'] * terminos)};\n"
            f"    emit x;\n    return x;\n}}\n").encode()


def pelado(terminos: int) -> bytes:
    """La misma cadena sobre un `str` pelado: cota con el clon de V6 puesto."""
    return (f'isyco 0.5\n\nfn cuanto(s: str) -> i64 {{\n'
            f'    return {" + ".join(["len(s)"] * terminos)};\n}}\n\n'
            f'fn main() -> i64 !emit {{\n    emit cuanto("hola");\n'
            f'    return {4 * terminos};\n}}\n').encode()


def resultado(fuente: bytes) -> dict:
    doc, _ = run(fuente, [])
    return {k: doc[k] for k in KEYS}


#: (legal en el borde, un nivel más arriba): las tres caras de la misma cota
BORDES = ((parentesis(N - 1), parentesis(N)),
          (cadena(N), cadena(N + 1)),
          (pelado(N - 1), pelado(N)))


class CotaNombrada(unittest.TestCase):
    """El número es un literal de la spec, no una consecuencia del anfitrión."""

    def test_la_constante_es_un_literal_del_spec(self):
        self.assertEqual(A.MAX_EXPR_DEPTH, 64)

    def test_el_borde_es_exclusivo_por_debajo(self):
        """Único instrumento del off-by-one: `>` y no `>=`. Nivel N se acepta, N+1 no."""
        forlegal, fallos = zip(*BORDES)
        for fuente in forlegal:
            with self.subTest(fuente=fuente[:24]):
                self.assertEqual(resultado(fuente)["status"], "HALTED")
        for fuente in fallos:
            with self.subTest(fuente=fuente[:24]):
                visto = resultado(fuente)
                self.assertEqual(visto["status"], "INVALID_PROGRAM")
                self.assertEqual(visto["code"], "SPEC_LIMIT")
                self.assertEqual((visto["emits"], visto["return"]), ([], None))

    def test_las_tres_caras_llegan_al_mismo_nivel(self):
        """La cota es de niveles de expresión, no de una forma concreta del fuente."""
        niveles = [expr_depth(load_program(parentesis(N - 1)))[0],
                   expr_depth(load_program(cadena(N)))[0],
                   expr_depth(load_program(pelado(N - 1)))[0]]
        self.assertEqual(niveles[1:], [N, N])          # AST: 64 y 64
        self.assertEqual(niveles[0], 1)                 # paréntesis: no son nodos
        compile_ir(parentesis(N - 1))                   # y aun así la guarda del parser la frena


class LaGuardaGanaAlAnfitrion(unittest.TestCase):
    """Con la pila que traen los caminos del paquete, el rechazo es del idioma."""

    def con_frames(self, n: int, f):
        return self.con_frames(n - 1, f) if n else f()

    def test_un_llamante_hondo_sigue_obteniendo_spec_limit(self):
        # Medido (C4 de `tools/z2_guard_probe.py`): la CLI llega al frontend con 6 frames y un
        # test del paquete con 10. Aquí se prueba con 100 —diez veces el margen real— y la señal
        # sigue siendo SPEC_LIMIT.
        for _, fuente in BORDES:
            with self.subTest(fuente=fuente[:24]):
                self.assertEqual(self.con_frames(100, lambda: resultado(fuente))["code"],
                                 "SPEC_LIMIT")

    def test_la_guarda_no_agota_la_pila_que_mide(self):
        hondo = lambda: expr_depth(load_program(cadena(N)))
        self.assertEqual(hondo()[0], N)
        self.assertEqual(self.con_frames(400, hondo)[0], N)


class EsLaGuardaLoQueRechaza(unittest.TestCase):
    """Sabotaje: mover la constante mueve el borde. Si el rechazo viniera de otro lado, no."""

    def test_subir_la_cota_devuelve_la_aceptacion(self):
        with mock.patch.object(A, "MAX_EXPR_DEPTH", 200):
            for _, fuente in BORDES:
                with self.subTest(fuente=fuente[:24]):
                    self.assertEqual(resultado(fuente)["status"], "HALTED")

    def test_bajar_la_cota_rechaza_lo_que_hoy_es_legal(self):
        self.assertEqual(resultado(cadena(6))["status"], "HALTED")
        with mock.patch.object(A, "MAX_EXPR_DEPTH", 5):
            self.assertEqual(resultado(cadena(6))["code"], "SPEC_LIMIT")


class LaPoblacionQuedaDebajo(unittest.TestCase):
    """Tripwire: ningún programa del repo roza la cota; si uno la cruza, esto lo nombra."""

    FUENTES_Z2 = tuple(f"{n}_" for n in range(449, 455))   # viven en la cota: no son población

    def test_toda_fuente_del_repo_cabe_bajo_la_cota(self):
        """Se miden los programas que la spec acepta; los rechazos a propósito no tienen AST."""
        censadas, profunda, donde = 0, 0, ""
        for carpeta in ("conformance", "conformance_v0.2", "conformance_v0.3",
                        "conformance_v0.4", "conformance_v0.5", "dogfood"):
            for ruta in sorted((ROOT / "programs" / carpeta).rglob("*.isy")):
                if ruta.parent.name == "gemelos":
                    continue
                esperado = ruta.with_suffix(".expect.json")
                if esperado.exists() and not self.se_acepta(esperado):
                    continue
                try:
                    hondo, _ = expr_depth(load_program(ruta.read_bytes()))
                except InvalidProgram:
                    continue                    # rechazos a propósito: no tienen AST que medir
                censadas += 1
                self.assertLessEqual(hondo, A.MAX_EXPR_DEPTH, str(ruta))
                if not ruta.name.startswith(self.FUENTES_Z2) and hondo > profunda:
                    profunda, donde = hondo, str(ruta.relative_to(ROOT))
        self.assertGreaterEqual(censadas, 150, "la población censada cambió sin decir nada")
        self.assertLessEqual(profunda, 8, f"la población real se pasó de lo censado: {donde}")

    @staticmethod
    def se_acepta(expect: Path) -> bool:
        return json.loads(expect.read_text())["expected"]["status"] != "INVALID_PROGRAM"


if __name__ == "__main__":
    unittest.main()
