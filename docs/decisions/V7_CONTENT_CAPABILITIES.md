# Decisión V7 — capacidades por contenido del programa, no por etiqueta de schema (2026-10-31)

**Decisión:** `UNSUPPORTED` tiene que señalar una capacidad que **este programa exige**.
`features_of(módulo)` (`isyco/backends/base.py:96`) deja de leer la cabecera: pasa a ser
`PROGRAM_REQUIRES`, calculado caminando tipos bajados y sentencias. El número de schema
queda para lo que realmente describe —`SCHEMA_CAN_EXPRESS`, lo que el contenedor puede
representar— y deja de ser una capacidad.

Nace de la fila V7 de `spec/CORE_v0.5_propuesta.md` y de la corrección §8: la librería de
texto se escribe en `0.5`, y mientras la etiqueta decida, cualquier programa 0.3+ es
`UNSUPPORTED` en COBOL aunque no use una sola característica 0.2. COBOL es el canario
precisamente porque es el único backend instalado que declara no saber nada de 0.2.

## Las dos preguntas separadas

| pregunta | dónde vive | ejemplo |
|---|---|---|
| `SCHEMA_CAN_EXPRESS` | `module["schema"]` | `442_nucleo_03_sin_str` baja con `isy-ir/0.2` |
| `PROGRAM_REQUIRES` | `features_of(module)` | el mismo programa pide `{bool, calls, emit, int64, ovf:trap, while}` — cero 0.2 |

Regla concreta: `ir0.2` solo se añade si el contenido usa `str` o `struct`, que son los
únicos tipos que no caben en `isy-ir/0.1` (`ir_validate._has_v2_type`). Es la misma
relación que ya aplicaba el validador para *aceptar* el módulo; ahora la aplica el contrato
de backend, así que no hay dos criterios.

## El átomo nuevo: `emit_array`

Emitir un arreglo es una relajación de CORE v0.3, no un tipo 0.2. COBOL no lo implementa —
el emisor revienta con `AttributeError: 'ArrT' object has no attribute 's'`— y hasta V7 ese
hueco estaba tapado por la etiqueta, que respondía `ir0.2` (una capacidad que el programa no
pedía). Se añade el átomo para que el `code` de `UNSUPPORTED` diga la verdad:
`253_emit_array` → `emit_array`, `441_emit_arreglo_v03` → `emit_array`.

**No es un parche cosmético, y se midió.** Regalando la capacidad a COBOL
(`features | {"emit_array"}`) los dos casos siguen sin coincidir: `BUILD_FAIL` con el mismo
`AttributeError`. Un átomo que, al concederlo, hubiera dado `EQUIV` no nombra nada; este
nombra un hueco real. `tools/v7_capability_probe.py` → sección 4 del recibo.

## El bug que la etiqueta ocultaba (arreglado en el emisor, no declarado como capacidad)

`327_qualified_call_stmt` bajaba a IR sin `str` ni `struct`, así que con la puerta abierta
llegaba al emisor y `cobc` lo rechazaba: `LS-RET no está definido`. Causa real: el resultado
viaja como último argumento por referencia, y el hueco `{prefijo}RET` solo se declaraba si la
función retornaba algo; pero el proemio y el epílogo escriben su conteo de profundidad en
ese mismo hueco aunque la función sea `void`, y una llamada en posición de sentencia pasa un
destino igualmente. Se arregló `isyco/backends/cobol.py:907` declarando el hueco siempre.

Es un defecto **previo y alcanzable fuera de v0.5**: `isyco 0.1` con `fn f() { }` y `f();`
lo dispara (canario `439`, capacidades `{calls, emit, int64, ovf:trap}`, sin `ir0.2`). La
alternativa tentadora —declarar «COBOL no sabe llamadas void»— habría sido una capacidad
inventada para tapar un bug, exactamente lo que el contrato de este repo prohíbe.

## Corpus

Canarios V7 en `programs/conformance_v0.5/`, con `expected` escrito a mano **antes** de
tocar `isyco/` (rito `AGENTS.md` §5). La predicción falló en un punto y se corrigió el
programa, no el motor: `emit` llama a `typeof(expr, None)`, así que un literal suelto en
posición de emisión es `AMBIGUOUS_LITERAL` **en cualquier versión**; los canarios emiten
locales tipados.

- `439_void_en_sentencia` (`isyco 0.1`): forma del bug de COBOL → `HALTED`, emite `7`.
- `440_llamada_calificada_void` (módulos, `0.4`): llamada calificada void + `emit` → `99`, `1`.
- `441_emit_arreglo_v03` (`0.3`): `emit` de un arreglo → `["[\"4\",\"-5\"]\"]`; en COBOL
  `UNSUPPORTED(emit_array)`, no `ir0.2`.
- `442_nucleo_03_sin_str` (`0.3`, `while` + función + bool): el caso central —etiqueta 0.2,
  contenido sin 0.2 → `HALTED`, emite `6`.

Pruebas: `tests/test_backends.py:ContenidoNoEtiqueta` (7) fija la separación etiqueta/
contenido, que el `code` diga la capacidad exacta, que los cuatro canarios coincidan en
COBOL, y **la medición completa**: `(60, 46)` sobre el corpus congelado. Suite: 138 OK.

## Medición

`tools/v7_capability_probe.py` (recibo `isyco.evidence/0.1`; sección 1 del recibo). Dos
corridas con el mismo `corpus_hash` `b446fea8bf5e…` sobre los mismos 118 módulos:
`evidence/v05_v7/run_20261031T194109Z.json` (`EVIDENCE_ONLY`, árbol sucio) y
`evidence/v05_v7/run_20261031T200146Z.json` (`RELEASE_GATE`, HEAD `a66689c`, árbol limpio).

- Corpus congelado (170 casos, 114 bajan a IR): **60** llevan `isy-ir/0.2`, **46** usan `str`
  o `struct`, **14** pedían `ir0.2` por pura etiqueta.
- Con los canarios: 63 por etiqueta / 46 por contenido / 17 solo por etiqueta.
- **A quién le cambia:** solo a COBOL. `c`, `rust`, `zig` y `pydecimal` declaran `ir0.2`,
  `str`, `struct` y `emit_array`, así que sus capacidades no dependen de la etiqueta
  (UNSUPPORTED 0 → 0 en cada uno). COBOL: 63 → 48 en esta población.

**Nota 2026-11-01:** «congelado» es la población de estos recibos —los cuatro corpus anteriores
a v0.5, 170 casos, `corpus_hash` `b446fea8…`— y **no** `CORPORA`, que desde `57f38bc` tiene 212.
La sonda y la suite nombran la población a propósito (`FROZEN` + `cargar_congelado()` en
`tools/v7_capability_probe.py:55,144`, `CONGELADO` en `tests/test_backends.py:31`) para que
ensanchar el gate no reescriba estos números: con los 212 actuales dan 90 por etiqueta / 66 por
contenido, y eso queda registrado en el docstring del test, no aquí.

El brazo viejo no es un espantajo: se lee el `features_of` real del commit previo
(`git show f856d55:isyco/backends/base.py`), se ejecuta en el mismo proceso y se compara
contra la simulación caso por caso — **FIEL en los 118 módulos**, cero divergencias. Con eso
la comparación brazo-a-brazo es contra el código que corría, no contra una caricatura.

Brazo a brazo sobre los 17 casos solo-etiqueta (ejecutados en COBOL, caché de compilación
separada por brazo):

| brazo | clasificación |
|---|---|
| etiqueta (pre-V7) | 17 `UNSUPPORTED(ir0.2)` |
| contenido (V7) | **15 EQUIV** (status, code, emits, return **y pasos** iguales a la referencia) + 2 `UNSUPPORTED(emit_array)` |

Gate F5 de COBOL re-corrido (`tools/backend_gate.py --only cobol`): **113 → 125** de 170,
UNSUPPORTED **57 → 45**, cero fallos, 8 484 corridas diferenciales sin diferencias,
`does_the_work` `True`, los dos sabotajes detectados. Dos corridas, mismo resultado:
`gate_2026-10-31T193053Z.json` (sha `7bd113bf…`, árbol de V7 aún sin commitear — el recibo
del gate no registra suciedad, así que vale como EVIDENCE_ONLY) y
`gate_2026-10-31T200602Z.json` (sha `f24c8f0c…`, `git_head` = `a66689c`, árbol limpio:
el RELEASE_GATE). Los 12 recuperados son
`119, 248, 264, 301, 313, 314, 318, 321, 324, 326, 327, 328`; `253` sigue sin cubrirse pero
ahora con el nombre correcto (`emit_array` en vez de `ir0.2`), y `254_lvalue_order` pasa de
`ir0.2,struct` a `emit_array,ir0.2,struct`. `322_header_v05` aparece como recuperado en el
brazo pero nunca estuvo en la lista del gate: con `0.5` declarado (V6) dejó de ser
`INVALID_PROGRAM` y lo resuelve el frontend compartido, no las capacidades.

## Control anti-fake

- **Nunca BUILD_FAIL → UNSUPPORTED.** El brazo `contenido` clasifica `BUILD_FAIL` por
  excepción real y la registra; los 15 EQUIV no pasan por ahí. Y el camino inverso también
  se cerró: `UNSUPPORTED` de COBOL sobre 441/253 es una capacidad exigida, no una excusa.
- **Un vacío no se vende como cobertura.** Los sabotajes de COBOL sobre la población recuperada se
  declaran `NO_MIDE_EN_ESTA_POBLACION` y se remiten al gate: `half_even_as_half_up` no tiene
  ningún caso con `dec`, y `div_floor` tiene uno solo (`314`), cuyos operandos reales son
  `10/2` —exacto, así que trunc y floor coinciden— y `1/0`, que trampa antes de producir
  valor. VACÍO declarado, no vendido como cobertura.
- **El engine hace el trabajo.** Variante sobre `442`: `while k < 3` → `while k < 4`
  convierte el `emit` de COBOL en `12`, igual que la referencia, y `DISPLAY "12"` no está
  escrito en el fuente generado (se arma en el bucle). Variante sobre `248`: `b[0] = 5` →
  `b[0] = 1` mueve el segundo `emit` de `false` a `true`. El control de literales para el
  caso booleano se declara `NO_APLICABLE`: el preámbulo del runtime de COBOL ya escribe
  `"true"`/`"false"` al formatear, así que buscar la salida en el fuente no distingue un
  valor calculado de uno escrito.
- **La medición no se autoinfla:** la sonda devuelve 1 y **no sella** si algún recuperado
  diverge, si los pasos no coinciden, si el brazo viejo no es fiel, si regalar `emit_array`
  diera `EQUIV` o si las variantes no mueven la salida.

## Lo que V7 NO hace

No añade ninguna capacidad a COBOL: los 46 programas que sí usan `str`/`struct` siguen
`UNSUPPORTED`, ahora por la razón cierta. No toca el frontend ni la semántica —el intérprete
de referencia sigue siendo la semántica normativa (`AGENTS.md` §4)— y no cambia la IR: los
mismos 60 módulos conservan su `schema`.

## Claims

| claim | estado | dónde |
|---|---|---|
| La etiqueta decidía `UNSUPPORTED` sin que el programa pidiera nada | **DEMONSTRATED** | 60 vs 46 medidos sobre el corpus congelado; los 14 nombres están en el recibo |
| Con capacidades por contenido, esos programas ejecutan y coinciden en COBOL | **DEMONSTRATED** | 15 EQUIV con pasos, brazo a brazo en la misma corrida (`tools/v7_capability_probe.py`) |
| `emit_array` nombra un hueco real de COBOL | **DEMONSTRATED** | regalar la capacidad da `BUILD_FAIL` (`AttributeError`), no `EQUIV` |
| La llamada void en sentencia era un bug del emisor, no una capacidad ausente | **DEMONSTRATED** | reproducible en `isyco 0.1` (`439`), arreglado en `cobol.py:907`, `327` coincide |
| Ningún otro backend cambia su dominio | **DEMONSTRATED** | UNSUPPORTED 0 → 0 en c, rust, zig y pydecimal (aritmética de conjuntos sobre 118 módulos) |
| El dominio declarado de COBOL sube de 113 a 125 de 170 sin divergencias | **DEMONSTRATED** (RELEASE_GATE) | `gate_2026-10-31T200602Z.json` (sha `f24c8f0c…`, HEAD `a66689c`, árbol limpio), que reproduce `gate_2026-10-31T193053Z.json`; sonda `run_20261031T200146Z.json` con `veredicto_arbol=RELEASE_GATE` |
| COBOL puede imprimir arreglos | **NOT_DEMONSTRATED** a propósito | es el hueco que el átomo declara |

## Deriva de citas (2026-11-01)

`features_of` es hoy `isyco/backends/base.py:97` (arriba se citó `:96`) y sus dos reglas
siguen en `:130` (`emit_array`) y `:134` (`ir0.2`). El conjunto de COBOL no está escrito a
mano en la clase: es `FEATURES = ALL_FEATURES - V03_FEATURES` (`isyco/backends/cobol.py:41`)
con `V03_FEATURES = frozenset({"ir0.2","str","struct","emit_array"})` (`base.py:43`). La
línea `:1504` que citan los documentos de V6 y V6-bis es hoy `class CobolBackend`. Lo que
está medido no cambia; se comprueba con `grep -n 'def features_of' isyco/backends/base.py`.
