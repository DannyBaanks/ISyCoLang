# ISyCoLang — propuesta de core v0.5 (BORRADOR, no congelada)

**Estado:** `PROPUESTA` (2026-10-30). Ninguna decisión de este documento está
aprobada. Las siete se numeran **V1–V7** con opciones y una recomendación; las
que necesitan elección explícita de Danny se marcan **[D]**, y los detalles que
hay que cerrar para implementar se marcan **[P]** — mismo rito que S1–S8 (v0.3)
y M1–M4 (v0.4).
**Base:** `CORE.md` + `CORE_v0.2.md` + `CORE_v0.3.md` + `CORE_v0.4.md`.
**Medición:** `tools/v05_proposal_probe.py` → `evidence/v05_propuesta/run_2026-10-31T001600Z.{json,txt}`
(sha256 `32e68726…` / `3b7285a5…`), sobre `programs/conformance_v0.5/` y sus gemelos.
**Promesa de no regresión:** ningún programa `isyco 0.1`–`0.4` cambia de
resultado, de schema ni de traza. Es condición de aprobación, no consecuencia.

## 1. Origen

`docs/DOGFOOD_2026-10-30.md` midió qué no se puede escribir hoy, con el mensaje
del checker en crudo. Este borrador responde a **cuatro** bloqueos medidos y a
**dos** huecos de spec, y deja otros cuatro explícitamente fuera:

| entrada | qué dice la medición |
|---|---|
| B1 | `for it in items` → `INVALID_PROGRAM(SYNTAX) at 24:9` |
| B2 | `len` de un arreglo → `INVALID_PROGRAM(TYPE_MISMATCH) at 9:15: len requiere un str`; el tamaño se duplica como literal |
| B6 | `str` sin capacidad → `INVALID_PROGRAM(SYNTAX) at 5:16`; no hay librería de texto reutilizable |
| B7 | contador `i32` vs `len()` `i64` → `INVALID_PROGRAM(TYPE_MISMATCH) at 8:13` |
| D1 | los parámetros son reasignables en la implementación; ningún caso del corpus ni la spec lo otorga |
| D2 | `[reporte.Linea; 3]` enlaza, pero la EBNF de v0.4 §3 no declara `qname` en `elem_type` |
| dogfood §7 | `isyco/ir.py:228` estampa `isy-ir/0.2` por **cabecera**: `03_criba.isy` a `0.4` es `UNSUPPORTED(ir0.2)` y a `0.2` corre en COBOL con el resultado correcto |

## 2. Decisiones

### V1 — `len` sobre arreglos **[D]**

`len(a)` con `a: [T; N]` devuelve `N`, tipo `i64` (la misma familia que `len(s)`
de v0.3 §2.4). Es estático: el frontend lo resuelve con el tipo, así que no
cuenta paso ni profundidad, igual que `len`, `slice` y `chr`.

- **Opción adoptada si se aprueba:** el frontend reemplaza `len(a)` por el
  entero `N` en el AST. **La IR no cambia**: ningún backend nuevo, ninguna
  capacidad nueva, `features_of` intacto. Es el mismo movimiento que v0.4 hizo
  con los imports (frontend, IR `isy-ir/0.2` sin tocar).
- Tipo `i64` y no "el tipo del índice": coherencia con `len(s)`. B7 no se
  arregla aquí; ver §3.
- Rechazado: `a.len`, métodos (v0.3 §9 los excluye y v0.4 §4 los reafirma).

### V2 — `for x in a` como azúcar del frontend **[D]**

```ebnf
stmt = … | "for" IDENT "in" expr block ;      (* expr de tipo [T; N] *)
```

Significa exactamente:

```text
{ let i#k: i64 = -1; while i#k + 1 < len(a) { i#k = i#k + 1; let x: T = a[i#k]; <cuerpo>; } }
```

- **El incremento va antes del cuerpo, y eso es medido, no estético.** La forma
  intuitiva —`while i < len(a) { let x = a[i]; <cuerpo>; i = i + 1; }`— hace que un
  `continue` del cuerpo salte el avance:
  `programs/conformance_v0.5/gemelos/404_while_incremento_abajo.isy` (cabecera `0.4`,
  corre hoy) queda girando sobre el elemento 5 y termina
  `LIMIT_REACHED(max_steps)` con `emits=["2","3"]`. Con el incremento arriba, el mismo
  cuerpo da exactamente el esperado de 404. El `-1` inicial existe desde v0.2, así que
  el azúcar no necesita regla nueva.

- `x` es una **copia** del elemento (principio §1.2, sin aliasing) y es
  reasignable dentro del cuerpo sin tocar el arreglo (esto es V4).
- `break`/`continue`/`return` dentro del cuerpo: idénticos a `while`.
- Choca con un nombre visible ⇒ `DUPLICATE_NAME`, la misma regla de `let`
  (CORE.md §4, sin shadowing).
- **Expansiones en el parser, no en el lowering.** El AST que ve el intérprete
  de referencia ya es el `while` equivalente, así que `steps`, límites y trazas
  quedan definidos sin regla nueva: `max_steps` cuenta los mismos pasos que el
  `while` gemelo. Valores medidos hoy con los gemelos escritos a mano: **23** pasos
  para 403, **38** para 404 y **20** para 405 — esos números son los que exige el
  gate (§5, ítem 2).
- **[P1]** el `i` sintético y el `let x` llevan `at` = la línea del `for`.
- **[P2]** ¿se permite `for x in [1, 2, 3]` (literal sin tipo esperado)?
  Recomendación **no**: un literal de arreglo sin contexto es
  `AMBIGUOUS_LITERAL` (§3.5) y el `for` no aporta tipo esperado. Probarlo y
  registrarlo.

### V3 — `in` queda contextual, no reservada **[D]**

`for` es palabra reservada nueva; `in` **no** se añade a la lista de
reservadas, porque hoy es un identificador legal en v0.1–v0.4 (§2.1: la lista
no la incluye) y reservarla cambiaría el significado de programas existentes,
lo que viola la promesa de no regresión del encabezado.

### V4 — parámetros reasignables pasan a texto normativo **[D]**

`CORE.md` §4 dice solo «`let` declara una variable mutable». La implementación
trata el parámetro como una local del marco (`locals` lo incluye, `params` lo
indexa) y `s = s + "!"` compila y corre. D1: **cero** casos del corpus reasignan
un parámetro, y los programas naturales lo usan. Se propone escribirlo en la
spec (CORE.md §4: «los parámetros son variables locales mutables del marco; asignarles
no afecta al llamador, porque todo paso es por copia») con su caso 407.
La alternativa es prohibirlo; sería una regla sin beneficio medible.

### V5 — `qname` en `elem_type` **[D]**

Añadir `qname` a `elem_type` en la EBNF de v0.4 §3 (los elementos de arreglo
pueden ser tipos de un módulo importado: `[reporte.Linea; 3]`). No es un cambio
de comportamiento: enlaza hoy. Es texto para que la spec congelada no quede más
estricta que la implementación, y caso 408 que lo fije.

### V6 — `str` sin capacidad, solo en posiciones donde el contexto la fija **[D]**

Objetivo medido: que exista una librería de texto reutilizable. Hoy `pad` solo
sirve para `str<16>` y hay que reescribirla por ancho.

- Se propone: un `str` **sin capacidad** es válido en parámetro y en `let` con
  inicializador, y significa "la capacidad del tipo concretizado en el sitio de
  llamada". El frontend monomorfiza: dos llamadas con `str<16>` y `str<40>`
  generan dos funciones. **La IR no cambia** (solo aparecen dos funciones con
  nombres de especialización, codificados como en v0.4 §7 [P7]).
- **Alcance honesto:** sirve para funciones que *no hacen crecer* la cadena
  (`primero(s) -> u8`, `es_vacia(s) -> bool`, `empieza_con(s, p) -> bool`,
  contar, buscar). No sirve para `pad` ni `grito`: devolver `str<N+1>` exige
  **aritmética de capacidades**, que es una regla nueva sobre la capacidad de
  `+` (v0.3 §2.4 [P]) y sobre `TYPE_TOO_LARGE`. Eso se queda fuera de v0.5 (§3).
- **[P3]** nombre de la especialización y su efecto sobre `program_sha256` y las
  trazas. **[P4]** cota de especializaciones por programa: se decide midiendo el
  primer corpus, no inventando un número.

### V7 — el schema se deriva del contenido, no de la cabecera **[D]**

`isyco/ir.py:228`: `schema = SCHEMA_V2 if program.version in ("0.3","0.4")`.
Con V1/V2 aprobadas, un programa `isyco 0.5` puramente numérico —sin `str`, sin
`struct`, sin `import`— heredaría el stamp `isy-ir/0.2` y **perdería COBOL por la
cabecera**, que es exactamente el defecto que §7 del dogfood midió. La corrección:
`schema = SCHEMA_V2` si y solo si el programa usa un tipo u operación que no
exista en `isy-ir/0.1` (`str`, `struct`, `==` entre arreglos, `emit` de arreglo,
nombres calificados). El validador ya rechaza esos tipos fuera de `0.2`
(`isyco/ir_validate.py:75`), así que la regla es coherente con lo que se valida.

- Coste real: hay tests y evidencia que afirman «`isyco 0.4` ⇒ `isy-ir/0.2`» y
  se reescriben. Ningún programa del corpus cambia de resultado (los 11 casos
  medidos en `docs/DOGFOOD_2026-10-30.md` §7 siguen en `0.2` por contenido).
- Riesgo declarado: un programa `0.4` con `import` bajaría a `isy-ir/0.1` con
  nombres calificados, que COBOL nunca recibió. **No se afirma** que los acepte:
  el gate (§5) lo ejecuta y se registra lo que salga. Si COBOL los necesita
  declarar, se agregan a su dominio o siguen `UNSUPPORTED` por la vía correcta
  (contenido), no por la etiqueta.

## 3. Fuera de alcance de v0.5 (explícito)

| bloqueo | por qué no entra |
|---|---|
| B4 estado entre llamadas / variables de unidad | toca el principio §1.2 (sin aliasing) y §4 (sin globales); el work-around existe y está medido (+63 % líneas) |
| B5 efectos de lectura (reloj, ambiente, stdin, archivos) | es una decisión de alcance del lenguaje: o ISyCoLang observa el mundo con efectos declarados, o el host lo hace. Merece su propio documento, no un parche |
| B7 anchos enteros mixtos | regla de coerción sobre 6 tipos de entero con `ovf` distinto; con V1 el dolor real desaparece en los casos medidos |
| B8 texto decimal no canónico (`"199.9"` ⇒ `BAD_FORMAT`) | cambiar `ERROR(BAD_FORMAT)` es cambiar la forma canónica de §10.1 y los cinco backends. Es la decisión más valiosa de la lista y la más cara: va a v0.6 con su propio estudio |
| B9 valor ausente / arreglos que crecen | `null`/optional exige forma canónica de salida y entrada, y los arreglos dinámicos rompen §1.1 (sin heap) |
| V6 aritmética de capacidad (`str<N+k>`) | sin ella no hay `pad` genérico; es la fila honesta de §2 V6 |

## 4. Corpus propuesto

`programs/conformance_v0.5/` (401–410). **Los `expected` están escritos a mano el
2026-10-30, antes de implementar cualquier V** (commits `dd561c6` y `0e9ca79`). Las
fechas de commit son hora local (`-06:00`) y la evidencia se sella en UTC: por eso
`run_2026-10-31T001600Z` es el mismo 30 de octubre, 18:16 locales. El directorio está
fuera de `CORPORA` (`isyco/conformance.py:13`) hasta que F2.4 se apruebe: el gate de
170 casos no se mueve.

La columna «cuerpo a 0.4» es la medición de ese mismo cuerpo con **solo la línea 1
reescrita** a `isyco 0.4` (`tools/v05_proposal_probe.py`): así el rechazo registrado
es el de la regla que falta, no el de la versión. Corrida
`evidence/v05_propuesta/run_2026-10-31T001600Z.txt` (sha256 `3b7285a5…`).

| caso | fija | esperado (a mano) | cuerpo a 0.4 (medido) |
|---|---|---|---|
| `401_len_arreglo` | V1 | emite `5`, retorna `5` | `TYPE_MISMATCH at 5:12: len requiere un str` |
| `402_for_decimales` | V2 | retorna `3.85` | `SYNTAX at 7:9: se esperaba '=', llegó 'it'` |
| `403_for_enteros` | V2 | retorna `17` | `SYNTAX at 6:9: se esperaba '=', llegó 'x'` |
| `404_for_break_continue` | V2 | emite `2 3 7`, retorna `3` | `SYNTAX at 6:9: se esperaba '=', llegó 'x'` |
| `405_for_copia` | V2+V4 | emite `1 3`, retorna `2` | `SYNTAX at 5:9: se esperaba '=', llegó 'x'` |
| `406_len_parametro` | V1 | retorna `21` | `TYPE_MISMATCH at 6:15: len requiere un str` |
| `407_parametro_reasignable` | V4 | emite `41`, retorna `42` | **`HALTED` en 8 pasos**: ya funciona |
| `408_qname_arreglo` (2 archivos) | V5 | retorna `9.00` | **`HALTED` en 7 pasos**: ya funciona |
| `409_str_cualquier_capacidad` | V6 | emite `104 97`, retorna `4` | `SYNTAX at 3:18: se esperaba '<', llegó ')'` |
| `410_str_vacia_reutilizable` | V6 | emite `true false`, retorna `false` | `SYNTAX at 3:19: se esperaba '<', llegó ')'` |

Con la cabecera `isyco 0.5` los diez casos fallan hoy, pero **no todos por la misma
razón**: siete devuelven `SYNTAX at 1:1: la cabecera debe ser 'isyco' + una de
['0.1', '0.2', '0.3', '0.4']`, y `408`/`409`/`410` tropezan antes, en el léxico, con
`carácter inesperado '"'` — `isyco/lexer.py:64` solo enciende los strings para
`0.3`/`0.4`. Es la prueba ejecutable de §7: declarar la versión no es añadir un
string a una lista.

Los dos «ya funciona» son D1 y D2 medidos: la implementación hace algo que la spec
congelada no otorga, y ningún caso del corpus actual lo cubre. Por eso V4 y V5 son
texto de spec, no código nuevo.

## 5. Gate F2.4 propuesto

1. Referencia: 10/10 en `programs/conformance_v0.5/` **sin tocar ningún
   `expected`** y sin cambiar ningún resultado de los 170 anteriores (corrida
   completa `180/180`).
2. Equivalencia `for`/`while` (V2): `programs/conformance_v0.5/gemelos/` guarda los
   tres `while` equivalentes, medidos hoy con cabecera `0.4`: 403 → `17` en **23**
   pasos, 404 → `2 3 7`/`3` en **38**, 405 → `1 3`/`2` en **20**. Al implementar V2,
   los casos `for` deben dar el mismo `status`, `code`, `emits`, `return` **y los
   mismos pasos**; la traza `stmt` coincide línea a línea salvo el `at` [P1]. El
   cuarto archivo, `404_while_incremento_abajo.isy`, es el control negativo del orden
   del incremento (`LIMIT_REACHED(max_steps)` con `emits=["2","3"]`) y no debe cambiar
   nunca: si algún día termina, el azúcar dejó de ser el `while` que la spec declara.
3. IR: los casos V1/V2/V4 **no** introducen capacidades nuevas
   (`features_of` igual o más chico que hoy); V6 introduce solo nombres de
   especialización.
4. V7: `03_criba.isy` con cabecera `isyco 0.5` produce `isy-ir/0.1` y COBOL lo
   ejecuta igual que la referencia. **Esta fila es la que falsifica V7**; si COBOL
   falla por otra razón, se registra y se decide.
5. Los cinco backends existentes pasan el corpus completo con sus capacidades
   declaradas, y los tres sabotajes de costumbre siguen detectándose.
6. `does_the_work` sobre un caso `for` (que el backend no esté evaluando el
   programa en el host).

## 6. Tabla de claims de este borrador

| Claim | Status |
|---|---|
| V1–V7 resuelven B1, B2, B6, D1, D2 | **INFERRED** — es una propuesta; nada está implementado |
| Los `expected` de 401–410 se escribieron antes de implementar | **DEMONSTRATED** — `git show --stat 0e9ca79` y `dd561c6` no tocan ningún archivo de `isyco/`: el árbol de esos commits tiene los diez `expected` y cero implementaciones V1–V7; la columna «cuerpo a 0.4» está medida contra el core actual (`evidence/v05_propuesta/run_2026-10-31T001600Z.txt`) |
| El azúcar V2 con el incremento **después** del cuerpo es incorrecto: `continue` no avanza | **DEMONSTRATED** — `404_while_incremento_abajo.isy` corre hoy en `0.4` y da `LIMIT_REACHED(max_steps)` con `emits=["2","3"]` |
| Los esperados de 403/404/405 son reproducibles hoy con el `while` gemelo | **DEMONSTRATED** — los tres gemelos coinciden (`17`, `2 3 7`/`3`, `1 3`/`2`) |
| D1 (parámetros reasignables) y D2 (`[modulo.Tipo; N]`) ya funcionan sin spec que los otorgue | **DEMONSTRATED** — 407 `HALTED`/`42` en 8 pasos y 408 `HALTED`/`9.00` en 7 pasos, cuerpo a cabecera `0.4` |
| Añadir la cabecera `0.5` es agregar un string a `SUPPORTED_VERSIONS` | **REFUTADO por medición** — hay **10** sitios con la versión fijada en código (§7); los casos con strings fallan en el léxico, no en la cabecera |
| `isyco/modules.py:33` es inalcanzable hoy | **DEMONSTRATED** — `import` con cabecera `0.3` es `SYNTAX`; solo `0.4` produce `UNKNOWN_MODULE` |
| Ningún programa `0.1`–`0.4` cambia con V1–V6 | **INFERRED** (V1/V2/V6 se resuelven en el frontend y V7 solo reetiqueta `isy-ir/0.2` de programas que usan contenido `0.2`); se vuelve `DEMONSTRATED` al correr el gate 1 |
| V2 no altera los `steps` respecto del `while` gemelo | **INFERRED** — los pasos del gemelo están medidos (23/38/20); los del `for` no existen hasta implementar V2 |
| COBOL ejecutará un programa `0.5` sin `str`/`struct` bajado a `isy-ir/0.1` | **NOT_DEMONSTRATED** — medido solo con `03_criba` a cabecera `0.2` (`docs/DOGFOOD_2026-10-30.md` §7); con `import` calificado no se probó nunca |
| V6 sin aritmética de capacidad alcanza para una librería de texto útil | **NOT_DEMONSTRATED** — 409/410 son dos funciones de lectura; `pad` y `grito` siguen imposibles |
| La monomorfización de V6 no infla los programas | **NOT_DEMONSTRATED** — [P4] abierto a propósito, se cierra midiendo |

## 7. Los sitios que fijan la versión en el código

Medición: `tools/v05_proposal_probe.py` → `evidence/v05_propuesta/run_2026-10-31T001600Z.*`.
`grep` de `"0.3"`/`"0.4"` sobre `isyco/*.py` da **diez** decisiones de versión
escritas a mano, en cuatro archivos que no se consultan entre sí:

| # | sitio | qué habilita | si se olvida |
|---|---|---|---|
| 1 | `lexer.py:64` `v03 = version in ("0.3","0.4")` | strings y las palabras de v0.3 | el lexer rechaza `"…"` antes que el parser mire la cabecera: así cayeron 408/409/410 con la cabecera `0.5` |
| 2 | `lexer.py:66` `if version == "0.4"` | `import`, `pub` | `import` vuelve a ser un identificador |
| 3 | `parser.py:12` `SUPPORTED_VERSIONS` | la cabecera | `SYNTAX at 1:1` |
| 4 | `parser.py:24` `Parser.v03` | sintaxis de v0.3 | nombres calificados/strings mal parseados |
| 5 | `parser.py:28` `Parser.v04` | sintaxis de módulos | `is_qualified()` falso |
| 6 | `checker.py:36` `self.v03 = … in ("0.3","0.4")` | reglas de tipos v0.3 (struct, `str`, `emit` no escalar) | el checker trata un programa `0.5` como `0.2` |
| 7 | `ir.py:228` stamp de schema | `isy-ir/0.2` | **esto lo cambia V7**: hoy depende de la etiqueta, no del contenido |
| 8 | `__main__.py:50` `== "0.4"` | leer el programa como `Bundle` (carpeta + imports) | un `0.5` modular se lee como archivo suelto |
| 9 | `modules.py:33` `root.version != "0.4"` | enlazar módulos del raíz | **fail-open**: devuelve el raíz sin enlazar y sin error. Hoy es inalcanzable (sitio 2 lo demuestra: `import` en `0.3` es `SYNTAX`), y por eso es traicionero: se activa el día que se toque el sitio 5 sin tocar este |
| 10 | `modules.py:47` `header_version(text) != "0.4"` | cada módulo importado | `VERSION_MISMATCH` en todos los imports |

Lo que pide la propuesta no es una regla nueva sino **una sola fuente de verdad**:
que `parser.py` exponga el predicado («¿esta versión trae v0.3? / v0.4?») y los sitios
1, 2, 4, 5, 6, 8, 9 y 10 lo llamen. Con eso, añadir `0.5` es una línea y el gate F2.4
detecta cualquier olvido.

Hoy los diez son conjuntos o igualdades literales contra `0.3`/`0.4`, repartidos en
seis archivos que no se consultan entre sí, y **ninguno se activa con una versión
mayor**. El olvido es ruidoso en los sitios 1 y 3 — así cayeron 408/409/410, con el
léxico rechazando el string antes de mirar la cabecera — pero los sitios 8, 9 y 10
son comparaciones de igualdad: en cuanto `0.5` entre en `Parser.v04` sin entrar en
`modules.py:33`, un programa modular se enlaza como si no tuviera `import` y **no salta
ningún error**. Ninguna de las pruebas actuales ejercita esa combinación, porque hoy es
inalcanzable; se convierte en test en el momento de declarar `0.5`.
