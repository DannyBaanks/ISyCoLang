# Decisión V6 — `str` sin capacidad en los parámetros (2026-10-30)

**Decisión:** especializar en el frontend, antes de la IR. La IR no conoce V6.

Medición que lo motivó (`docs/DOGFOOD_2026-10-30.md` §8, `spec/CORE_v0.5_propuesta.md` §8):
`programs/dogfood/06_biblioteca_texto.isy` escribe `pad`, `empieza_con`, `cuenta_letra`
y `mayus` en `isyco 0.4` y corre en los cinco ejecutores — la semántica de capacidades
ya estaba (`checker.py:str_binary`). Lo que no se podía era **reutilizar una sola
definición a distintos anchos**: `pad(s: str<8>)` obliga a reescribir `pad` para
`str<24>`.

## Qué es una capacidad diferida

`ContextStrT` (`isyco/types.py`) representa el `str` **escrito sin capacidad**. Solo
existe en el AST de la definición, antes de especializar:

- `ty_to_json` (`isyco/ir.py`) no la conoce y `type_size` lanza `AssertionError` si
  alguien la mide: una capacidad diferida que llega a la IR es un bug, no un dato.
- No hay centinela numérico en ningún lado. Cero, `-1`, `None` y `MAX_STR` (`65536`)
  siguen significando lo de siempre; «abierto» no se codifica con un entero.
- El parser solo la acepta en parámetros (`fn p(s: str)`), y solo con `isyco 0.5`.
  En un `let`, un campo de struct, un `cast` o un arreglo sigue siendo `SYNTAX`: ahí
  no hay contexto que la fije. El retorno se abre en V6-bis.

## Cómo se resuelve

`Checker.call` tipa el argumento **sin** esperar nada: si el parámetro está pelado,
la capacidad instanciada es la del tipo real del argumento. Un literal sin contexto
aporta la suya propia (`"hi"` ⇒ `str<2>`, `""` ⇒ `str<1>` por la regla v0.3
`max(len, 1)`), y eso es medible, no una excepción: caso `412`.

Por cada clave `(nombre, anchos en orden posicional [, ancho de retorno])` se hace una
copia del `A.Fn` con los tipos ya acotados (`isyco/specialize.py:make_clone`) y se
reescribe el `A.Call` al nombre de la copia. La definición original **nunca se
chequea**: lo que se chequea es cada copia, con tipos corrientes del core v0.3. Nada
de esto toca un backend.

El nombre interno (`pad.8`, `geo.pad.8.16`, `pad.8.r16`) son segmentos adicionales del
nombre calificado, así que `backends/base.py:fn_ident` —que ya codifica nombres con
puntos como `m_4geo3pad…`, inyectivo por longitud de segmento— produce un identificador
legal sin saber nada de V6. Para una base fija la secuencia de segmentos se lee sola
(los anchos son decimales sin ceros a la izquierda, el del retorno empieza con `r`), y
la base nunca termina en un segmento numérico porque el léxico no permite un
identificador que empiece en dígito: dos resoluciones distintas no colisionan entre sí
ni con un nombre de usuario (canario F: `414` y `415` son el mismo programa con las
llamadas invertidas; `tests/test_specialize.py:Nombres` lo comprueba).

## Orden de los errores

Una copia se chequea en el sitio de su primera llamada, no en su posición de fuente.
En un archivo normal —definición antes del `main`— es el mismo orden que antes; cambia
solo cuando una llamada contextual precede a la definición (`413` lo permite). El `at`
reportado sigue siendo el de la definición original, que es el fuente que el programista
escribió.

## Fail-closed, en las dos direcciones

- si el **cuerpo** exige un máximo que la resolución no le da (`let t: str<4> = s`
  con `s` instanciado en `str<5>`), el error es estático: `TYPE_MISMATCH` al chequear
  la copia (`422`).
- si el desborde solo se ve al **ejecutar** (`s as str<2>` con `s` de 3 bytes, o una
  concatenación que rebasa el `str<16>` declarado), es `ERROR(OVERFLOW)` — la regla
  «OVERFLOW nunca truncación» de v0.3, ahora con capacidad que llega de un llamado
  (`416`, `418`).

Ninguna de las dos se resuelve truncando. Y tampoco se abre la puerta por el otro lado:

- un parámetro pelado exige `str`: darle un entero es `TYPE_MISMATCH` **en el argumento**
  (`427`), no una coerción ni una especialización con un ancho inventado.
- `main` no tiene sitio de llamada —sus argumentos vienen de stdin—, así que un
  parámetro pelado de `main` se rechaza (`424`); no se le fija `MAX_STR` ni ningún otro
  número por defecto.
- el `str` pelado fuera de un parámetro sigue siendo `SYNTAX` en 0.5 (`425`), y lo es
  también dentro de un parámetro con cabecera 0.3/0.4 (`426`): V6 no relaja ninguna
  semántica anterior.

## Equivalencia con el programa escrito a mano (gemelo)

`411` y `423` tienen un gemelo `isyco 0.4` con la capacidad escrita a mano y, cuando
hace falta, la definición duplicada por ancho. Los dos programas coinciden en status,
code, emits, return **y steps** (`tests/test_specialize.py:Gemelo`): el azúcar añade una
definición en el AST y ningún paso en la ejecución. La prueba al revés también está: una
sola definición con `str<2>` fijo rechaza el llamado de 8 bytes, y lo hace con el error
más preciso que existe —`LITERAL_OUT_OF_RANGE`—, que es exactamente el muro que V6 quita
(`414` adaptado, en el mismo archivo de test).

> **Aclaración medida al cerrar V6-bis (2026-10-31):** la igualdad de `steps` solo vale
> entre programas de **misma forma**. El primer gemelo de `429` se escribió con
> `emit f(...)` directo mientras el caso usaba `let` + `emit`, y daba 7 pasos contra 9 —
> la diferencia eran los `let`, no la especialización. Los gemelos de `411` y `423` sí
> son de forma idéntica (mismos `emit`, misma anidación), así que la afirmación de arriba
> se mantiene tal cual; el control de forma queda escrito en
> `docs/decisions/V6B_CONTEXTUAL_RETURN.md`.

## Lo que se descarta

Una definición contextual que nadie llama no tiene capacidad que resolver; se quita
del programa después de especializar (`419`). No es un error: ninguna observable
depende de ella. Es la única concesión de este diseño y queda fijada por un caso.

## Transmisión

La capacidad viaja de llamado a copia, y de copia a copia: dentro de `envia[str<3>]`
el parámetro ya es `str<3>` concreto, así que la llamada contextual que hace instancia
`copia[str<3>]` (`413`). La recursión se ve a sí misma porque la clave ya está registrada
cuando se chequea el cuerpo (`420`).

## Corpus

`programs/conformance_v0.5/411`–`428`, con los `expected` escritos a mano **antes** de
tocar `isyco/` (rito de `AGENTS.md` §5). Escalera de anchos instanciados: 1, 2, 3, 4, 5,
6, 7, 8, 16, 64 (y 32 por ensanchamiento); conteo de llamados 1, 2 y anidado; un caso
entre módulos (`421`); uno que entra por stdin (`428`); tres rechazos estáticos (`422`,
`424`, `427`), dos de sintaxis (`425`, `426`) y dos `ERROR(OVERFLOW)` (`416`, `418`). El
directorio sigue **fuera de `CORPORA`** hasta que V1–V5 estén implementados: `401`–`406`
todavía fallan, y meter el directorio a medias bajaría la cobertura del gate.

## Medición (base de P4, sin límite fijado)

`tools/v05_v6_probe.py` cuenta, por caso, cuántas especializaciones crea el checker y
cuántas funciones llegan a la IR. Medido en la corrida sellada
(`evidence/v05_v6/run_20261031T103514Z.json`): **22 clones en todo el corpus**, máximo **2
copias por definición** (`pad`, `copia`, `envia`, `largo`, `cuenta`, `doble`,
`util.marca`) y máximo **4 copias por programa** —`413`, que tiene dos definiciones
contextuales y dos llamados cada una—. ningún caso pide una tercera copia de la misma
definición. No se fija ningún tope: P4 pide medir antes de poner número, y la escalera
completa de anchos está en el corpus para poder medir cuando crezca.

## Diferencial sellado

`evidence/v05_v6/run_*.json` (recibo `isyco.evidence/0.1`: `git_head`, `arbol_sucio`,
`corpus_hash`, versiones de los cinco toolchains, semilla `n/a`). Los 18 casos V6 contra
tres rutas —referencia, ISY-IR en ida y vuelta por JSON, y cada backend— dan **77 EQUIV y
13 UNSUPPORTED, y cero DIVERGENT / BUILD_FAIL / RUNTIME_FAIL / INCONCLUSIVE**.

Detalles que podrían leerse como fallo y no lo son:

- Los cinco casos de rechazo estático (`422`, `424`, `425`, `426`, `427`) no tienen IR:
  `compile_ir` lanza el mismo `INVALID_PROGRAM(code)` que la referencia. La sonda lo
  registra como `RECHAZADO IGUAL QUE LA REFERENCIA`, no como ausencia.
- Los 13 UNSUPPORTED son todos COBOL, y vienen de la etiqueta, no de V6:
  `features_of` (`isyco/backends/base.py:96`) añade `ir0.2` cuando el módulo lleva
  `schema: isy-ir/0.2`, y COBOL declara `FEATURES = ALL_FEATURES - {"ir0.2","str","struct"}`
  (`isyco/backends/cobol.py:1504`). Cualquier programa 0.3+ queda fuera de COBOL por la
  cabecera, aunque no use ningún rasgo 0.3. Eso es exactamente lo que V7 tiene que
  separar (`SCHEMA_CAN_EXPRESS` vs `PROGRAM_REQUIRES`); hasta que exista, COBOL aporta
  aquí **cinco testigos** —los cinco rechazos, que resuelve el frontend compartido— y
  ninguno de los casos ejecutables. La sonda lo imprime: `control cobol (testigos
  propios: 5/18)`.

## Control anti-fake (y la trampa que cazó)

Todo diferencial de este repo lleva un backend saboteado, y la sonda lo compara **contra
sí mismo**, no contra la referencia. Es un cambio que hubo que hacer a la fuerza: con la
comparación contra la referencia, COBOL "detectaba" los dos sabotajes en 13 casos sin
que el parche llegara a ejecutarse — el UNSUPPORTED ya difería de la referencia, y eso
se habría contado como prueba de que el engine miraba los datos.

Además, un sabotaje solo vale si el corpus usa el rasgo. La sonda lee los rasgos **del
programa bajado** (`k: "concat"`, `dec` en un operando, `div`/`rem` sobre `int`), no de
la cabecera:

- `str_concat_truncates`: **DETECTADO** en c, pydecimal, rust y zig — 5 casos con
  concatenación de strings, `418_junta_desborda` se rompe. Es el control que le da
  dientes a este milestone.
- `half_even_as_half_up` y `div_floor`: **VACÍOS**. Ningún caso V6 tiene decimales ni
  división entera; lo que se rompa o no ahí no lo mide este corpus y no se vende como
  cobertura. Queda escrito en la corrida.
- Un cascos del sabotaje no cuenta como detección (se registra aparte, en `cascos`).
- `does_the_work`: en `423` la cadena de 32 bytes que se emite NO está en el código
  generado (la arma el engine con `s + s`), y en `428` cambiar la entrada por stdin
  (`adios`) cambia la salida (`5` en vez de `4`). El trabajo lo hace el engine.
