# Decisión Z3 — cota de 64 niveles de sentencias de control, con `SPEC_LIMIT` (2026-11-12)

**Decisión de Danny (2026-11-12): cerrar Z3 «igual que Z2».** El anidamiento de sentencias de
control tiene una cota de **64 niveles**, y el nivel 65 se rechaza con `INVALID_PROGRAM` /
**`SPEC_LIMIT`** antes de la IR, nombrando el nivel y la cota. Regla, número y error nombrado: el
patrón de P4 y de Z2, aplicado al eje que Z2-b encontró abierto.

Lo que Danny decidió es cerrarla con cota nombrada. **El número 64, qué cuenta como nivel y el
presupuesto de ejecución son propuesta de quien lo implementó**, con el censo delante, y quedan a
revisión suya.

## De dónde sale

`MAX_EXPR_DEPTH` (Z2) acota expresiones. Un `if` dentro de otro no pasa por `Parser.nivel` ni por
`expr_depth`, así que las sentencias anidaban sin cota. P8 de
`evidence/z2_pila/run_2026-11-12T024856Z.json` lo dejó medido: 676 `if` anidados bajaban y 677
morían por `RecursionError`, sin número ni por qué —y ese 676 lo ponía el presupuesto de pila de
Z2-b; sin él, el borde estaba en 324/325—.

## La regla, y qué cuenta

`ast.MAX_STMT_DEPTH = 64` (`isyco/ast.py`), literal normativo paralelo a `MAX_EXPR_DEPTH`.

Un **nivel** es un `if` o un `while` en la cadena que encierra a una sentencia. Tres precisiones:

- el `for` es azúcar de `while` (V2) y cuenta como uno;
- el cuerpo de una función es nivel 0: una función sin control de flujo no anida nada;
- **un `else if` cuenta un nivel más**, porque es un `if` dentro del `else` del anterior. En el
  fuente se lee plano; en el AST, en la IR, en los emisores y en la pila es una cadena. Una
  cadena de 64 ramas `if`/`else if` (más el `else` final) es legal; la rama 65 no.

Se mide dos veces, como Z2:

- `Parser.control` (`isyco/parser.py`) sube el contador al abrir un `if`, un `while` o un `for`
  y lo baja en un `finally`. Es la guarda necesaria: el parser es quien recursiona primero.
- `Checker.check` mide el AST con `stmt_depth`, iterativo.

A diferencia de Z2, **las dos guardas cuentan lo mismo**: aquí no hay una cara que el parser
construya en bucle. La del checker es segunda línea —corta un AST que no pasó por
`Parser.control`— y `test_el_checker_rechaza_aunque_el_parser_no_haya_contado` lo ejerce.

## Por qué 64

**No sale de una medición de techo.** Sale de:

| dato | valor | qué aporta |
|---|---|---|
| anidamiento máximo de la población del repo | **4** (`programs/dogfood/02_csv.isy`) sobre 220 fuentes que parsean | 64 es dieciséis veces lo más hondo que existe |
| histograma | 186 fuentes en 0, 27 fuentes en 1, 4 fuentes en 2, 2 fuentes en 3, 1 fuentes en 4 | la población vive en 0–1 |
| los cinco backends en el tope | C, Rust, Zig, pydecimal y COBOL compilan y ejecutan 64 `if` anidados y la cadena de 64 ramas | la cota no promete nada que un toolchain no dé |
| coste en frames de las dos cotas al tope | 1 039 de 4 096 reservados | cabe con las dos a la vez |

64 es el mismo número que Z2, y eso es deliberado: una sola cifra que recordar para «cuánto se
puede anidar». **El punto débil es el `else if`:** una cadena de 65 ramas es código que alguien
puede escribir a mano (un despacho por casos), y la cota lo rechaza. La población no lo hace —el
máximo es 4— pero un censo de 220 fuentes no demuestra que nadie lo necesite. Si eso pesa, las
salidas son subir el número o hacer que la cadena `else if` no cuente (y entonces quitarle la
recursión en parser, checker, IR y emisores). Ninguna se hizo.

## Lo que arrastró: la pila de la ejecución

Con una sola cota, el coste en frames de **una llamada** del programa no estaba acotado, y la
acomodación de la ejecución —`50 * max_call_depth + 1000`— era una apuesta. Medido: una llamada
recursiva al fondo de 60 `if` gasta 126 frames por llamada, y el programa moría por
`RecursionError` **dentro de `max_call_depth`**. Era un fallo de la referencia normativa
anterior a este cambio, no una consecuencia de él.

Con las dos cotas nombradas el coste por llamada sí tiene techo, y el presupuesto sale de ellas
(`isyco/pila.py`):

- recorridos de árbol: `FRAMES_POR_NIVEL × (MAX_EXPR_DEPTH + MAX_STMT_DEPTH)` = 32 × 128 = 4 096;
- ejecución: `FRAMES_EJECUCION_POR_NIVEL × (64 + 64) × max_call_depth` + 4 096, o sea 512
  frames por llamada. El peor programa legal medido gasta menos de la mitad
  (`LaEjecucionCabe.test_el_presupuesto_dobla_el_coste_medido_por_llamada`).

## Dónde se fija cada borde

| borde | quién lo fija |
|---|---|
| 64 niveles legal, `if` anidado y cadena `else if` | `455_if_anidado_al_tope`, `457_else_if_al_tope` (referencia, IR y cinco backends) |
| 65 → `SPEC_LIMIT`, las mismas dos caras | `456_if_anidado_pasa_tope`, `458_else_if_pasa_tope` |
| `while` y `for` | `tests/test_depth.py::CotaDeSentencias` (mismo contador; no entran al corpus) |
| formas distintas suman | `test_los_niveles_se_suman_entre_formas_distintas` (`while`, `if`, `else if`, `if` = 4) |
| la constante es el número | `test_mover_la_constante_mueve_el_borde`: con 200 se aceptan los 65; con 3 se rechazan 4 |
| el borde no es de la pila | `test_un_llamante_hondo_sigue_obteniendo_spec_limit` (3 000 frames) + P8 |
| las dos cotas a la vez | `test_las_dos_cotas_al_tope_recorren_todo_el_camino` + P9 |
| la ejecución del peor programa | `LaEjecucionCabe` (5 tests) + P10 |
| la población | tripwire en `LaPoblacionQuedaDebajo`: la población real anida exactamente 4 |

## Claims

| claim | estado | dónde |
|---|---|---|
| El nivel 64 es legal y el 65 es `SPEC_LIMIT`, en cuatro caras | **DEMONSTRATED** | P8 + `455`–`458` + `CotaDeSentencias` |
| El borde no se mueve con la pila del llamante | **DEMONSTRATED** | P8 (0, 300, 3 000 frames) |
| Rechaza la guarda y no el anfitrión | **DEMONSTRATED** | sabotaje en las dos direcciones; P11: 677 y 10 000 bloques son `SPEC_LIMIT` |
| Las dos cotas al tope caben en el presupuesto | **DEMONSTRATED** | P9 (1 039 de 4 096) |
| El peor programa legal medido recursiona hasta `max_call_depth` | **DEMONSTRATED** | P10 (250 llamadas, dos rutas, también con 3 000 frames) |
| Los cinco backends ejecutan el tope legal igual que la referencia | **DEMONSTRATED** | `455` y `457` en F5 |
| Ninguna fuente del repo roza la cota | **DEMONSTRATED** | P12 (máximo 4) + tripwire |
| 64 es el óptimo | **NOT_DEMONSTRATED** | decisión con población delante |
| Nadie necesita una cadena `else if` de 65 ramas | **NOT_DEMONSTRATED** | la población no la tiene; no es una prueba |
| El «peor programa» de P10 es el peor que la gramática permite | **NOT_DEMONSTRATED** | es el peor que se supo construir: 64 `if` y 64 niveles de llamadas anidadas |
| Los backends compilados aguantan la recursión del peor programa | **NOT_DEMONSTRATED** | P10 mide la referencia y el intérprete de IR, no los binarios |

## Lo que Z3 NO hace

No quita la recursión: parser, checker, bajada, validador, emisores e intérpretes siguen siendo
recursivos; las cotas no los dejan llegar al muro.

No acota la **cantidad** de sentencias ni de ramas hermanas: mil `if` uno detrás de otro son nivel
1. Tampoco acota la anidación de tipos (`[[[i64; 2]; 2]; 2]`) ni la de literales de struct más
allá de lo que ya cuenta Z2.

Retira libertad que el anfitrión toleraba: entre 65 y 676 `if` anidados bajaban el 2026-11-12 por
la mañana y hoy se rechazan. Nadie lo escribe y la población está en 4, pero antes podía.

No cambia ningún programa `0.1`–`0.4` existente: la guarda vive en el camino compartido y la
población entera está dieciséis veces por debajo.

## El sello

- **Sonda:** `evidence/z2_pila/run_2026-11-12T042036Z.json` (sha `e5bac1c0…`): `RELEASE_GATE`, `arbol_sucio_codigo: false` sobre
  `ec22d57`, P1–P12 `DEMONSTRADO`, 23 fuentes al lado. Instrumento:
  `tools/z2_pila_probe.py` (esquema `/2`: P1–P7 son Z2-b, P8–P12 son Z3).
- **El recibo que abrió Z3**, preservado sin retocar: `evidence/z2_pila/run_2026-11-12T024856Z.json`
  (P8: 676/677, `RecursionError`).
- **Lote de gates con los 228 casos:** ver la tabla de recibos del `README.md`.
- Todo medido en un contenedor (Python 3.13.18, gcc 13.3.0, zig 0.16.0, GnuCOBOL 3.1.2,
  rustc 1.97.0), no en el host de los lotes anteriores (rustc 1.98.1).
