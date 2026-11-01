# Matriz de evidencia

Inventario de qué está sellado, dónde, y con qué árbol de código. Existe porque
`tests/test_evidence.py` puede verificar que un recibo no se tocó, pero **no puede**
verificar que una frase escrita en un `.md` tenga recibo: esa comprobación la hace esta
matriz a mano. Cuando una afirmación no tiene fila aquí, o tiene un comando que la
re-produce o es prosa.

**Reglas de lectura.**

- Un recibo `RELEASE_GATE` significa `arbol_sucio_codigo=false`: ni el engine, ni el
  corpus, ni las pruebas estaban modificados cuando corrió. `EVIDENCE_ONLY` es el mismo
  dato con el árbol de código sucio — sirve como referencia, no como gate.
- Las rutas de recibo son relativas al repo. Cada `evidence/<dir>/SHA256SUMS.txt` guarda
  nombres **sin carpeta**, así que se verifica **desde adentro** del directorio:
  `(cd evidence/c && sha256sum -c SHA256SUMS.txt)`. Desde la raíz falla con «No existe el
  archivo». Verificado el 2026-11-01 sobre los **20** listados que hay (14 en `evidence/`,
  `spec/` y los cinco `programs/conformance*/`): los 20 pasan desde adentro y todos fallan
  desde la raíz. La única lista que sí corre desde la raíz es `docs/origin/SHA256SUMS.txt`.
  `programs/dogfood/` no tiene lista (no es corpus congelado) y `tests/test_evidence.py`
  resuelve las rutas él mismo, por eso no depende del `cwd`.
- `git_head` se abrevia a 7. Un recibo viejo sigue siendo válido para el árbol que fija.
- Los cuatro recibos de la población **213** (`a4f608c`, el commit que metió `443`) salen de
  **una sola corrida en lote**, en ese orden: `run_conformance`, `ir_gate`, `c_gate`,
  `backend_gate`. El stdout sellado de cada uno es la **sección verbatim** de ese log —
  incluye la línea `### herramienta ###` y su `EXIT_<herramienta>=N`, que son del lote y no
  de la herramienta, y son el registro del código de salida. El log completo vivió en `/tmp`
  y no es evidencia canónica; lo canónico son los cuatro `_stdout.txt` sellados.

## Gates

| gate | recibo más reciente | head | veredicto | cifras |
|---|---|---|---|---|
| F2 — referencia contra el corpus | `evidence/conformance/run_2026-11-01T074055Z.json` | `a4f608c` | `PASS` | 213/213 en los cinco corpus |
| F3 — ISY-IR vs referencia | `evidence/ir/gate_2026-11-01T074055Z.json` | `a4f608c` | — | 426/426 comparaciones iguales, 145 programas bajados (`443` no baja: se comparan sus dos rechazos) |
| F4 — backend C (tres vías + sanitizers) | `evidence/c/gate_2026-11-01T074655Z.json` | `a4f608c` | `PASS` | 213 casos en las cuatro combinaciones (`gcc/plain`, `gcc/sanitized`, `clang/plain`, `clang/sanitized`), cada una con las tres vías expected ↔ referencia ↔ binario en 213/213, cero fallos y cero `UNSUPPORTED`; diferencial 24 612 corridas en `gcc/plain` (40 parejas por operación, semilla 20261028, 32 tipos, 0 diferencias) y 6 468 con sanitizers; los dos sabotajes detectados; `missing_compilers: []`. stdout crudo sellado al lado: `gate_2026-11-01T074655Z_stdout.txt` |
| F5 — contrato `ISY_BACKEND/1` | `evidence/backends/gate_2026-11-01T082046Z.json` | `a4f608c` | `PASS` | c/rust/zig/pydecimal 213/213; cobol 147/213 con 66 `UNSUPPORTED` nombrados; 8 484 corridas diferenciales por backend y 1 270 de strings en los cuatro completos; `missing_toolchains: []`. stdout crudo sellado al lado: `gate_2026-11-01T082046Z_stdout.txt` |

**Hueco de F4 — CERRADO el 2026-11-01.** Existió así: F4 no se había re-corrido desde que
`conformance_v0.5` entró en `CORPORA`, así que su recibo más reciente (`ec6b823`) fijaba 170
casos, no 212; los 42 nuevos estaban cubiertos por F5, que incluye a C sobre los 212, pero
la vía de F4 con sanitizers (`gcc/sanitized`) no había corrido sobre ellos. Se cerró con
`python3 tools/c_gate.py` sobre el commiteado `422719a`, árbol limpio: **212/212 en las
cuatro combinaciones**, 0 `UNSUPPORTED`, 0 diferencias en las 31 080 corridas diferenciales
y los dos sabotajes detectados. El recibo anterior sigue siendo válido para el árbol que
fija; lo que cambió es el más reciente.

## Decisiones de CORE v0.5

| decisión | recibo | head | veredicto | qué fija |
|---|---|---|---|---|
| V1 (`len` en posición de i) | `evidence/v05_revalida/run_20261101T001608Z.json` | `dcd6880` | `RELEASE_GATE` | `401`–`406` contra `expected`, IR igual al gemelo, brazos viejo y nuevo |
| V2 (azúcar `for`) | el mismo recibo (`gemelos`, `no_regresion`) | `dcd6880` | `RELEASE_GATE` | traza `stmt` del `for` igual a la del `while` gemelo salvos `at`, y `pasos.azucar == pasos.gemelo` caso por caso; los valores **exigidos** (23/38/20) viven en `tests/test_v05_core.py:105` |
| V3, V4, V5 (léxico, parámetro reasignable, forma del `elem_type`) | `evidence/v05_spec/run_20261101T043007Z.json` | `a9a17bc` | `RELEASE_GATE` | 4 cabeceras del léxico; 11 formas del iterando; 4 programas a forma constante (24 pasos) con su control de forma (20) |
| V6 y V6-bis (`str` contextual) | `evidence/v05_v6/run_20261031T184709Z.json` | `f856d55` | `RELEASE_GATE` | 28 casos `411`–`438` diferenciales: 123 EQUIV, 17 `UNSUPPORTED` (COBOL por etiqueta), cero DIVERGENT |
| V7 (capacidades por contenido) | `evidence/v05_v7/run_20261031T200146Z.json` | `a66689c` | `RELEASE_GATE` | 118 módulos del corpus congelado en dos brazos, brazo viejo FIEL, conteos 113→125 en COBOL, canario `439` |
| Borrador normativo v0.5 | `evidence/v05_spec/run_20261101T153344Z.json` | `a4ef362` | `RELEASE_GATE` | las 6 matrices de aristas que el corpus no fija — las 5 de `run_20261101T043007Z.json` (`a9a17bc`, siguen válidas para su corrida) más la nueva del `let` sin anotación (§3, N3) |
| Censo y forma de P4 | `evidence/v05_p4/run_20261101T062234Z.json` | `52f5564` | `RELEASE_GATE` | 32 clones en 18/42 casos; curvas K, W², W³; control de 20 sitios → 1 clon; sin techo hasta 2048 |

## Preguntas y puntos nuevos

| id | estado | recibo o falta |
|---|---|---|
| P1 (`at` del azúcar) | cerrada | `evidence/v05_revalida/run_20261101T001608Z.json` + test `ForAzucar` |
| P2 (`for` sobre literal de arreglo) | cerrada: no | `evidence/v05_spec/run_20261101T153344Z.json` §4 |
| P3 (nombres e identidad) | cerrada | el mismo recibo §6 (`411`/`417`/`420`) + `tests/test_specialize.py` |
| P4 (cota de especializaciones) | **abierta — decisión, no medición** | base sellada en `evidence/v05_p4/run_20261101T062234Z.json`; falta elegir granularidad, número y el error nombrado |
| N1 (`for` sobre `str`) | abierta — decisión | medido en `evidence/v05_spec/…` §4; ningún caso del corpus lo fija |
| N2 (diagonal `0.5` de M4) | abierta — decisión | medido en `evidence/v05_spec/…` §1 (8 combinaciones); el corpus no cubre ningún cruce con raíz `0.5` |
| N3 (`let` sin anotación) | cerrada: por texto y por sonda | la regla estaba en `checker.py:205-209` y en el docstring; ya está en `spec/CORE_v0.5.md` §4.1 y medida en `evidence/v05_spec/run_20261101T153344Z.json` §3 (cuatro formas, tres sabotajes) |

## Evidencia de contexto (no es gate)

| directorio | qué | cuándo |
|---|---|---|
| `evidence/v05_propuesta/` | las mediciones que reordenaron v0.5 (diez → doce sitios de versión) | 2026-10-31, head `4688517` |
| `evidence/dogfood/` | `programs/dogfood/` contra los cinco backends y su pared de tiempo | 2026-10-30, head `b0daac5` |
| `evidence/textlib/` | la librería de texto que motivó V6/V6-bis (`pad`, `mayus`, desbordamiento) | 2026-10-31, head `e94bb84` |
| `evidence/human_guide/` | transcripción de una persona operando `GUIA.md` sin ayuda | 2026-10-30 |
| `evidence/inventory/` | inventario de `workspace/assembly` (solo lectura) y toolchains | 2026-10-28/29 |

## Afirmaciones que no son evidencia

Viven en `README.md`, `GUIA.md` y `tests/README.md`, y se re-producen con un comando — no
tienen recibo porque un recibo de ellas sería una foto de un día:

| afirmación | comando |
|---|---|
| «167 tests OK» y el tiempo de la suite | `python3 -m unittest discover -s tests` |
| «sha256sum -c de `docs/origin/` coincide» | `sha256sum -c docs/origin/SHA256SUMS.txt` desde la raíz del repo |
| conteos de `SUPPORTED`, llamadas a `has()` y sitios de versión | `grep -n` de `spec/CORE_v0.5.md` §0, fijados como test en `tests/test_versions.py` |

## Auditoría 2026-11-01

Qué encontró esta matriz al cotejar prose contra recibos:

1. **El censo de P4 no estaba en ningún recibo.** `V6_CONTEXTUAL_STR.md` y
   `V6B_CONTEXTUAL_RETURN.md` atribuían «22 clones» y «28 clones, máximo 2 por definición»
   a `evidence/v05_v6/run_*`, y esos recibos solo guardan el resultado de cada backend
   por caso. Medido desde el instrumento (`Checker.specs`): **32** clones en 18 de los 42
   casos, 26 V6 + 6 V6-bis, máximo 4 por programa, 2 por definición **dentro de un
   programa** pero **7 de `doble` en todo el corpus**. Las dos secciones y `ROADMAP.md`
   llevan la corrección fechada; el dato nuevo está sellado arriba.
2. **Contar la población equivocada.** El primer censo usaba `glob("4*.isy")` y perdía los
   tres casos con módulos (`408`, `421`, `440`) — `421` es justo el de `util.marca.3` y
   `util.marca.4`. La sonda ahora itera `load_corpus`, la misma población del gate. Es el
   mismo clase de bug de deriva de población que V7 ya había cazado con el «corpus
   congelado» de 118.
3. **F4 con 170 mientras F5 tiene 212.** No era un error: era un gate que no se re-corré.
   Quedó escrito arriba en vez de suponerse, y **se cerró el mismo día** con 212/212 en las
   cuatro combinaciones (arriba, «Hueco de F4»). Lo que sí quedaba abierto —que este gate no
   tenía cifra atada a la suite— **se cerró el 2026-11-01**: `DocsMatchLatestEvidence` ya no
   se detiene en `conformance/`, `ir/` y `backends/`; `test_c_gate_figure`
   (`tests/test_evidence.py`) lee `latest("c", "gate_")`, exige `verdict=PASS`, cero fallos,
   cero `UNSUPPORTED` y las tres vías completas en cada combinación presente, exige cero
   diferencias en el diferencial y que los dos sabotajes se detecten, y reclama que el README
   cite la **población** del recibo más nuevo. Su primera mordida fue real y documentada: con
   `443` en el corpus el README seguía diciendo «sobre los 212» y el gate decía 213, así que
   la prueba enrojeció sola — es el control negativo, sin tocar ninguna evidencia.
4. **La segunda pasada encontró su propio fallo.** La fila «techo encontrado» de
   `docs/OPEN_QUESTIONS_P1_P4.md` decía «474 ms de referencia, 3,7 s de `c_ms`» citando el
   recibo `v05_p4`, y el recibo dice `ref_ms=508,7` y `c_ms=1037,0`: lo escribí de memoria
   tras la corrida sin re-leer el JSON. Corregido allí mismo con nota fechada. Es el
   hallazgo 1 reproduciéndose a sí mismo, y por eso el cotejo es un paso de la matriz, no
   una confianza: la fila nueva cita bytes y milisegundos exactos del `costo`.

5. **Renumerar la sonda rompe las citas a los recibos sellados.** Al meter la matriz del
   `let` como sección 3, las secciones viejas 3/4/5 pasaron a 4/5/6, y varias filas del docs
   citaban «`run_20261101T043007Z.json` §4» con la numeración nueva: apuntaban al recibo
   viejo, donde §4 es *pasos a forma constante* y no *el iterando*. Arreglado moviendo la
   cita al recibo que sí tiene esa numeración (`run_20261101T153344Z.json`). De paso la
   re-sello sirve de control de no-regresión sobre la propia sonda: comparando los dos
   `.txt` sección por sección (mismo script, mismo día), las cinco matrices viejas salen
   **byte a byte iguales** sobre los cabezales `a9a17bc` → `a4ef362`, y la sexta es la nueva.
   Un sello no es una foto inmóvil: re-correr la sonda y obtener lo mismo es parte del
   control.

Nada de lo anterior cambia un `expected`, un hash congelado ni un resultado de gate: son
correcciones de *atribución* (una cifra que no tenía recibo) y una re-medición.
