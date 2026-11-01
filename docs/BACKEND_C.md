# Backend C (F4)

`isyco/backends/c.py` traduce ISY-IR v0.1 y v0.2 validada a C (GNU C11) y la compila
con gcc o clang. Es el primer backend nativo del proyecto.

```bash
python3 -m isyco run programa.isy --input '["1000.00","0.0525"]' --via c
ISYCO_CC=clang python3 -m isyco run programa.isy --via c     # elegir compilador
```

## Cómo cumple la spec

| requisito de CORE | cómo lo resuelve el C generado |
|---|---|
| evaluación de izquierda a derecha (§7) | C no fija el orden de operandos ni de argumentos; toda subexpresión que puede fallar o tener efectos se guarda en una temporal, en orden |
| `trap`/`wrap`/`sat` sin comportamiento indefinido (§3.2) | el resultado exacto se calcula en `__int128` (cabe para ±, ×, ÷ de 64 bits con signo) y `isy_fit` aplica la regla; `u64 × u64` usa `__builtin_mul_overflow` |
| división truncada y `MIN % -1 = 0` | se calcula en `__int128`, donde no hay desborde |
| decimales con una sola rondeada (§3.3) | `int64_t` escalado (p ≤ 18, D3); producto y cociente exactos en `__int128` (≤ 10³⁶) y `isy_rdiv` redondea una vez |
| arreglos por copia (§3.4) | cada tipo arreglo es un `struct`, que C copia por valor |
| pasos, profundidad y emits (§8) | el binario los cuenta como la referencia, así que `steps` también se compara |
| salida parcial al fallar (§9, D5) | cada `emit` se imprime al momento; el error termina con `X ERROR <code> <steps>` |
| `str<N>` (CORE v0.3) | `struct { uint32_t len; char v[N]; }`: valor por copia, sin heap; concatenar, `slice`, `as str` revisan la capacidad y dan `OVERFLOW` |
| structs (CORE v0.3) | un `struct` de C por tipo, campos `f_<nombre>`; `==` y la salida JSON con funciones generadas por tipo (nunca `memcmp` sobre el struct: hay relleno y bytes después de `len`) |
| `str` → número (CORE v0.3 §2.5) | forma canónica revisada byte a byte; el valor se acumula en `unsigned __int128`, que guarda el exacto módulo 2¹²⁸: `wrap` toma los bits bajos aunque el texto tenga 45 dígitos, `trap`/`sat` solo necesitan saber que no cabe |

## Protocolo del binario

```text
./prog MAX_STEPS MAX_CALL_DEPTH MAX_EMITS ARG...
stdout:  E <emit> … [R <retorno>] X <status> <code|-> <steps>
```

Los argumentos llegan crudos (enteros, decimales escalados, bools 1/0, arreglos
aplanados). La forma canónica de la entrada la valida el frontend antes de
llamar al binario: `BAD_INPUT` lo decide el frontend, igual que en la referencia.

## Qué no hace

- **No produce traza.** Se compara `status`, `code`, `emits`, `return` y `steps`.
- **`TIMEOUT`** lo decide el proceso padre con el reloj (no es semántica).
- Depende de extensiones GNU (`__int128`, builtins de overflow): gcc y clang sí;
  MSVC no.
- Si el binario muere sin escribir la línea `X`, el resultado es
  `BACKEND_CRASH`: eso es un bug del backend, nunca un resultado válido.

## Verificación

`tools/c_gate.py` (evidencia en `evidence/c/`):

1. **Corpus en tres vías:** expected ↔ referencia ↔ binario, con gcc y clang,
   con y sin `-fsanitize=undefined,address -fno-sanitize-recover=all`.
2. **Diferencial por tipo** (`isyco/difftest.py`): los 24 tipos enteros y 8
   decimales × 15 operaciones (aritmética, negación, comparación, 8
   conversiones) × parejas forzadas (fronteras, `MIN/-1`, `x/0`, empates exactos de
   redondeo) + parejas aleatorias con semilla fija.
3. **Sabotajes:** `half_even_as_half_up` y `div_floor` tienen que fallar el
   corpus **y** el diferencial.

**Última corrida (2026-11-01, head `a4f608c`):** `evidence/c/gate_2026-11-01T074655Z.json`
(`PASS`) — 213/213 en las cuatro combinaciones con cero `UNSUPPORTED` y cero fallos, 24 612
corridas diferenciales en `gcc/plain` y 6 468 con sanitizers sin diferencias, y los dos
sabotajes detectados. La población que cubre el gate creció 58 → 78 → 170 → 212 → **213** en
`gate_2026-10-29T005211Z.json`, `gate_2026-10-29T011246Z.json`,
`gate_2026-10-30T220800Z.json`, `gate_2026-11-01T071619Z.json` y la actual; son las cinco
`gate_*.json` que hay en `evidence/c/`, contadas renglón por renglón del campo `cases`, y
las cinco son `PASS` con las cuatro combinaciones. Desde esta entrega el número está atado a
la suite:
`tests/test_evidence.py::DocsMatchLatestEvidence::test_c_gate_figure` lee el recibo más
nuevo y exige que el README cite su población.
