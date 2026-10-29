# ISY_BACKEND/1 — Contrato de backend

**Estado:** v1 (F5, 2026-10-28). Todo backend de ISyCoLang cumple este
contrato. La semántica la fija `spec/CORE.md` (+ `CORE_v0.2.md`); la forma de la
entrada, `spec/IR.md`. Un backend **implementa** esa semántica; nunca la define.

## 1. Qué recibe y qué entrega

```text
entrada:  módulo ISY-IR validado  +  entrada canónica  +  límites
salida:   documento de resultado de CORE §10.2 (status, code, emits, return, steps) + `cost` (§3.1)
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
ir0.2 str struct                        (isy-ir/0.2, CORE v0.3)
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
  Desde `isy-ir/0.2`: un `str` va como un argumento con su texto tal cual, y un
  struct se aplana campo por campo en orden de declaración (recursivo).
- stdout, una línea por evento:

```text
E <forma canónica>               cada emit, en orden
R <forma canónica>               retorno de main (si tiene tipo)
X <status> <code|-> <steps>      siempre la última línea
```

- En la carga de `E` y `R`, una barra invertida se escribe `\\` y un salto de
  línea `\n` (2026-10-29: un `str` puede contener saltos de línea). Los
  números nunca contienen ninguno de los dos, así que la salida de v0.1/v0.2 no
  cambia. Un `str` se emite como su texto; un arreglo o struct, como JSON
  canónico (CORE v0.3 §6).

- Si el binario termina sin línea `X`, con código de salida ≠ 0 o escribe en
  stderr, el resultado es `BACKEND_CRASH`: es un bug del backend, nunca un
  resultado válido.
- `TIMEOUT` lo decide el proceso padre con el reloj (no es semántica).
- El proceso padre sube `RLIMIT_STACK` hasta el límite duro: la recursión
  profunda con arreglos copiados por valor necesita pila.

### 3.1 Costo medido

Todo resultado de un backend nativo lleva `cost` (agregado 2026-10-29):

```text
wall_ms      tiempo de pared de la ejecución (sin compilar)
user_ms      CPU de usuario del hijo (wait4)
sys_ms       CPU de sistema del hijo (wait4)
max_rss_kb   pico de memoria del binario, por GNU time (`/usr/bin/time -f %M`)
compile_ms   ms de compilación, o null si el binario venía de la caché
```

- El costo es **medido, no semántico**: varía entre corridas y máquinas, y
  nunca entra en la comparación de conformidad (§5).
- `max_rss_kb` no se toma del rusage de un hijo de Python: Linux conserva el
  pico de memoria a través de `execve`, así que mediría al intérprete
  (~12 MB) y no al binario. Sin GNU time vale `null` (no medido), nunca se
  estima. El piso de GNU time es ~1,3 MB (C/Rust usan libc; Zig no, ~0,4 MB).
- En `TIMEOUT` el costo es parcial: el grupo de procesos se mata antes de
  que GNU time reporte, y `max_rss_kb` queda `null`.

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
   esperadas y cambiar la entrada cambia la salida (estándar §9);
5. **la suite lo distingue de un backend roto**: cada sabotaje que el backend
   declara (`sabotages`: hoy `half_even_as_half_up` y `div_floor`) hace
   fallar el corpus y el diferencial.

`tools/backend_gate.py` comprueba los cinco puntos y resume el costo medido para cada backend instalado
y guarda la evidencia en `evidence/backends/`.

## 6. Backends registrados

| backend | toolchain | capacidades | notas |
|---|---|---|---|
| `c` | gcc / clang (GNU C11) | todas (desde 2026-10-29 también `ir0.2 str struct`) | `__int128`, builtins de overflow; 3 sabotajes de prueba (2 numéricos, 1 de str) |
| `rust` | rustc (ed. 2021) | todas menos `ir0.2 str struct` | `-C overflow-checks=on -C panic=abort`; 2 sabotajes de prueba |
| `zig` | zig 0.16 | todas menos `ir0.2 str struct` | `-O ReleaseSafe`; 2 sabotajes de prueba; solo Linux (syscall `write`); un arreglo local de 64 KB cuesta ~10 s de compilación (limitación de Zig/LLVM, no del lowering) |
