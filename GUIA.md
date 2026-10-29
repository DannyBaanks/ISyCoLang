# GUÍA — escribir y correr un programa ISyCoLang

Guía para una persona, no para un agente. Todo lo de aquí se ejecutó el
2026-10-29 en este host (Ubuntu 24.04, Python 3). La semántica exacta está en
`spec/CORE.md` + `spec/CORE_v0.2.md`; esta guía no la reemplaza.

## 1. Un programa

Archivo `precio.isy`:

```text
isyco 0.2
fn con_iva(precio: dec<12,2>) -> dec<12,2> {
    return precio * 1.16;
}

fn main(precio: dec<12,2>, piezas: i32) -> dec<12,2> !emit {
    let total: dec<12,2> = 0.00;
    let i: i32 = 0;
    while i < piezas {
        total = total + con_iva(precio);
        emit total;
        i = i + 1;
    }
    return total;
}
```

- La primera línea elige las reglas: `isyco 0.2` (recomendada) o `isyco 0.1`.
- Tipos: `bool`, enteros `i8`…`i64` / `u8`…`u64` (desborde = error), o
  `int<N,signed|unsigned,trap|wrap|sat>` para elegir qué pasa al desbordar;
  decimales `dec<p,s>` (redondeo `half_even` por defecto) o
  `dec<p,s,half_up|down|exact>`; arreglos `[T; N]` (se copian al pasarlos).
- Una función que usa `emit` lo declara con `!emit`.
- No hay strings, structs, módulos ni lectura de archivos (todavía).

## 2. Correrlo

```bash
cd ~/Development/ISyCo\ Git/ISyCoLang
python3 -m isyco run precio.isy --input '["19.99","3"]'
```

Las entradas son un arreglo JSON, un elemento por parámetro de `main`, cada
uno en forma canónica como **string** (`"19.99"`, `"3"`, `"true"`); un
parámetro arreglo va como arreglo JSON de strings: `--input '[["1","2","3"],"true"]'`.
Salida (JSON):

```text
"status":"HALTED", "emits":["23.19","46.38","69.57"], "return":"69.57", "steps":24
```

`19.99 × 1.16 = 23.1884` se redondea **una vez** a `23.19`.

## 3. Elegir quién lo ejecuta (`--via`)

| `--via` | qué es |
|---|---|
| `ast` (por defecto) | intérprete de referencia: la semántica normativa |
| `ir` | intérprete de la IR canónica (lo que reciben los backends) |
| `c`, `rust`, `zig` | compila a binario nativo y lo corre |

Los cinco dan el mismo `status`/`emits`/`return`/`steps` (eso es lo que
prueban los tests). Los nativos agregan `cost`: tiempo, CPU, pico de memoria y
tiempo de compilación (`null` si el binario ya estaba en `build/`). La primera
corrida en Zig tarda unos segundos en compilar.

```bash
python3 -m isyco run precio.isy --input '["19.99","3"]' --via c
python3 -m isyco ir  precio.isy          # ver la IR canónica
```

## 4. Cuando algo sale mal

| status | código de salida | ejemplo |
|---|---|---|
| `HALTED` | 0 | terminó bien |
| `INVALID_PROGRAM` | 2 | error de tipos, o entrada mala: `"19.999"` en un `dec<12,2>` da `code: BAD_INPUT` |
| `ERROR` | 3 | `OVERFLOW`, `DIV_ZERO`, `INEXACT` (con `exact`), índice fuera de rango |
| `LIMIT_REACHED` | 4 | `code: max_steps` / `max_emits` / `max_call_depth` |
| `TIMEOUT` | 5 | pasó `--timeout-ms` (lo decide el reloj, no la semántica) |
| — | 1 | error de uso, archivo, o toolchain no instalado |

Los `emits` hechos antes del error **sí** aparecen en la salida.

Límites por defecto: 1 000 000 pasos, 256 de profundidad de llamadas, 100 000
emits. Se cambian con `--max-steps`, `--max-call-depth`, `--max-emits`; por
ejemplo `--input '["19.99","3000000"]'` se detiene en `max_emits`.

Para ver paso a paso: `--trace stmt --trace-out traza.jsonl` (solo `ast`/`ir`).

## 5. Comprobar que todo sigue bien

```bash
python3 -m unittest discover -s tests          # suite completa (varios minutos: compila C, Rust y Zig)
python3 tools/backend_gate.py                  # gate de backends: escribe evidence/backends/gate_<UTC>.json
```

Si agregas evidencia nueva, agrega su hash a `SHA256SUMS.txt` de esa carpeta.
Nunca edites un caso del corpus ni un archivo de evidencia existente: el
corpus usa `SUPERSEDED.json`, la evidencia usa archivos nuevos.

## 6. Dónde está cada cosa

- `spec/` — semántica (`CORE*.md`), IR (`IR.md`), contrato de backend (`BACKEND.md`).
- `programs/conformance*/` — ejemplos con su resultado esperado escrito a mano.
- `ROADMAP.md` §6 — qué está demostrado y qué no.
