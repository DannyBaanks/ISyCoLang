# GUÍA — escribir y correr un programa ISyCoLang

Guía para una persona, no para un agente. Todo lo de aquí se ejecutó el
2026-10-29 y se volvió a ejecutar **tal cual** el 2026-10-30 en este host
(Ubuntu 24.04, Python 3); el transcript crudo, con los códigos de salida de
cada comando, está en `evidence/human_guide/transcript_*.txt`. Los ejemplos
`precio.isy`, `ticket.isy` y `proyecto/` viven en la raíz del repo para que
los comandos de esta guía corran sin pasos previos. La semántica exacta está
en `spec/CORE*.md` (v0.1–v0.4); esta guía no la reemplaza.

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

- La primera línea elige las reglas: `isyco 0.5` (la más nueva), `0.4`, `0.3`, `0.2` o `0.1`.
- Tipos: `bool`, enteros `i8`…`i64` / `u8`…`u64` (desborde = error), o
  `int<N,signed|unsigned,trap|wrap|sat>` para elegir qué pasa al desbordar;
  decimales `dec<p,s>` (redondeo `half_even` por defecto) o
  `dec<p,s,half_up|down|exact>`; arreglos `[T; N]` (se copian al pasarlos).
- Una función que usa `emit` lo declara con `!emit`.
- Strings y structs existen desde `isyco 0.3` (§2b) y los módulos desde
  `isyco 0.4` (§2c); el azúcar `for` y `len` de un arreglo existen desde
  `isyco 0.5` (§2d). No hay lectura de archivos (todavía).

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

## 2b. Strings y structs (`isyco 0.3`)

```text
isyco 0.3
struct Item { nombre: str<16>, precio: dec<10,2>, piezas: i32 }

fn linea(it: Item) -> str<48> {
    let total: dec<10,2> = it.precio * (it.piezas as dec<10,2>);
    return it.nombre + " x" + (it.piezas as str<6>) + " = " + (total as str<14>);
}

fn main(cliente: str<20>, it: Item) -> Item !emit {
    emit "Cliente: " + cliente;
    emit linea(it);
    it.piezas = it.piezas + 1;
    return it;
}
```

```bash
python3 -m isyco run ticket.isy --input '["Danny", {"nombre":"Mezcal","precio":"350.00","piezas":"2"}]'
# emits: "Cliente: Danny", "Mezcal x2 = 700.00"
# return: {"nombre":"Mezcal","precio":"350.00","piezas":"3"}
```

- `str<N>`: hasta N bytes ASCII; si algo no cabe es `ERROR(OVERFLOW)`, nunca se corta.
  Un `str<16>` cabe donde se pide un `str<48>`; al revés hay que usar `as`.
- `+` concatena, `len(s)`, `s[i]` (byte como `u8`), `slice(s, a, b)`, `chr(n)`.
- `x as str<N>` escribe un número en forma canónica; `s as i32` lo lee
  (`"05"` o `"2.5"` en un `dec<…,2>` dan `ERROR(BAD_FORMAT)`).
- Los structs se copian al asignarlos o pasarlos, y se comparan con `==`.
  En la condición de un `if`/`while`, un literal de struct va entre paréntesis.
- En la entrada, un struct es un objeto JSON; `emit` de un struct o arreglo
  saca JSON en una línea.
- v0.3 corre con los seis ejecutores: `ast`, `ir`, `c`, `rust`, `zig` y `pydecimal`.

## 2c. Módulos (`isyco 0.4`)

```text
proyecto/
├── main.isy          isyco 0.4
│                     import util;
│                     import geo.punto;
│                     fn main() -> i32 { return util.doble(punto.x0()); }
├── util.isy          isyco 0.4
│                     pub fn doble(x: i32) -> i32 { return x * 2; }
└── geo/punto.isy     isyco 0.4
                      pub fn x0() -> i32 { return 21; }
```

```bash
python3 -m isyco run proyecto/main.isy          # return "42"; el resultado lista "modules"
```

- `import a.b;` busca `a/b.isy` desde la carpeta de `main.isy`, y se usa como `b.f()`.
- Solo lo marcado `pub` se puede usar desde otro archivo; lo demás da `NOT_PUBLIC`.
- Sin imports circulares (`IMPORT_CYCLE`); todos los archivos deben ser `isyco 0.4`.
- Ninguna variable o función puede llamarse como un módulo importado.
- Un error dentro de un módulo dice el archivo: `at: "util.isy:2:38"`.
- Los seis ejecutores (`ast`, `ir`, `c`, `rust`, `zig`, `pydecimal`) corren programas con módulos.

## 2d. Recorrer un arreglo (`isyco 0.5`)

```text
isyco 0.5
fn total(item: [dec<8,2>; 3]) -> dec<8,2> {
    let s: dec<8,2> = 0.00;
    for precio in item {
        s = s + precio;
    }
    return s;              // len(item) vale 3: la capacidad la sabe el tipo
}
```

- `len(a)` con `a: [T; N]` devuelve `N` en `i64`. Lo resuelve el compilador: no es una
  operación nueva, no gasta ni un paso más que escribir `3` a mano.
- `for x in a { … }` es azúcar del `while` gemelo (`let i: i64 = -1;` …
  `while i + 1 < len(a) { i = i + 1; let x = a[i]; … }`). Los `steps`, los límites y las
  trazas son exactamente los del `while` escrito a mano.
- Se recorre un **lugar** (`xs` o `p.xs`), no una expresión: `for x in [1, 2, 3]` y
  `for x in f()` son `SYNTAX`.
- `x` es una **copia** del elemento y muere al salir del bucle; reasignarla no toca el
  arreglo, y usarla después da `UNKNOWN_NAME`. `break` y `continue` valen lo mismo que
  en el `while`.
- `for` es palabra reservada **solo** desde `0.5`; en `0.4` y anteriores sigue siendo un
  nombre normal, y `in` nunca se reservó (puedes tener una variable `in`).

## 3. Elegir quién lo ejecuta (`--via`)

| `--via` | qué es |
|---|---|
| `ast` (por defecto) | intérprete de referencia: la semántica normativa |
| `ir` | intérprete de la IR canónica (lo que reciben los backends) |
| `c`, `rust`, `zig` | compila a binario nativo y lo corre |
| `pydecimal` | genera un programa Python 3 (con el módulo `decimal`) y lo corre |
| `cobol` | compila con GnuCOBOL y lo corre; solo el núcleo numérico v0.1 (`str`/`struct` responden `UNSUPPORTED`) |

Los ejecutores dan el mismo `status`/`emits`/`return`/`steps` dentro de su dominio
declarado (`cobol` cubre el núcleo numérico; `c`, `rust`, `zig` y `pydecimal`,
todo). Eso es lo que prueban los tests. Los compilados agregan `cost`: tiempo,
CPU, pico de memoria y tiempo de compilación (`null` si el binario ya estaba en
`build/`). La primera corrida en Zig tarda unos segundos en compilar.

```bash
python3 -m isyco run precio.isy --input '["19.99","3"]' --via c
python3 -m isyco ir  precio.isy          # ver la IR canónica
```

## 4. Cuando algo sale mal

| status | código de salida | ejemplo |
|---|---|---|
| `HALTED` | 0 | terminó bien |
| `INVALID_PROGRAM` | 2 | error de tipos, o entrada mala: `"19.999"` en un `dec<12,2>` da `code: BAD_INPUT` |
| `ERROR` | 3 | `OVERFLOW`, `DIV_ZERO`, `INEXACT` (con `exact`), índice fuera de rango, `BAD_FORMAT`/`BAD_CHAR` (v0.3) |
| `LIMIT_REACHED` | 4 | `code: max_steps` / `max_emits` / `max_call_depth` |
| `TIMEOUT` | 5 | pasó `--timeout-ms` (lo decide el reloj, no la semántica) |
| `UNSUPPORTED` | 1 | el backend nativo no implementa algo que el programa usa; `code` dice qué |
| — | 1 | error de uso, archivo, o toolchain no instalado |

Los `emits` hechos antes del error **sí** aparecen en la salida.

Límites por defecto: 1 000 000 pasos, 256 de profundidad de llamadas, 100 000
emits. Se cambian con `--max-steps`, `--max-call-depth`, `--max-emits`; por
ejemplo `--input '["19.99","3000000"]'` se detiene en `max_emits`.

Para ver paso a paso: `--trace stmt --trace-out traza.jsonl` (solo `ast`/`ir`).

## 5. Comprobar que todo sigue bien

```bash
python3 tools/warm_build_cache.py              # opcional: precompila en paralelo (la primera vez tarda)
python3 -m unittest discover -s tests          # suite completa: 166 tests; rango medido 2026-11-01: 191,3-329,6 s con la caché llena (cinco corridas: 191,3 / 191,6 / 200,2 / 251,9 / 329,6; la última después de `tools/v05_p4_probe.py` y la de 251,9 después de `tools/c_gate.py`; los 206,7 s eran de la suite de 165 tests con 170 casos, y los 379,5 s de la de 138 en frío)
python3 tools/backend_gate.py                  # gate de backends: escribe evidence/backends/gate_<UTC>.json
```

Si no quieres esperar a Zig: `ISYCO_TEST_BACKENDS=c,rust python3 -m unittest discover -s tests`.

Si falta el toolchain de un backend, la suite falla en vez de saltarse tests en
silencio; para correr igual: `ISYCO_ALLOW_MISSING_TOOLCHAINS=1 python3 -m unittest discover -s tests`.

Si agregas evidencia nueva, agrega su hash a `SHA256SUMS.txt` de esa carpeta.
Nunca edites un caso del corpus ni un archivo de evidencia existente: el
corpus usa `SUPERSEDED.json`, la evidencia usa archivos nuevos.

## 6. Dónde está cada cosa

- `spec/` — semántica (`CORE*.md`), IR (`IR.md`), contrato de backend (`BACKEND.md`).
- `programs/conformance*/` — ejemplos con su resultado esperado escrito a mano.
- `ROADMAP.md` §6 — qué está demostrado y qué no.
