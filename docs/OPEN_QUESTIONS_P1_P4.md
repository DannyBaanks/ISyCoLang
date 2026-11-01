# Preguntas del CORE v0.5: P1–P4 y lo que abrió la implementación

**Estado (2026-11-01).** P1, P2 y P3 están **cerradas por medición**. P4 queda
**abierta a propósito**: el enunciado pedía cerrar midiendo, no inventando un número, y la
medición ya está hecha y sellada — lo que falta es la decisión, ahora con dos lecturas
posibles que la medición distingue. Aparecieron además tres puntos que la propuesta no
preveía (N1–N3) y que son decisión de Danny antes de congelar `spec/CORE_v0.5.md`.

Las preguntas vienen de `spec/CORE_v0.5_propuesta.md` §2, donde se marcaron **[P]**.
Las pruebas se pueden re-correr: `tools/v05_revalida_probe.py`, `tools/v05_v6_probe.py`,
`tools/v7_capability_probe.py`, `tools/v05_p4_probe.py` y `tools/v05_spec_probe.py` — estos
dos últimos sellan las aristas que el borrador de la spec afirma y el corpus no fija.

| id | pregunta | respuesta | dónde está la prueba |
|---|---|---|---|
| P1 | ¿qué `at` llevan las sentencias sintéticas del `for`? | el del `for` | gate F2.4 ítem 2 + `tests/test_v05_core.py:ForAzucar` |
| P2 | ¿se permite `for x in [1, 2, 3]`? | **no**: `SYNTAX` | `tools/v05_spec_probe.py` §3 |
| P3 | nombre de la especialización: ¿afecta a `program_sha256` y a las trazas? | identidad **no**, traza **sí** | `tools/v05_spec_probe.py` §5, `tests/test_specialize.py` |
| P4 | ¿cuántas especializaciones puede crear un programa? | **abierto**, con censo y forma sellados | `evidence/v05_p4/run_20261101T062234Z.json` |

## P1 — las posiciones del azúcar `[CERRADA]`

El enunciado: las sentencias que `for` inyecta (`let foridx{n} = -1`, el `while`, el
`Assign`, el `let x`) no existen en el fuente, así que alguien tiene que decir qué
posición llevan.

**Respuesta:** todas llevan `at` = la posición del `for` (`parser.py:347-351` construye
los nodos con el `at` recibido en `for_stmt`). Consecuencia: un error de tipos dentro
del cuerpo o en la cota apunta a la línea que el programista escribió, no a una línea
inexistente.

**Cómo se comprueba sin copiarse la respuesta a sí misma:** el gate exige que la traza
`stmt` del `for` sea la del `while` gemelo **línea a línea salvo los `at`**. Eso es un
control de dos filos —si el azúcar cambiara de posición la comparación sigue siendo
útil, y si la forma cambiara se rompe— y vive como test, no como prosa:
`ForAzucar.test_la_traza_stmt_es_la_traza_del_gemelo` (17, 22, 35 y 19 filas para
402/403/404/405, iguales a las de su gemelo tras normalizar el nombre del índice).

Recibo: `evidence/v05_revalida/run_20261101T001608Z.json` (`RELEASE_GATE`,
`git_head=dcd6880`, `arbol_sucio_codigo=false`).

**Qué la reabriría:** cualquier expansión que inyecte sentencias con un `at` tomado del
cuerpo o del iterando; o un `for` cuyo índice sea visible en un mensaje de error.

## P2 — `for` sobre un literal de arreglo `[CERRADA: no]`

El enunciado recomendaba **no**, porque un literal de arreglo sin tipo esperado es
`AMBIGUOUS_LITERAL` (v0.3 §3.5) y el `for` no aporta tipo esperado. Faltaba probarlo.

**Medición** (`tools/v05_spec_probe.py` §3, siete formas más): la posición del iterando
no es una expresión, es un **lugar** (`IDENT ("." IDENT)*`):

| forma | observado |
|---|---|
| `for x in xs`, `for x in p.xs`, `for x in p.q.ys` | `HALTED` con los elementos esperados |
| `for x in [1, 2, 3]` | `INVALID_PROGRAM(SYNTAX)` — **P2 cerrada: no** |
| `for x in xs[0]`, `for x in (xs)`, `for x in id(xs)` | `INVALID_PROGRAM(SYNTAX)` |

Las dos razones por las que la posición es un lugar y no una expresión son medidas, no
estéticas: (a) `p.xs { … }` sería ambiguo con la sintaxis de un literal de struct, y
(b) copiar una llamada o un literal en la cota **y** en el índice la evaluaría dos
veces, duplicando sus efectos. La cota usa `len(<lugar>)` con `<lugar>` duplicado, que
es seguro precisamente porque un lugar no tiene efectos.

**Qué la reabriría:** que el lenguaje reciba un tipo esperado en posición de `for`, o
arreglos de longitud dinámica (B9, fuera de v0.5).

## P3 — los nombres de la especialización `[CERRADA]`

El enunciado: si V6 monomorfiza, los nombres nuevos (`pad.8`, `geo.pad.8.16`,
`pad.8.r16`) tienen que caber en la IR, en los identificadores de cada backend y en la
**identidad** del programa.

**Respuesta medida, en tres partes** (sello `evidence/v05_spec/run_20261101T043007Z.json`,
sha `ad8d7c29…`, `RELEASE_GATE` sobre `a9a17bc`):

1. **La identidad no se mueve.** `program_sha256` sigue siendo el SHA-256 del archivo
   principal (v0.4 §6 P6) porque la especialización ocurre en el checker, después de
   leer la fuente. Medido en `411`, `417` y `420`: el `program_sha256` del resultado es
   igual al `sha256` del `.isy` en los tres casos.
2. **La traza sí lo muestra.** En `411` las funciones que aparecen en la traza `stmt`
   son `main`, `pad.2` y `pad.7`; la definición pelada `pad` nunca aparece, porque no
   se chequea ni se ejecuta (V6 §Cómo se resuelve). Es observable y está fijado como
   control: si un recibo mostrara `pad` a secas, la sonda lo reporta como falso.
3. **No colisionan.** Los anchos son segmentos adicionales del nombre calificado, y
   `backends/base.py:fn_ident` ya codifica los nombres con punto por longitud de
   segmento (`m_4geo3pad…`), inyectivo. La secuencia se lee sola: decimales sin ceros a
   la izquierda, el segmento del retorno empieza con `r`, y la base no puede terminar en
   un segmento numérico porque el léxico no admite un identificador que empiece en
   dígito. Canario: `414` y `415` son el mismo programa con las llamadas en orden
   inverso y resuelven las mismas dos copias (`tests/test_specialize.py:Nombres`).

**Qué la reabriría:** cambiar `fn_ident`, permitir literales de arreglo sin contexto en
el nombre, o que `program_sha256` pase a hashar el AST enlazado (ahí las copias entrarían
en la identidad por la puerta).

## P4 — cota de especializaciones por programa `[ABIERTA, base sellada]`

El enunciado decía: *«se decide midiendo el primer corpus, no inventando un número»*. La
medición está hecha y sellada en `evidence/v05_p4/run_20261101T062234Z.json` (sha
`26af3945…`, `RELEASE_GATE` sobre `52f5564`, `arbol_sucio_codigo=false`), recalculada
desde el instrumento — `Checker.specs` en `isyco/checker.py` — y sobre **la población del
gate** (`load_corpus`: los 42 casos de `programs/conformance_v0.5`, incluidos los 3 con
módulos, que un glob de `.isy` se llevaba por delante).

| magnitud | medido |
|---|---|
| clones en el corpus v0.5 | **32** en 18 programas (26 sin retorno pelado = V6, 6 con él = V6-bis) |
| máximo de copias por programa | **4** (`413_encadenar_contextuales`) |
| máximo de copias por definición **dentro de un programa** | **2** (12 pares caso+definición lo alcanzan) |
| máximo de copias por definición **en todo el corpus** | **7** (`doble`; después `largo` 5, `pad` 4) |
| escalera de anchos de parámetro | 1, 2, 3, 4, 6, 7, 8, 10, 16, 64 |
| escalera de anchos de retorno (V6-bis) | 4, 8, 16 |
| una ranura, K anchos distintos | **K** clones (K = 1…256) |
| dos ranuras, W anchos cada una | **W²** clones (W = 2, 3, 4, 6, 8) |
| tres ranuras | **W³** clones (W = 2, 3) |
| 20 sitios de llamada con el MISMO ancho | **1** clon — el registro cuenta resoluciones, no llamadas |
| techo encontrado | **ninguno hasta 2048 clones**: 2,1 MB de fuente, 3,2 MB de IR, 474 ms de referencia, 3,7 s de `c_ms` en C, `HALTED` y EQUIV contra la referencia |

Los recibos anteriores de V6 y V6-bis (`evidence/v05_v6/run_20261031T104749Z.json` y
`run_20261031T184709Z.json`, ambos `RELEASE_GATE`) sí sellan el diferencial por backend,
pero **no contienen ningún censo de clones**: lo que `docs/decisions/V6_CONTEXTUAL_STR.md`
y `V6B_CONTEXTUAL_RETURN.md` afirmaban («22 clones», «máximo 2 por definición, sin ningún
caso que pida una tercera») estaba en prosa. Corregido el 2026-11-01 en las dos Decisiones
y en `ROADMAP.md`.

**Lo que la medición cambia en el enunciado.** «Máximo 2 por definición» era ambiguo y las
dos lecturas dan reglas distintas: como cota **por programa** se cumple hoy con margen (el
peor caso es 4); como cota **global del corpus** ya está rota — `doble` tiene 7 copias. Y
como el conteo es **multiplicativo en las ranuras**, un tope por programa castiga a quien
escribe una función de dos parámetros contextuales frente a quien escribe diez de una.

**Por qué sigue abierta.** Fijar el número sin estas curvas era una ocurrencia; con ellas
sigue siendo decisión de Danny, y el costo de equivocarse es asimétrico: un tope bajo rompe
librerías que hoy funcionan (la de texto usa `pad`, `doble`, `junta`), un tope alto no
protege de nada — medido: hasta 2048 copias no hay fallo, solo crecimiento silencioso.
Lo que falta para cerrarla es elegir **granularidad** (por definición en un programa / por
programa / por módulo), **número**, y el **error nombrado** que se lanza al superarlo
(`SPEC_LIMIT` u otro) en lugar del crecimiento silencioso. Con esa decisión hay un caso de
límite que la fije en el corpus.

**Permanece mientras:** no exista un programa real (la librería de texto del dogfood) que
produzca más copias de las que el corpus produce hoy.

## N1 — `for` sobre un `str` `[NUEVA, decisión pendiente]`

`for c in s` con `s: str<N>` funciona: emite los bytes (`104 111 108 97` sobre
`"hola"`). No es una operación nueva — es `len(s)` y `s[i]` de v0.3— y su `while` gemelo
de **forma idéntica** cuesta lo mismo (24 pasos los cuatro programas de la matriz: `for`
/ `while`, ancho fijo / `str` pelado; medido en `tools/v05_spec_probe.py` §4). Pero la
propuesta §2 describía el iterando como «`expr` de tipo `[T; N]`», así que **no estaba
adoptado**, y ningún caso del corpus lo fija. Es exactamente lo que una librería de
texto necesita (`cuenta_letra`, `mayus`). Opción recomendada: adoptarlo como normativo
con su caso y su gemelo. Lo contrario: rechazarlo en el checker para que el azúcar sea
solo de arreglos.

## N2 — M4 generalizada, sin caso de corpus `[NUEVA, medición sin corpus]`

La regla es ahora «todo módulo tiene la **misma versión** que la raíz»
(`modules.py:48`). Medido en las ocho combinaciones raíz ∈ {0.4, 0.5} × módulo ∈
{0.2, 0.3, 0.4, 0.5}: ejecutan solo `0.4/0.4` y `0.5/0.5` (`HALTED`, `return 7`); las
seis restantes son `VERSION_MISMATCH` (`tools/v05_spec_probe.py` §1). El corpus cubre la
diagonal `0.5/0.5` (`408`) pero **no** cubre ningún cruce con raíz `0.5`, que es el
renglón nuevo de la regla. Falta un caso (`4xx`) que lo fije antes de congelar.

## N3 — el `let` sin anotación `[NUEVA, regla que hace falta escribir]`

`let x = a[i];` no es legal en el lenguaje (CORE §4 exige anotación); la única
excepción es el `let` que inyecta el azúcar del `for` (`checker.py:205-209`), que toma
el tipo del elemento. La implementación ya lo hace así y `402`–`405` lo ejercen, pero
**el texto no lo dice**: hay que escribirlo en la spec para que la excepción no se lea
como un `let` inferencial general. Lo contrario sería una regla nueva (inferencia de
tipos) que v0.5 no pretende.
