Tests: `python3 -m unittest discover -s tests -v`

| archivo | qué prueba |
|---|---|
| `test_reference.py` | intérprete de referencia contra los cinco corpus (v0.1–v0.5, 216 casos), hashes congelados, sabotajes de la semántica (F2, v0.2, v0.3) — incluido `test_len_de_str_se_hace_estatico`, el sabotaje de N1 |
| `test_ir.py` | ISY-IR v0.1/v0.2: resultado y traza iguales a la referencia, validador de mundo cerrado (F3) |
| `test_backend_c.py` | backend C: tres vías, diferencial numérico, sabotajes (F4) |
| `test_modules.py` | módulos (v0.4): identificadores seguros en backends, CLI con módulos, sabotaje del enlazador |
| `test_backends.py` | contrato ISY_BACKEND/1 en C, Rust, Zig, pydecimal y cobol: corpus, UNSUPPORTED, diferenciales, sabotajes por testigos, costo (F5) |
| `test_evidence.py` | `evidence/*/SHA256SUMS.txt` verificadas dentro de la suite y cifras del README contra la evidencia más reciente (PL-02), ahora también la población y los diferenciales del gate C (F4); control negativo con `ISYCO_EVIDENCE_ROOT=<copia>` |
| `test_versions.py` | `isyco/versions.py` como única fuente de la versión: familias monotónicas, fail-closed con versiones desconocidas, y ningún literal de versión suelto en `isyco/` |
| `test_v05_core.py` | V1 (`len` de arreglo resuelto en el frontend, cero nodos de IR, cero pasos) y V2 (`for x in a` como azúcar del parser): forma, gemelos, trazas, nombres sintéticos y rechazos en 0.1–0.4; la clase `ForSobreStr` (12 tests) añade N1 (`for` sobre un lugar `str`: cota = longitud del valor, variable `u8` copia sin alias — y el alias inverso no es construible porque `s[i] = …` es `NOT_ASSIGNABLE` desde v0.3 —, pasos e IR iguales al `while` gemelo) |
| `test_specialize.py` | V6 y V6-bis: la capacidad diferida en parámetro y en retorno se resuelve por el sitio de llamada — sin centinela, inyectiva en los nombres, fail-closed en las dos direcciones y paso-neutral contra el gemelo escrito a mano |

Tiempos (12 núcleos, 2026-10-30): ~3 min (197.0 s medidos, 91 tests) con la
caché `build/` llena. **Re-medido 2026-11-01: 166 tests en 191,3 s, 191,6 s, 200,2 s,
251,9 s y 329,6 s** (ventana de esas cinco: 191,3–329,6 s) con la caché llena y los 212 casos dentro del
gate — el 329,6 con `build/` en 3,3 G y justo después de `tools/v05_p4_probe.py`, que
compila programas de 256 a 2048 funciones, y el 251,9 después de una corrida completa de
`tools/c_gate.py` (cuatro combinaciones × 212 casos más el diferencial y los sabotajes);
no se ha atribuido la causa, solo medido
el rango. **Sexta y séptima corrida del día, ya con los 213 casos, el test nuevo del gate
C y el censo de P4 re-medido: 167 tests en 199,8 s y en 187,1 s** (200,1 s y 187,3 s de
pared). 187,1 es el mínimo del día y **amplía el rango a 187,1–329,6 s**. **Octava y novena
corrida, ya con N1 dentro (216 casos, 179 tests):** 228,9 s con el host cargado por otros agentes
y **188,3 s** en la corrida limpia de las 23:30 UTC (`real 188,57`). **Décima corrida, con el
test de copia sin alias ya dentro (180 tests): 189,006 s** (`real 189,27`, 2026-11-02 01:36 UTC),
así que el rango del día no se mueve. Entre la octava y la novena hubo una corrida
con **6 fallas**, y ninguna era de N1: cuatro leyeron el `README.md` mientras se editaba (la suite
corrió a la vez que la edición) y dos por la convención de rutas de los `SHA256SUMS.txt`
(`./x` ≠ `x` para `test_every_dir_has_sums_and_lists_every_file`, con todos los digest iguales).
Está dicho como hallazgo 11 de `docs/EVIDENCE_MATRIX.md`, no escondido. El sub-set
`tests.test_v05_core.ForSobreStr tests.test_reference.Sabotage` —19 tests, los 12 de N1 más los 7
sabotajes de la referencia— mide **0,386 s**: no toca backends. En frío
casi todo es compilar Zig; para no esperar:

```bash
python3 tools/warm_build_cache.py              # precompila en paralelo (añade --sabotages para el gate)
ISYCO_TEST_BACKENDS=c,rust python3 -m unittest discover -s tests   # suite sin Zig
ISYCO_ALLOW_MISSING_TOOLCHAINS=1 python3 -m unittest discover -s tests   # permitir un toolchain ausente
```

Si falta el toolchain de un backend registrado, la suite **falla**
(`test_backends.Toolchains`) en vez de saltarse tests en silencio; el contador
de skips ya no es la única señal.

Los sabotajes se prueban aquí solo con sus casos testigo (`SABOTAGE_WITNESSES` en
`test_backends.py`); el barrido completo de corpus + diferenciales saboteados lo hace
`tools/backend_gate.py`.
