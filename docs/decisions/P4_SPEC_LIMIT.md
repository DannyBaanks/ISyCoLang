# Decisión P4 — tope de 256 especializaciones por definición, con `SPEC_LIMIT` (2026-11-02)

**Decisión de Danny (2026-11-02):** el CORE v0.5 fija un tope de **256 resoluciones de capacidad
por definición fuente dentro del programa**, y la resolución 257 se rechaza con
`INVALID_PROGRAM` / **`SPEC_LIMIT`** en el sitio de llamada que la produce. Granularidad **por
definición** (no por programa, no por módulo), regla **y** número **y** error nombrado — las tres
cosas a la vez, porque un número sin error nombrado es crecimiento silencioso y un error sin
número es una promesa sin cota. Cierra la única fila `[D]` que quedaba en `spec/CORE_v0.5.md` y
la pregunta P4 de `docs/OPEN_QUESTIONS_P1_P4.md`.

Nace del mismo objetivo que N1: una **librería de texto**. La pregunta real no era «cuántas
copias aguanta el compilador», sino «qué le pasa a quien escriba `pad` con cincuenta anchos».
Hoy la respuesta es: el programa se rechaza con un error que nombra la cota, antes de bajar a
la IR.

## La regla, y qué cuenta

`specialize.MAX_CLONES_PER_DEFINITION = 256` (`isyco/specialize.py`) es un literal normativo del
spec — paralelo a `types.MAX_STR`, no un ajuste configurable. El contador vive en
`Checker.spec_counts` (`isyco/checker.py`) y gasta **resoluciones distintas por definición**, no
sitios de llamada:

- La llave es `callee.name`, que ya viene módulo-calificada del enlace, así que «por definición»
  no exige parsear ningún nombre ni inventar una identidad nueva.
- Se incrementa **dentro** del `if name not in self.specs`, y la comparación es `>` **después**
  del incremento: 256 claves distintas son legales, la 257 se rechaza.
- El rechazo es **estático**: el `InvalidProgram` sale con el registro de clones vacío y el
  programa no baja a la IR. `447_tope_de_especializaciones` es exactamente eso: 257 resoluciones
  de una sola definición por la orilla de retorno (V6-bis).

Que el presupuesto sea de resoluciones y no de llamadas no se afirma, se mide, y la medición está
en el borde de la regla: **20 sitios de llamada con el mismo ancho dan 1 clon**
(`tools/v05_p4_probe.py` §4, y `416`/`411` en el corpus). Si el registro contara llamadas, ese
control daría 20 y todo lo demás sería basura.

## Por qué por definición y no por programa

Medido antes de decidir (`evidence/v05_p4/run_20261101T234407Z.json`, población 46 casos): el
peor **programa** del corpus tiene 4 copias, la peor **definición dentro de un programa** 2, y
`doble` acumula **7 en todo el corpus**. Un tope por programa castiga a quien escribe una
función de dos parámetros contextuales, porque el conteo es **multiplicativo en las ranuras** —
una ranura con K anchos da K clones, dos dan W², tres W³ (secciones 2 y 3 de
`run_20261102T081925Z.json`)— mientras que un tope por definición deja crecer a la librería y
corta solo la definición que se dispara. La aritmética de la cota también es por definición:
256 = 2⁸, y con dos ranuras el
espacio útil es 16×16, que es la forma de `448_dieciseis_clones_por_definicion`.

## El número, dicho sin adornos

256 **no** sale de una medición de techo: sale de la escalera del corpus —antes de estos dos
casos la peor definición dentro de un programa usaba **2** copias, y el peor programa 4— y del
hecho de que 256 resoluciones por definición ya son demasiadas para cualquier librería escrita a
mano: a dos ranuras eso es una cuadrícula de 16×16, y a tres la más grande que cabe debajo de la
cota es 6×6×6 = 216. Dicho con la modestia
que corresponde: un censo de 46 casos no demuestra que nadie necesite 257 ni que 256 sea el
óptimo; demuestra que la cota está muy por encima de lo que el corpus usa, y que por debajo de
ella el lenguaje no corta nada.

Lo que **sí** midió la sonda, y cambia el enunciado, es que el número no protege del toolchain:
el tope corta antes de la IR, así que ningún backend ve nunca más de 256 copias de una
definición, pero esas 256 **sí** llegan al compilador y ahí la cota no garantiza nada. Matriz
medida (sección 6 de `run_20261102T081925Z.json`):

| aridad de la definición | Zig | C y rust |
|---|---|---|
| 1 ranura, 256 copias | **OK** | OK |
| 2 ranuras, 256 copias (W=16) | `error: evaluation exceeded 1000 backwards branches` | OK |
| 3 ranuras, 216 copias (W=6) | igual | OK |
| 4 ranuras, 256 copias (W=4) | igual | OK |

Con `--bisect-zig` la frontera queda medida en lugar de afirmada, sobre la forma parcial (las
ranuras primeras fijas en 2, solo suelta la última, paso de 2^(n-1) clones), con los dos bordes
compilados antes de recorrer: **aridad 2 → 250 OK / 252 FALLO; aridad 3 → 164 / 168; aridad 4 →
120 / 128; aridad 1 → SIN_FALLO_DENTRO_DEL_TOPE** (la cota del idioma llega antes que el techo).
Es decir: **hay programas legales bajo P4 que Zig no compila.** Eso abre **Z1**
(`docs/OPEN_QUESTIONS_P1_P4.md`) y es la limitación honesta que está escrita en
`spec/CORE_v0.5.md` §7. No se arregla subiendo o bajando el tope: subir no compra nada (el techo
no es del frontend) y bajar no es una decisión de P4 sin medir la población real de una librería.

## Dónde se fija cada borde

| borde | quién lo fija | por qué ahí |
|---|---|---|
| 256 legal (último) | `tests/test_specialize.py::TopePorDefinicion` | el corpus no puede con él: un caso con 256 clones es legal bajo la regla y Zig no lo compila. Desde el arnés endurecido eso **deja renglón, no abort**, pero el caso sigue fuera del corpus por decisión: se corre con `--extra-case` y tiene recibo propio —`evidence/backends/gate_2026-11-02T235456Z.json` (`4bb9ab5`, `verdict=FAIL`, `zig.corpus.harness` con una fila `TOOLCHAIN_BUILD_FAIL` y `failures: []`) y la sonda `evidence/f5_harness/run_2026-11-02T233718Z.json` (`8df68b8`)—; cierre del hallazgo 13 de `docs/EVIDENCE_MATRIX.md` |
| 257 → `SPEC_LIMIT` | `447_tope_de_especializaciones` (corpus) + el mismo test | el rechazo sí viaja por el frontend compartido: los cinco backends devuelven lo mismo que la referencia sin una línea de `backend_stderr` |
| 16 copias de una definición legal | `448_dieciseis_clones_por_definicion` | piso con la forma que justifica la granularidad (dos ranuras × 4 anchos) |
| el contador no cuenta llamadas | §4 de la sonda + `TopePorDefinicion` | control negativo, no caso de corpus |

**Asimetría declarada, no escondida:** la mutación off-by-one (`>` → `>=`) **no la detecta ningún
sabotaje de corpus**, porque no existe ningún caso con 256 clones. Lo detecta
`TopePorDefinicion.test_256_es_el_ultimo_legal`. Escrito aquí, en `tests/README.md` y en el
`README.md` del corpus para que nadie lea el verde de los sabotajes como cobertura del borde.

## Falsificación

- `tests/test_reference.py::Sabotage.test_el_tope_de_especializaciones_se_desactiva`: con
  `MAX_CLONES_PER_DEFINITION = 10**9` falla **exactamente** `447` (`assertEqual`, no `assertIn`:
  si el tope se apaga y se lleva otro caso por delante, eso es información, no cobertura).
- `test_bajar_el_tope_a_uno_rompe_el_corpus`: con `1` cae `411_pad_dos_anchos` (2 resoluciones de
  `pad`) y **sigue en verde** `416_cast_mas_estrecho` (1 resolución) — la cota muerde por encima
  de 1, no en 1.
- La sonda lee el tope **vivo** de `isyco/specialize.py` en cada uso, así que esas dos mutaciones
  mueven también las curvas de la sonda: no hay una copia del número que se oxide.
- Ningún `expected` ni hash congelado existente se reescribió: en el recibo F2 nuevo las
  **2 727** hojas compartidas con el de 216 salen idénticas salvo `total`, `passed` y el sello del
  recibo (`generated_utc`, `git_head`); no se pierde ninguna y entran 54 nuevas (las dos filas de
  `447` y `448`). El mismo cotejo, extendido a los otros tres gates e indexado por la **identidad
  del renglón** —el caso, y caso más nivel de traza en F3, que ocupa dos renglones por caso;
  alinear por posición devuelve 35 y 53 diferencias falsas, y indexar solo por `name` parte el
  conteo por la mitad—: F3 tiene 3 462 compartidas y 5 distintas (los tres contadores y el sello;
  cero diferencias en los hashes de los 432 renglones previos), F4 tiene 42 compartidas y 14
  distintas (doce contadores `216→218` y el sello; los dos diferenciales, la semilla, los 32
  tipos y los sabotajes idénticos) y F5 tiene 398 compartidas con 39 distintas (contadores,
  campos de costo —no semánticos por `tools/backend_gate.py:67`— y el sello), 2 altas, que son
  `448` entrando al `UNSUPPORTED` de COBOL con `ir0.2,str`, y 0 bajas, con los difftest de 8 484
  y 1 270 idénticos.
  **Corregido el 2026-11-02 en este mismo ADR:** la fila de abajo decía «1 734 hojas» desde
  `d363e7c`, y esa cifra venía de indexar solo por `name`; son 3 462 con la identidad del renglón.
  El error de método queda escrito como hallazgo 14 de `docs/EVIDENCE_MATRIX.md`. Ninguna
  conclusión cambia: siguen siendo 4 y 5 hojas distintas, todas contadores y sello.

## Población y gates después de la decisión

Corpus v0.5 **46 → 48** casos (44 a un archivo + 4 carpetas con módulos), gate **216 → 218**.
Recibos del lote: los cuatro gates registran `git_head=14b19a9`, la sonda R1 registra `203f579` y
la sonda R2 `d363e7c` —`isyco/` y `tools/` son **idénticos** en los tres árboles; entre medias
solo entraron evidencia, documentación y el arreglo de `tests/test_backends.py` (`79670b2`): `git
diff --name-only 14b19a9 d363e7c -- isyco/ tools/` sale vacío—.

| gate | recibo | resultado |
|---|---|---|
| F2 referencia | `evidence/conformance/run_2026-11-02T070428Z.json` | **218/218 `PASS`**, las 2 727 hojas compartidas con el de 216 idénticas salvo los dos contadores y el sello, y ninguna perdida |
| F3 IR | `evidence/ir/gate_2026-11-02T070428Z.json` | **436/436** iguales sobre **149** programas bajados |
| F4 C | `evidence/c/gate_2026-11-02T072103Z.json` | `PASS`, **218/218** en las cuatro combinaciones gcc/clang × plain/sanitized, difftest **24 612** en `gcc/plain` y **6 468** con sanitizers, ambos con 0 diferencias |
| F5 backends | `evidence/backends/gate_2026-11-02T081912Z.json` | `PASS`, c/rust/zig/pydecimal **218/218** con 0 `UNSUPPORTED`, COBOL **148/218** con **70** `UNSUPPORTED` nombrados; difftest **8 484** por backend y **1 270** de strings en los cuatro con `str`, todos con 0 diferencias |
| Sonda P4 — R2 (grado de gate) | `evidence/v05_p4/run_20261102T085025Z.{json,txt}` | `RELEASE_GATE`: censo 48 casos / 49 clones, máximo 16 (448), 2 sin los casos de tope; matriz de toolchain y librería V6 |
| Sonda P4 — R1 (la del lote) | `evidence/v05_p4/run_20261102T081925Z.{json,txt}` | `EVIDENCE_ONLY` por árbol sucio en docs; mismos números que R2, divulgación abajo |

El censo se partió, no se excluyó: con 447 y 448 dentro, el «máximo por definición» del corpus
lo pone el caso que prueba la cota (se muerde la cola), así que la sonda reporta aparte
`casos_de_tope` y el máximo **sin** ellos, que sigue en 2 — esa es la base que decidió el número.

**El sello de la sonda y su limitación, dichos aquí.** `run_20261102T081925Z.json` sale
`veredicto_arbol=EVIDENCE_ONLY` con `arbol_sucio_codigo=true`: mientras corría el lote
estaba esta documentación a medio editar, y la etiqueta pide árbol limpio para decir
`RELEASE_GATE` sin distinguir docs de código (`isyco/` y `tools/` no tenían
modificaciones). No se retocó el recibo: se commiteó tal cual (`5965bd2`). Con el árbol
limpio se vuelve a sellar una corrida nueva en `evidence/v05_p4/` —sin sobrescribir
ninguna—; su nombre y su veredicto van en la sección final de este archivo, y ya están: esa es
**R2**, y es el recibo al que hay que ir a leer la regla y el techo del toolchain.

## Lo que P4 NO hace

No define semántica en ningún backend (la referencia sigue siendo normativa). No toca la IR, ni
`ir_validate`, ni `fn_ident`, ni ningún backend: el tope es del frontend y ahí se queda. No
promete que 256 copias compilen en ninguna parte — **dice lo contrario con la matriz encima**. No
cambia ningún programa `0.1`–`0.4`: `str` contextual solo existe con familia `v05`. No fija una
cota de rendimiento: `512`/`1024`/`2048` clones ya no son construibles, pero eso no es una
garantía de que 256 sean baratos (medido en la sección 5: 172 718 B de IR y 257 funciones).

## Claims

| claim | estado | dónde |
|---|---|---|
| 256 resoluciones por definición son legales y la 257 es `SPEC_LIMIT` | **DEMONSTRATED** | `TopePorDefinicion` (9 tests) + `447` en F2/F3/F4/F5 |
| El presupuesto gasta resoluciones, no sitios de llamada | **DEMONSTRATED** | control §4 de la sonda (20 sitios, 1 clon) + `448` |
| El conteo es multiplicativo en las ranuras | **DEMONSTRATED** | curvas K, W², W³ de la sonda |
| El rechazo es estático y llega igual a los cinco backends | **DEMONSTRATED** | `TopeFrontend` (3 tests) + F5 |
| Con el tope puesto hay programas legales que Zig no compila | **DEMONSTRATED** | matriz §6 y bisección §6b de `run_20261102T085025Z.json` (R2, `RELEASE_GATE`) |
| El número 256 está decidido con la población real delante | **DEMONSTRATED** (decisión) / **NOT_DEMONSTRATED** (que 256 sea el óptimo) | censo 48/49 con `casos_de_tope` partido |
| Ningún programa existente cambia de significado | **DEMONSTRATED** | cotejo hoja por hoja contra los recibos de 216, indexado por la identidad del renglón: 2 727 compartidas en F2 con 4 distintas y 3 462 en F3 con 5 (antes decía 1 734, ver la corrección más arriba), y en los dos son solo contadores (216→218, 432→436, 148→149) más el sello del recibo, con 0 hojas perdidas |
| Sabotear el tope se detecta | **DEMONSTRATED** | dos mutaciones de `tests/test_reference.py` y la lectura viva del número |
## El sello limpio: la corrida R2, nombrada aquí

Lo que anunciaba el párrafo «El sello de la sonda y su limitación» se cumple aquí.

- **R2: `evidence/v05_p4/run_20261102T085025Z.{json,txt}`** — `veredicto_arbol=RELEASE_GATE`,
  `arbol_sucio_codigo=false`, `git_head=d363e7c` (el commit de esta documentación), corrida
  2026-11-02 08:50:25Z con `--bisect-zig --write`. Es el recibo con grado de gate para la regla
  y para el techo del toolchain.
- **R1 sigue donde estaba**: `run_20261102T081925Z.json` (`203f579`, `EVIDENCE_ONLY`), commiteado
  sin retocar en `5965bd2` y verificado con `sha256sum -c` dentro del directorio. No se borró ni
  se sobrescribió ninguna corrida: `evidence/v05_p4/` tiene las cinco (`062234`, `154040`,
  `234407`, `081925`, `085025`).
- **R2 no cambia nada de lo que afirma esta decisión.** Comparación hoja por hoja de los dos
  JSON: **1 135 hojas compartidas, 1 017 idénticas**, y las **118** restantes son **114 campos de
  tiempo** (`ms`, `chequeo_ms`, `c_ms`, `ref_ms`) y **4 del propio sello** (`utc`, `git_head`,
  `arbol_sucio_codigo`, `veredicto_arbol`). Cero diferencias estructurales (ninguna hoja aparece
  o desaparece) y cero diferencias en los números que se citan arriba: el censo 48/49, el máximo
  16 en `448` y 2 sin los casos de tope, `chequeo=SPEC_LIMIT` con `clones=0` en 512/1024/2048, la
  matriz `aridad × ancho` y las cuatro fronteras biseccionadas (250/252, 164/168, 120/128 y
  `SIN_FALLO_DENTRO_DEL_TOPE`).
- **Lo que R2 no compra:** sigue sin ser una demostración de que 256 sea el óptimo, ni de que Zig
  pueda con 256 copias de dos ranuras. **Z1** sigue abierta con su medición hecha.

Comprobación, desde la raíz del repo: `(cd evidence/v05_p4 && sha256sum -c SHA256SUMS.txt)` — 10
archivos listados (los cinco `.json` con sus cinco `.txt`), todos «La suma coincide». La lista
**no se incluye a sí misma**: `tools/v05_p4_probe.py:995` la filtra al regenerarla, y por eso se
verifica desde adentro del directorio.
