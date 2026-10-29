"""Módulos de CORE v0.4: identificadores en backends, CLI y sabotaje del enlazador."""
from __future__ import annotations

import itertools
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import modules  # noqa: E402
from isyco.backends.base import fn_ident  # noqa: E402
from isyco.conformance import load_all, run_corpus  # noqa: E402
from isyco.source import Bundle  # noqa: E402

CORPUS = load_all(ROOT)
V04 = ROOT / "programs" / "conformance_v0.4"


class Identifiers(unittest.TestCase):
    def test_plain_names_unchanged(self):
        """v0.1–v0.3 generan el mismo código que antes: `f_<nombre>`."""
        self.assertEqual(fn_ident("main"), "f_main")
        self.assertEqual(fn_ident("a__b"), "f_a__b")

    def test_qualified_names_are_injective(self):
        """P7: nombres con punto que un reemplazo ingenuo (`.` -> `__`) confundiría."""
        names = ["a.b", "a__b", "a.b__c", "a__b.c", "a.b.c", "ab.c", "a.bc", "m_1a1b", "geo.punto.f"]
        idents = [fn_ident(n) for n in names]
        self.assertEqual(len(set(idents)), len(names))
        for a, b in itertools.combinations(names, 2):
            self.assertNotEqual(fn_ident(a), fn_ident(b), (a, b))
        self.assertTrue(all(i.replace("_", "").isalnum() for i in idents))


class Cli(unittest.TestCase):
    def test_runs_main_with_modules_from_any_cwd(self):
        main = V04 / "311_diamond" / "main.isy"
        proc = subprocess.run([sys.executable, "-m", "isyco", "run", str(main)],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual((doc["status"], doc["emits"]), ("HALTED", ["50"]))
        self.assertEqual(set(doc["modules"]), {"a.isy", "b.isy", "c.isy"})

    def test_bundle_reads_nested_modules(self):
        bundle = Bundle.from_path(V04 / "302_nested_path" / "main.isy")
        self.assertIsNotNone(bundle.get("geo/punto.isy"))
        self.assertEqual(bundle.main, "main.isy")


class Sabotage(unittest.TestCase):
    def test_ignoring_pub_is_detected(self):
        """M2: un enlazador que no revisa `pub` debe romper el corpus."""
        original = modules._Linker.resolve

        def no_pub_check(self, name, at, kind):
            if "." in name:
                alias, member = name.split(".", 1)
                if alias in self.aliases:
                    target = self.modules[self.aliases[alias]]
                    if member in getattr(target, kind):
                        return modules.module_prefix(self.aliases[alias]) + member
            return original(self, name, at, kind)

        modules._Linker.resolve = no_pub_check
        try:
            failing = [row["name"] for row in run_corpus(CORPUS) if row["verdict"] != "PASS"]
        finally:
            modules._Linker.resolve = original
        self.assertTrue({"304_private_fn", "305_private_struct"} <= set(failing))


if __name__ == "__main__":
    unittest.main()
