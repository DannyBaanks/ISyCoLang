# ISY_BACKEND/1 — Contrato de backend

**Estado:** v1 (F5, 2026-10-28). Todo backend de ISyCoLang cumple este
contrato. La semántica la fija `spec/CORE.md` (+ `CORE_v0.2.md`); la forma de la
entrada, `spec/IR.md`. Un backend **implementa** esa semántica; nunca la define.

## 1. Qué recibe y qué entrega

```text
entrada:  módulo ISY-IR validado  +  entrada canónica  +  límites
salida:   documento de resultado de CORE §10.2 (status, code, emits, return, steps)
```

- El frontend (lexer, parser, checker, lowering, validador de IR) es **común** a
  todos los backends. `INVALID_PROGRAM` y `BAD_INPUT` los decide el frontend; un
  backend nunca recibe un programa inválido.
- Un backend no produce traza salvo que lo declare.

## 2. Capacidades declaradas

Cada backend declara qué partes de la IR implementa (`features`):

```text
int8 int16 int32 int64 unsigned ovf:trap ovf:wrap ovf:sat
dec dec:half_even dec:half_up dec:down dec:exact
bool arrays calls recursion while emit
```

`features_of(módulo)` calcula lo que un programa necesita (recursión = ciclo
en el grafo de llamadas). Si al backend le falta algo, el resultado es
`status = UNSUPPORTED`, `code = <capacidades que faltan>`, y el programa **no
se ejecuta**. Nunca se aproxima ni se degrada en silencio.

`UNSUPPORTED` no es un estado de la semántica (CORE §9): es una respuesta del
backend, y en conformidad cuenta como **no cubierto**, nunca como PASS.

## 3. Protocolo del binario (backends nativos)

```text
./prog MAX_STEPS MAX_CALL_DEPTH MAX_EMITS ARG...
```

- `ARG`: valores crudos validados por el frontend. Entero en base 10, decimal
  como entero escalado `m`, bool `1`/`0`, arreglo aplanado elemento por elemento.
- stdout, una línea por evento:

```text
E <forma canónica>               cada emit, en orden
R <forma canónica>               retorno de main (si tiene tipo)
X <status> <code|-> <steps>      siempre la última línea
```

- Si el binario termina sin línea `X`, con código de salida ≠ 0 o escribe en
  stderr, el resultado es `BACKEND_CRASH`: es un bug del backend, nunca un
  resultado válido.
- `TIMEOUT` lo decide el proceso padre con el reloj (no es semántica).
- El proceso padre sube `RLIMIT_STACK` hasta el límite duro: la recursión
  profunda con arreglos copiados por valor necesita pila.

## 4. Obligaciones semánticas (todas las de CORE, en particular)

| obligación | por qué es fácil equivocarse |
|---|---|
| evaluar de izquierda a derecha | C no lo garantiza; Rust y Zig sí, pero las llamadas anidadas con estado compartido no (préstamos en Rust) |
| `trap`/`wrap`/`sat` exactos y sin comportamiento indefinido | el desborde con signo es UB en C; Rust/Zig lo atrapan o envuelven según el modo de compilación |
| división truncada, `MIN / -1`, `MIN % -1 = 0` | `MIN % -1` es UB en C |
| decimales con **una** rondeada y los cuatro modos | el empate de `half_even` con negativos |
| arreglos por copia | aliasing accidental |
| contar pasos, profundidad y emits igual que la referencia | `else if`, `while` y la llamada inicial a `main` (CORE_v0.2 §1) |
| salida parcial antes de un error | búferes que no se vacían al salir |

## 5. Conformidad de un backend

Un backend es **conforme** cuando, sobre los corpus `programs/conformance*`:

1. todo caso dentro de sus capacidades da el mismo `status`, `code`, `emits`,
   `return` y `steps` que la referencia (y por tanto que el `expected`);
2. todo caso fuera de sus capacidades da `UNSUPPORTED`;
3. **pasa el diferencial por tipo** (`isyco/difftest.py`) en los tipos que
   declara. Un stub que imprime respuestas conocidas no puede pasarlo: las
   entradas son aleatorias con semilla y en valores frontera;
4. **el engine hace el trabajo**: el código generado no contiene las salidas
   esperadas y cambiar la entrada cambia la salida (estándar §9).

`tools/backend_gate.py` comprueba los cuatro puntos para cada backend instalado
y guarda la evidencia en `evidence/backends/`.

## 6. Backends registrados

| backend | toolchain | capacidades | notas |
|---|---|---|---|
| `c` | gcc / clang (GNU C11) | todas | `__int128`, builtins de overflow; sabotajes de prueba |
| `rust` | rustc (ed. 2021) | todas | `-C overflow-checks=on -C panic=abort` |
| `zig` | zig 0.16 | todas | `-O ReleaseSafe`; solo Linux (syscall `write`); un arreglo local de 64 KB cuesta ~10 s de compilación (limitación de Zig/LLVM, no del lowering) |
