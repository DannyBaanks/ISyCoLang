"""La guarda del arnés: el fallo del instrumento es dato, no abort (hallazgo 13).

Prueba el clasificador (`isyco.harness`), la caché negativa de `Backend.build`, el aborta-y-
sigue del diferencial y el pliegue fail-closed de `tools/_gate.py`. El crash se fabrica aquí,
así que no hace falta un toolchain que reviente de verdad: lo que se comprueba es que una fila
del arnés no puede blanquearse como verde aunque `failures` y `diffs` estén vacíos, que era
exactamente el hueco.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _gate  # noqa: E402
import backend_gate  # noqa: E402
from isyco.backends.base import Backend, ToolchainBuildFailure  # noqa: E402
from isyco.conformance import load_all  # noqa: E402
from isyco.difftest import INT_TYPES, compare, reference  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.harness import DETAIL_CHARS, EXCERPT_CHARS, detalle, fila, intento  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

FUENTE_RECHAZADA = b"isyco 0.1\nfn main(a: i9) { return a; }\n"      # tipo inexistente
ERROR_FALSO = "arnes_falso.txt:1:1: error: muerto a propósito"


def _lanza(exc: BaseException):
    def interior():
        raise exc
    return interior


class FalsoBackend(Backend):
    """Toolchain de mentiras: muere siempre al compilar y lleva la cuenta de invocaciones."""

    name = "arnes_falso"
    extension = ".txt"
    features: frozenset = frozenset()          # sin `str`: la pierna de cadenas no se corre
    sabotages = ("fake_sabotage",)

    def __init__(self, contador):
        self.contador = contador

    def toolchain(self) -> str:
        return "falso 1.0"

    def compile_cmd(self, source, binary, extra_flags):
        self.contador.append(str(source))
        return ["/usr/bin/env", "sh", "-c", f"echo '{ERROR_FALSO}' >&2; exit 1"]

    def run(self, data, inputs, limits=None, trace="none", sabotage=None):
        raise ToolchainBuildFailure(self.name, "c" * 24, ERROR_FALSO)


class Clasificador(unittest.TestCase):
    def test_resultado_normal_no_deja_fila(self):
        res, fr = intento(lambda x: x * 2, 21, fase="t", contexto={"leg": "corpus"})
        self.assertEqual(res, 42)
        self.assertIsNone(fr)

    def test_una_excepcion_del_arnes_es_harness_internal(self):
        res, fr = intento(_lanza(ValueError("el instrumento se cayó")), fase="t",
                          contexto={"leg": "corpus"})
        self.assertIsNone(res)                 # nunca un dict que se parezca a un resultado
        self.assertEqual(fr["code"], "HARNESS_INTERNAL")
        self.assertEqual(fr["exception"], "ValueError")
        self.assertEqual(fr["leg"], "corpus")
        self.assertNotIn("build_key", fr)      # la clave del artefacto solo la pone el toolchain

    def test_el_rechazo_del_frontend_se_propaga(self):
        # Que el idioma rechace un programa no es un fallo del banco de pruebas: tiene que subir.
        with self.assertRaises(InvalidProgram):
            intento(compile_ir, FUENTE_RECHAZADA, fase="t", contexto={"leg": "frontend"})

    def test_toolchain_roto_deja_fila_con_su_clave_de_build(self):
        exc = ToolchainBuildFailure("zig", "7443b5e8e72fb777",
                                    "x.zig:1635:23: error: comptime roto\nlínea de relleno")
        res, fr = intento(_lanza(exc), fase="build", contexto={"leg": "corpus"})
        self.assertIsNone(res)
        self.assertEqual(fr["code"], "TOOLCHAIN_BUILD_FAIL")
        self.assertEqual(fr["build_key"], "7443b5e8e72fb777")
        self.assertEqual(fr["detail"], "x.zig:1635:23: error: comptime roto")
        self.assertEqual(fr["excerpt"].splitlines()[0], "zig: el compilador falló:")

    def test_detalle_toma_la_linea_error_y_la_recorta(self):
        self.assertEqual(detalle("noise\nx.zig:2:3: error: uno\ny.zig:9:9: error: dos"),
                         "x.zig:2:3: error: uno")
        self.assertEqual(len(detalle("x.zig:1:1: error: " + "k" * 400)), DETAIL_CHARS)
        self.assertEqual(detalle("sin esa palabra\núltima línea"), "última línea")
        self.assertEqual(detalle(""), "")

    def test_la_fila_conserva_las_coordenadas_del_contexto(self):
        coordenadas = {"leg": "difftest", "type": "i32", "op": "div", "input": ["7", "6", "5"]}
        fr = fila("HARNESS_INTERNAL", ValueError("boom"), "difftest", coordenadas, 12.34)
        self.assertEqual((fr["leg"], fr["type"], fr["op"], fr["input"]),
                         ("difftest", "i32", "div", ["7", "6", "5"]))
        self.assertEqual(fr["ms"], 12.3)       # décimas, no el crudo del cronómetro
        self.assertEqual(len(fila("HARNESS_INTERNAL", ValueError("z" * (EXCERPT_CHARS + 50)),
                                  "t", None, 0)["excerpt"]), EXCERPT_CHARS)


class CacheNegativa(unittest.TestCase):
    def test_cinco_intentos_sobre_la_mesma_fuente_una_invocacion(self):
        contador: list[str] = []
        backend = FalsoBackend(contador)
        filas = [intento(backend.build, "fuente idéntica", fase="t",
                         contexto={"leg": "corpus"})[1] for _ in range(5)]
        self.assertEqual(len(contador), 1, "el compilador volvió a correr sabiéndose muerto")
        self.assertEqual({f["code"] for f in filas}, {"TOOLCHAIN_BUILD_FAIL"})
        self.assertEqual({f["detail"] for f in filas}, {ERROR_FALSO})
        self.assertEqual(len({f["build_key"] for f in filas}), 1)

    def test_otra_fuente_u_otra_instancia_si_vuelven_al_compilador(self):
        contador: list[str] = []
        backend = FalsoBackend(contador)
        intento(backend.build, "fuente A", fase="t", contexto={"leg": "corpus"})
        intento(backend.build, "fuente B", fase="t", contexto={"leg": "corpus"})
        self.assertEqual(len(contador), 2, "la caché no puede dar por muertas dos fuentes")
        intento(FalsoBackend(contador).build, "fuente A", fase="t", contexto={"leg": "corpus"})
        # Vive en la instancia: este recibo documenta que NO sobrevive a otro proceso del gate.
        self.assertEqual(len(contador), 3)


class Diferencial(unittest.TestCase):
    def test_un_crash_aborta_ese_tipo_y_deja_correr_el_siguiente(self):
        tipos = INT_TYPES[:2]
        vistas: list[int] = []

        def executor(program, inputs):
            if not vistas:                     # el primer caso del primer tipo
                vistas.append(0)
                raise RuntimeError("el arnés se cayó")
            return reference(program, inputs), []

        report = compare(executor, pairs=0, types=tipos)
        self.assertEqual(report["types_aborted"], [str(tipos[0])])
        self.assertEqual(len(report["harness"]), 1)
        fr = report["harness"][0]
        self.assertEqual((fr["code"], fr["leg"], fr["type"]),
                         ("HARNESS_INTERNAL", "difftest", str(tipos[0])))
        for campo in ("op", "input", "program_sha256"):
            self.assertIn(campo, fr, f"la fila no dice {campo}: el crash no es reproducible")
        self.assertGreater(fr["omitted_after"], 0, "hay que decir cuántos casos se perdieron")
        self.assertEqual(report["types"][0]["runs"], 0)
        self.assertGreater(report["types"][1]["runs"], 0, "el tipo siguiente no se corrió")
        # La trampa que deja cerrado el resto del lote: `diffs == []` era verde sobre un crash.
        self.assertEqual(report["diffs"], [])
        self.assertEqual(report["runs"], sum(t["runs"] for t in report["types"]))


class Pliegue(unittest.TestCase):
    def entrada(self) -> dict:
        return {"completado": True, "corpus": {"failures": [], "harness": []},
                "difftest": {"diffs": [], "harness": [], "runs": 100, "diff_count": 0},
                "difftest_str": {"diff_count": 0, "harness": []},
                "does_the_work": {"ok": True, "harness": []},
                "sabotage": {"s": {"detected": True, "harness": []}}}

    def test_conforme_con_todas_las_piernas_limpias(self):
        self.assertTrue(_gate.es_conforme(self.entrada()))

    def test_una_fila_de_arnes_en_cualquier_pierna_vuelve_no_conforme(self):
        sucias = {
            "corpus": lambda e: e["corpus"]["harness"].append({"code": "X"}),
            "difftest": lambda e: e["difftest"]["harness"].append({"code": "X"}),
            "difftest_str": lambda e: e["difftest_str"]["harness"].append({"code": "X"}),
            "does_the_work": lambda e: e["does_the_work"]["harness"].append({"code": "X"}),
            "sabotage": lambda e: e["sabotage"]["s"]["harness"].append({"code": "X"})}
        for nombre, mutar in sorted(sucias.items()):
            e = self.entrada()
            mutar(e)
            self.assertFalse(_gate.es_conforme(e), f"{nombre}: verde sobre un crash")
            self.assertEqual(e["corpus"]["failures"], [])   # ningún crash se volvió fallo
            self.assertEqual(e["difftest"]["diffs"], [])    # ni se escribió en la lista semántica

    def test_pierna_no_corrida_no_es_un_cero(self):
        for pierna in ("corpus", "difftest", "does_the_work", "difftest_str"):
            e = self.entrada()
            e[pierna] = {"not_run": True}
            self.assertFalse(_gate.es_conforme(e), f"{pierna} sin corrida pasó como verde")

    def test_incompleto_o_sabotaje_sin_deteccion_no_es_conforme(self):
        e = self.entrada()
        e["completado"] = False
        self.assertFalse(_gate.es_conforme(e))
        e = self.entrada()
        e["sabotage"]["s"]["detected"] = False
        self.assertFalse(_gate.es_conforme(e))

    def test_piernas_que_no_existen_en_ese_backend_no_lo_enrojecen(self):
        e = self.entrada()
        del e["difftest_str"]                    # un backend sin `str` no tiene esa pierna
        self.assertTrue(_gate.es_conforme(e))
        e = self.entrada()
        e["sabotage"] = {}                       # "cada sabotaje declarado es detectado": vacío
        self.assertTrue(_gate.es_conforme(e))    # es la afirmación vacía, no un verde heredado
        e = self.entrada()
        del e["sabotage"]                        # gates sin la pierna (p. ej. F4 sin sabotage)
        self.assertTrue(_gate.es_conforme(e))


class SabotajeConCrash(unittest.TestCase):
    def test_un_crash_no_puede_blanquearse_como_deteccion_de_sabotaje(self):
        caso = load_all(ROOT)[0]
        res = backend_gate.sabotages(FalsoBackend([]), [caso], 0)
        fila_s = res["fake_sabotage"]
        self.assertFalse(fila_s["detected"], "un crash del instrumento se afirmó como detección")
        self.assertTrue(fila_s["harness"], "la fila del crash no quedó en el recibo")
        self.assertEqual(fila_s["corpus_failures"], 0)   # la lista sigue siendo solo semántica
        self.assertEqual({f["code"] for f in fila_s["harness"]}, {"TOOLCHAIN_BUILD_FAIL"})
        self.assertEqual({f["backend"] for f in fila_s["harness"]}, {"arnes_falso"})
        self.assertEqual({f["toolchain"] for f in fila_s["harness"]}, {"falso 1.0"})
        self.assertEqual({f["leg"] for f in fila_s["harness"]},
                         {"corpus", "difftest"})         # las dos piernas del sabotaje


if __name__ == "__main__":
    unittest.main()
