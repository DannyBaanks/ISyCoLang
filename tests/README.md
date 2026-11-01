Tests: `python3 -m unittest discover -s tests -v`

| archivo | qué prueba |
|---|---|
| `test_reference.py` | intérprete de referencia contra los cinco corpus (v0.1–v0.5, 212 casos), hashes congelados, sabotajes de la semántica (F2, v0.2, v0.3) |
| `test_ir.py` | ISY-IR v0.1/v0.2: resultado y traza iguales a la referencia, validador de mundo cerrado (F3) |
| `test_backend_c.py` | backend C: tres vías, diferencial numérico, sabotajes (F4) |
| `test_modules.py` | módulos (v0.4): identificadores seguros en backends, CLI con módulos, sabotaje del enlazador |
| `test_backends.py` | contrato ISY_BACKEND/1 en C, Rust, Zig, pydecimal y cobol: corpus, UNSUPPORTED, diferenciales, sabotajes por testigos, costo (F5) |
| `test_evidence.py` | `evidence/*/SHA256SUMS.txt` verificadas dentro de la suite y cifras del README contra la evidencia más reciente (PL-02); control negativo con `ISYCO_EVIDENCE_ROOT=<copia>` |
| `test_versions.py` | `isyco/versions.py` como única fuente de la versión: familias monotónicas, fail-closed con versiones desconocidas, y ningún literal de versión suelto en `isyco/` |
| `test_v05_core.py` | V1 (`len` de arreglo resuelto en el frontend, cero nodos de IR, cero pasos) y V2 (`for x in a` como azúcar del parser): forma, gemelos, trazas, nombres sintéticos y rechazos en 0.1–0.4 |
| `test_specialize.py` | V6 y V6-bis: la capacidad diferida en parámetro y en retorno se resuelve por el sitio de llamada — sin centinela, inyectiva en los nombres, fail-closed en las dos direcciones y paso-neutral contra el gemelo escrito a mano |

Tiempos (12 núcleos, 2026-10-30): ~3 min (197.0 s medidos, 91 tests) con la
caché `build/` llena. **Re-medido 2026-11-01: 166 tests en 200,2 s, 191,6 s, 191,3 s y
329,6 s** con la caché llena y los 212 casos dentro del gate — el último con `build/` en
3,3 G y justo después de `tools/v05_p4_probe.py`, que compila programas de 256 a 2048
funciones; no se ha atribuido la causa, solo medido el rango. En frío
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
