"""PL-02/PL-04 de la lista de pulido: la evidencia se verifica dentro de la suite.

Antes de este archivo nada corría `sha256sum -c` sobre `evidence/*/SHA256SUMS.txt`
(solo `programs/`, en test_reference.py): la integridad de la evidencia dependía
de que alguien lo corriera a mano. Aquí también se comprueba que las cifras que
README.md declara demostradas siguen siendo las de la evidencia más reciente,
de modo que un gate nuevo con números distintos enrojece la suite en vez de
dejar el README desactualizado en silencio.

Control negativo (sin tocar evidencia real):

    cp -r evidence /tmp/opencode/evidence_control
    f=$(ls /tmp/opencode/evidence_control/conformance/run_*.json | tail -1)
    printf 'X' | dd of="$f" bs=1 seek=10 conv=notrunc
    ISYCO_EVIDENCE_ROOT=/tmp/opencode/evidence_control \\
        python3 -m unittest tests.test_evidence.EvidenceIntegrity -v   # debe fallar
    rm -rf /tmp/opencode/evidence_control
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.backends import registry  # noqa: E402

EVIDENCE = Path(os.environ.get("ISYCO_EVIDENCE_ROOT") or ROOT / "evidence")


def norm(text: str) -> str:
    """`8 484`, `8 484` con espacio duro y `8484` cuentan lo mismo."""
    return re.sub(r"[\s  ]+", "", text)


def latest(folder: str, prefix: str) -> Path:
    """El archivo más reciente por nombre (los timestamps UTC ordenan lexicográficamente)."""
    files = sorted((EVIDENCE / folder).glob(f"{prefix}*.json"))
    if not files:
        raise AssertionError(f"evidence/{folder}: sin archivos {prefix}*.json")
    return files[-1]


def evidence_dirs() -> list[Path]:
    return sorted(p for p in EVIDENCE.iterdir() if p.is_dir())


class EvidenceIntegrity(unittest.TestCase):
    def test_every_dir_has_sums_and_lists_every_file(self):
        self.assertTrue(evidence_dirs(), str(EVIDENCE))
        for d in evidence_dirs():
            sums = d / "SHA256SUMS.txt"
            self.assertTrue(sums.is_file(), f"{d.name}: falta SHA256SUMS.txt")
            listed = {line.split()[1] for line in sums.read_text().splitlines() if line.strip()}
            on_disk = {p.name for p in d.iterdir()
                       if p.is_file() and p.name != "SHA256SUMS.txt"}
            self.assertEqual(listed, on_disk, d.name)

    def test_every_listed_hash_matches(self):
        for d in evidence_dirs():
            sums = d / "SHA256SUMS.txt"
            if not sums.is_file():
                continue  # lo reporta test_every_dir_has_sums_and_lists_every_file
            for line in sums.read_text().splitlines():
                if not line.strip():
                    continue
                digest, name = line.split()
                data = (d / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest,
                                 f"{d.name}/{name}")


class DocsMatchLatestEvidence(unittest.TestCase):
    """README.md no puede citar cifras que la evidencia más reciente ya no respalda."""

    def readme(self) -> str:
        return norm((ROOT / "README.md").read_text(encoding="utf-8"))

    def test_conformance_figure(self):
        run = json.loads(latest("conformance", "run_").read_text(encoding="utf-8"))
        self.assertEqual(run["passed"], run["total"], "la última corrida no es 100%")
        self.assertIn(norm(f"{run['passed']}/{run['total']}"), self.readme())

    def test_ir_figure(self):
        gate = json.loads(latest("ir", "gate_").read_text(encoding="utf-8"))
        self.assertEqual(gate["equal"], gate["comparisons"], "el último gate IR no es 100%")
        self.assertIn(norm(f"{gate['equal']}/{gate['comparisons']}"), self.readme())

    def test_c_gate_figure(self):
        # F4 no estaba atado a nada: era el único gate cuyo recibo más reciente el
        # README podía dejar atrás sin que la suite se enterara (hallazgo 3 de
        # docs/EVIDENCE_MATRIX.md — F4 con 170 mientras F5 tenía 212).
        gate = json.loads(latest("c", "gate_").read_text(encoding="utf-8"))
        self.assertEqual(gate["verdict"], "PASS", "el último gate de C no es PASS")
        self.assertTrue(gate["corpus"], "evidence/c: el gate no cubrió ninguna combinación")
        readme = self.readme()
        for combo, entrada in sorted(gate["corpus"].items()):
            self.assertEqual(entrada["failures"], [], f"C {combo}: fallos")
            self.assertEqual(entrada["unsupported"], [], f"C {combo}: UNSUPPORTED sin dominio")
            self.assertEqual(entrada["expected_vs_reference_ok"], entrada["cases"],
                             f"C {combo}: expected ↔ referencia incompleto")
            self.assertEqual(entrada["reference_vs_backend_ok"], entrada["cases"],
                             f"C {combo}: referencia ↔ binario incompleto")
            self.assertIn(norm(f"sobre los {entrada['cases']}"), readme,
                          f"C {combo}: el README no cita la población {entrada['cases']} "
                          f"del gate más reciente")
        for combo, entrada in sorted(gate["difftest"].items()):
            self.assertEqual(entrada["diff_count"], 0, f"C {combo}: diferencial con diferencias")
        for nombre, entrada in sorted(gate["sabotage"].items()):
            self.assertTrue(entrada["detected"], f"el sabotaje {nombre} no se detecta")

    def test_backend_figures(self):
        # `--only X` escribe un gate parcial: cada backend se ata a su entrada
        # más reciente en cualquier gate, no solo al último archivo, para que un
        # gate parcial no deje a los demás sin cifra que los respalde.
        gates = [json.loads(p.read_text(encoding="utf-8"))
                 for p in sorted((EVIDENCE / "backends").glob("gate_*.json"))]
        self.assertTrue(gates, "evidence/backends: sin gates")
        self.assertEqual(gates[-1]["verdict"], "PASS", "el último gate de backends no es PASS")
        newest: dict[str, dict] = {}
        for gate in gates:
            newest.update(gate["backends"])
        self.assertLessEqual(set(registry()), set(newest), "backend registrado sin evidencia")
        readme = self.readme()
        for name, entry in sorted(newest.items()):
            corpus = entry["corpus"]
            # UNSUPPORTED no es fallo: es el dominio declarado (p. ej. cobol con
            # el núcleo numérico y str/struct fuera de alcance). Pero el README
            # debe citar la cifra exacta: si el dominio se encoge en silencio,
            # la suite enrojece en vez de aceptarlo.
            self.assertTrue(entry["conformant"], name)
            self.assertEqual(corpus["failures"], [], name)
            self.assertIn(norm(f"{corpus['passed']}/{corpus['cases']}"), readme, name)
            self.assertEqual(entry["difftest"]["diff_count"], 0, name)
            runs = norm(f"{entry['difftest']['runs']:,}".replace(",", " "))
            self.assertIn(runs, readme,
                          f"README no cita {entry['difftest']['runs']} corridas (backend {name})")
