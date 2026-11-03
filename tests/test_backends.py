"""Tests de ISY_BACKEND/1 (F5): capacidades, UNSUPPORTED y conformidad por backend.

Cada backend instalado se prueba contra los dos corpus y una muestra del
diferencial por tipo. El gate completo con evidencia es tools/backend_gate.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends import available, registry  # noqa: E402
from isyco.backends.base import ALL_FEATURES, GNU_TIME, features_of, missing_features  # noqa: E402
from isyco.backends.c import CBackend  # noqa: E402
from isyco.conformance import COMPARED, load_all, load_corpus  # noqa: E402
from isyco.difftest import DEC_TYPES, INT_TYPES, compare, compare_str  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

CORPUS = load_all(ROOT)
#: Población del claim «60 por etiqueta, 46 por contenido»: los cuatro corpus congelados
#: ANTES de v0.5. No es `CORPUS`, que desde 2026-10-31 incluye `conformance_v0.5` y daría
#: 90/66 — lo que V7 midió fue la población que ya existía, no el total del gate.
CONGELADO = [case for nombre in ("conformance", "conformance_v0.2", "conformance_v0.3",
                                 "conformance_v0.4")
             for case in load_corpus(ROOT / "programs" / nombre)]
KEYS = COMPARED + ("steps",)
AVAILABLE = available()
# ISYCO_TEST_BACKENDS=c,rust limita qué backends nativos prueba esta suite (p. ej. para
# no esperar a Zig en frío). Sin la variable se prueban todos los instalados.
if os.environ.get("ISYCO_TEST_BACKENDS"):
    AVAILABLE = {k: v for k, v in AVAILABLE.items()
                 if k in os.environ["ISYCO_TEST_BACKENDS"].split(",")}
# Casos del corpus que hacen fallar cada sabotaje (medido con el barrido completo del
# gate, evidence/backends/). Cambiar el corpus puede exigir actualizar esta tabla.
SABOTAGE_WITNESSES = {
    "half_even_as_half_up": ("019_dec_half_even", "031_cast_dec_rescale"),
    "div_floor": ("014_div_trunc",),
    "str_concat_truncates": ("203_str_concat_overflow",),
}


def by_name(name):
    return next(c for c in CORPUS if c["name"] == name)


class Features(unittest.TestCase):
    def test_features_of_examples(self):
        f = features_of(compile_ir(by_name("027_interes")["program"]))
        self.assertTrue({"dec", "dec:half_even", "int32", "ovf:trap", "calls", "while", "emit"} <= f)
        self.assertNotIn("recursion", f)
        self.assertIn("recursion", features_of(compile_ir(by_name("036_recursion_fact")["program"])))
        self.assertIn("arrays", features_of(compile_ir(by_name("033_array_copy")["program"])))
        self.assertIn("unsigned", features_of(compile_ir(by_name("012_u8_wrap_neg")["program"])))
        v03 = features_of(compile_ir(by_name("234_struct_nested")["program"]))
        self.assertTrue({"ir0.2", "str", "struct", "arrays", "int8", "unsigned"} <= v03)
        self.assertNotIn("ir0.2", features_of(compile_ir(by_name("027_interes")["program"])))

    def test_every_valid_program_needs_only_known_features(self):
        for case in CORPUS:
            try:
                module = compile_ir(case["program"])
            except InvalidProgram:
                continue
            self.assertLessEqual(features_of(module), ALL_FEATURES, case["name"])


V05 = ROOT / "programs" / "conformance_v0.5"


def por_numero(numero: str):
    """Un caso del corpus v0.5, cogido por número (está en `CORPORA` desde 2026-10-31)."""
    return next(c for c in load_corpus(V05) if c["name"].startswith(f"{numero}_"))


class ContenidoNoEtiqueta(unittest.TestCase):
    """CORE v0.5 V7: `UNSUPPORTED` tiene que señalar una capacidad que el programa
    realmente exige, no el número de schema con el que bajó la IR.

    Medido sobre el corpus congelado: 60 programas llevan `isy-ir/0.2` y los 60
    recibían `ir0.2` por la etiqueta; solo 46 usan `str` o `struct`. Los 14 restantes
    eran `UNSUPPORTED` sin pedir nada que COBOL no sepa hacer.
    """

    def test_la_etiqueta_no_es_una_capacidad(self):
        modulo = compile_ir(por_numero("442")["program"])
        self.assertEqual(modulo["schema"], "isy-ir/0.2")        # lo que el contenedor puede
        self.assertNotIn("ir0.2", features_of(modulo))          # lo que este programa no pide

    def test_un_tipo_0_2_si_la_requiere(self):
        self.assertIn("ir0.2", features_of(compile_ir(by_name("234_struct_nested")["program"])))

    def test_emitir_arreglo_pide_emit_array_no_ir02(self):
        f = features_of(compile_ir(por_numero("441")["program"]))
        self.assertIn("emit_array", f)
        self.assertNotIn("ir0.2", f)         # no hay str ni struct: la etiqueta no cuenta
        self.assertIn("arrays", f)
        # Átomos distintos: `033` usa arreglos y emite enteros, así que no pide imprimirlos.
        self.assertNotIn("emit_array", features_of(compile_ir(by_name("033_array_copy")["program"])))

    def test_el_unsupported_dice_la_capacidad_exacta(self):
        self.assertEqual(missing_features(AVAILABLE["cobol"], por_numero("441")["program"]),
                         ["emit_array"])
        self.assertEqual(missing_features(AVAILABLE["cobol"], by_name("253_emit_array")["program"]),
                         ["emit_array"])

    @unittest.skipUnless("cobol" in AVAILABLE, "no hay cobc")
    def test_cobol_ejecuta_lo_que_el_contenido_permite(self):
        """Canario D: los cuatro casos que la etiqueta bloqueaba se ejecutan y coinciden."""
        for numero in ("439", "440", "442"):
            case = por_numero(numero)
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            got, _ = AVAILABLE["cobol"].run(case["program"], case["input"], case.get("limits"))
            with self.subTest(caso=case["name"]):
                self.assertNotEqual(got["status"], "UNSUPPORTED", case["name"])
                self.assertEqual({k: got[k] for k in KEYS}, {k: ref[k] for k in KEYS},
                                 case["name"])

    @unittest.skipUnless("cobol" in AVAILABLE, "no hay cobc")
    def test_llamada_void_en_sentencia_compila(self):
        """La forma que 327 expuso: antes el proemio escribía en un hueco que solo se
        declaraba si la función retornaba algo, y `cobc` rechazaba el programa."""
        case = by_name("327_qualified_call_stmt")
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        got, _ = AVAILABLE["cobol"].run(case["program"], case["input"], case.get("limits"))
        self.assertEqual({k: got[k] for k in KEYS}, {k: ref[k] for k in KEYS})

    def test_sesenta_por_etiqueta_cuarenta_y_seis_por_contenido(self):
        """La separación es medible en el corpus congelado, no una declaración.

        La población se nombra explícitamente (`CONGELADO`): con `conformance_v0.5` dentro de
        `CORPORA` el conteo total sube a 90 por etiqueta y 66 por contenido, medido el
        2026-10-31, y el claim de V7 dejaría de ser el que se selló.
        """
        by_schema = by_content = 0
        for case in CONGELADO:
            try:
                modulo = compile_ir(case["program"])
            except InvalidProgram:
                continue
            if modulo["schema"] == "isy-ir/0.2":
                by_schema += 1
            if "ir0.2" in features_of(modulo):
                by_content += 1
        self.assertEqual((by_schema, by_content), (60, 46))


class NoDecimalC(CBackend):
    """Backend de prueba que declara no saber decimales (además de lo que C no sabe)."""
    name = "c_nodec"
    features = CBackend.features - {"dec", "dec:half_even", "dec:half_up", "dec:down", "dec:exact"}


@unittest.skipUnless("c" in AVAILABLE, "no hay compilador de C")
class Unsupported(unittest.TestCase):
    def test_missing_feature_is_unsupported_never_approximated(self):
        backend = NoDecimalC()
        seen_unsupported = seen_pass = 0
        for case in CORPUS:
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            got, _ = backend.run(case["program"], case["input"], case.get("limits"))
            missing = missing_features(backend, case["program"])
            if missing and ref["status"] == "INVALID_PROGRAM":
                # El frontend decide INVALID_PROGRAM/BAD_INPUT antes que el backend
                # (spec/BACKEND.md §1): la capacidad declarada no interviene.
                self.assertEqual({k: ref[k] for k in KEYS},
                                 {k: got.get(k) for k in KEYS}, case["name"])
            elif missing:
                self.assertEqual(got["status"], "UNSUPPORTED", case["name"])
                self.assertEqual(got["code"], ",".join(missing), case["name"])
                self.assertEqual(got["emits"], [])
                if "dec" in missing:
                    seen_unsupported += 1
            else:
                self.assertEqual({k: ref[k] for k in KEYS}, {k: got.get(k) for k in KEYS}, case["name"])
                seen_pass += 1
        self.assertGreater(seen_unsupported, 5)
        self.assertGreater(seen_pass, 20)


class Registry(unittest.TestCase):
    def test_every_sabotage_has_witnesses(self):
        for backend in registry().values():
            for sabotage in backend.sabotages:
                self.assertIn(sabotage, SABOTAGE_WITNESSES, f"{backend.name}: {sabotage}")

    def test_wave_one_registered(self):
        # Ola 1: C, Rust, Zig (F5). Ola 2: pydecimal (ROADMAP F5, "decimal de
        # punto fijo verificable"). El nombre del test es de la ola 1; el
        # registro hereda backends a medida que se cierra cada ola.
        self.assertEqual(set(registry()), {"c", "cobol", "pydecimal", "rust", "zig"})


class Toolchains(unittest.TestCase):
    def test_every_registered_backend_is_testable(self):
        # Un backend registrado sin toolchain dejaría la suite en verde sin
        # probarlo (solo quedaría el contador de skips). Falla salvo opt-out
        # explícito. No usa AVAILABLE: ISYCO_TEST_BACKENDS filtra qué probar,
        # no qué está instalado.
        missing = sorted(set(registry()) - set(available()))
        if missing and os.environ.get("ISYCO_ALLOW_MISSING_TOOLCHAINS") == "1":
            self.skipTest("toolchains ausentes (permitido): " + ", ".join(missing))
        self.assertEqual(missing, [],
                         "toolchain ausente: " + ", ".join(missing)
                         + " (define ISYCO_ALLOW_MISSING_TOOLCHAINS=1 para correr sin ellos)")


@unittest.skipUnless(AVAILABLE, "no hay toolchain nativo instalado")
class Cli(unittest.TestCase):
    def test_native_via_matches_reference(self):
        program = ROOT / "programs" / "conformance" / "027_interes.isy"
        ref, _ = run(program.read_bytes(), ["1000.00", "0.0525"])
        want = {k: ref[k] for k in KEYS}
        seen = []
        for via in AVAILABLE:
            proc = subprocess.run(
                [sys.executable, "-m", "isyco", "run", str(program),
                 "--input", '["1000.00","0.0525"]', "--via", via],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual({k: json.loads(proc.stdout)[k] for k in KEYS}, want, via)
            seen.append(via)
        self.assertTrue(seen)


@unittest.skipUnless(AVAILABLE, "no hay toolchain nativo instalado")
class TopeFrontend(unittest.TestCase):
    """P4 (CORE v0.5 §7): el tope de especializaciones se aplica ANTES de la IR, así que
    los cinco backends responden lo mismo sin compilar nada y sin una línea en stderr.

    Es la parte diferencial del rechazo de frontend: `447` cuesta ~1 ms en cada columna
    porque `base.py:_module` cachea el `InvalidProgram` y `run()` cae a la referencia.
    """

    def test_el_tope_llega_igual_a_los_cinco_backends(self):
        case = by_name("447_tope_de_especializaciones")
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        want = {k: ref[k] for k in KEYS}
        self.assertEqual((ref["status"], ref["code"]), ("INVALID_PROGRAM", "SPEC_LIMIT"))
        for nombre, backend in AVAILABLE.items():
            got, _ = backend.run(case["program"], case["input"], case.get("limits"))
            with self.subTest(backend=nombre):
                self.assertEqual({k: got.get(k) for k in KEYS}, want, nombre)
                self.assertFalse(got.get("backend_stderr"), nombre)

    def test_los_dieciseis_clones_ejecutan_igual_que_la_referencia(self):
        """`448` sí baja a la IR: los cuatro backends que implementan `str` lo ejecutan igual
        que la referencia; COBOL responde `UNSUPPORTED` nombrando la capacidad que le falta."""
        case = by_name("448_dieciseis_clones_por_definicion")
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        want = {k: ref[k] for k in KEYS}
        self.assertEqual(len(ref["emits"]), 16)
        with_str = []
        for nombre, backend in AVAILABLE.items():
            missing = missing_features(backend, case["program"])
            got, _ = backend.run(case["program"], case["input"], case.get("limits"))
            with self.subTest(backend=nombre):
                if missing:
                    self.assertEqual(got["status"], "UNSUPPORTED", nombre)
                    self.assertEqual(got["code"], ",".join(missing), nombre)
                    self.assertIn("str", got["code"], nombre)
                else:
                    with_str.append(nombre)
                    self.assertEqual({k: got.get(k) for k in KEYS}, want, nombre)
                    self.assertFalse(got.get("backend_stderr"), nombre)
        esperados = sorted(n for n in ("c", "pydecimal", "rust", "zig") if n in AVAILABLE)
        self.assertEqual(sorted(with_str), esperados,
                         "cada backend `str` presente ejecuta 448; con los cinco "
                         "instalados la lista es cuatro")
        if "cobol" in AVAILABLE:
            self.assertNotIn("cobol", with_str)

    def test_la_salida_de_447_es_la_de_la_cli(self):
        """El mismo rechazo por la puerta de la CLI: `INVALID_PROGRAM` con `SPEC_LIMIT` y
        código de salida 2 (`__main__.py`, sin bajar a la IR)."""
        program = ROOT / "programs" / "conformance_v0.5" / "447_tope_de_especializaciones.isy"
        proc = subprocess.run([sys.executable, "-m", "isyco", "run", str(program)],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["code"], "SPEC_LIMIT")
        self.assertIn("INVALID_PROGRAM", proc.stdout)


class CuotaYAliasZig(unittest.TestCase):
    """Z1: el techo de comptime de Zig es forma del emisor, no del idioma.

    Dos invariantes del código generado, con el `expected` contado en el lenguaje (llamadas
    con literal de `str`), no en el texto emitido: la cuota que el emisor se autoconcede vale
    `1000 + 8·sitios` y vive dentro del cuerpo, y cada ancho de `str` se instancia una sola
    vez a nivel de archivo. Sin la segunda, la firma de un clone con 1024 parámetros agota
    el marco de la declaración y ninguna cuota de cuerpo lo alcanza (medido en
    `tools/z1_ceiling_probe.py`).
    """

    K = 5

    def setUp(self):
        if "zig" not in AVAILABLE:
            self.skipTest("zig no instalado")
        cuerpo = "".join('    emit m("ab");\n' for _ in range(self.K))
        self.fuente = ('isyco 0.5\n\nfn m(a: str) -> i64 { return len(a); }\n'
                       f'fn main() -> i64 !emit {{\n{cuerpo}    return 0;\n}}\n').encode()

    def linea_cuota(self, src: str) -> str | None:
        for linea in src.splitlines():
            if "setEvalBranchQuota" in linea:
                return linea.strip()
        return None

    def test_la_cuota_vale_mil_mas_ocho_por_sitio_y_vive_en_el_cuerpo(self):
        src = AVAILABLE["zig"].emit(compile_ir(self.fuente))
        lineas = src.splitlines()
        esperada = f"comptime {{ @setEvalBranchQuota({1000 + 8 * self.K}); }}"
        self.assertEqual(self.linea_cuota(src), esperada)
        i = next(n for n, l in enumerate(lineas) if l.startswith("fn f_main"))
        self.assertEqual(lineas[i + 1].strip(), esperada,
                         "la cuota tiene que ser la primera sentencia del cuerpo: a nivel "
                         "de archivo es otro marco y no autoriza nada (medido)")
        self.assertNotIn(esperada, "\n".join(lineas[:i]))

    def test_cada_ancho_se_instancia_una_vez_y_el_codigo_generado_no_usa_isystr(self):
        src = AVAILABLE["zig"].emit(compile_ir(self.fuente))
        lineas = src.splitlines()
        self.assertEqual([l for l in lineas if l.startswith("const Str")], ["const Str2 = IsyStr(2);"])
        desde_alias = next(n for n, l in enumerate(lineas) if l.startswith("const Str"))
        self.assertFalse([l for l in lineas[desde_alias + 1:] if "IsyStr(" in l],
                         "después de los alias todo tipo de `str` se nombra por el alias")

    def test_un_programa_sin_str_no_lleva_cuota_ni_alias(self):
        fuente = (b"isyco 0.5\n\nfn m(a: i64) -> i64 { return a; }\n"
                  b"fn main() -> i64 !emit { emit m(7); return 0; }\n")
        src = AVAILABLE["zig"].emit(compile_ir(fuente))
        self.assertIsNone(self.linea_cuota(src))
        self.assertFalse(any(l.startswith("const Str") for l in src.splitlines()))

    def test_el_programa_fronteira_ejecuta_como_la_referencia(self):
        """512 sitios: con la cuota de fábrica Zig no compila; emitido así, sí y coincide."""
        n = 512
        firma = ", ".join(f"a{i}: str" for i in range(1, n + 1))
        args = ", ".join('"{}"'.format("x" * (1 + i % 4)) for i in range(n))
        fuente = (f'isyco 0.5\n\nfn m({firma}) -> i64 {{ return len(a1); }}\n'
                  f'fn main() -> i64 !emit {{\n    emit m({args});\n    return 0;\n}}\n').encode()
        esperado, _ = run(fuente, [])
        obtenido, _ = AVAILABLE["zig"].run(fuente, [], None)
        self.assertEqual({k: obtenido.get(k) for k in KEYS}, {k: esperado.get(k) for k in KEYS})


def _make_conformance(name):
    @unittest.skipUnless(name in AVAILABLE, f"toolchain de {name} no instalado")
    class Conformance(unittest.TestCase):
        backend = AVAILABLE.get(name)

        def test_corpus(self):
            bad = []
            for case in CORPUS:
                ref, _ = run(case["program"], case["input"], case.get("limits"))
                got, _ = self.backend.run(case["program"], case["input"], case.get("limits"))
                missing = missing_features(self.backend, case["program"])
                if missing and ref["status"] != "INVALID_PROGRAM":
                    # Fuera de capacidades: UNSUPPORTED exacto, nunca una aproximación.
                    if got["status"] != "UNSUPPORTED" or got["code"] != ",".join(missing):
                        bad.append((case["name"], got.get("status"), got.get("code")))
                elif {k: ref[k] for k in KEYS} != {k: got.get(k) for k in KEYS} or got.get("backend_stderr"):
                    bad.append((case["name"], got.get("status"), got.get("backend_stderr")))
            self.assertEqual(bad, [])

        def test_difftest_sample(self):
            # Muestra: forzados + 1 aleatorio, en un subconjunto de tipos para que corra rápido.
            types = INT_TYPES[::5] + DEC_TYPES[::2]
            report = compare(self.backend.run, pairs=1, types=types)
            self.assertEqual(report["diffs"], [])
            # `diffs == []` también lo escribe un diferencial que abortó el tipo por un fallo
            # del instrumento: sin estas dos la muestra podría pasar sobre un crash (F5).
            self.assertEqual(report.get("harness", []), [])
            self.assertEqual(report.get("types_aborted", []), [])
            if "str" in self.backend.features:
                str_report = compare_str(self.backend.run, per_op=2)
                self.assertEqual(str_report["diffs"], [])
                self.assertEqual(str_report.get("harness", []), [])
                self.assertFalse(str_report.get("aborted"))

        def test_engine_does_the_work(self):
            case = by_name("027_interes")
            source = self.backend.emit(compile_ir(case["program"]))
            for value in case["expected"]["emits"]:
                self.assertNotIn(value, source)
            other, _ = self.backend.run(case["program"], ["2000.00", "0.0525"])
            self.assertEqual(other["emits"], ["8.22", "16.44", "24.66"])

        def test_sabotages_detected(self):
            # Cada sabotaje declarado debe hacer fallar sus casos testigo del corpus: si no,
            # la suite no distinguiría este backend de uno roto (spec/BACKEND.md §5). Solo
            # los testigos, para no recompilar el corpus entero saboteado en cada corrida;
            # el barrido completo (corpus + diferenciales) lo hace tools/backend_gate.py.
            self.assertLessEqual({"half_even_as_half_up", "div_floor"}, set(self.backend.sabotages))
            for sabotage in self.backend.sabotages:
                witnesses = [by_name(name) for name in SABOTAGE_WITNESSES[sabotage]]
                caught = [c["name"] for c in witnesses
                          if {k: run(c["program"], c["input"], c.get("limits"))[0][k] for k in KEYS}
                          != {k: self.backend.run(c["program"], c["input"], c.get("limits"),
                                                  sabotage=sabotage)[0].get(k) for k in KEYS}]
                self.assertTrue(caught, sabotage)

        def test_cost_is_measured_and_not_compared(self):
            case = by_name("027_interes")
            got, _ = self.backend.run(case["program"], case["input"])
            cost = got["cost"]
            self.assertEqual(set(cost), {"wall_ms", "user_ms", "sys_ms", "max_rss_kb", "compile_ms"})
            self.assertGreater(cost["wall_ms"], 0)
            if GNU_TIME:
                # Pico del binario, no del intérprete de Python que lo lanza
                # (~12 MB). pydecimal SÍ es un intérprete: su techo es propio.
                self.assertLess(cost["max_rss_kb"], self.backend.rss_ceiling_kb)
            else:
                self.assertIsNone(cost["max_rss_kb"])
            self.assertNotIn("cost", KEYS)

    Conformance.__name__ = Conformance.__qualname__ = f"Conformance_{name}"
    return Conformance


for _name in ("c", "rust", "zig", "pydecimal", "cobol"):
    globals()[f"Conformance_{_name}"] = _make_conformance(_name)


if __name__ == "__main__":
    unittest.main()
