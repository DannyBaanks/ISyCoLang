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
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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

    def test_backend_figures(self):
        gate = json.loads(latest("backends", "gate_").read_text(encoding="utf-8"))
        self.assertEqual(gate["verdict"], "PASS", "el último gate de backends no es PASS")
        readme = self.readme()
        for name, entry in gate["backends"].items():
            corpus = entry["corpus"]
            self.assertEqual(corpus["passed"], corpus["cases"], name)
            self.assertEqual(entry["difftest"]["diff_count"], 0, name)
            runs = norm(f"{entry['difftest']['runs']:,}".replace(",", " "))
            self.assertIn(runs, readme,
                          f"README no cita {entry['difftest']['runs']} corridas (backend {name})")
