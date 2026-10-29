# ISyCoLang — Semántica del core v0.2

**Estado:** `FROZEN v0.2` (2026-10-28; cambios C1–C3 aprobados por Danny).
**Base:** `CORE.md` (v0.1), que sigue congelada y vigente. Este documento solo
lista lo que cambia; todo lo demás es idéntico a v0.1.

## 0. Versionado

- La cabecera decide la versión: `isyco 0.1` o `isyco 0.2`. Cualquier otra ⇒
  `INVALID_PROGRAM(SYNTAX)`.
- Un programa `isyco 0.1` se interpreta **exactamente** con las reglas de v0.1.
  Ningún programa v0.1 cambia de significado.
- La ISY-IR no cambia (`isy-ir/0.1`): las tres reglas nuevas se resuelven en el
  frontend, antes de producir la IR. Los backends no se tocan.

## 1. Aclaraciones que pasan a ser normativas (ambas versiones)

Las interpretaciones E1–E4, E6–E9 y E12–E14 de `ERRATA_v0.1.md` dejan de ser
interpretaciones: son la semántica de v0.1 y v0.2. (E5, E10 y E11 se resuelven
abajo como C3, C1 y C2.)

## 2. Cambios de v0.2

### C1 — Índices literales (resuelve E10)

Si la expresión de un índice (`a[e]` o `a[e] = …`) no tiene tipo propio
(un literal numérico, o aritmética solo de literales), toma el tipo **`i64`**.

```text
a[0]          # v0.2: válido, índice i64
a[1 + 1]      # v0.2: válido, i64
a[-1]         # v0.2: válido en compilación; en ejecución ERROR(INDEX_OUT_OF_BOUNDS)
a[0]          # v0.1: INVALID_PROGRAM(AMBIGUOUS_LITERAL), sin cambios
```

Solo aplica a índices. El resto de los literales sigue la regla de §3.5.

### C2 — Literales negativos (resuelve E11)

Un `-` seguido **directamente** de un `INT_LIT` o `DEC_LIT` (con o sin espacios
en medio, pero sin paréntesis) forma **un solo literal negativo**, y es ese
valor negativo el que debe caber en el tipo esperado. El literal negativo es
una expresión primaria: `-1 as u8` convierte el literal `-1` (y por eso es
`LITERAL_OUT_OF_RANGE`), en lugar de negar `1 as u8`. La resta binaria no
cambia: `x -100` es `x - 100`.

| fuente | tipo | v0.1 | v0.2 |
|---|---|---|---|
| `-128` | `i8` | `LITERAL_OUT_OF_RANGE` (128 no cabe) | `-128` |
| `-129` | `i8` | `LITERAL_OUT_OF_RANGE` | `LITERAL_OUT_OF_RANGE` |
| `-1` | `int<8,unsigned,wrap>` | `255` (negación con wrap, en ejecución) | `LITERAL_OUT_OF_RANGE` |
| `-(128)` | `i8` | `LITERAL_OUT_OF_RANGE` | `LITERAL_OUT_OF_RANGE` (es negación de `128`) |
| `-0.50` | `dec<2,2>` | `-0.50` | `-0.50` |
| `- -5` | `i32` | `5` | `5` (negación del literal `-5`) |

La negación de cualquier otra expresión (`-x`, `-(1 + 2)`, `-f()`) sigue
siendo el operador `-` de §3.2/§3.3.

### C3 — Tamaño de arreglo (resuelve E5)

Un tipo `[T; N]` con `N` fuera de `1..65536` ⇒ `INVALID_PROGRAM(ARRAY_SIZE)`.
Se agrega `ARRAY_SIZE` a la lista de códigos de §9. Aplica también a v0.1, que
ya se comportaba así (E5).

## 3. Corpus

`programs/conformance_v0.2/` con `expected` escritos a mano antes de implementar
C1–C3. El corpus v0.1 (`programs/conformance/`) no se modifica.
