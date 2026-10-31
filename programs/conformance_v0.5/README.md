# `programs/conformance_v0.5/` — corpus **propuesto**, aún inerte

Los `expected` de este directorio se escribieron a mano el **2026-10-30** (commits
`dd561c6` y `0e9ca79`, que no tocan ningún archivo de `isyco/`), antes de implementar
ninguna decisión V1–V7 de `spec/CORE_v0.5_propuesta.md`. Ningún caso corre hoy: los
siete sin strings los rechaza la cabecera
(`isyco/parser.py:12`, `SYNTAX at 1:1`) y los tres con strings tropezan antes, en el
léxico (`isyco/lexer.py:64` solo enciende `"…"` para `0.3`/`0.4`). El directorio está
**fuera de `CORPORA`** (`isyco/conformance.py:13`), así que el gate de 170 casos no se
mueve.

| archivo | qué fija | decisión |
|---|---|---|
| `401_len_arreglo` | `len([T; N])` → `N` | V1 |
| `402_for_decimales` | `for` sobre arreglo de structs | V2 |
| `403_for_enteros` | `for` sobre arreglo de enteros | V2 |
| `404_for_break_continue` | `break`/`continue` dentro de `for` | V2 |
| `405_for_copia` | la variable del `for` es copia, no alias | V2 + V4 |
| `406_len_parametro` | `len(a)` como cota del `while` gemelo | V1 |
| `407_parametro_reasignable` | asignar a un parámetro no muta al llamador | V4 |
| `408_qname_arreglo/` | `[modulo.Tipo; N]` | V5 |
| `409_str_cualquier_capacidad` | `str` sin capacidad en un parámetro | V6 |
| `410_str_vacia_reutilizable` | la misma utilidad sirve con la cadena vacía | V6 |

## `gemelos/`

`403_while.isy`, `404_while_incremento_arriba.isy`, `404_while_incremento_abajo.isy`
y `405_while.isy` están escritos con la cabecera `isyco 0.4` y **corren hoy**. Sirven
a dos cosas:

1. son la prueba ejecutable de que los esperados `17`, `2 3 7 → 3` y `1 3 → 2` no se
   copiaron de ningún resultado nuevo, y
2. fijan los `steps` que el azúcar V2 debe reproducir (23, 38 y 20).

`404_while_incremento_abajo.isy` es el **control negativo**: es el azúcar V2 escrito
como «`while` con el incremento al final del cuerpo», y su `continue` salta el avance.
Termina en `LIMIT_REACHED(max_steps)` con `emits=["2","3"]`. Por eso la desugaring de
V2 pone el incremento **antes** del cuerpo.

Medición completa (las diez columnas «hoy» y los cuatro gemelos):

    python3 tools/v05_proposal_probe.py
    evidence/v05_propuesta/run_2026-10-31T001600Z.txt   # sha256 3b7285a5…
