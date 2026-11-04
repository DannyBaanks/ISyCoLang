# Preguntas del CORE v0.5: P1–P4 y lo que abrió la implementación

**Estado (2026-11-03).** P1, P2, P3 y **P4** están **cerradas**. P4 se cerró el 2026-11-02 con
la decisión de Danny —**256 resoluciones por definición dentro del programa**, rechazadas con
`SPEC_LIMIT`— sobre la base sellada que este documento ya tenía; la regla está en
`spec/CORE_v0.5.md` §7 y la decisión en `docs/decisions/P4_SPEC_LIMIT.md`. Cerrar P4 abrió una
pregunta que la decisión no puede responder: **Z1**, si el techo de un toolchain concreto forma
parte del idioma. Aparecieron además tres puntos que la propuesta no
preveía (N1–N3). **N2 se cerró el 2026-11-01 con el caso `443`**, **N3 con el texto de
§4.1 más su matriz en la sonda** y **N1 el mismo día, adoptada, con tres casos y sus
gemelos y el texto de §4.4 sin el `[D]`**. No queda ninguna decisión abierta antes de congelar
`spec/CORE_v0.5.md`. **Z1 se respondió por medición el 2026-11-03**
(`evidence/z1_ceiling/run_2026-11-03T035753Z.json`): el techo que la abrió no era de Zig sino de
cómo el emisor escribía el programa, y hoy no queda ningún testigo concreto — la pregunta de
política sigue siendo de Danny. La medición abrió otra, **Z2**: un techo de *profundidad* en el
frontend de referencia que era artefacto del anfitrión Python y lo pagaba la propia referencia
normativa. **Z2 se cerró el 2026-11-03 con una cota nombrada de 64 niveles, `SPEC_LIMIT` y las
dos guardas del caso** (`docs/decisions/Z2_MAX_EXPR_DEPTH.md`); la única pregunta que sigue
abierta es Z1, ahora sin testigo concreto.

Las preguntas vienen de `spec/CORE_v0.5_propuesta.md` §2, donde se marcaron **[P]**.
Las pruebas se pueden re-correr: `tools/v05_revalida_probe.py`, `tools/v05_v6_probe.py`,
`tools/v7_capability_probe.py`, `tools/v05_p4_probe.py` y `tools/v05_spec_probe.py` — estos
dos últimos sellan las aristas que el borrador de la spec afirma y el corpus no fija. Las de
Z1 y Z2 son `tools/z1_ceiling_probe.py`, `tools/z2_depth_probe.py` y `tools/z2_guard_probe.py`;
las dos de Z2 no tocan ningún toolchain, la de Z1 sí invoca a Zig y Rust. `z2_depth_probe` mide
el techo **antes** de la decisión y `z2_guard_probe` el estado **después**, sobre los mismos
materiales: correr la primera hoy mide fuentes que el idioma ya rechaza, y así está dicho en su
docstring.

| id | pregunta | respuesta | dónde está la prueba |
|---|---|---|---|
| P1 | ¿qué `at` llevan las sentencias sintéticas del `for`? | el del `for` | gate F2.4 ítem 2 + `tests/test_v05_core.py:ForAzucar` |
| P2 | ¿se permite `for x in [1, 2, 3]`? | **no**: `SYNTAX` | `tools/v05_spec_probe.py` §4 |
| P3 | nombre de la especialización: ¿afecta a `program_sha256` y a las trazas? | identidad **no**, traza **sí** | `tools/v05_spec_probe.py` §6, `tests/test_specialize.py` |
| P4 | ¿cuántas especializaciones puede crear un programa? | **cerrada el 2026-11-02**: **256 resoluciones por definición dentro del programa**, la 257 es `SPEC_LIMIT` estático | `docs/decisions/P4_SPEC_LIMIT.md`, `447`/`448`, `tests/test_specialize.py::TopePorDefinicion`, `evidence/v05_p4/run_20261102T085025Z.json` (R2, `RELEASE_GATE`) |
| Z1 | ¿el techo de un toolchain forma parte del idioma? | **abierta y sin testigo concreto (2026-11-03)**: el techo no era de Zig sino del emisor; con el alias por ancho y la cuota del cuerpo compilan las ocho formas medidas, hasta 2048 instanciaciones, y coinciden con la referencia y con C | `evidence/z1_ceiling/run_2026-11-03T035753Z.json` (C1-C10); la bisección histórica que abrió la pregunta sigue en `evidence/v05_p4/run_20261102T085025Z.json` (R2) §6/§6b; la guarda del fallo ya-nombrado, `evidence/f5_harness/run_2026-11-02T233718Z.json`; el re-run que la cerró, `evidence/backends/gate_2026-11-03T040610Z.json` |
| Z2 | ¿el frontend de referencia tiene un techo de profundidad de expresión, y de quién es? | **cerrada el 2026-11-03 — cota nombrada: 64 niveles, el 65 es `INVALID_PROGRAM`/`SPEC_LIMIT` antes de la IR.** Sí había techo y era del anfitrión: una cadena izquierda de 241 términos `len(s)` se aceptaba y 242 soltaban `RecursionError` contra el límite de fábrica de Python, sin número y sin por qué; sin el clon de V6 la misma forma llegaba a 329; el techo bajo lo ponía el `copy.deepcopy` con que `specialize.py:55` copia el cuerpo por resolución (985 de 999 frames) y lo pagaba igual la referencia normativa por las tres rutas. La guarda va en **dos puntos con un solo número** (`Parser.nivel` y `Checker.check` con `expr_depth`) porque anidar tiene dos caras que no cuentan lo mismo, y las cuatro caras llegan al **mismo nivel 64** con conteos de fuente distintos. Es profundidad y no tamaño: un árbol de 2000 términos sigue bajando | decisión: `docs/decisions/Z2_MAX_EXPR_DEPTH.md`; antes: `evidence/z2_depth/run_2026-11-03T074629Z.json` (E1-E10, `RELEASE_GATE`) con sus cinco fuentes selladas, apareció en el claim C10 de `evidence/z1_ceiling/run_2026-11-03T035753Z.json`; después: `tools/z2_guard_probe.py` con `evidence/z2_guard/run_2026-11-03T211418Z.json` (C1-C8) y su re-sello `RELEASE_GATE`, `run_2026-11-04T001913Z.json` (sha `5a295289…`, sobre `7022ae4`, corrido justo después de los cuatro gates); los bordes, `449`–`454` y `tests/test_depth.py` |
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

## P4 — cota de especializaciones por programa `[CERRADA el 2026-11-02 — regla, número y error]`

**Decisión (2026-11-02, de Danny): 256 resoluciones por definición dentro del programa, y la
257 se rechaza con `SPEC_LIMIT`.** Las tres cosas a la vez —granularidad, número y error
nombrado— porque un número sin error es crecimiento silencioso y un error sin número no es una
cota. Regla y limitación honesta en `spec/CORE_v0.5.md` §7; decisión completa, evidencia y
falsificación en `docs/decisions/P4_SPEC_LIMIT.md`; los dos casos que la fijan son `447` (la
resolución 257 → `INVALID_PROGRAM/SPEC_LIMIT`) y `448` (16 = 4×4 copias de una definición de dos
ranuras, legal). Lo que la decisión **no** compra es techo de toolchain: con el tope puesto Zig
sigue reventando antes, y eso es la pregunta **Z1** más abajo.

Todo lo que sigue debajo de esta línea es la base **sellada antes** de decidir, conservada tal
cual: el enunciado pedía cerrar midiendo y esa medición es la que Danny tenía delante.

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

**Re-medido de nuevo el 2026-11-01, ya con N1 dentro** — `evidence/v05_p4/run_20261101T234407Z.json`
(sha `7d3bafba…`, `RELEASE_GATE` sobre `6ebb00d`, `arbol_sucio_codigo=false`), sobre los **46**
casos y los cuatro directorios de módulos: **33 clones en 19 programas**, 27 sin retorno pelado
y 6 con él, 13 definiciones únicas. El clon extra es `emite.16` de `445_for_str_pelado_stdin` —el
`str` pelado de V6 recorrido por un `for`—, y `444_for_sobre_str` y `446_for_copia_str` aportan
**0**, así que el azúcar del `for` no especializa nada por sí solo: lo que especializa es el
`str` contextual que ya estaba. Cotejo recibo-vs-recibo con la corrida de las 15:40: las 43 filas
compartidas son idénticas en nombres y conteos, `casos_con_error` sigue con los mismos 12, y las
secciones `curva_una_ranura`, `curva_dos_ranuras`, `curva_tres_ranuras` y `control_mismo_ancho`
salen byte a byte iguales. En `costo` las siete filas conservan `fuente_bytes`, `ir_bytes`,
`ir_funciones`, `pasos`, `c_equiv`, `control`, `chequeo` y `status`; solo difieren `ref_ms` y
`c_ms` (para `K=2048`: `458,9`/`986,1` entonces, `470,8`/`989,8` ahora).

**Re-medido el 2026-11-02 con la decisión dentro** —
`evidence/v05_p4/run_20261102T085025Z.json` (**R2**, `RELEASE_GATE` sobre `d363e7c`, árbol
limpio), que repite con el árbol despejado la corrida del lote: **R1**
`run_20261102T081925Z.json` (`EVIDENCE_ONLY` sobre `203f579`, `arbol_sucio_codigo=true`: la
documentación del lote estaba a medio editar mientras corría, con `isyco/` y `tools/` intactos)
sigue en su sitio y commiteada sin retocar (`5965bd2`). Hoja por hoja, R2 repite R1: de las
1 135 hojas compartidas, las 118 distintas son 114 campos de tiempo y las 4 del propio sello.
Sobre los **48** casos y los cuatro directorios de módulos:
**49 clones en 20 programas**, 14 definiciones únicas. Los 16
clones nuevos son los de `dim` en `448` (4×4), y `447` aporta **0** porque se rechaza antes de
especializar. La tabla de abajo es la **base de 46 casos**, la que Danny tenía delante para
elegir; sobre ella el máximo por definición dentro de un programa era 2 y por eso la sonda
reporta ahora aparte `casos_de_tope` y `max_por_definicion_en_un_programa_sin_casos_de_tope`
(**sigue en 2**): con `448` dentro, el «máximo por definición» del corpus lo pondría el caso que
prueba la cota, que es morderse la cola. `casos_con_error` pasa de 12 a **13** (`447`). La
escalera de anchos de parámetro gana el **5** —`448` usa 5, 6, 7 y 8— y queda
`[1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 64]`; la de retornos (V6-bis) no se mueve: 4, 8, 16.

| magnitud | medido (base de 46 casos, sellada el 2026-11-01) |
|---|---|
| clones en el corpus v0.5 | **33** en 19 programas sobre los 46 casos (27 sin retorno pelado = V6, 6 con él = V6-bis); sobre 43 eran 32 en 18 |
| definiciones únicas especializadas | **13** (antes 12; la que entra es `emite` de `445`, con 1 copia) |
| máximo de copias por programa | **4** (`413_encadenar_contextuales`) |
| máximo de copias por definición **dentro de un programa** | **2** (12 pares caso+definición lo alcanzan) |
| máximo de copias por definición **en todo el corpus** | **7** (`doble`; después `largo` 5, `pad` 4) |
| escalera de anchos de parámetro | 1, 2, 3, 4, 6, 7, 8, 10, 16, 64 |
| escalera de anchos de retorno (V6-bis) | 4, 8, 16 |
| una ranura, K anchos distintos | **K** clones (K = 1…256) |
| dos ranuras, W anchos cada una | **W²** clones (W = 2, 3, 4, 6, 8) |
| tres ranuras | **W³** clones (W = 2, 3) |
| 20 sitios de llamada con el MISMO ancho | **1** clon — el registro cuenta resoluciones, no llamadas |
| techo encontrado | **ninguno hasta 2048 clones**: 2.139.231 B de fuente, 3.228.420 B de IR (2049 funciones), `ref_ms` 508,7 / `c_ms` 1037,0 en `run_20261101T062234Z.json`, 458,9 / 986,1 en `run_20261101T154040Z.json` y 470,8 / 989,8 en `run_20261101T234407Z.json` — los bytes y los pasos son iguales en las tres, los milisegundos no; `HALTED` y EQUIV contra la referencia en las tres |

**Corregida 2026-11-01, segunda pasada.** La fila del techo traía «474 ms de referencia,
3,7 s de `c_ms`», que no son los valores del recibo (`508,7` y `1037,0`): los escribí de
memoria tras la corrida sin re-leer el JSON. Es el mismo fallo que esta sección denuncia —
una cifra en prosa que no está en el recibo que la nombra —, así que la fila cita ahora
los bytes y los milisegundos exactos de `censo`/`costo`. Nada de lo demás cambia: el techo
sigue sin aparecer y los 2048 clones siguen dando `HALTED` y EQUIV.

**Corregida 2026-11-02 por la decisión.** Esa fila del techo **ya no es construible**: con P4
dentro, `512`, `1024` y `2048` anchos distintos de una misma definición se cortan en el
frontend —el recibo nuevo los reporta como `chequeo=SPEC_LIMIT`, `resoluciones_max=257` y
`clones=0`, y conserva las fuentes de 141 663 / 545 375 / 2 139 231 B para que el renglón de
arriba siga comprobable—. Lo que la fila afirmaba para su población sigue siendo verdad en el
recibo que la nombra: antes del tope no aparecía ningún techo del *lenguaje*. Lo que no sabía es
que había un techo del *toolchain* por debajo, y eso se midió aparte: **Zig** aborta la
evaluación en tiempo de compilación con 256 copias de una definición de dos ranuras mientras C y
Rust las compilan (sección 6 del recibo y **Z1** abajo).

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

**Cómo se decidió, dicho con las curvas delante.** El costo de equivocarse es asimétrico y la
asimetría no se deshizo con la medición: un tope bajo rompe librerías que hoy funcionan (la de
texto usa `pad`, `doble`, `junta`) y un tope alto, mientras el error no exista, no protege de
nada. Danny eligió **por definición dentro del programa** porque el conteo es multiplicativo en
las ranuras —una ranura con K anchos da K clones, dos W², tres W³— y un tope por programa
castigaría a quien escribe una función de dos parámetros contextuales frente a quien escribe
diez de una; eligió **256** sobre la base de 46 casos (peor definición: 2) y porque a dos ranuras
es una cuadrícula 16×16; y eligió el **error nombrado** `SPEC_LIMIT` en lugar del crecimiento
silencioso, estático y antes de la IR. La decisión está sellada con sus dos casos, sus nueve
tests de checker y su matriz de toolchain en `docs/decisions/P4_SPEC_LIMIT.md`.

**Permanece mientras:** la condición del enunciado —«no exista un programa real que produzca más
copias de las que el corpus produce hoy»— no ocurrió: la librería del dogfood, sintetizada en la
forma real de tres módulos, llega a **58** clones con ocho anchos por pool y **ninguna definición
pasa de 6**, a un mundo de distancia de la cota. P4 se cerró con la población real delante.

## Z1 — ¿el techo de un toolchain forma parte del idioma? `[ABIERTA desde 2026-11-02]`

Z1 no existía antes de P4: cerrar P4 es lo que la abrió. Con la cota de 256 puesta, el frontend ya
no deja pasar más copias, así que ningún backend recibe programas fuera de la cota — pero **dentro**
de ella hay programas que un backend concreto no puede construir. Medido en
`evidence/v05_p4/run_20261102T085025Z.json` (R2, `RELEASE_GATE`; R1 tiene los mismos valores
no temporales) — sección 6 de la forma `aridad × ancho`, y su
bisección con `--bisect-zig`:

| aridad | escalera de la sonda (clones) | frontera de Zig (biseccionada, bordes compilados) | C y Rust |
|---|---|---|---|
| 1 ranura | 8 · 16 · 32 · 64 · 96 · 128 · **256** — todas OK | `SIN_FALLO_DENTRO_DEL_TOPE` | OK |
| 2 ranuras | 16 · 64 · 144 OK, **256** (W=16) FALLO | **250 OK / 252 FALLO** | OK |
| 3 ranuras | 64 · 125 OK, **216** (W=6) FALLO | **164 OK / 168 FALLO** | OK |
| 4 ranuras | 81 OK, **256** (W=4) FALLO | **120 OK / 128 FALLO** | OK |

> Las cuatro fronteras de esta tabla son del **emisor de ese día**, no de Zig: así lo midió Z1 el
> 2026-11-03 y está escrito más abajo. Se conservan sin retocar porque son el registro de la corrida
> que abrió la pregunta, y porque la bisección sigue siendo la de `evidence/v05_p4/…` (R2).

El fallo es de evaluación en tiempo de compilación (`error: evaluation exceeded 1000 backwards
branches`), no de enlaces ni de memoria, y la bisección barre una forma **parcial**: fija en 2 las
ranuras primeras y suelta la última, así que el umbral es de esa forma (paso de 2^(n-1) clones por
ranura) y no de la escalera de anchos iguales. Lo que Z1 pregunta, en términos de decisión: ¿es
aceptable que un programa legal de v0.5 compile en C y Rust y no en Zig, o el idioma tiene que
heredar el techo del toolchain más débil?

Lo que **no** es la respuesta obvia: ni subir el tope (no compra nada: el techo no es del
frontend) ni bajarlo sin medir (compraría la ignorancia de programas que hoy sí compilan en los
cuatro completos). Lo que falta para cerrarla es decidir si la cota de una capacidad es del
idioma, del backend, o de los dos con un `UNSUPPORTED` nombrado por plataforma —y, si se elige lo
último, en qué capa vive ese dato, porque hoy `PROGRAM_REQUIRES` (V7) describe **contenido**, no
costes de compilación.

**El arnés dejó de ser parte de la pregunta (2026-11-03).** Hasta el lote anterior Z1 tenía un
coste de instrumento encima: el mismo programa legal de 256 clones que Zig no compila se llevaba
por delante F5 sin dejar recibo (hallazgo 13 de `docs/EVIDENCE_MATRIX.md`), así que discutir la
frontera de Zig significaba quedarse sin gate. Hoy esa fuente corre y el fallo es un renglón: la
sonda `evidence/f5_harness/run_2026-11-02T233718Z.json` (`8df68b8`, siete claims `DEMONSTRADO`) y
el gate con `--extra-case`, `evidence/backends/gate_2026-11-02T235456Z.json` (`4bb9ab5`,
`verdict=FAIL` con `zig.corpus.harness` de una fila `TOOLCHAIN_BUILD_FAIL`, `failures: []` y
cobol/C/Rust/pydecimal respondiendo normal). Z1 queda entonces como lo que es: una pregunta de
capacidad, no de arnés.

**La pregunta se respondió por medición (2026-11-03), y la premisa se cayó.**
`tools/z1_ceiling_probe.py` separó los dos mecanismos que estaban mezclados. Zig cobra **una** rama
de evaluación por instanciación de `str` (acotado: 960 sitios con una firma de cuatro parámetros
caben en los 1000 de fábrica y 1024 revientan, con el mismo texto de error en las cuatro formas que
mueren). El emisor de octubre cobraba **dos**, porque cada sitio instanciaba además su propio tipo;
por eso la bisección de P4 cortó en 500 OK / 504 FALLO. Prueba directa, no inferencia: el punto que
P4 selló como FALLO —504 instanciaciones— compila **sin** la cuota del emisor con el arreglo puesto
(lo que lo arregló fue el alias, que bajó el coste de dos ramas a una), y 1024 instanciaciones
siguen muriendo sin esa cuota aunque el alias ya esté: la cuota no es el adorno que arregló P4, es
lo que sostiene el resto (claims C1, C4 y C7). Los dos mecanismos son distintos y no son
intercambiables: la misma cuota escrita a nivel de **archivo** no autoriza el marco del cuerpo (C2,
sabotaje medido en 0,7 s), y la **firma** vive en su propio marco —una declaración de 1024
parámetros `IsyStr(2)` agota el de la declaración aunque el cuerpo traiga su cuota, y
`const Str2 = IsyStr(2);` lo evita (C3)—. El arreglo cabe en tres líneas por función y está
conmuteado: un `const StrN = IsyStr(N);` por ancho usado en todo el código, y
`@setEvalBranchQuota(1000 + 8·sitios)` como primera sentencia de todo cuerpo que instancia `str`
(el ocho es margen sobre el coste medido, no aritmética; un programa sin `str` no escribe ni una
cosa ni la otra). Con eso compilan las ocho formas de la sonda —incluida la aridad 2048, la firma
más grande probada— y cada una coincide con la referencia y con C (C5, C8). Continuidad con el FAIL
que motivó la guarda de F5: el caso extra de 256 clones de cuatro ranuras tiene hoy
`program_sha256 = 52a28039…`, **el mismo del recibo** `gate_2026-11-02T235456Z.json`, y compila
(C6). Y el gate re-corrido con ese emisor salió `PASS`:
`evidence/backends/gate_2026-11-03T040610Z.json` (`b4b8873`, `RELEASE_GATE`) da 219/219 en c, rust,
zig y pydecimal con **cero filas de arnés** en
las cinco piernas; el FAIL del 2026-11-02 se conserva intacto como estaba. Lo que NO se afirmó: que
el arreglo sea barato (18 s para 512 sitios y 60,8 s para el caso extra; la cuota levanta el techo,
no acelera el compilador — C9, dato para F6) ni que no haya otro techo más arriba (aridad no está
topada por el idioma, así que el producto `256 clones × aridad` sigue siendo construible y no se
midió por encima de 2048 instanciaciones en un cuerpo).

**Z1 queda entonces como pregunta de política sin testigo.** Lo que la abrió —«hay programas
legales que un backend concreto no puede construir»— no se reproduce con el emisor de hoy en
ninguna forma medida. Lo que sigue siendo de Danny es lo que la medición no puede decir: si el
idioma debe heredar el **coste** de un toolchain (aquí: decenas de segundos por programa, y un
techo que se compra con una línea escrita en el fuente generado), y en qué capa viviría ese dato
si se eligiera nombrarlo —hoy `PROGRAM_REQUIRES` (V7) describe contenido, no costes—. Bajar la
cota de P4 para tapar esto habría comprado ignorancia; subirla no compra nada, porque el techo no
era del frontend. Ninguna de las dos se hizo.

**Y la medición abrió Z2.** Buscar el techo de Zig con una cadena de `len(s)+len(s)+…` terminó en
un `RecursionError` del propio frontend antes de que el programa llegara a IR: eso es
`## Z2` más abajo, y es una pregunta de anfitrión, no de toolchain.

**Lo que sigue sin medir es el otro modo de romperse.** `Backend.build()`
(`isyco/backends/base.py:182`) llama al compilador sin `timeout=`: un toolchain que se **cuelga**
en vez de morir no produce `ToolchainBuildFailure` y cuelga la pierna igual que antes del arreglo.
La guarda ampara «muere», no «no devuelve»; el `timeout_ms` de 60 s existe para la *ejecución* del
binario, no para su construcción. Escrito como `NOT_DEMONSTRATED` — este lote no lo toca y no hay
recibo que lo afirme en ningún sentido.

**Permanece mientras:** un backend del corpus falle por volumen de especializaciones dentro de la
cota del idioma, y nadie haya dicho si eso es un bug del backend o una frontera del lenguaje.

## Z2 — ¿hay techo de profundidad, y de quién es? `[CERRADA 2026-11-03: 64 niveles, SPEC_LIMIT]`

Z2 apareció midiendo Z1: la cadena de `len(s) + len(s) + …` con que se buscaba la frontera de Zig
revienta antes de que el programa llegue a IR. **No es del emisor, ni del idioma, ni de un
toolchain: es del anfitrión Python.** La ruta `compile_ir` —`load` → `check` → `lower` →
`validate`— desciende por la expresión de forma recursiva, así que lo que agota el límite de
fábrica de Python (1000 frames) es la **profundidad** de una expresión, no el tamaño del
programa. Medido en `evidence/z2_depth/run_2026-11-03T074629Z.json` (`tools/z2_depth_probe.py`,
head `d4bb95a`, diez claims E1–E10 `DEMONSTRADO`, `RELEASE_GATE`, `arbol_sucio_codigo=false`), con
cada caso en un proceso hijo de pila limpia y tres familias de la misma forma:

| familia | frontera | qué la pone |
|---|---|---|
| `str` pelado (dispara el clon de V6) | **241 OK / 242** `RecursionError` | el `copy.deepcopy` del clon |
| `str<64>` (misma forma, sin clon) | **329 OK / 330** `RecursionError` | la recursión del frontend |
| `i64` (sin `str` ninguno) | **329 OK / 330** `RecursionError` | la recursión del frontend |

De esa tabla caen cuatro cosas, y ninguna es la que la pregunta esperaba.

**Primera: no hay un techo, hay dos, y el más bajo lo pone el clon** (E1, E2). Cada resolución de
una definición contextual copia el cuerpo entero, y esa copia es recursiva. En el caso que muere,
**985 de los 999 frames** del traceback son de `copy.py`, y las marcas que asoman por debajo son
`checker.py:check|block|call|_typeof` — la línea que copia es `isyco/specialize.py:55`,
`clone = copy.deepcopy(fn)`. La atribución no es una inferencia: es la pila de la excepción. Los
mismos 242 términos escritos con `str<64>` bajan a IR sin excepción (E2, medido en la misma
corrida), y las dos familias sin clon cortan a un término una de otra sobre forma y término
idénticos: lo que separa 241 de 329 no es el AST sino si hay resolución contextual de `str`.

**Segunda: el número no es una capacidad de nada** (E3, E8). Bajar la frontera depende de cuánta
pila traiga quien llama: con 0 frames previos corta en 241, y con 50, 100, 150, 200 y 300 previos
corta en 228, 216, 203, 191 y **166**. Y se mueve a voluntad con `sys.setrecursionlimit`: 242
términos pasan con 2000 de límite y 1200 con 5000, mientras 6000 no pasan **ni con 20000** y 60000
no pasan con 200000. Un techo que cambia con el llamante no se puede escribir en una spec.

**Tercera: el techo lo paga la semántica normativa, no un detalle del camino a la IR** (E10). El
mismo fuente que muere en `compile_ir` a 242 términos muere igual por `interp.run` —la referencia
de F2, que es la semántica según `AGENTS.md` regla 4— y por `run_via_ir`, en las dos familias; la
bisección de la ruta de referencia corta en 241 OK / 242, a cero términos de la bajada, con los
**mismos dos `program_sha256`** (`151ac361…` OK, `5e2d021e…` FALLO) y el `deepcopy` comiéndose el
99 % de los frames también ahí. Y la acomodación de pila que **sí** existe está mal atada (E4):
las dos del paquete — `sys.setrecursionlimit(max(old, 50 * lim["max_call_depth"] + 1000))` en
`isyco/interp.py:374` y `isyco/ir_interp.py:346` — envuelven la **ejecución** del intérprete y
se restauran en un `finally`, así que la bajada de un fuente nunca pasa por ahí — subir
`max_call_depth` no abre margen en el frontend. Nadie captura `RecursionError` en `isyco/`, y no
existe `MAX_DEPTH` ni `profundidad_max` de expresión (búsqueda medida, cero coincidencias). Lo
que produce este techo, por tanto, no es un rechazo: el checker **acepta** el programa, no existe
`SPEC_LIMIT` ni `UNSUPPORTED` ni número, y sube una excepción de Python.

**Cuarta: es profundidad, no tamaño — y la población está a un orden de magnitud** (E9, E6). Un
árbol de 2000 términos (22097 bytes, profundidad 12) se acepta, mientras una cadena izquierda de
242 (2277 bytes) revienta. Censada la población con la misma regla sobre las **151 fuentes del
repo que bajan a IR** (127 son rechazos a propósito): la profundidad de expresión **máxima de
todo el repo es 8** (`programs/dogfood/01_recibo.isy`) y la librería de texto que motivó V6 está
en **5** (`programs/dogfood/06_biblioteca_texto.isy`), frente a los 241 medidos; la regla
`cadena(k) → profundidad k+1`, calibrada sobre tres puntos que sí bajan a IR (3→4, 120→121,
200→201), pone la cadena que muere en 242. Es el mismo tipo de margen que encontró el censo de P4
(2 clones por definición contra una cota de 256): el techo es real y hoy nadie lo roza.

**Lo que sí cuesta: el clon se paga en tiempo, y es multiplicativo** (E7). Bajar un programa con
200 resoluciones de un cuerpo de 2 términos cuesta **0,076 s**; las mismas 200 resoluciones con un
cuerpo de 240 términos cuestan **4,663 s** en la sola referencia, sin compilador delante — y eso
está dentro de lo que el tope de P4 permite (256 por definición). Como P4 topa clones **por
definición** y la aridad no está topada, el producto `clones × términos` sigue siendo construible
dentro del idioma. Dato para F6, que mide costes.

**Dónde tropieza con los gates** (E5). Cinco bajadas del frontend están fuera de
`harness.intento`: `tools/ir_gate.py:62`, `:66` y `:67` y `tools/backend_gate.py:77` llaman al
frontend pelado — el cuarto a propósito: «si la referencia explota, el bug es del idioma y tiene
que subir» — y en `tools/backend_gate.py:170` la bajada se evalúa como **argumento** de `intento`,
es decir antes del paraguas. Lo que las cubre es la capa 3 de cada gate (`except Exception` en
`tools/ir_gate.py:77` y `tools/backend_gate.py:334`), así que **el recibo no se pierde**: un
programa suficiente profundo sale `FAIL` con `abortado`. Lo que se pierde es la pierna entera y la
identidad del caso, que queda solo en el excerpt del traceback en vez de una fila
`HARNESS_INTERNAL` con `leg`/`case`/`program_sha256` — la forma en que el hallazgo 13 de
`docs/EVIDENCE_MATRIX.md` cerró el lado del toolchain. Medido aparte: envuelto a propósito en
`intento`, el mismo fuente de 242 términos da esa fila con excepción `RecursionError`. Hay código
para registrar el crash; no lo hay para evitarlo ni para nombrarlo.

**NOT_DEMONSTRATED**, escrito antes de decidir nada: dónde está el techo físico del anfitrión si
se sube el límite — en todo el rango medido el fallo siguió siendo `RecursionError` y nunca una
señal del proceso, con 188 MB de RSS en el punto más hondo (60000 términos con límite 200000),
así que no se sabe si un `setrecursionlimit` alto desemboca en desbordamiento de C stack—; **la
consecuencia atribuida a los gates es lectura de código, no ejercida**: ninguna de las cinco
bajadas se ejecutó con un programa que reviente dentro de un gate real; si el `parser` solo o el
`checker` solo tienen fronteras propias por debajo de la compuesta (aquí se midió la ruta
completa); y cuánto cuesta el `deepcopy` frente a una copia superficial con compartición (no
medido).

**Las tres salidas que existen**, sin recomendar ninguna —es decisión de Danny y depende de si se
quiere un límite *nombrado* o ninguno—: (a) una guarda explícita con número medido sobre la
población, en el patrón que ya fijó P4 (`SPEC_LIMIT` estático, antes de la IR, con el por qué),
que además obligaría a decir si la cota cuenta con clon o sin él; (b) quitar la recursión de
enmedio —copiar el clon con un recorrido explícito, o no copiar el cuerpo entero—, que sube el
techo sin nombrar ninguno pero toca el mecanismo más sensible del checker; (c) envolver las cinco
bajadas en `intento`, que es lo mínimo y no requiere decidir la cota. Lo que no vale es el estado
de hoy: un techo que existe, no lo nombra nadie, depende del llamante y lo paga la referencia
normativa.

Prueba: `evidence/z2_depth/run_2026-11-03T074629Z.json` (`DEMONSTRADO`, diez claims) con sus cinco
fuentes selladas y `tools/z2_depth_probe.py`; continuidad con el claim C10 de
`evidence/z1_ceiling/run_2026-11-03T035753Z.json`, que es donde apareció.

### Decidida el 2026-11-03: la salida (a), cota de 64 niveles

Danny eligió **(a)** — «cota nombrada», en el preview del 2026-11-03: `RecursionError` del
anfitrión convertido en `INVALID_PROGRAM`/`SPEC_LIMIT` con un número medido, en el patrón que fijó
P4, antes de la IR y con el por qué en el mensaje. Las salidas (b) y (c) **no se hicieron**: (b)
toca el mecanismo más sensible del checker sin comprar la garantía que se pidió, y (c) es lo mínimo
pero deja el borde en manos del anfitrión. Nada de lo escrito arriba se reescribió: es el registro
de la medición que sostuvo la decisión, y su recibo sigue siendo la prueba del «antes». Decisión,
números y límites: `docs/decisions/Z2_MAX_EXPR_DEPTH.md`.

Lo que quedó puesto es **un número en dos puntos**: `ast.MAX_EXPR_DEPTH = 64`, ejercitado por
`Parser.nivel` (cuenta los niveles que le bajan frames) y por `Checker.check` (mide la cadena de
nodos del AST con `expr_depth`, iterativo). Se midió que hacen falta los dos y no por prudencia:
una suma izquierda de k términos se construye en un bucle y no le baja ni un frame al parser, así
que un contador de solo-parser veía anidar 1 nivel un AST de 64.

Los números del «después», todos sellados en `evidence/z2_guard/` (C1–C8 de
`tools/z2_guard_probe.py`): el borde cae en el **mismo nivel 64** en las cuatro caras del anidar
—63 pares de paréntesis, 64 prefijos `-`, 64 términos sumados, 63 términos `len(s)` con clon—; con
0, 50, 100, 150, 200 y 300 frames del llamante el rechazo sigue siendo `SPEC_LIMIT`; la cara más
cara al tope pide **716** frames de los 999 útiles y los llamantes reales del paquete llegan con
**6** (la CLI) y **10** (un test); la población del repo sigue en **8** sobre **154** fuentes que
bajan; los 242 términos que morían se rechazan en **27 ms** (0,027 s medidos en las dos fuentes,
C6 de `evidence/z2_guard/run_2026-11-04T001913Z.json`), y con ellos los **241 que antes
bajaban** — nombrar el borde cuesta dejar fuera lo que el anfitrión toleraba—; y con
`MAX_EXPR_DEPTH` levantado a 200 el muro del anfitrión aparece en **89** pares con pila limpia y
**62** con 300 frames encima, o sea que estaba **por debajo** de la cota que hoy se eligió: sin la
guarda, un fuente de 64 niveles moría según quién llamara.

**La cota no borra el muro**, y es la limitación que queda escrita (C8, y en `spec/CORE_v0.5.md`
§7): con la guarda puesta, el fuente del tope legal —63 pares, 64 niveles— baja con pila limpia y
revienta por `RecursionError` si quien llama trae 300 frames. Lo garantizado es que el **idioma**
nombra el borde, no que la forma legal quepa en cualquier pila heredada. La salida (b) habría
cambiado esto; la (a) lo deja como limitación nombrada.

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
