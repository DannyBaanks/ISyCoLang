"""`isyco/versions.py`: un solo sitio fija las versiones y sus familias de reglas.

El segundo test es el que evita la recaída que midió
`spec/CORE_v0.5_propuesta.md` §7: diez comparaciones literales repartidas en seis
archivos, ninguna activada por una versión mayor.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest import TestCase

from isyco.errors import InvalidProgram
from isyco.versions import SUPPORTED, has

ISYCO = Path(__file__).resolve().parent.parent / "isyco"
LITERAL = re.compile(r'(?:version|header_version\([^)]*\))\s*(?:[!=]=|in\b)\s*[("\']')


class VersionFamily(TestCase):
    def test_una_version_nueva_trae_las_anteriores(self):
        for family, first in (("v02", "0.2"), ("v03", "0.3"), ("v04", "0.4"), ("v05", "0.5")):
            self.assertFalse(has("0.1", family), family)
            self.assertTrue(has(first, family), family)
            later = SUPPORTED[SUPPORTED.index(first) + 1:]
            for version in later:
                self.assertTrue(has(version, family), f"{family} en {version}")

    def test_version_no_soportada_no_trae_nada(self):
        for family in ("v02", "v03", "v04", "v05"):
            self.assertFalse(has("9.9", family), family)


class Cabecera(TestCase):
    """La cabecera `0.5` existe y una versión que no está en SUPPORTED sigue siendo SYNTAX.

    Este segundo caso es el que deja pinzado el corpus cuando `322_header_v05` pasa a
    SUPERSEDED.json: la afirmación «una versión desconocida se rechaza» no se pierde.
    """

    def test_0_5_es_valida(self):
        from isyco.interp import run
        self.assertEqual(run(b"isyco 0.5\nfn main() { }\n", [])[0]["status"], "HALTED")

    def test_version_desconocida_es_syntax(self):
        from isyco.interp import load
        with self.assertRaises(InvalidProgram) as exc:
            load(b"isyco 0.6\nfn main() { }\n")
        self.assertEqual(exc.exception.code, "SYNTAX")


class NoHayLiteralesSueltos(TestCase):
    def test_el_frontend_pregunta_al_predicado(self):
        offenders = [f"{path.relative_to(ISYCO.parent)}:{i + 1}: {line.strip()}"
                     for path in sorted(ISYCO.glob("*.py")) if path.name != "versions.py"
                     for i, line in enumerate(path.read_text(encoding="utf-8").splitlines())
                     if LITERAL.search(line)]
        self.assertEqual(offenders, [], "la versión se compara a mano otra vez")
