# `programs/conformance_v0.5/` — corpus **activo**: 42/42 coinciden con su `expected`

Los `expected` de este directorio se escribieron a mano el **2026-10-30** (commits
`dd561c6` y `0e9ca79`, que no tocan ningún archivo de `isyco/`), antes de implementar
ninguna decisión V1–V7 de `spec/CORE_v0.5_propuesta.md`.

**Corrección 2026-10-31.** Cuando se escribió el README, ningún caso corría: los siete
sin strings los rechazaba la cabecera (`isyco/parser.py:12`, `SYNTAX at 1:1`) y los tres
con strings tropezaban antes, en el léxico (`isyco/lexer.py:64` solo encendía `"…"` para
`0.3`/`0.4`). Eso ya no es cierto. Con V6, V6-bis, V7, V1 y V2 implementados y sellados,
los **42** casos del directorio coinciden en `status`, `code`, `emits` y `return` con su
`expected` a mano, medido contra la referencia de este árbol:

    python3 - <<'PY'   # 42/42 IGUAL (2026-10-31)
    from isyco import run
    from isyco.conformance import COMPARED, load_corpus
    from pathlib import Path
    for c in load_corpus(Path("programs/conformance_v0.5")):
        got, _ = run(c["program"], c["input"], c.get("limits"))
        print(c["name"], {k: got[k] for k in COMPARED} == c["expected"])
    PY

`408_qname_arreglo/` y `440_llamada_calificada_void/` tienen que leerse con
`load_corpus`, que arma el `Bundle` del directorio: tomar `main.isy` como bytes sueltos
devuelve un falso `UNKNOWN_MODULE`.

| archivo | qué fija | decisión | hoy (referencia) |
|---|---|---|---|
| `401_len_arreglo` | `len([T; N])` → `N` | V1 | `HALTED`, `5`, 6 pasos |
| `402_for_decimales` | `for` sobre arreglo de structs | V2 | `HALTED`, `3.85`, 18 pasos — COBOL dice `UNSUPPORTED(ir0.2,str,struct)` |
| `403_for_enteros` | `for` sobre arreglo de enteros | V2 | `HALTED`, `17`, 23 pasos |
| `404_for_break_continue` | `break`/`continue` dentro de `for` | V2 | `HALTED`, `2 3 7 → 3`, 38 pasos |
| `405_for_copia` | la variable del `for` es copia, no alias | V2 + V4 | `HALTED`, `1 3 → 2`, 20 pasos |
| `406_len_parametro` | `len(a)` como cota del `while` gemelo | V1 | `HALTED`, `21`, 27 pasos |
| `407_parametro_reasignable` | asignar a un parámetro no muta al llamador | V4 | `HALTED`, `41 → 42`, 8 pasos |
| `408_qname_arreglo/` | `[modulo.Tipo; N]` | V5 | `HALTED`, `9.00`, 7 pasos |
| `409_str_cualquier_capacidad` | `str` sin capacidad en un parámetro | V6 | `HALTED`, `104 97 → 4`, 8 pasos |
| `410_str_vacia_reutilizable` | la misma utilidad sirve con la cadena vacía | V6 | `HALTED`, `true false → false`, 10 pasos |

`411`–`428` (V6), `429`–`438` (V6-bis) y `439`–`442` (V7) se agregaron con sus propias
decisiones: `docs/decisions/V6_CONTEXTUAL_STR.md`, `docs/decisions/V6B_CONTEXTUAL_RETURN.md`
y `docs/decisions/V7_CONTENT_CAPABILITIES.md`.

## `gemelos/`

`403_while.isy`, `404_while_incremento_arriba.isy`, `404_while_incremento_abajo.isy`
y `405_while.isy` están escritos con la cabecera `isyco 0.4` y **corren hoy**. Sirven
a dos cosas:

1. son la prueba ejecutable de que los esperados `17`, `2 3 7 → 3` y `1 3 → 2` no se
   copiaron de ningún resultado nuevo, y
2. fijan los `steps` que el azúcar V2 reproduce: medidos el 2026-10-31, el `for` gasta
   **23, 38 y 20** — los mismos que su gemelo — y su IR es idéntica a la del gemelo tras
   podar posiciones y el nombre del índice sintético.

`404_while_incremento_abajo.isy` es el **control negativo**: es el azúcar V2 escrito
como «`while` con el incremento al final del cuerpo», y su `continue` salta el avance.
Termina en `LIMIT_REACHED(max_steps)` con `emits=["2","3"]`. Por eso la desugaring de
V2 pone el incremento **antes** del cuerpo. Sabotear `for_stmt` con esa forma produce
hoy 12 `CONTROL FALSO` en la sonda y ninguna evidencia sellada.

## Dónde se mide

- Propuesta (las diez columnas «hoy» de 2026-10-30 y los cuatro gemelos):
  `python3 tools/v05_proposal_probe.py` →
  `evidence/v05_propuesta/run_2026-10-31T001600Z.txt`   # sha256 3b7285a5…
- Revalidación V1/V2 (tres vías, gemelos, no regresión, auto-falsación, forma de la IR):
  `python3 tools/v05_revalida_probe.py --casos 401,402,403,404,405,406 --write` →
  `evidence/v05_revalida/`
- El directorio sigue **fuera de `CORPORA`** (`isyco/conformance.py:13`); entra con el
  gate de backends en cuanto V3–V5 queden documentados.
