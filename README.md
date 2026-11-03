# ISyCoLang

**Un lenguaje de programación con semántica propia y múltiples backends verificables.**

ISyCoLang define el comportamiento de sus programas en un intérprete de referencia, baja el código a una representación intermedia canónica (**ISY-IR**) y permite ejecutarlo mediante distintos backends. Un backend no decide qué significa el programa: debe reproducir el contrato común o declarar la capacidad que no soporta.

`.isy` → lexer/parser → tipos y efectos → ISY-IR → intérprete IR / C / Rust / Zig / Python `decimal` / GnuCOBOL.

**Estado (3 de noviembre de 2026):** `EXECUTABLE` dentro de los dominios y corpus medidos. Las especificaciones v0.1–v0.4 están congeladas; el engine ya implementa decisiones de v0.5, pero `spec/CORE_v0.5.md` sigue en **BORRADOR**, no es una especificación congelada. No hay aquí una afirmación de soporte universal ni de paridad fuera de los casos medidos.

**Acceso:** repositorio **privado**, sin licencia publicada ni autorización de distribución pública. Hay información de infraestructura e identidad en el historial/recibos; antes de publicar se debe resolver `docs/PUBLICACION.md`. No cambiar la visibilidad ni reescribir la evidencia sellada para mejorar la apariencia del README.

## Inicio rápido

Desde la raíz de este repositorio, con Python 3 y el código ya disponible:

```bash
python3 -m isyco run precio.isy --input '["19.99","3"]'
python3 -m isyco ir precio.isy
python3 -m isyco run precio.isy --input '["19.99","3"]' --via c
```

El primer comando usa `--via ast` (intérprete de referencia, opción predeterminada). Para el ejemplo, la guía registra `status=HALTED`, emisiones `23.19`, `46.38`, `69.57`, y retorno `69.57`. El segundo imprime ISY-IR; el tercero compila y ejecuta mediante C, siempre que el toolchain esté instalado.

También puedes usar `--via ir`, `--via rust`, `--via zig`, `--via pydecimal` o `--via cobol`. **No todos los backends implementan todas las capacidades:** cuando el programa requiere una capacidad ausente, el contrato exige `UNSUPPORTED`, no una simulación silenciosa. La ruta por COBOL necesita GnuCOBOL, la ruta Zig necesita Zig, etc.; no se proporciona aquí un instalador de toolchains.

**Para aprender la sintaxis y los resultados:** [GUIA.md](GUIA.md). **Semántica:** [spec/](spec/README.md). **Contrato de backends:** [spec/BACKEND.md](spec/BACKEND.md).

## Lenguaje y arquitectura

- **Formatos y versiones.** Código UTF-8 en `.isy`; la cabecera `isyco 0.1` … `isyco 0.5` selecciona las reglas. Las versiones antiguas conservan su comportamiento documentado.
- **Tipos y efectos.** Enteros con políticas explícitas de desbordamiento, decimales con escala/redondeo, `bool`, arreglos, funciones, efectos `!emit`; desde v0.3, strings ASCII acotados y structs; desde v0.4, módulos e imports.
- **v0.5 en el engine.** `len` para arreglos, `for` sobre lugares/arreglos/strings según sus reglas, y especialización contextual acotada de parámetros/retornos `str`. El límite P4 es de **256 resoluciones por definición fuente**; la siguiente debe dar `INVALID_PROGRAM/SPEC_LIMIT`.
- **Referencia y lowering.** `isyco/` alberga lexer, parser, comprobador de tipos, intérprete y bajada a ISY-IR; `isyco/backends/` contiene los ejecutores. La comparación obliga a conservar `status`, `code`, `emits`, `return` y `steps` dentro del dominio declarado.
- **Investigación separada.** El carril **3OPS Lab** y los posibles backends futuros (p. ej. Prolog, Fortran o esolangs) son líneas del roadmap, **no** implementaciones verificadas en este repositorio.

## Resultados respaldados por recibos

Estos números son **resultados de corridas selladas en los commits indicados en los recibos**, no una ejecución independiente sobre el HEAD actual ni una demostración de equivalencia para todos los programas posibles.

| Gate / alcance | Resultado registrado | Recibo |
|---|---|---|
| F2 · referencia vs expected | **218/218** casos de los corpus v0.1–v0.5 | [F2](evidence/conformance/run_2026-11-03T003813Z.json) |
| F3 · ISY-IR vs referencia | **436/436** comparaciones iguales; **149** programas bajados a IR (otros rechazos se cotejan como rechazo) | [F3](evidence/ir/gate_2026-11-03T003813Z.json) |
| F4 · C en gcc/clang, normal y sanitizado | Tres vías (expected ↔ referencia ↔ binario) **sobre los 218** casos en cada una de las cuatro combinaciones; 0 diferencias reportadas y controles saboteados detectados | [F4](evidence/c/gate_2026-11-03T003814Z.json) |
| F5 · C, Rust, Zig, pydecimal | **219/219** por backend; **8 484** corridas diferenciales numéricas y 1 270 de strings por backend, sin diferencias reportadas | [F5](evidence/backends/gate_2026-11-03T040610Z.json) |
| F5 · COBOL en su dominio numérico | **148/219**, con **71 `UNSUPPORTED`** explícitos, 0 discrepancias reportadas y **8 484** corridas diferenciales numéricas sin diferencias | [F5](evidence/backends/gate_2026-11-03T040610Z.json) |

**Importante:** el gate F5 usó **218 casos del corpus + 1 caso adicional con `--extra-case`**; el corpus formal sigue siendo de 218, no 219. Una coincidencia de rechazo del **frontend** (por ejemplo `INVALID_PROGRAM/SPEC_LIMIT`) puede contar como caso conforme: **219/219 no significa 219 programas compilados en binarios**. `UNSUPPORTED` es el rechazo previsto fuera del dominio de COBOL, **no** un caso aprobado como ejecución equivalente. Los gates incluyen controles con fallos inyectados y `does_the_work`, pero eso valida el alcance de sus pruebas, no todas las entradas futuras.

La [matriz de evidencia](docs/EVIDENCE_MATRIX.md) distingue gates `RELEASE_GATE` / `EVIDENCE_ONLY`, versiones de árbol y contraejemplos. La [claim table y los planes](ROADMAP.md) conservan afirmaciones no demostradas.

## Límites conocidos y trabajo pendiente

1. **Profundidad del frontend (Z2):** la [sonda sellada](evidence/z2_depth/run_2026-11-03T074629Z.json) encontró `RecursionError` con cadenas de expresiones profundas. En el host medido (Python 3.12.3, límite de recursión 1000), la forma con especialización contextual pasó con 241 términos y falló con 242; dos formas sin ese clon pasaron con 329 y fallaron con 330. **Son fronteras observadas dependientes del proceso, no límites normativos del lenguaje.** El error aún no se convierte sistemáticamente en un rechazo controlado.
2. **Compilación Zig (Z1):** una familia legal antes fallaba por presupuesto de evaluación `comptime`. El emisor se corrigió y la [sonda Z1](evidence/z1_ceiling/run_2026-11-03T035753Z.json) y F5 muestran que los casos medidos ahora compilan; **esto no prueba ausencia de nuevos fallos de compilador**.
3. **Conformidad acotada:** el corpus, los pares diferenciales y los sabotajes no agotan el espacio de programas/entradas, plataformas ni variantes de toolchain. No se afirma ventaja general de rendimiento ni equivalencia formal universal.
4. **v0.5 todavía en borrador.** Implementar decisiones y pasar gates no equivale a congelar el texto normativo.
5. **Publicación pendiente:** el historial y algunos recibos contienen datos del host o metadata de autor. El repositorio permanece privado; ver `docs/PUBLICACION.md`.

## Cómo verificar sin confundir evidencia con tests nuevos

```bash
python3 -m unittest discover -s tests -v
sha256sum -c docs/origin/SHA256SUMS.txt
```

La suite comprueba también el contenido de `evidence/*/SHA256SUMS.txt` y la coherencia de ciertas cifras de este README con los recibos. **La existencia de esos tests no significa que se hayan ejecutado en esta revisión del README.** Los gates que generan recibos escriben archivos nuevos en `evidence/` y actualizan sus listas SHA-256: ejecutarlos deliberadamente y con el árbol controlado; para ensayos, usar `ISYCO_EVIDENCE_ROOT` según [GUIA.md](GUIA.md). No modificar recibos sellados.

## Referencia del repositorio

### Mapa de archivos

```text
ROADMAP.md                         fases F0–F9 + carril 3OPS Lab, con gates
docs/FEASIBILITY_2026-10-28.md     estudio de viabilidad (por qué esta arquitectura)
docs/origin/                       roadmap V0 y estándar, preservados con SHA-256
tools/inventory_assembly.py        inventario de solo lectura de workspace/assembly
evidence/inventory/                salidas del inventario y de toolchains
spec/CORE.md                       semántica v0.1 congelada (+ ERRATA_v0.1.md)
spec/CORE_v0.2.md … CORE_v0.4.md   cambios congelados de v0.2, v0.3 (str<N>, structs) y v0.4 (módulos)
spec/CORE_v0.5_propuesta.md        propuesta V1–V7 (2026-10-30) con sus correcciones fechadas
spec/CORE_v0.5.md                  texto normativo de v0.5 — BORRADOR, sin congelar ni sellar
spec/IR.md                         forma de ISY-IR v0.1 y v0.2 (lo que reciben los backends)
GUIA.md                            guía para personas: escribir, correr y leer un resultado
spec/BACKEND.md                    contrato ISY_BACKEND/1 (capacidades, protocolo, conformidad, costo)
docs/decisions/                    decisiones registradas (p. ej. no reusar Code IR)
docs/OPEN_QUESTIONS_P1_P4.md       qué respondieron P1–P4 —P4 cerrada 2026-11-02— y qué abrió: Z1 y Z2
docs/EVIDENCE_MATRIX.md            qué está sellado, con qué árbol, y qué afirmación no tiene recibo
docs/BACKEND_C.md                  backend C: garantías, protocolo, límites
docs/PUBLICACION.md                qué información sensible lleva la historia y qué falta antes de publicar
isyco/backends/base.py             driver común: validación, capacidades, caché, ejecución
isyco/backends/c.py                ISY-IR -> C -> binario nativo
isyco/backends/rust.py             ISY-IR -> Rust -> binario nativo
isyco/backends/zig.py              ISY-IR -> Zig -> binario nativo
isyco/backends/cobol.py            ISY-IR -> GnuCOBOL -> binario nativo (núcleo numérico)
isyco/backends/pydecimal.py        ISY-IR -> Python 3 con `decimal` (ola 2: otro sustrato, mismo contrato)
isyco/versions.py                  única fuente de la versión: SUPPORTED, INTRODUCED, has()
isyco/specialize.py                V6/V6-bis: las copias acotadas de una definición `str` pelado
isyco/modules.py                   enlazado de módulos (v0.4) y la regla «misma versión que la raíz»
isyco/difftest.py                  diferencial por tipo numérico en valores frontera
isyco/harness.py                   la guarda del arnés: un fallo del instrumento es dato, no abort
isyco/                             intérprete de referencia y CLI
programs/conformance/              corpus v0.1 (expected previos al intérprete; SUPERSEDED.json)
programs/conformance_v0.2/         corpus v0.2 (expected previos a implementar v0.2)
programs/conformance_v0.3/         corpus v0.3 (strings y structs)
programs/conformance_v0.4/         corpus v0.4 (módulos)
programs/conformance_v0.5/         corpus v0.5 (401–448, decisiones V1–V7; censo P4: 48 casos) + gemelos
programs/dogfood/                  programas que Danny quiere escribir; fuera del gate, miden dolor real
tests/                             conformidad, determinismo, sabotaje, oráculo
tools/_gate.py                     capa compartida de los gates: head, sello, árbol, sums, sellado
tools/run_conformance.py           corre el corpus y guarda evidencia nueva
tools/ir_gate.py                   compara IR vs referencia y guarda evidencia
tools/c_gate.py                    gate F4 (tres vías, gcc/clang, sanitizers, sabotaje)
tools/c_sanitize_v03.py            backend C con UBSan+ASan sobre v0.3 (corpus + strings)
tools/backend_gate.py              gate F5 (corpus, capacidades, diferencial, stub) por backend
tools/warm_build_cache.py          precompila en paralelo los binarios del corpus y diferenciales
tools/v05_proposal_probe.py        qué dice el core HOY del corpus y los gemelos de la propuesta
tools/v05_revalida_probe.py        revalidación de V1 y V2: tres vías, gemelos, no regresión
tools/v05_v6_probe.py              diferencial de V6/V6-bis: referencia, IR ida y vuelta, backends
tools/v05_spec_probe.py            aristas que `spec/CORE_v0.5.md` afirma y ningún caso fija
tools/v05_p4_probe.py              censo de clones (P4), costo y frontera de Zig (Z1)
tools/v7_capability_probe.py       V7: capacidades por contenido vs por etiqueta, con brazo viejo
tools/textlib_probe.py             ¿librería de texto hoy? tres vías sobre `programs/dogfood/`
tools/dogfood_wall_probe.py        el «muro de cabecera» del dogfood: víctimas de la etiqueta o del programa
tools/f5_harness_probe.py          mide la guarda del arnés: el zig que rompe su comptime
tools/z1_ceiling_probe.py          techo de comptime de Zig (Z1): cuota, sabotajes y controles
tools/z2_depth_probe.py            techo de profundidad del frontend (Z2): dos fronteras y quién las paga
```

### Gates y comandos avanzados

```bash
sha256sum -c docs/origin/SHA256SUMS.txt
python3 tools/inventory_assembly.py            # escribe un JSON nuevo con timestamp
python3 -m unittest discover -s tests -v       # suite; recuento y duración dependen del árbol/toolchains
python3 -m isyco ir programa.isy               # ISY-IR canónica
python3 tools/ir_gate.py                       # gate F3 + evidencia nueva
python3 tools/c_gate.py                        # gate F4 + evidencia nueva (varios minutos)
python3 tools/backend_gate.py                  # gate F5: C, Rust, Zig, pydecimal y cobol + evidencia nueva
python3 tools/backend_gate.py --extra-case caso.isy   # …y un caso fuera del corpus
python3 tools/f5_harness_probe.py              # mide la guarda del arnés (--write sella)
python3 tools/run_conformance.py               # corpus + evidencia nueva
python3 tools/v05_spec_probe.py                # aristas del borrador v0.5: mide y reporta
python3 tools/v05_spec_probe.py --write        # …y sella en evidence/v05_spec/ (árbol limpio = RELEASE_GATE)
python3 tools/v05_p4_probe.py                  # censo (P4): K, W2, W3, costo y techo de toolchain
python3 tools/v05_p4_probe.py --bisect-zig --write   # …+ frontera de Zig (Z1), y sella en evidence/v05_p4/
python3 tools/z1_ceiling_probe.py --write          # …y sella la frontera de Zig re-medida (Z1)
python3 tools/z2_depth_probe.py --write            # …y sella la frontera de profundidad (Z2)
```

### Relación con el monorepo

Los backends candidatos viven en `~/Development/ISyCo/workspace/assembly`
(copias; fuente de verdad en `~/Development/ISyCo Git/<Repo>`). Este repo los
lee, no los modifica. Se rige por `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`.
