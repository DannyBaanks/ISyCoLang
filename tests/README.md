Tests: `python3 -m unittest discover -s tests -v`

| archivo | qué prueba |
|---|---|
| `test_reference.py` | intérprete de referencia contra los cuatro corpus (v0.1–v0.4), hashes congelados, sabotajes de la semántica (F2, v0.2, v0.3) |
| `test_ir.py` | ISY-IR v0.1/v0.2: resultado y traza iguales a la referencia, validador de mundo cerrado (F3) |
| `test_backend_c.py` | backend C: tres vías, diferencial numérico, sabotajes (F4) |
| `test_modules.py` | módulos (v0.4): identificadores seguros en backends, CLI con módulos, sabotaje del enlazador |
| `test_backends.py` | contrato ISY_BACKEND/1 en C, Rust y Zig: corpus, UNSUPPORTED, diferenciales, sabotajes por testigos, costo (F5) |
| `test_evidence.py` | `evidence/*/SHA256SUMS.txt` verificadas dentro de la suite y cifras del README contra la evidencia más reciente (PL-02); control negativo con `ISYCO_EVIDENCE_ROOT=<copia>` |

Tiempos (12 núcleos, 2026-10-29): ~2 min (101.6 s medidos el 2026-10-29) con la
caché `build/` llena. En frío
casi todo es compilar Zig; para no esperar:

```bash
python3 tools/warm_build_cache.py              # precompila en paralelo (añade --sabotages para el gate)
ISYCO_TEST_BACKENDS=c,rust python3 -m unittest discover -s tests   # suite sin Zig
```

Los sabotajes se prueban aquí solo con sus casos testigo (`SABOTAGE_WITNESSES` en
`test_backends.py`); el barrido completo de corpus + diferenciales saboteados lo hace
`tools/backend_gate.py`.
