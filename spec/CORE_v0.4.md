# ISyCoLang — Semántica del core v0.4: módulos

**Estado:** `DRAFT v0.4` (2026-10-29). Decisiones M1–M4 tomadas por Danny el
2026-10-29; los detalles marcados **[P]** son propuestas pendientes de su
revisión antes de congelar.
**Base:** `CORE.md` + `CORE_v0.2.md` + `CORE_v0.3.md`. Todo lo de v0.3 vale en
v0.4; este documento solo lista lo que cambia.

## 0. Versionado

- Cabecera `isyco 0.4`. v0.1–v0.3 conservan exactamente su significado.
- Palabras reservadas nuevas (solo en v0.4): `import pub`.
- **La IR no cambia** (`isy-ir/0.2`): los imports se resuelven en el frontend,
  que une todos los módulos en un solo programa antes de bajar a IR.

## 1. Decisiones de Danny (2026-10-29)

| id | decisión |
|---|---|
| M1 | `import util;` busca `util.isy`; todo lo importado se usa **con prefijo**: `util.f()`, `util.Punto` |
| M2 | solo lo marcado `pub` se puede usar desde otro módulo |
| M3 | los imports circulares están **prohibidos** (`IMPORT_CYCLE`) |
| M4 | todos los módulos de un programa son `isyco 0.4` |

## 2. Programa, módulos y archivos

- Un **programa** es un archivo principal (el que se ejecuta; su `fn main` es la
  entrada) más los módulos que importa, directa o indirectamente.
- **[P1]** `import a.b.c;` se resuelve a `a/b/c.isy` **relativo a la carpeta del
  archivo principal**, sea cual sea el módulo que importa. Cada archivo es un
  solo módulo, identificado por esa ruta.
- **[P2]** El nombre local del módulo es su último segmento (`import geo.punto;`
  → `punto.f()`). Dos imports con el mismo nombre local en un archivo ⇒
  `INVALID_PROGRAM(DUPLICATE_NAME)`.
- Un módulo que dos archivos importan (diamante) se carga **una vez**: sus
  structs son el mismo tipo en todo el programa.
- Importar no reexporta: si `a` importa `c`, quien importa `a` no ve `c`.

## 3. Gramática

```ebnf
file      = header { import } { [ "pub" ] ( fn_decl | struct_decl ) } ;
import    = "import" IDENT { "." IDENT } ";" ;
qname     = MODULE "." IDENT ;      (* MODULE = nombre local de un import del archivo *)
type      = … | IDENT | qname ;
primary   = … | qname "(" args ")" | qname "{" fields "}" ;
stmt      = … | qname "(" args ")" ";" ;
```

- Los `import` van antes de toda declaración; un `import` después ⇒ `SYNTAX`.
- `pub` solo antecede a `fn` o `struct`. En el archivo principal está permitido
  y no cambia nada.
- **[P3]** El nombre local de un módulo ocupa el espacio de nombres del archivo:
  una función, struct, parámetro o variable con ese nombre ⇒
  `INVALID_PROGRAM(DUPLICATE_NAME)`. Así `util.f` nunca es ambiguo entre un
  módulo y un campo.

## 4. Visibilidad (M2)

- Usar con prefijo algo que existe pero no es `pub` ⇒ `INVALID_PROGRAM(NOT_PUBLIC)`.
- Algo que no existe en el módulo ⇒ `INVALID_PROGRAM(UNKNOWN_NAME)`.
- `x.f(…)`, `x.S {…}` y el tipo `x.S` siempre son nombres calificados (no hay
  métodos): si `x` no es un import de **este** archivo ⇒ `UNKNOWN_NAME`.
- Los campos de un struct `pub` se leen, escriben y construyen libremente.
- **[P4]** Una función `pub` puede usar structs privados en su firma; quien la
  importa podrá pasar esos valores pero no escribir su tipo. No se agrega una
  regla extra.
- `main` de un módulo importado es una función más (no es entrada).

## 5. Errores nuevos

| status | código | cuándo |
|---|---|---|
| `INVALID_PROGRAM` | `UNKNOWN_MODULE` | el archivo del import no existe |
| `INVALID_PROGRAM` | `IMPORT_CYCLE` | un módulo se importa a sí mismo, directa o indirectamente |
| `INVALID_PROGRAM` | `VERSION_MISMATCH` | un módulo importado no tiene cabecera `isyco 0.4` (M4) |
| `INVALID_PROGRAM` | `NOT_PUBLIC` | uso con prefijo de algo no `pub` |

**Orden de los errores estáticos (extiende E4 y v0.3 §7.1):** el archivo
principal (lexer, parser) → sus imports en el orden escrito, en profundidad: por
cada módulo, existe (`UNKNOWN_MODULE`) → no está ya en el camino actual
(`IMPORT_CYCLE`) → cabecera (`VERSION_MISMATCH`) → lexer y parser → sus imports →
enlace de nombres de cada módulo en orden de carga (`DUPLICATE_NAME`,
`UNKNOWN_NAME`, `NOT_PUBLIC`) → el chequeo de v0.3 sobre el programa unido.

## 6. Posiciones, identidad y resultado

- **[P5]** `at` en un módulo importado es `ruta.isy:línea:columna`
  (`geo/punto.isy:3:12`); en el archivo principal sigue siendo `línea:columna`.
- **[P6]** `program_sha256` sigue siendo el SHA-256 del archivo principal. Si el
  programa importa módulos, el resultado agrega `modules`: `{ruta: sha256}` de
  cada módulo usado, para que la identidad cubra todo el código ejecutado. La
  equivalencia entre ejecuciones no cambia (`status`, `code`, `emits`, `return`).
- Pasos, límites, efectos (`!emit`) y orden de evaluación: idénticos a v0.3; una
  llamada a otro módulo es una llamada más.

## 7. IR y backends

- **[P7]** En la IR, las funciones y structs de un módulo importado llevan nombre
  calificado con su ruta: `geo.punto.dist2`, `geo.punto.P`. Los del archivo
  principal no cambian (`main`, `f`).
- Un backend no puede suponer que un nombre de la IR es un identificador de su
  lenguaje (spec/BACKEND.md): los nombres con punto se codifican sin
  ambigüedad (cada segmento con su longitud: `geo.punto.f` → `m_3geo5punto1f`).

## 8. Lo que v0.4 NO incluye

Reexportar, importar nombres sueltos, alias explícitos, imports con comodín,
paquetes o versiones de dependencias, compilar módulos por separado. Cada uno
es una decisión futura.

## 9. Corpus

`programs/conformance_v0.4/` (28 casos, 301–328): un caso = una carpeta con
`main.isy`, sus módulos y `expect.json`, escritos a mano **antes** de implementar. El caso v0.3 `264`
(afirma que `isyco 0.4` es `SYNTAX`) se supera explícitamente al congelar, como
se hizo con v0.1/003 y v0.2/119.
