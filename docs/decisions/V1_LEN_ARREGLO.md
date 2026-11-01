# Decisión V1 — `len` de un arreglo lo resuelve el frontend (2026-10-31)

**Decisión:** `len(a)` con `a: [T; N]` devuelve `N` con tipo `i64`, y el `N` lo pone el
**frontend en el AST** (`isyco/checker.py:37` `static_len`, llamado en `checker.py:102-105`).
No es una operación nueva: no hay nodo en la IR, no hay capacidad en `features_of`, no hay
backend que tocar. Es la fila V1 de `spec/CORE_v0.5_propuesta.md` §2, en la opción que el
propio borrador adoptaba —el mismo movimiento que CORE v0.4 hizo con los imports: frontend,
IR `isy-ir/0.2` intacta.

Nace del dogfood: la librería de texto (`programs/dogfood/06_biblioteca_texto.isy`) recorre
arreglos y hoy no puede escribir la cota sin copiar la capacidad a mano en cada sitio.

## La regla, en dos partes

| dónde | qué hace |
|---|---|
| `checker.py:323-333` (`_typeof`, rama `A.Len`) | con cabecera `0.5`, `len` de un `ArrT` es `i64`; sin `0.5` sigue siendo `TYPE_MISMATCH` |
| `checker.py:37` (`static_len`) | después de chequear, cada `Len` cuyo `expr.ty` es `ArrT` se reemplaza por `IntLit(at, N)` con `ty = i64` y `val = N` |

Que el reemplazo vaya **después** del chequeo no es un detalle: el checker ya decidió el tipo
con la regla de arriba, así que el literal sintético carga exactamente lo que `int_literal`
habría anotado con `expected = i64`. Y se aplica sobre las funciones que sobreviven al chequeo
—las copias de V6 incluidas—, no sobre las definiciones `str` pelado que nunca se ejecutan.

El reemplazo camina listas y las tuplas `(nombre, expr, at)` de un literal de struct, así que
`Par { x: len(xs), ys: [...] }` también queda resuelto (test `test_dentro_de_un_literal_de_struct`).

## Corpus

`401_len_arreglo` y `406_len_parametro`, con `expected` escrito a mano **antes** de tocar
`isyco/` (rito `AGENTS.md` §5). Estaban en el corpus desde la propuesta y no pasaban: la
referencia respondía `INVALID_PROGRAM(TYPE_MISMATCH)`.

## Medición

`tools/v05_revalida_probe.py --casos 401,406` (recibo `isyco.evidence/0.1`), sellado dos
veces con los mismos números: `run_20261031T210001Z` con el árbol de trabajo sucio
(`veredicto_arbol=EVIDENCE_ONLY`) y `run_20261031T210258Z` ya con `HEAD` en el commit de V1
y `git status` vacío (`RELEASE_GATE`, `arbol_sucio_codigo=false`, `git_head=8c230aa`). Los
recibos del gate de backends no llevan campo de suciedad, así que la etiqueta la escribe la
sonda y por eso la primera corrida no se cita como release.

- **Tres vías:** los dos casos coinciden en `expected` ↔ referencia ↔ los cinco backends
  instalados (`c`, `cobol`, `pydecimal`, `rust`, `zig`): 10 EQUIV, cero DIVERGENT, cero
  BUILD_FAIL, cero UNSUPPORTED. Los `steps` del backend son los de la referencia (6 y 27).
- **Estático de verdad:** con la capacidad escrita a mano (`len(a)` → `6`) el programa gasta
  **los mismos pasos**: 6 = 6 y 27 = 27 (`programs/conformance_v0.5/gemelos/` hace lo mismo
  para V2). Si `len` fuera una operación, el conteo se movería.
- **La IR no gana nodos:** `401` y `406` bajan con **cero** nodos `{"k": "len"}`; el control
  positivo (`len(s)` de v0.3 sobre un `str<8>`) baja con **uno**. El `len` del arreglo aparece
  como `{"k": "const", "v": "5"}` con `ty` `int<64>`.
- **Ninguna capacidad nueva:** `features_of` de 401 es `{arrays, calls, emit, int32, int64,
  ovf:trap}` y la de 406 `{arrays, bool, calls, int32, int64, ovf:trap, while}` — ni `ir0.2`
  ni `emit_array`; COBOL los ejecuta (V7 ya había abierto esa puerta).
- **No regresión:** la misma fuente recabezada a versiones anteriores sigue rechazada, y por
  la razón de cada época: `0.1`/`0.2` → `UNKNOWN_NAME` (ahí `len` ni siquiera es palabra
  clave: llega como una llamada desconocida), `0.3`/`0.4` → `TYPE_MISMATCH` (`len` existe y
  es de strings). Cero programas existentes cambian de significado.

## Control anti-fake

- **Brazo viejo, apagando la regla de verdad:** se parcha `checker.has` para que
  `("0.5", "v05")` devuelva `False` — el estado exacto previo — y los dos casos vuelven a
  `INVALID_PROGRAM(TYPE_MISMATCH)`. Si hubieran ejecutado, el EQUIV de arriba sería vacuo:
  las sonda imprime `CONTROL FALSO` y **no sella** (exit 1) en ese caso.
- **El valor viene del tipo, no de la sonda:** cambiar la capacidad declarada mueve la salida
  y estaba predicho a mano — `[i32; 5]` → `[i32; 6]` da `emits=["6"]`, y `[i32; 6]` → `[i32; 7]`
  da `return="28"` (1+…+7) con 30 pasos.
- **La sonda se prueba contra sí misma:** con `--casos 402` (V2 todavía sin implementar)
  reporta `CONTROL FALSO: la referencia rechaza un caso que debe ejecutar` y devuelve 1 sin
  escribir evidencia.
- **La cota no se estrecha:** `let n: i8 = len(xs)` es `TYPE_MISMATCH`, igual que `len(s)`.
  `len` devuelve `i64` por coherencia con v0.3 §2.4, no «el tipo del índice» (§3 deja B7
  sin arreglar a propósito).

## Lo que V1 NO hace

No añade un átomo de capacidad, no toca la IR ni `ir_validate`, no toca ningún backend, no
define semántica en un backend (la referencia sigue siendo normativa, `AGENTS.md` §4), y no
activa `len` sobre `struct` ni sobre ninguna otra cosa: sobre un `StructT` sigue siendo
`TYPE_MISMATCH`.

Suite: 148 OK en el commit de V1 (138 + 10); con V2 son 165. El corpus v0.5 estaba **fuera** de
`CORPORA` (`isyco/conformance.py:13`) hasta que `402`–`405` pasaran con V2 —ocurrió el
2026-10-31, los 42 casos coinciden con su `expected`— y entra en el commit siguiente, que es
cuando el gate de backends (hasta entonces 170 casos) lo cubre. Mientras tanto la evidencia de
V1 y V2 es la sonda `tools/v05_revalida_probe.py`, no el gate.

**Corrección 2026-11-01:** ese commit siguiente ocurrió. El directorio está en `CORPORA` y el
gate de backends pasó de 170 a **212** casos: referencia `212/212` y C, Rust, Zig y pydecimal
`212/212`, con COBOL en `146/212`. Recibo `evidence/backends/gate_2026-11-01T015245Z.json`
(`verdict=PASS`, `git_head=57f38bc`, árbol de código limpio). La suite es 166 tests.

## Claims

| claim | estado | dónde |
|---|---|---|
| `len` de un arreglo devuelve su capacidad en la referencia y en los cinco backends | **DEMONSTRATED** (RELEASE_GATE) | 10 EQUIV de tres vías, recibo limpio `run_20261031T210258Z` sobre `8c230aa` |
| Es estático: no cuesta pasos | **DEMONSTRATED** | gemelos 6 = 6 y 27 = 27, medidos |
| La IR no cambia (ningún nodo `len` nuevo) | **DEMONSTRATED** | 0 nodos en 401/406; control `len(str)` = 1 |
| Ningún programa 0.1–0.4 cambia de significado | **DEMONSTRATED** | recabezados: `UNKNOWN_NAME` (0.1/0.2), `TYPE_MISMATCH` (0.3/0.4) |
| Los canarios ejercitan la regla nueva (no pasan por otro lado) | **DEMONSTRATED** | brazo viejo apagando `v05` → `INVALID_PROGRAM` |
| V1 está dentro del gate de release de backends | **DEMONSTRATED** desde 2026-11-01 (hasta entonces **NOT_DEMONSTRATED** a propósito) | el corpus v0.5 entró en `CORPORA`; gate `212/212` con los 42 casos incluidos, recibo `gate_2026-11-01T015245Z.json` |
