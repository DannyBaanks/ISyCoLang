# Preguntas del CORE v0.5: P1–P4 y lo que abrió la implementación

**Estado (2026-11-01).** P1, P2 y P3 están **cerradas por medición**. P4 queda
**abierta a propósito**: el enunciado pedía cerrar midiendo, no inventando un número, y la
medición ya está hecha y sellada — lo que falta es la decisión, ahora con dos lecturas
posibles que la medición distingue. Aparecieron además tres puntos que la propuesta no
preveía (N1–N3). **N2 se cerró el 2026-11-01 con el caso `443`**, **N3 con el texto de
§4.1 más su matriz en la sonda** y **N1 el mismo día, adoptada, con tres casos y sus
gemelos y el texto de §4.4 sin el `[D]`**. Queda como decisión de Danny antes de congelar
`spec/CORE_v0.5.md` **solo P4**.

Las preguntas vienen de `spec/CORE_v0.5_propuesta.md` §2, donde se marcaron **[P]**.
Las pruebas se pueden re-correr: `tools/v05_revalida_probe.py`, `tools/v05_v6_probe.py`,
`tools/v7_capability_probe.py`, `tools/v05_p4_probe.py` y `tools/v05_spec_probe.py` — estos
dos últimos sellan las aristas que el borrador de la spec afirma y el corpus no fija.

| id | pregunta | respuesta | dónde está la prueba |
|---|---|---|---|
| P1 | ¿qué `at` llevan las sentencias sintéticas del `for`? | el del `for` | gate F2.4 ítem 2 + `tests/test_v05_core.py:ForAzucar` |
| P2 | ¿se permite `for x in [1, 2, 3]`? | **no**: `SYNTAX` | `tools/v05_spec_probe.py` §4 |
| P3 | nombre de la especialización: ¿afecta a `program_sha256` y a las trazas? | identidad **no**, traza **sí** | `tools/v05_spec_probe.py` §6, `tests/test_specialize.py` |
| P4 | ¿cuántas especializaciones puede crear un programa? | **abierto**, con censo y forma sellados | `evidence/v05_p4/run_20261101T062234Z.json` |
| N1 | ¿`for c in s` con `s: str<N>` es normativo? | **cerrada el 2026-11-01 — adoptado**: la regla de §4.4 ya no tiene `[D]` y tres casos la fijan | `programs/conformance_v0.5/444`–`446` + sus gemelos, `tools/v05_spec_probe.py` §7 |
| N2 | ¿algún caso fija el cruce con raíz `0.5` de M4? | **cerrada el 2026-11-01** | `programs/conformance_v0.5/443_m4_modulo_v04/` + `tools/v05_spec_probe.py` §1 |
| N3 | ¿el `let` sin anotación es inferencia? | **cerrada el 2026-11-01**: no, es solo el sintético del `for` | `spec/CORE_v0.5.md` §4.1 + `evidence/v05_spec/run_20261101T153344Z.json` §3 |

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

**Medición** (`tools/v05_spec_probe.py` §4, siete formas más): la posición del iterando
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
gate** (`load_corpus`: los 42 casos de `programs/conformance_v0.5` que había al sellar,
incluidos los 3 con
módulos, que un glob de `.isy` se llevaba por delante). **Re-medido el 2026-11-01 con `443`
dentro** — `evidence/v05_p4/run_20261101T154040Z.json` (sha `101e2cfc…`, `RELEASE_GATE`
sobre `2938c01`, `arbol_sucio_codigo=false`), sobre los **43** casos y los 4 directorios de
módulos: **los mismos 32 clones en los mismos 18 programas**, las tres curvas y el control
negativo byte a byte iguales, y en `costo` los mismos `fuente_bytes`, `ir_bytes`,
`ir_funciones` y `pasos` en los siete tamaños (solo difieren `ref_ms` y `c_ms`, que son de
una corrida suelta). La diferencia del censo es un renglón: `443` aparece con **0 clones** y
su `VERSION_MISMATCH`, y los casos que rechaza el frontend pasan de 11 a **12**. La
predicción que estaba escrita aquí («lo esperable es que el número no se mueva») quedó
confirmada por medición, no por lectura del caso.

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
| techo encontrado | **ninguno hasta 2048 clones**: 2.139.231 B de fuente, 3.228.420 B de IR (2049 funciones), `ref_ms` 508,7 / `c_ms` 1037,0 en `run_20261101T062234Z.json` y 458,9 / 986,1 en `run_20261101T154040Z.json` — los bytes y los pasos son iguales en las dos, los milisegundos no; `HALTED` y EQUIV contra la referencia en ambas |

**Corregida 2026-11-01, segunda pasada.** La fila del techo traía «474 ms de referencia,
3,7 s de `c_ms`», que no son los valores del recibo (`508,7` y `1037,0`): los escribí de
memoria tras la corrida sin re-leer el JSON. Es el mismo fallo que esta sección denuncia —
una cifra en prosa que no está en el recibo que la nombra —, así que la fila cita ahora
los bytes y los milisegundos exactos de `censo`/`costo`. Nada de lo demás cambia: el techo
sigue sin aparecer y los 2048 clones siguen dando `HALTED` y EQUIV.

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

## N1 — `for` sobre un `str` `[CERRADA el 2026-11-01 — por caso y por texto]`

`for c in s` con `s: str<N>` funciona: emite los bytes (`104 111 108 97` sobre
`"hola"`). No es una operación nueva — es `len(s)` y `s[i]` de v0.3— y su `while` gemelo
de **forma idéntica** cuesta lo mismo (24 pasos los cuatro programas de la matriz: `for`
/ `while`, ancho fijo / `str` pelado; medido en `tools/v05_spec_probe.py` §4). Pero la
propuesta §2 describía el iterando como «`expr` de tipo `[T; N]`», así que **no estaba
adoptado**, y ningún caso del corpus lo fija. Es exactamente lo que una librería de
texto necesita (`cuenta_letra`, `mayus`). Opción recomendada: adoptarlo como normativo
con su caso y su gemelo. Lo contrario: rechazarlo en el checker para que el azúcar sea
solo de arreglos.

**Cerrada el 2026-11-01, adoptada.** Danny eligió adoptarla con tres casos y sus gemelos, y la
regla quedó escrita en `spec/CORE_v0.5.md` §4.4 sin el `[D]`: **todo lugar de tipo `str`**
(local `str<N>`, campo calificado, parámetro `str` pelado de V6, entrada por stdin) se recorre
`len(s)` veces y la variable es `u8` **copia**; la cota es la **longitud del valor**, no la
capacidad declarada. Los tres casos, en `programs/conformance_v0.5/`: `444_for_sobre_str`
(`str<8>` con `"hola"` emite `104 111 108 97` y devuelve `4` — fija longitud ≠ capacidad),
`445_for_str_pelado_stdin` (N1 × V6: `fn emite(s: str)` sobre `"mundo"` por stdin, cinco bytes
y `return 5`) y `446_for_copia_str` (`c = 65` dentro del bucle emite `65 65 65` y `s[0]` sigue
dando `97` — copia, sin aliasing). Cada uno con su gemelo `while` escrito a mano en `gemelos/`,
misma salida y misma traza `stmt` e IR. La población sube de 43 a **46** casos y del gate de
213 a **216**; ningún `expected` de los 213 anteriores se movió y **no hizo falta tocar
`isyco/`**: el azúcar es agnóstico del tipo del lugar — `parser.py:334-350` construye un lugar
y `interp.py:238` resuelve `len` en tiempo de ejecución.

Los cuatro recibos de la corrida de 216: referencia `216/216`
(`evidence/conformance/run_2026-11-01T210445Z.json`, sha `62da1207…`), IR `432/432` sobre 148
programas bajados (`evidence/ir/gate_2026-11-01T210450Z.json`, sha `8473534c…`), F4 `PASS` con
`216/216` en las cuatro combinaciones (`evidence/c/gate_2026-11-01T211424Z.json`, sha
`3ba9864e…`) y F5 `PASS` con c/rust/zig/pydecimal `216/216` y COBOL `147/216` con 69
`UNSUPPORTED` (`evidence/backends/gate_2026-11-01T225011Z.json`, sha `63d7a9b4…`). Los tres
primeros en un solo lote con `git_head=2499fae`; F5 se re-corrió solo porque su corrida en
`2499fae` dio `FAIL` por un `TIMEOUT` del arnés en el diferencial de strings de pydecimal —
recibo preservado con su diagnóstico en `evidence/f5_flake/run_20261101T220854Z.json`— y en la
re-corrida esa misma pasada de 1 270 casos salió con 0 diferencias. Ninguna de las 213 filas
anteriores se movió.

Rechazarla era lo contrario de lo que fija V2: el desugaring no ve tipos y el checker solo ve
un `let` sintético sin anotación (`checker.py:204-209`), así que negar el `str` exigía etiquetar
los nodos sintéticos — y el `while` gemelo escrito a mano seguiría siendo legal, o sea el `for`
dejaría de ser azúcar.

**Corrección al párrafo de arriba.** «24 pasos los cuatro programas de la matriz: … medido en
`tools/v05_spec_probe.py` §4» mezcla dos cosas. La matriz de forma constante está en **§5**, no
en §4, y sus 24 pasos son de un recorrido **dentro de una función**; el programa de la forma de
`444` —todo dentro de `main`— gasta **22**, y su gemelo lo mismo. Medido y pinneado en
`tests/test_v05_core.py:PASOS_EXIGIDOS`: 444 → 22/22, 445 → 27/27, 446 → 22/22 (`for` vs
gemelo). Es el mismo fallo de citación que el hallazgo 1 de `docs/EVIDENCE_MATRIX.md`, y la
misma corrección quedó en el spec. La sonda tiene ahora sección propia para N1 (**§7**) con los
bordes que el corpus no fija (`str<1>` vacío, `for c in s[0]`, campo calificado, anidado) y el
espejo del sabotaje.

**Cómo se falsifica.** `tests/test_reference.py::Sabotage.test_len_de_str_se_hace_estatico`
pliega `len` de un `str` a su capacidad declarada —lo que V1 hace con los arreglos— y rompe
`444_for_sobre_str` (`INDEX_OUT_OF_BOUNDS` en el quinto byte). Decisión y controles completos:
`docs/decisions/N1_FOR_SOBRE_STR.md`.

**Lo que N1 NO abre:** no hace legal `for x in [1, 2, 3]` (P2 sigue siendo `SYNTAX`), no da
soporte de `str` a ningún backend (COBOL pasa los tres casos como `UNSUPPORTED`), y no toca `len`
de `str`, que ya era de v0.3.

## N2 — M4 generalizada, sin caso de corpus `[CERRADA el 2026-11-01 — por caso]`

La regla es ahora «todo módulo tiene la **misma versión** que la raíz»
(`modules.py:48`). Medido en las ocho combinaciones raíz ∈ {0.4, 0.5} × módulo ∈
{0.2, 0.3, 0.4, 0.5}: ejecutan solo `0.4/0.4` y `0.5/0.5` (`HALTED`, `return 7`); las
seis restantes son `VERSION_MISMATCH` (`tools/v05_spec_probe.py` §1). El corpus cubre la
diagonal `0.5/0.5` (`408`) pero **no** cubre ningún cruce con raíz `0.5`, que es el
renglón nuevo de la regla. Falta un caso (`4xx`) que lo fije antes de congelar.

**Cerrada el 2026-11-01:** entra `443_m4_modulo_v04` (raíz `0.5`, módulo `0.4` →
`VERSION_MISMATCH`); la población sube de 42 a **43** casos y del gate de 212 a **213**.
Los cuatro gates se re-corrieron sobre `a4f608c` y quedaron sellados:
`evidence/conformance/run_2026-11-01T074055Z.json` (`213/213`),
`evidence/ir/gate_2026-11-01T074055Z.json` (`426/426`),
`evidence/c/gate_2026-11-01T074655Z.json` (`PASS`) y
`evidence/backends/gate_2026-11-01T082046Z.json` (`PASS`). Qué cruce fija cada caso, leído
en su `expected`: `0.4/0.4` en `301` y compañía (`HALTED`), `0.4/0.3` en `308`
(`VERSION_MISMATCH`), `0.5/0.5` en `408` y ahora `0.5/0.4` en `443`. Con raíz `0.3` no hay
cruce que fijar: ahí `import` ni siquiera existe y `319` da `SYNTAX`, así que M4 nunca se
evalúa. **Siguen sin caso propio** `0.5/0.2`, `0.5/0.3` y `0.4/0.5`: los cubre la sonda (§1,
las ocho combinaciones) y `0.4/0.5` además está corrido como control al alta de `443`, con
su tabla en `programs/conformance_v0.5/README.md`. Añadir los tres sería repetir el mismo
renglón de `modules.py:48`.

## N3 — el `let` sin anotación `[CERRADA el 2026-11-01 — por texto y por sonda]`

`let x = a[i];` no es legal en el lenguaje (CORE §4 exige anotación); la única
excepción es el `let` que inyecta el azúcar del `for` (`checker.py:205-209`), que toma
el tipo del elemento. La implementación ya lo hace así y `402`–`405` lo ejercen, pero
**el texto no lo dice**: hay que escribirlo en la spec para que la excepción no se lea
como un `let` inferencial general. Lo contrario sería una regla nueva (inferencia de
tipos) que v0.5 no pretende.

**Cerrada el 2026-11-01:** el texto está en `spec/CORE_v0.5.md` §4.1 — y corrige lo que la
versión anterior del borrador afirmaba, que el `let` sintético tomaba el tipo del **índice**
(toma el del **elemento**, `checker.py:205-209`). Medido en la sonda nueva, sección 3
(`let_anotacion`): cuatro formas, `let x = 1;` escrito a mano en `0.5` y en `0.4` (los dos
`SYNTAX`), `let x: i32 = 1;` (`HALTED`, `1`) y el `for x` sobre `[dec<8,2>; 2]` (`HALTED`,
`3.85`, o sea el tipo del elemento). Sello
`evidence/v05_spec/run_20261101T153344Z.json` (sha `067fbf1b…`, `RELEASE_GATE` sobre
`a4ef362`). La matriz trae tres controles de sabotaje: si un `let x = 1;` escrito a mano
llegara a correr, si las dos formas del `let` dieran el mismo `status`, o si una fila se
desvía de su predicho, la sonda se auto-falsifica y no sella.
