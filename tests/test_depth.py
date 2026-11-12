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

**Z2-b (2026-11-12).** La cota decidía el borde, pero el fuente del tope legal seguía muriendo si
quien llamaba traía 300 frames (C8). `isyco/pila.py` reserva la pila del paquete contada desde el
llamante; `LoLegalCabe` fija que lo legal baja, se valida, se emite y ejecuta con 300 y 3 000
frames encima, y que es la reserva —no el anfitrión— la que lo consigue.

**Z3 (2026-11-12).** Medir Z2-b dejó a la vista el mismo defecto en otro eje: las sentencias de
control anidaban sin cota (676 `if` bajaban, 677 morían por `RecursionError`). `CotaDeSentencias`
fija `ast.MAX_STMT_DEPTH = 64` con el patrón de Z2 —literal, borde exclusivo, dos guardas,
sabotaje en las dos direcciones—, y `LaEjecucionCabe` que con las dos cotas nombradas la pila de
la ejecución deja de ser una apuesta: el peor programa legal recursiona hasta `max_call_depth`.
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
from isyco import pila                                         # noqa: E402
from isyco.backends import registry                            # noqa: E402
from isyco.backends.base import features_of                    # noqa: E402
from isyco.checker import check, expr_depth, stmt_depth  # noqa: E402
#                          # noqa: E402
from isyco.errors import InvalidProgram                        # noqa: E402
from isyco.interp import run                                   # noqa: E402
from isyco.ir_interp import compile_ir, run_via_ir             # noqa: E402
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


def llamadas(niveles: int) -> bytes:
    """`f(f(…f(1)…))`: la cara legal más cara medida (12,2 frames por nivel en el frontend)."""
    return (f"isyco 0.5\n\nfn f(a: i64) -> i64 {{\n    return a;\n}}\n\n"
            f"fn main() -> i64 !emit {{\n"
            f"    let x: i64 = {'f(' * niveles}1{')' * niveles};\n"
            f"    emit x;\n    return x;\n}}\n").encode()


def recursivo(hondo: int) -> bytes:
    """Un programa que se llama a sí mismo `hondo` veces: gasta pila de **ejecución**."""
    return (f"isyco 0.5\n\nfn baja(n: i64) -> i64 {{\n    if n == 0 {{\n        return 0;\n    }}\n"
            f"    return 1 + baja(n - 1);\n}}\n\n"
            f"fn main() -> i64 !emit {{\n    emit baja({hondo});\n    return 0;\n}}\n").encode()


#: Las cuatro caras en su tope legal: las tres del corpus más la más cara.
TOPES = {"parentesis": parentesis(N - 1), "cadena": cadena(N), "pelado": pelado(N - 1),
         "llamadas": llamadas(N - 1)}


def con_llamante(frames: int, f):
    """Corre `f` con `frames` frames encima y un límite que deja solo 40 de aire.

    Es el llamante hostil: no llega «con pila de sobra», llega casi agotado. Lo que pase debajo
    lo decide la reserva del paquete o no lo decide nadie.
    """
    def baja(n):
        return baja(n - 1) if n else f()
    antes = sys.getrecursionlimit()
    sys.setrecursionlimit(pila.profundidad() + frames + 40)     # exacto: también puede bajarlo
    try:
        return baja(frames)
    finally:
        sys.setrecursionlimit(antes)


def todo_el_camino(fuente: bytes) -> list:
    """Baja, valida, censa, emite por cada backend que lo declara y ejecuta por las dos rutas."""
    modulo = compile_ir(fuente)
    for backend in registry().values():
        if features_of(modulo) <= set(backend.features):
            backend.emit(modulo)
    return [run(fuente, [])[0]["status"], run_via_ir(fuente, [])[0]["status"]]


class LoLegalCabe(unittest.TestCase):
    """Z2-b: la pila que trae quien llama no decide si un programa legal baja."""

    def test_el_tope_legal_recorre_todo_el_camino_con_cualquier_llamante(self):
        for frames in (0, 300, 3000):
            for cara, fuente in TOPES.items():
                with self.subTest(cara=cara, frames=frames):
                    self.assertEqual(con_llamante(frames, lambda: todo_el_camino(fuente)),
                                     ["HALTED", "HALTED"])

    def test_el_rechazo_sigue_siendo_del_idioma_con_cualquier_llamante(self):
        for frames in (300, 3000):
            for _, fuente in BORDES:
                with self.subTest(fuente=fuente[:24], frames=frames):
                    self.assertEqual(con_llamante(frames, lambda: resultado(fuente))["code"],
                                     "SPEC_LIMIT")

    def test_sin_la_reserva_vuelve_el_muro_del_anfitrion(self):
        """Sabotaje: con presupuesto 0 el tope legal muere con 300 frames, como medía C8."""
        fuente = TOPES["parentesis"]
        with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
            with self.assertRaises(RecursionError):
                con_llamante(300, lambda: compile_ir(fuente))
        self.assertEqual(con_llamante(300, lambda: compile_ir(fuente))["schema"][:6], "isy-ir")

    def test_el_validador_y_los_emisores_tambien_dependian_del_llamante(self):
        """El hueco no era solo del frontend: la IR es un árbol y sus recorridos bajan frames."""
        modulo = compile_ir(TOPES["cadena"])
        recorridos = {"features_of": lambda: features_of(modulo),
                      **{n: (lambda b=b: b.emit(modulo)) for n, b in registry().items()}}
        for nombre, recorrer in recorridos.items():
            with self.subTest(recorrido=nombre):
                with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
                    with self.assertRaises(RecursionError):
                        con_llamante(300, recorrer)
                con_llamante(300, recorrer)

    def test_el_presupuesto_dobla_el_coste_medido(self):
        """La holgura no es fe: la cara más cara gasta menos de la mitad de lo reservado."""
        def coste(fuente: bytes) -> int:
            base, lo, hi = pila.profundidad(), 5, pila.frames_frontend()
            antes = sys.getrecursionlimit()
            while lo + 1 < hi:
                medio = (lo + hi) // 2
                sys.setrecursionlimit(base + medio)
                try:
                    with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
                        todo_el_camino(fuente)
                    hi = medio
                except RecursionError:
                    lo = medio
                finally:
                    sys.setrecursionlimit(antes)
            return hi
        costes = {cara: coste(fuente) for cara, fuente in TOPES.items()}
        self.assertEqual(max(costes, key=costes.get), "llamadas", costes)
        self.assertLessEqual(2 * max(costes.values()), pila.frames_frontend(), costes)
        self.assertGreater(max(costes.values()), 700, costes)     # y no es un coste de juguete

    def test_el_limite_del_llamante_queda_como_estaba(self):
        antes = sys.getrecursionlimit()
        todo_el_camino(TOPES["llamadas"])
        self.assertEqual(sys.getrecursionlimit(), antes)
        self.assertEqual(resultado(BORDES[0][1])["code"], "SPEC_LIMIT")    # sale por excepción
        self.assertEqual(sys.getrecursionlimit(), antes)
        with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
            with self.assertRaises(RecursionError):
                con_llamante(300, lambda: compile_ir(TOPES["parentesis"]))
        self.assertEqual(sys.getrecursionlimit(), antes)                   # y por RecursionError

    def test_la_ejecucion_tambien_cuenta_desde_el_llamante(self):
        """El presupuesto de ejecución era absoluto: un llamante más hondo que él lo anulaba."""
        fuente, limites = recursivo(5), {"max_call_depth": 8}
        hondo = pila.frames_ejecucion(8) + 800       # más frames de llamante que el presupuesto
        corre = lambda: run(fuente, [], limites)[0]
        self.assertEqual(corre()["emits"], ["5"])
        self.assertEqual(con_llamante(hondo, corre)["emits"], ["5"])
        with mock.patch.object(pila, "profundidad", lambda: 0):           # sabotaje: absoluto
            with self.assertRaises(RecursionError):
                con_llamante(hondo, corre)


M = A.MAX_STMT_DEPTH


def anidados(niveles: int, cabecera: str = "if true", fondo: str = "emit x;") -> bytes:
    """`niveles` sentencias de control una dentro de otra, con `fondo` en la más honda."""
    sale = "break;\n" if cabecera.startswith("while") else ""
    cuerpo = "".join("    " * (i + 1) + cabecera.format(i=i) + " {\n" for i in range(niveles))
    cuerpo += "    " * (niveles + 1) + fondo + "\n"
    cuerpo += "".join("    " * (i + 2) + sale + "    " * (i + 1) + "}\n"
                      for i in reversed(range(niveles))) if sale else \
        "".join("    " * (i + 1) + "}\n" for i in reversed(range(niveles)))
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n    let x: i64 = 1;\n"
            f"    let a: [i64; 1] = [1];\n{cuerpo}    return 0;\n}}\n").encode()


def else_if(ramas: int) -> bytes:
    """Cadena plana de `ramas` ramas: cada `else if` es un `if` dentro del `else`."""
    cadena = "    if n == 1 {\n        r = 1;\n    }" + "".join(
        f" else if n == {i} {{\n        r = {i};\n    }}" for i in range(2, ramas + 1))
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n    let n: i64 = {ramas};\n"
            f"    let r: i64 = 0;\n{cadena} else {{\n        r = -1;\n    }}\n"
            f"    emit r;\n    return 0;\n}}\n").encode()


def recursivo_al_fondo(ifs: int, pares: int, veces: int) -> bytes:
    """La llamada recursiva al fondo de `ifs` sentencias y de `pares` llamadas anidadas."""
    cuerpo = "".join("    " * (i + 1) + "if n > 0 {\n" for i in range(ifs))
    cuerpo += "    " * (ifs + 1) + f"return 1 + {'id(' * pares}baja(n - 1){')' * pares};\n"
    cuerpo += "".join("    " * (i + 1) + "}\n" for i in reversed(range(ifs)))
    return (f"isyco 0.5\n\nfn id(a: i64) -> i64 {{\n    return a;\n}}\n\n"
            f"fn baja(n: i64) -> i64 {{\n{cuerpo}    return 0;\n}}\n\n"
            f"fn main() -> i64 !emit {{\n    emit baja({veces});\n    return 0;\n}}\n").encode()


#: (legal en el borde, un nivel más arriba): las cuatro caras de la cota de sentencias
BORDES_Z3 = {"if": (anidados(M), anidados(M + 1)),
             "while": (anidados(M, "while true"), anidados(M + 1, "while true")),
             "for": (anidados(M, "for v{i} in a"), anidados(M + 1, "for v{i} in a")),
             "else_if": (else_if(M), else_if(M + 1))}


class CotaDeSentencias(unittest.TestCase):
    """Z3: el anidamiento de sentencias de control lo corta el idioma, no la pila."""

    def test_la_constante_es_un_literal_del_spec(self):
        self.assertEqual(A.MAX_STMT_DEPTH, 64)

    def test_el_borde_es_exclusivo_en_las_cuatro_caras(self):
        for cara, (legal, pasado) in BORDES_Z3.items():
            with self.subTest(cara=cara):
                visto = resultado(legal)
                self.assertEqual(visto["status"], "HALTED", visto)
                self.assertEqual(visto["emits"], [str(M)] if cara == "else_if" else ["1"])
                self.assertEqual(run_via_ir(legal, [])[0]["emits"], visto["emits"])
                visto = resultado(pasado)
                self.assertEqual((visto["status"], visto["code"]),
                                 ("INVALID_PROGRAM", "SPEC_LIMIT"))
                self.assertEqual((visto["emits"], visto["return"]), ([], None))

    def test_el_parser_y_el_ast_cuentan_lo_mismo(self):
        for cara, (legal, _) in BORDES_Z3.items():
            with self.subTest(cara=cara):
                self.assertEqual(stmt_depth(load_program(legal))[0], M)

    def test_los_niveles_se_suman_entre_formas_distintas(self):
        mezcla = (b"isyco 0.5\n\nfn main() -> i64 !emit {\n    let x: i64 = 1;\n"
                  b"    while x < 2 {\n        if x == 5 {\n            x = 9;\n"
                  b"        } else if x == 1 {\n            if true {\n                emit x;\n"
                  b"            }\n        }\n        x = x + 1;\n    }\n    return 0;\n}\n")
        self.assertEqual(stmt_depth(load_program(mezcla))[0], 4)   # while, if, else-if, if
        self.assertEqual(resultado(mezcla)["emits"], ["1"])
        with mock.patch.object(A, "MAX_STMT_DEPTH", 3):
            self.assertEqual(resultado(mezcla)["code"], "SPEC_LIMIT")

    def test_el_checker_rechaza_aunque_el_parser_no_haya_contado(self):
        """Segunda guarda: un AST que no pasó por `Parser.control` se corta igual."""
        with mock.patch.object(A, "MAX_STMT_DEPTH", 200):
            programa = load_program(anidados(M + 1))
        with self.assertRaises(InvalidProgram) as visto:
            check(programa)
        self.assertEqual(visto.exception.code, "SPEC_LIMIT")

    def test_un_llamante_hondo_sigue_obteniendo_spec_limit(self):
        for cara, (_, pasado) in BORDES_Z3.items():
            with self.subTest(cara=cara):
                self.assertEqual(con_llamante(3000, lambda: resultado(pasado))["code"],
                                 "SPEC_LIMIT")

    def test_mover_la_constante_mueve_el_borde(self):
        """Sabotaje en las dos direcciones, como en Z2."""
        with mock.patch.object(A, "MAX_STMT_DEPTH", 200):
            for cara, (_, pasado) in BORDES_Z3.items():
                with self.subTest(cara=cara):
                    self.assertEqual(resultado(pasado)["status"], "HALTED")
        self.assertEqual(resultado(anidados(4))["status"], "HALTED")
        with mock.patch.object(A, "MAX_STMT_DEPTH", 3):
            self.assertEqual(resultado(anidados(4))["code"], "SPEC_LIMIT")

    def test_las_dos_cotas_al_tope_recorren_todo_el_camino(self):
        """Lo más hondo que el idioma acepta: expresión al tope dentro de sentencias al tope."""
        peor = anidados(M, fondo=f"emit {'(' * (N - 1)}x{')' * (N - 1)};")
        for frames in (0, 300, 3000):
            with self.subTest(frames=frames):
                self.assertEqual(con_llamante(frames, lambda: todo_el_camino(peor)),
                                 ["HALTED", "HALTED"])
        with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
            with self.assertRaises(RecursionError):
                con_llamante(300, lambda: compile_ir(peor))


class LaEjecucionCabe(unittest.TestCase):
    """Con las dos cotas nombradas, cada llamada del programa tiene un coste de pila acotado."""

    def test_el_peor_programa_esta_en_las_dos_cotas(self):
        programa = load_program(self.PEOR)
        self.assertEqual((stmt_depth(programa)[0], expr_depth(programa)[0]), (M, N))

    LIMITES = {"max_call_depth": 256}
    PEOR = recursivo_al_fondo(M, N - 4, 250)     # 64 `if` y `1 + id(…id(baja(n - 1)))` en nivel 64

    def test_el_peor_programa_legal_recursiona_hasta_el_limite(self):
        """Antes: `RecursionError` con la llamada dentro de 60 `if`, muy por debajo de 256."""
        for ejecutar in (run, run_via_ir):
            with self.subTest(ruta=ejecutar.__name__):
                visto = ejecutar(self.PEOR, [], self.LIMITES)[0]
                self.assertEqual((visto["status"], visto["emits"]), ("HALTED", ["250"]))
                hondo = con_llamante(3000, lambda: ejecutar(self.PEOR, [], self.LIMITES)[0])
                self.assertEqual(hondo["emits"], ["250"])

    def test_el_limite_de_llamadas_lo_sigue_poniendo_el_idioma(self):
        pasado = recursivo_al_fondo(M, N - 4, 300)
        for ejecutar in (run, run_via_ir):
            with self.subTest(ruta=ejecutar.__name__):
                visto = ejecutar(pasado, [], self.LIMITES)[0]
                self.assertEqual((visto["status"], visto["code"]),
                                 ("LIMIT_REACHED", "max_call_depth"))

    def test_sin_el_presupuesto_por_nivel_vuelve_el_muro(self):
        with mock.patch.object(pila, "FRAMES_EJECUCION_POR_NIVEL", 0):
            for ejecutar in (run, run_via_ir):
                with self.subTest(ruta=ejecutar.__name__):
                    with self.assertRaises(RecursionError):
                        ejecutar(self.PEOR, [], self.LIMITES)

    def test_el_presupuesto_dobla_el_coste_medido_por_llamada(self):
        def frames(veces: int) -> int:
            fuente = recursivo_al_fondo(M, N - 4, veces)
            lo, hi = 1, pila.frames_ejecucion(256)
            real = pila.frames_ejecucion
            while lo + 1 < hi:
                medio = (lo + hi) // 2
                with mock.patch.object(pila, "frames_ejecucion", lambda _: medio), \
                        mock.patch("isyco.interp.frames_ejecucion", lambda _: medio):
                    try:
                        con_llamante(0, lambda: run(fuente, [], self.LIMITES))
                        hi = medio
                    except RecursionError:
                        lo = medio
            self.assertIs(pila.frames_ejecucion, real)
            return hi
        por_llamada = (frames(60) - frames(20)) / 40
        reservado = pila.FRAMES_EJECUCION_POR_NIVEL * pila.niveles()
        self.assertGreater(por_llamada, 150, por_llamada)       # no es un coste de juguete
        self.assertLessEqual(2 * por_llamada, reservado, por_llamada)


class LaPoblacionQuedaDebajo(unittest.TestCase):
    """Tripwire: ningún programa del repo roza la cota; si uno la cruza, esto lo nombra."""

    FUENTES_Z2 = tuple(f"{n}_" for n in range(449, 459))   # viven en las cotas: no son población

    def test_toda_fuente_del_repo_cabe_bajo_la_cota(self):
        """Se miden los programas que la spec acepta; los rechazos a propósito no tienen AST."""
        censadas, profunda, donde, sentencias = 0, 0, "", 0
        for carpeta in ("conformance", "conformance_v0.2", "conformance_v0.3",
                        "conformance_v0.4", "conformance_v0.5", "dogfood"):
            for ruta in sorted((ROOT / "programs" / carpeta).rglob("*.isy")):
                if ruta.parent.name == "gemelos":
                    continue
                esperado = ruta.with_suffix(".expect.json")
                if esperado.exists() and not self.se_acepta(esperado):
                    continue
                try:
                    programa = load_program(ruta.read_bytes())
                    hondo, _ = expr_depth(programa)
                    anida, _ = stmt_depth(programa)
                except InvalidProgram:
                    continue                    # rechazos a propósito: no tienen AST que medir
                censadas += 1
                self.assertLessEqual(hondo, A.MAX_EXPR_DEPTH, str(ruta))
                self.assertLessEqual(anida, A.MAX_STMT_DEPTH, str(ruta))
                if not ruta.name.startswith(self.FUENTES_Z2):
                    sentencias = max(sentencias, anida)
                if not ruta.name.startswith(self.FUENTES_Z2) and hondo > profunda:
                    profunda, donde = hondo, str(ruta.relative_to(ROOT))
        self.assertGreaterEqual(censadas, 150, "la población censada cambió sin decir nada")
        self.assertLessEqual(profunda, 8, f"la población real se pasó de lo censado: {donde}")
        self.assertEqual(sentencias, 4, "Z3: la población real anida 4 sentencias (02_csv.isy)")

    @staticmethod
    def se_acepta(expect: Path) -> bool:
        return json.loads(expect.read_text())["expected"]["status"] != "INVALID_PROGRAM"


if __name__ == "__main__":
    unittest.main()
