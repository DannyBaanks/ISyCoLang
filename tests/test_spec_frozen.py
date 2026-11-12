"""Los núcleos congelados no se editan: `spec/SHA256SUMS.txt` se verifica en cada corrida.

Antes de este archivo el sello de `spec/` solo valía si alguien corría `sha256sum -c` a mano.
"""
import hashlib
import unittest
from pathlib import Path

from isyco.versions import SUPPORTED

SPEC = Path(__file__).resolve().parent.parent / "spec"
CONGELADOS = ("CORE.md", "CORE_v0.2.md", "CORE_v0.3.md", "CORE_v0.4.md", "CORE_v0.5.md")


class SpecCongelada(unittest.TestCase):
    def sellos(self) -> dict:
        lineas = (SPEC / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        return {nombre: sha for sha, nombre in (linea.split() for linea in lineas if linea)}

    def test_cada_nucleo_coincide_con_su_sello(self):
        for nombre, sha in self.sellos().items():
            real = hashlib.sha256((SPEC / nombre).read_bytes()).hexdigest()
            self.assertEqual(real, sha, f"{nombre} cambió después de congelarse")

    def test_estan_los_cinco_y_ninguno_mas(self):
        self.assertEqual(tuple(self.sellos()), CONGELADOS)

    def test_hay_un_nucleo_por_version_admitida(self):
        self.assertEqual(len(CONGELADOS), len(SUPPORTED))

    def test_cada_nucleo_dice_frozen(self):
        for nombre, version in zip(CONGELADOS, SUPPORTED):
            cabeza = (SPEC / nombre).read_text(encoding="utf-8")[:600]
            self.assertIn(f"`FROZEN v{version}`", cabeza, nombre)


if __name__ == "__main__":
    unittest.main()
