# Decisión Z2 — cota de 64 niveles de anidamiento, con `SPEC_LIMIT` (2026-11-03)

**Decisión de Danny (2026-11-03), salida (a) del preview —«cota nombrada».** El anidamiento de
expresiones tiene una cota de **64 niveles**, y el nivel 65 se rechaza con `INVALID_PROGRAM` /
**`SPEC_LIMIT`** en el sitio que lo produce, nombrando el nivel y la cota en el mensaje. Antes de
la IR: ningún backend ve el programa, la referencia no lo ejecuta y el conteo no lo decide la
pila del anfitrión. Regla **y** número **y** error nombrado, el mismo patrón que cerró **P4** el
2026-11-02 (`docs/decisions/P4_SPEC_LIMIT.md`), aplicado al borde que Z2 encontró abierto: el
frontend tenía un techo de profundidad que era de Python, se manifestaba como `RecursionError`
—sin número y sin por qué— y **se movía según quién llamara**.

Nace del mismo objetivo que P4 y que N1: una **librería de texto**. La pregunta real no era
«cuánta pila tiene el proceso», sino «qué le pasa a quien escriba una cadena larga de `len(s)` o
un `pad` con cuarenta anchos». Antes: el proceso moría a los 242 términos con una excepción del
anfitrión. Hoy: el programa se rechaza con un error que nombra la cota, y en 61 ms.

## La regla, y qué cuenta

`ast.MAX_EXPR_DEPTH = 64` (`isyco/ast.py`) es un literal normativo del spec —paralelo a
`types.MAX_STR` y a `specialize.MAX_CLONES_PER_DEFINITION`, no un ajuste configurable del
harness—, y se mide **dos veces** porque anidar tiene dos caras que no cuentan lo mismo:

- `Parser.nivel` (`isyco/parser.py`) sube el contador en cada entrada que le cuesta un frame al
  parser —paréntesis, argumentos de llamada, prefijos— y lo baja en un `finally`. Su cuenta es
  la **profundidad de descenso**.
- `Checker.check` (`isyco/checker.py`) mide antes de tocar nada recursivo la cadena de nodos del
  AST con `expr_depth`, iterativo. Su cuenta es la **profundidad del árbol**.

Un solo contador en el parser no basta, y no por prudencia: una suma izquierda de k términos se
construye **en un bucle** y no le baja ni un frame, así que el parser la ve anidar 1 nivel mientras
el AST resultante tiene k. Medido por la sonda (C1): 64 términos `1 + 1 + …` dan AST de 64 con el
parser en calma, y 63 pares de paréntesis dan AST de 1 con el parser en 64. O sea: **las dos caras
llegan al mismo nivel 64 por caminos que no se solapan**, y cada una se topa con el mismo número.
El borde es exclusivo por el lado de arriba (`>`, no `>=`): 64 niveles son legales, 65 se rechazan.

## Por qué 64 y no otro número

Dicho sin adornos: **64 no sale de una medición de techo.** Sale de dos datos medidos el
2026-11-03 (`evidence/z2_depth/run_2026-11-03T074629Z.json` y
`evidence/z2_guard/run_2026-11-03T…`):

| dato | valor | qué aporta a la elección |
|---|---|---|
| profundidad máxima de la población del repo | **8** (`programs/dogfood/01_recibo.isy`) sobre **154** fuentes que bajan | 64 es ocho veces lo más hondo que existe hoy |
| profundidad de la librería de texto | **5** (`programs/dogfood/06_biblioteca_texto.isy`) | el objetivo real está a 12 niveles del borde |
| precio en frames de la cara más cara al tope | **716** de 999 útiles (63 pares de paréntesis) | la forma legal más cara cabe con **283** de aire |
| frames que trae quien llama | **6** (`python3 -m isyco ir`), **10** (un test del paquete) | el aire no se lo come el frontend por su cuenta |
| muro real del anfitrión sin la guarda | **89** pares limpio, **62** con 300 frames encima | cualquier cota por encima de ~60 habría sido una promesa falsa |

Un número de 96 o 128 habría sido **falso en la cara de paréntesis**: esa forma ya no cabe debajo
de 999 frames con un llamante que traiga algo de pila. Un número de 16 habría cortado la libertad
del idioma sin necesidad —la población está en 8—. 64 queda encima de la población por un factor de
ocho, debajo del muro medido con aire, y es 2⁶ en la misma escala de potencias de dos que P4
(256 = 2⁸) y `MAX_STR`. Con la modestia que corresponde: un censo de 154 fuentes no demuestra que
nadie necesite 65; demuestra que **la cota no muerde a nada de lo que el repo hace hoy** — y eso se
mantiene atado, no se infiere: `tests/test_depth.py::LaPoblacionQuedaDebajo` falla si alguna fuente
real sube de 8 o si la población censada cambia de tamaño sin decir nada.

## Dónde se fija cada borde

| borde | quién lo fija | por qué ahí |
|---|---|---|
| 64 niveles legal (último) | `449_parentesis_al_tope`, `451_cadena_izquierda_al_tope`, `453_len_pelado_al_tope` | las tres caras que el corpus puede expresar con `expected` a mano, cada una en **su** tope: 63 pares, 64 términos, 63 términos con clon |
| 65 niveles → `SPEC_LIMIT` | `450_parentesis_pasa_tope`, `452_cadena_izquierda_pasa_tope`, `454_len_pelado_pasa_tope` | el rechazo viaja por el frontend compartido: los cinco backends devuelven lo mismo que la referencia |
| el prefijo `-` | `tests/test_depth.py::CotaNombrada.test_las_tres_caras_llegan_al_mismo_nivel` | no entra al corpus porque su borde **no es 63**: 64 prefijos son nivel 64 porque el último `-` se colapsa en el literal negativo (CORE v0.2 C2), y la cara con clon ya cubre la asimetría |
| el contador no es de la pila | `LaGuardaGanaAlAnfitrion.test_un_llamante_hondo_sigue_obteniendo_spec_limit` + C2 de la sonda | 100 y 300 frames del llamante encima y el borde sigue en 65 |
| la constante es el número | `EsLaGuardaLoQueRechaza` (dos tests) + C7 de la sonda | sabotaje en las dos direcciones: con 200 se aceptan 65 y 121 niveles, con 5 se rechaza una cadena de 6 |

**Asimetría declarada, no escondida:** los conteos fuente a nivel no son iguales entre las cuatro
caras —63 pares, 64 prefijos, 64 términos, 63 términos con clon— y esa asimetría es medible y
está en la sonda (C1, sección `caras`), no en un comentario. Quien lea el verde del corpus sin leer
esta tabla puede creer que «64 términos» es el borde en todas partes y escribir un caso que pasa de
largo sin probar nada.

## Falsificación

- `tests/test_depth.py::EsLaGuardaLoQueRechaza.test_subir_la_cota_devuelve_la_aceptacion`: con
  `MAX_EXPR_DEPTH = 200` (parcheo por `mock.patch.object`, sin tocar el archivo) las cuatro caras
  del borde se **aceptan**. Si la guarda no existiera, este test no tendría nada que aflojar.
- `test_bajar_la_cota_rechaza_lo_que_hoy_es_legal`: con `5`, una cadena de 6 términos que hoy es
  legal se rechaza con `SPEC_LIMIT`. La cota muerde por debajo y por encima: no es un límite que
  solo «corte lo enorme».
- `LaGuardaGanaAlAnfitrion.test_un_llamante_hondo_sigue_obteniendo_spec_limit`: el borde no se mueve
  con la pila. Antes se movía: 241 → 166 con 300 frames encima (C2 y la sonda pre-decisión).
- `test_la_guarda_no_agota_la_pila_que_mide`: la medición del AST es **iterativa**; con 400 frames
  del llamante sigue devolviendo un número en vez de reventar. Una guarda que se desliza por el
  anfitrión sería peor que la ausencia de guarda.
- La sonda lee la constante **viva** de `isyco/ast.py` en cada uso (`COTA = A.MAX_EXPR_DEPTH`), así
  que mover el número mueve las fronteras de la sonda: no hay una copia congelada que se oxide.
- Ningún `expected` ni hash congelado existente se reescribió: los seis casos nuevos entran como
  población nueva (218 → 224), y el cotejo hoja por hoja contra el lote de 218 está en el recibo F2
  que se cita abajo.

## Población y gates después de la decisión

Corpus v0.5 **48 → 54** casos (401–454; 50 de archivo suelto y 4 directorios con módulos), gate
**218 → 224**. Las fronteras previas de la decisión están selladas y no se retocaron:
`evidence/z2_depth/run_2026-11-03T074629Z.json` (E1–E10, `RELEASE_GATE`) sigue siendo el registro
de **por qué** se decidió. Su instrumento, `tools/z2_depth_probe.py`, se volvió a correr después de
la decisión y da `FALSO` en E1–E4 y E6–E10, `DEMONSTRADO` solo en E5 (lectura de procedimiento de
los gates, que no cambió): mide el muro del anfitrión sobre fuentes que el idioma ya rechaza en el
nivel 65. Queda dicho en su docstring, con los tres endurecimientos del arnés que hicieron falta
para que terminara en vez de abortar. La medición del estado **después** es
`tools/z2_guard_probe.py` con sus ocho claims (C1–C8).

## Lo que Z2 NO hace

No quita la recursión de enmedio: `Parser`, `Checker`, `lower` e `interp` siguen siendo recursivos,
y la cota lo que hace es **no dejarlos llegar al muro**. Las otras dos salidas del preview de Z2 —
«quitar la recursión» y «envolver las cinco bajadas de gate fuera de `harness.intento`»— **no se
hicieron**, y no porque fueran malas: porque la (a) era la que compraba la garantía que P4 ya había
puesto para el otro eje (número + error nombrado + antes de la IR).

No borra el muro del anfitrión, y esto es lo importante dicho sin adornos (C8, medido): el fuente
del tope legal —63 pares, 64 niveles— baja con pila limpia **y revienta por `RecursionError` si
quien llama trae 300 frames**, con la guarda puesta. La cota garantiza que **el idioma** decide
dónde está el borde; no garantiza que la forma legal más cara quepa en cualquier pila heredada. Lo
que sí quedó medido es que los llamantes reales del paquete traen 6 y 10 frames, muy por debajo del
aire de 283.

No topa tamaño ni aridad: un árbol balanceado de 2 000 términos (12 niveles, 12 078 bytes) sigue
bajando, y 64 términos en cadena izquierda sobre `str` pelado (695 bytes) se rechaza. El techo es de
**profundidad**, que es lo que Z2 midió, no de bytes ni de nodos totales.

No toca la IR, `ir_validate`, ningún backend, ni la acomodación de pila de la ejecución
(`interp.py:374` y `ir_interp.py:346`, atadas a `max_call_depth`): esa sigue gobernando otro eje —
cuánta pila tiene el **programa ejecutándose**— y sigue sin capturar `RecursionError`. No decide
Z1. No cambia ningún programa `0.1`–`0.4`: la guarda vive en el camino compartido, pero la cota de
64 está ocho veces por encima de la fuente más honda del repo entero, así que no hay fuente
congelada que la roce — medido, C5, con el mismo censo que la sonda pre-decisión.

Y deja una consecuencia que hay que decir en voz alta: la cota **retira libertad que el anfitrión
toleraba**. El fuente de 241 términos `len(s)`, que el 2026-11-03 bajaba a IR por las tres rutas
(`compile_ir`, `interp.run`, `run_via_ir`), hoy se rechaza con `SPEC_LIMIT` (C6). Nadie lo escribe
a mano y la población no lo usa, pero antes **podía** y ahora no puede: una cota nombrada es una
promesa, y las promesas recortan el conjunto de lo que antes pasaba por accidente.

## Claims

| claim | estado | dónde |
|---|---|---|
| El nivel 64 es legal y el 65 es `SPEC_LIMIT`, en las cuatro caras y en el mismo nivel | **DEMONSTRATED** | C1 + `449`–`454` en F2/F3/F4/F5 + `tests/test_depth.py` |
| El borde no se mueve con la pila del llamante | **DEMONSTRATED** | C2 (0…300 frames) + `LaGuardaGanaAlAnfitrion` |
| Rechaza la guarda y no el anfitrión | **DEMONSTRATED** | C7 (cota 200 y cota 5) + `EsLaGuardaLoQueRechaza` |
| La forma legal más cara cabe en el límite de fábrica con aire | **DEMONSTRATED** | C3 (716 de 999) y C4 (llamantes de 6 y 10) |
| Ninguna fuente del repo roza la cota | **DEMONSTRATED** | C5 (154 fuentes, máximo 8) + tripwire en `test_depth.py` |
| El clon de V6 ya no se alcanza por esta vía | **DEMONSTRATED** | C6 (242 términos: `SPEC_LIMIT`, sin `RecursionError`) |
| Sin la guarda el muro estaba **por debajo** de la cota | **DEMONSTRATED** | C8 (89 pares limpio / 62 con 300 frames; el fuente de 64 niveles moría) |
| La cota garantiza que la forma legal quepa en cualquier pila | **FALSO, y medido** | C8: el tope legal con 300 frames del llamante da `RecursionError` |
| 64 es el óptimo | **NOT_DEMONSTRATED** | es una decisión con población delante; nada mide que 65 sea malo ni 63 mejor |

## El sello

- **R2 (grado de gate):** `evidence/z2_guard/run_2026-11-03T213Z…` — `veredicto_arbol`
  `RELEASE_GATE`, árbol de código limpio, C1–C8 `DEMONSTRADO`. Es el recibo al que hay que ir a
  leer la regla después de la decisión.
- **R1 (las del lote, preservadas sin retocar):** `evidence/z2_guard/run_2026-11-03T205940Z.json` y
  `run_2026-11-03T211418Z.json` (sha `f27d59ae`), ambas con `git_head=8e5c2b2` y
  `veredicto_arbol=EVIDENCE_ONLY`: sellaron mientras la documentación de esta decisión estaba a
  medio editar. `run_2026-11-03T211418Z.json` es la que introduce C8 y el segundo llamante de C4;
  la anterior se queda como quedó —el precedente de P4 pide conservar la corrida del lote, no
  borrarla—. Ninguna reescribe a la otra: cada una con su stdout crudo y sus fuentes al lado.
