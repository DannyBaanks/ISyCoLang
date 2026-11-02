Tests: `python3 -m unittest discover -s tests -v`

| archivo | qué prueba |
|---|---|
| `test_reference.py` | intérprete de referencia contra los cinco corpus (v0.1–v0.5, 218 casos), hashes congelados, sabotajes de la semántica (F2, v0.2, v0.3) — 9 sabotajes: los 7 anteriores más los dos de P4 (`test_el_tope_de_especializaciones_se_desactiva`, `test_bajar_el_tope_a_uno_rompe_el_corpus`), y `test_len_de_str_se_hace_estatico`, el de N1 |
| `test_ir.py` | ISY-IR v0.1/v0.2: resultado y traza iguales a la referencia, validador de mundo cerrado (F3) |
| `test_backend_c.py` | backend C: tres vías, diferencial numérico, sabotajes (F4) |
| `test_modules.py` | módulos (v0.4): identificadores seguros en backends, CLI con módulos, sabotaje del enlazador |
| `test_backends.py` | contrato ISY_BACKEND/1 en C, Rust, Zig, pydecimal y cobol: corpus, UNSUPPORTED, diferenciales, sabotajes por testigos, costo (F5); `TopeFrontend` (3 tests) fija que el `SPEC_LIMIT` de P4 llega **idéntico** a los cinco backends y que los 16 clones de `448` ejecutan igual que la referencia |
| `test_harness.py` | la guarda del arnés (hallazgo 13), con el crash fabricado en vez de esperárselo a un toolchain: `intento` devuelve `(None, fila)` y nunca un resultado comparable, `InvalidProgram` sube, `TOOLCHAIN_BUILD_FAIL` trae su `build_key` recomponible, la caché negativa deja **una** invocación del compilador en cinco intentos sobre la misma fuente, `compare` aborta el tipo que murió y corre el siguiente, y una fila en cualquier pierna vuelve no-conforme el pliegue aunque `failures` y `diffs` estén vacíos — la prueba formal de que ningún verde puede heredarse sobre un crash (15 tests, 1,6 s medidos 2026-11-02) |
| `test_evidence.py` | `evidence/*/SHA256SUMS.txt` verificadas dentro de la suite y cifras del README contra la evidencia más reciente (PL-02), ahora también la población y los diferenciales del gate C (F4); control negativo con `ISYCO_EVIDENCE_ROOT=<copia>` |
| `test_versions.py` | `isyco/versions.py` como única fuente de la versión: familias monotónicas, fail-closed con versiones desconocidas, y ningún literal de versión suelto en `isyco/` |
| `test_v05_core.py` | V1 (`len` de arreglo resuelto en el frontend, cero nodos de IR, cero pasos) y V2 (`for x in a` como azúcar del parser): forma, gemelos, trazas, nombres sintéticos y rechazos en 0.1–0.4; la clase `ForSobreStr` (12 tests) añade N1 (`for` sobre un lugar `str`: cota = longitud del valor, variable `u8` copia sin alias — y el alias inverso no es construible porque `s[i] = …` es `NOT_ASSIGNABLE` desde v0.3 —, pasos e IR iguales al `while` gemelo) |
| `test_specialize.py` | V6 y V6-bis: la capacidad diferida en parámetro y en retorno se resuelve por el sitio de llamada — sin centinela, inyectiva en los nombres, fail-closed en las dos direcciones y paso-neutral contra el gemelo escrito a mano. `TopePorDefinicion` (9 tests) fija P4: 255 y 256 resoluciones legales, 257 es `SPEC_LIMIT`, la identidad contada es `nombre calificado por módulo` **por definición y no por programa**, la copia nunca es definición contada, y ningún programa `0.4` puede llegar al tope |

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
así que el rango del día no se mueve. **Undécima corrida, ya con los 218 casos y los 194 tests de
P4 dentro: 491,090 s** (`real 8 m 12,3 s`, 2026-11-02 08:41 UTC, OK). Es el máximo medido y
**amplía el rango a 187,1–491,1 s**: corrió justo después del gate de backends y de
`tools/v05_p4_probe.py --bisect-zig`, la misma condición que había subido la corrida de 329,6;
la causa sigue sin atribuirse — medido, no explicado —. **Duodécima corrida, ya sobre el árbol
commiteado `ac33000` y con los 194 tests: 347,739 s** (`real 5 m 48,0 s`, 2026-11-02 09:11 UTC,
OK), dentro del rango y con `build/` lleno, así que no lo mueve. Mientras corría se editaron
`docs/EVIDENCE_MATRIX.md`, el ADR de P4 y `spec/CORE_v0.5.md` — la ventana del hallazgo 11, esta
vez medida desde dentro: ninguno de los tres es un fichero que la suite abra, y por eso salió OK.
**Decimotercera corrida, sobre el árbol limpio `e2fe2a0` (el estado final del lote): 216,894 s**
(`real 3 m 37,3 s`, 2026-11-02 09:32 UTC, 194 tests, OK), en medio del rango y con el árbol
commiteado antes de arrancar, como debe medirse. Entre la octava y la novena hubo una corrida
con **6 fallas**, y ninguna era de N1: cuatro leyeron el `README.md` mientras se editaba (la suite
corrió a la vez que la edición) y dos por la convención de rutas de los `SHA256SUMS.txt`
(`./x` ≠ `x` para `test_every_dir_has_sums_and_lists_every_file`, con todos los digest iguales).
Está dicho como hallazgo 11 de `docs/EVIDENCE_MATRIX.md`, no escondido. El sub-set
`tests.test_v05_core.ForSobreStr tests.test_reference.Sabotage` —**21** tests, los 12 de N1 más
los 9 sabotajes de la referencia (los 7 de antes más los dos de P4)— mide **0,973 s** (2026-11-02;
antes, con 19, eran 0,386 s). Los dos sabotajes de P4, corridos solos, gastan **0,186 s**: no
explican los 0,587 s de diferencia y la causa no está atribuida, solo medida. No toca backends.
Otro sub-set medido sobre `d0a74bd`, con los docs ya commiteados:
`tests.test_specialize.TopePorDefinicion tests.test_reference.Sabotage` —18 tests, los 9 del
tope más los 9 sabotajes— en **0,748 s** y OK. En frío casi todo es compilar Zig; para no
esperar:

```bash
python3 tools/warm_build_cache.py              # precompila en paralelo (añade --sabotages para el gate)
ISYCO_TEST_BACKENDS=c,rust python3 -m unittest discover -s tests   # suite sin Zig
ISYCO_ALLOW_MISSING_TOOLCHAINS=1 python3 -m unittest discover -s tests   # permitir un toolchain ausente
ISYCO_EVIDENCE_ROOT=/tmp/evid python3 tools/backend_gate.py --only c   # sellar fuera del registro
```

Cualquier prueba o sonda que escriba evidencia **debe** pasar por `ISYCO_EVIDENCE_ROOT`: sin la
perilla, una corrida de demostración escribe archivos nuevos dentro de `evidence/<tema>/` y el
`SHA256SUMS.txt` del directorio pasa a incluirlos, que es destruir el registro del gate.

Si falta el toolchain de un backend registrado, la suite **falla**
(`test_backends.Toolchains`) en vez de saltarse tests en silencio; el contador
de skips ya no es la única señal.

Los sabotajes se prueban aquí solo con sus casos testigo (`SABOTAGE_WITNESSES` en
`test_backends.py`); el barrido completo de corpus + diferenciales saboteados lo hace
`tools/backend_gate.py`.
