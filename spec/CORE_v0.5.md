# ISyCoLang — Semántica del core v0.5

**Estado:** `BORRADOR` (2026-11-01; revisado para congelar el 2026-11-12, ver §11). **No congelada**: congelar es decisión de Danny,
como lo fueron S1–S8 (v0.3) y M1–M4 (v0.4), y este archivo no entra en
`spec/SHA256SUMS.txt` hasta ese día. Lo que sí hace este documento es pasar las
decisiones **V1–V7** de `spec/CORE_v0.5_propuesta.md` a texto normativo, con las
arestas medidas. La implementación, la medición y los controles anti-fake de cada
decisión viven en `docs/decisions/` y en `evidence/`; aquí va la regla.
**Base:** `CORE.md` + `CORE_v0.2.md` + `CORE_v0.3.md` + `CORE_v0.4.md`. Los cuatro
siguen `FROZEN` e intactos; todo lo de v0.4 vale en v0.5 y este documento solo lista
lo que cambia.
**Promesa de no regresión:** ningún programa `isyco 0.1`–`0.4` cambia de resultado,
de schema ni de traza. Es condición de aprobación, no consecuencia (§9).

## 0. Versionado y familias de reglas

- Cabecera `isyco 0.5`. `0.1`–`0.4` conservan exactamente su significado.
- **Un solo sitio fija las reglas por versión: `isyco/versions.py`.** Define
  `SUPPORTED = ("0.1"…"0.5")`, `INTRODUCED = {"v02","v03","v04","v05"}` y
  `has(version, familia)`. Una **familia es un conjunto de reglas, no una versión**:
  `v03` trae `str`/`struct`, `v04` los módulos, `v05` lo de este documento. La
  relación es monotónica por posición en `SUPPORTED`, así que `0.5` hereda `v03` y
  `v04` sin declararlo dos veces, y una cabecera desconocida no trae ninguna familia
  (fail-closed: `has` devuelve `False` y el parser rechaza la cabecera antes de eso).
  La propuesta §7 había medido **diez** sitios con la versión escrita literal en el
  código y ninguno se activaba al subir la cabecera; hoy quedan **13 llamadas a
  `has()`** y **cero** literales de versión como decisión: los dos que sobreviven
  fuera de `versions.py` son *defaults*: `Program.version` en `ast.py` y `Parser.version`
  en `parser.py`. Los sitios se citan por símbolo y no por línea: las líneas se mueven con
  cada cambio y este texto no (corregido el 2026-11-12; la mayoría de los números de línea
  del borrador ya no apuntaban a lo que decían).

  | sitio | qué habilita |
  |---|---|
  | `lexer.py`, `tokenize` (tres llamadas) | palabras de v0.3, `import`/`pub`, `for` |
  | `parser.py`, `Parser.v03`, `Parser.v04`, `Parser.v05` | sintaxis de v0.3, de módulos, de v0.5 |
  | `parser.py`, `SUPPORTED_VERSIONS` (no es llamada a `has`) | el conjunto de cabeceras admitidas (`SUPPORTED_VERSIONS`) |
  | `parser.py`, `Parser.unary` | enteros/decimales polimórficos (v0.2) |
  | `checker.py`, `Checker.v03`, `Checker.v05` y el hint de `Checker.index_type` | reglas de tipos v0.3, reglas v0.5, hint polimórfico |
  | `ir.py`, `lower` | número de schema que el contenedor puede expresar |
  | `__main__.py` (lectura del programa), `modules.py`, `load_program` | leer el programa como `Bundle` (carpeta + imports) |

- **La IR no cambia.** `isy-ir/0.1` y `isy-ir/0.2` son las únicas formas; V1, V2, V4,
  V5 y V6 son frontend. Lo que decide **qué exige el programa** es el contenido (§8), no la
  cabecera — V7 revierte exactamente esa dependencia, que la propuesta §7 y el
  dogfood §7 señalaron como defecto. **Precisión del 2026-11-12:** la *etiqueta* del
  contenedor (`schema`) la sigue poniendo la cabecera —un programa `0.5` puramente numérico
  baja rotulado `isy-ir/0.2`—; esta frase decía «a cuál se baja» y eso no es lo que V7
  hizo. Medido con la criba recabezada a `0.5`: etiqueta `isy-ir/0.2`, `features_of` sin
  `ir0.2`, y COBOL la ejecuta (`tools/v05_gate_f24_probe.py`).
- **M4 se generaliza.** v0.4 §1 decía «todos los módulos son `isyco 0.4`». La regla
  es ahora: **todo módulo de un programa tiene la misma versión que la raíz**; una
  diferencia ⇒ `INVALID_PROGRAM(VERSION_MISMATCH)` (`load_program` en `isyco/modules.py`). Medido en
  las ocho combinaciones de raíz ∈ {0.4, 0.5} × módulo ∈ {0.2, 0.3, 0.4, 0.5}: solo
  las diagonales `0.4/0.4` y `0.5/0.5` ejecutan (`return 7`, `HALTED`); las seis
  restantes son `VERSION_MISMATCH`. Mezclar familias quedaría sin respuesta sobre qué
  semántica gana, así que se rechaza por ambos lados. Fijado en corpus desde el
  2026-11-01: `443_m4_modulo_v04` (raíz `0.5`, módulo `0.4`), `308_version_mismatch`
  (raíz `0.4`, módulo `0.3`) y la diagonal `0.5/0.5` en `408_qname_arreglo` (§11, N2).

## 1. Decisiones

| id | qué admite | dónde vive la regla | documento de medición |
|---|---|---|---|
| V1 | `len(a)` de un arreglo | `checker.py`: rama `A.Len` de `Checker._typeof` (tipo) y `static_len`, aplicado en `Checker.check` (resolución) | `docs/decisions/V1_LEN_ARREGLO.md` |
| V2 | `for x in a { … }` | `lexer.py`: `KEYWORDS_V05` y `tokenize` (reserva); `parser.py`: `Parser.stmt` (despacho), `Parser.for_stmt` (expansión), `Parser.block` (aplanado); `checker.py`: rama `A.Let` de `Checker.stmt` (el `let` sintético) | `docs/decisions/V2_FOR_AZUCAR.md` |
| V3 | `in` sigue sin reservarse; `for` solo desde `0.5` | `lexer.py`, `KEYWORDS_V05` | idem V2, §Control anti-fake |
| V4 | el parámetro es una local mutable del marco | `CORE.md` §4 (esta sección lo pone por escrito) | §5 abajo |
| V5 | `qname` como tipo de elemento de arreglo | v0.4 §3 (EBNF) | §6 abajo |
| V6 | `str` sin capacidad en parámetros | `types.py`, `ContextStrT`; `specialize.py`, `spec_name` y `make_clone` | `docs/decisions/V6_CONTEXTUAL_STR.md` |
| V6-bis | `str` sin capacidad en el retorno | idem (la clave agrega `r<n>`) | `docs/decisions/V6B_CONTEXTUAL_RETURN.md` |
| V7 | capacidades derivadas del contenido | `backends/base.py`, `features_of` | `docs/decisions/V7_CONTENT_CAPABILITIES.md` |

## 2. Léxico (V3)

- `for` es palabra reservada **solo con cabecera `0.5`**. Con `0.4`,
  `let for: i32 = 5;` sigue siendo legal y corre (`HALTED`, `return 5`); con `0.5` es
  `SYNTAX`. Medido.
- `in` **no se añade nunca a la lista de reservadas**: es un token contextual que
  el parser exige como `IDENT` con el texto `"in"` (`Parser.for_stmt`). Con `0.4` y
  con `0.5`, `let in: i32 = 5;` es legal y corre. Reservarla habría cambiado el
  significado de programas existentes y viola la promesa del encabezado.

## 3. V1 — `len` de un arreglo

`len(a)` con `a: [T; N]` devuelve `N` con tipo `i64` (misma familia que `len(s)` de
v0.3 §2.4; no «el tipo del índice»: B7 sigue sin arreglar, §9). La regla tiene dos
mitades y las dos son de frontend:

1. **Chequeo** (rama `A.Len` de `Checker._typeof`): con familia `v05`, `len` de un `ArrT` es
   `i64`; sin `v05` es `TYPE_MISMATCH` — el `len` de v0.3 es solo de strings.
2. **Resolución** (`static_len`, aplicado en `Checker.check` después de chequear):
   cada `Len` cuyo `expr.ty` es `ArrT` se reemplaza por `IntLit(at, N)` con `ty = i64`.
   Camina listas y los `(nombre, expr, at)` de un literal de struct, así que
   `Par { x: len(xs) }` también queda resuelto. Se aplica sobre las funciones que
   sobreviven al chequeo —las copias de V6 incluidas—, no sobre las definiciones
   `str` pelado que nunca se ejecutan.

Consecuencias normativas: **es estático** —cero pasos, cero nodos en la IR (`401` y
`406` bajan con `{"k": "len"}` = 0; el control positivo, `len(s)` de v0.3 sobre un
`str<8>`, baja con 1)—, no añade capacidad ni a `features_of` ni a ningún backend, y
**no se estrecha**: `let n: i8 = len(xs)` es `TYPE_MISMATCH`, igual que `len(s)`.
Sobre `struct` u otro tipo no-arreglo sigue siendo `TYPE_MISMATCH`.

## 4. V2 — `for x in a { … }`

```ebnf
stmt  = … | "for" IDENT "in" lugar block ;
lugar = IDENT { "." IDENT } ;          (* de tipo [T; N] o str, ver 4.4 *)
```

### 4.1 Significado exacto

`for x in <lugar> { <cuerpo> }` **es**, y así lo ve el intérprete de referencia y
cada backend,

```text
let foridx{n}: i64 = -1;
while foridx{n} + 1 < len(<lugar>) {
    foridx{n} = foridx{n} + 1;
    let x = <lugar>[foridx{n}];
    <cuerpo>;
}
```

(`Parser.for_stmt`; la expansión está en el **parser**, no en el lowering, para que
`steps`, límites y trazas queden definidos sin regla nueva. El `-1` es `IntLit`, no
`Unary` — CORE v0.2 C2 ya define `-1` como un solo literal, y construirlo con el operador
dejaba un `{"k": "neg"}` en la IR que el `while` escrito a mano no tiene.)

**El `let` sin anotación es una excepción acotada, no inferencia [N3].** CORE §4 exige
anotación en todo `let`, y v0.5 no la afloja: la única sentencia del lenguaje que puede
llevar `let` sin tipo escrito es el `let x = <lugar>[foridx{n}];` que inyecta el azúcar de
arriba. La regla normativa es «el `let` sintético del `for` toma el tipo del
**elemento** del iterando», y vive en un solo sitio: la rama `A.Let` de `Checker.stmt` — si `Let.type`
es `None`, se chequea la expresión y se le copia el tipo; desde ahí es un `let` igual que
el escrito a mano. No hay inferencia general, medido: `let x = 1;` sin anotación es
`INVALID_PROGRAM(SYNTAX)` con cabecera `0.4` **y** con `0.5` (el parser la exige antes de
que el checker vea nada), mientras que `let x: i32 = 1;` da `HALTED` con `return 1`. Que el
tipo sea el del elemento y no el del índice lo ejerce `402_for_decimales`: sobre
`[dec<8,2>; 2]`, `x` es `dec<8,2>` y la suma cierra en `3.85`. La excepción entera está
medida y sellada por sonda — `tools/v05_spec_probe.py`, sección 3 (`let_anotacion`) — con
tres controles de sabotaje: el `let` a mano que corriera, una sonda que no distinguiera
la anotación y el sintético con el tipo del índice.

Las llaves del `while` son notacionales: el lenguaje no tiene sentencias-bloque, así
que las dos sentencias sintéticas se escriben en el bloque contenedor
(`Parser.block` aplana). Eso es seguro porque `foridx{n}` no puede aparecer en un
fuente de ese módulo (§4.6).

### 4.2 El incremento va antes del cuerpo, y eso es medido

La forma intuitiva —`while i < len(a) { let x = a[i]; <cuerpo>; i = i + 1; }`— hace
que un `continue` del cuerpo salte el avance.
`programs/conformance_v0.5/gemelos/404_while_incremento_abajo.isy` (cabecera `0.4`,
corre hoy) queda girando sobre el elemento 5 y termina `LIMIT_REACHED(max_steps)` con
`emits=["2","3"]`. Ese archivo es **control negativo permanente**: si algún día
termina, el azúcar dejó de ser el `while` que esta sección declara.

### 4.3 El iterando es un lugar, no una expresión

Medido, con cabecera `0.5`:

| forma | resultado | por qué |
|---|---|---|
| `for x in xs` | `HALTED`, recorre `xs` | lugar |
| `for x in p.xs`, `for x in p.q.ys` | `HALTED` | lugar con campos |
| `for x in xs[0]` | `SYNTAX` | el índice no es lugar |
| `for c in s`, `for c in l.texto` (`s`, `l.texto` de tipo `str`) | `HALTED` | lugar de `str`: recorre sus bytes, **[N1]** §4.4 |
| `for x in id(xs)` | `SYNTAX` | evaluar la cota y el índice dos veces duplicaría efectos |
| `for x in (xs)` | `SYNTAX` | idem |
| `for x in [1, 2, 3]` | `SYNTAX` | **[P2] resuelto: no.** Un literal de arreglo sin tipo esperado es `AMBIGUOUS_LITERAL` (v0.3 §3.5) y el `for` no aporta ninguno |

Que `xs {` no se lea como un literal de struct es la razón por la que el parser toma
el iterando con `ident()`/`Field` en vez de `expr()`: `p.xs { … }` sería ambiguo.

### 4.4 `for` sobre un `str` recorre sus bytes **[N1: adoptada, 2026-11-01]**

Regla normativa: todo **lugar** de tipo `str` —local `str<N>`, campo calificado, parámetro
`str` pelado (§7 / V6) y el valor que entra por stdin— se recorre **`len(s)` veces**, y la
variable del `for` es `u8` **copia**. La cota es la **longitud del valor, no la capacidad
declarada**: `str<8>` con `"hola"` emite 4 bytes, no 8. Es la misma fórmula de §4.1 con
`<lugar>` de `str`, así que no añade operación ni capacidad — medido: `features_of` del `for`
y de su gemelo dan el mismo conjunto (`bool, emit, int64, int8, ir0.2, ovf:trap, str,
unsigned, while`).

Fijado por tres casos con su gemelo escrito a mano (`programs/conformance_v0.5/README.md`):

| caso | qué fija | pasos `for` / gemelo |
|---|---|---|
| `444_for_sobre_str` | la cota es longitud y no capacidad (`str<8>` = `"hola"` → `104 111 108 97`, `len` 4) | 22 / 22 |
| `445_for_str_pelado_stdin` | N1 × V6: `fn emite(s: str)` recorre lo que llega por stdin → 5 bytes y `len` 5 | 27 / 27 |
| `446_for_copia_str` | copia sin alias: `c = 65` dentro del cuerpo y `s[0]` sigue dando `97` | 22 / 22 |

Bordes medidos el 2026-11-01, con cabecera `0.5` salvo donde se dice lo contrario:

| forma | observado |
|---|---|
| `str<1> = ""` | `HALTED`, 0 emisiones, `len` 0, 6 pasos |
| `for c in l.texto` con `L { texto: str<6> }` y `"abc"` | `HALTED`, `97 98 99`, `return 3`, 18 pasos |
| `c` después del bucle | `INVALID_PROGRAM(UNKNOWN_NAME)` |
| `n = n + c` con `n: i64` | `INVALID_PROGRAM(TYPE_MISMATCH)` — `c` es `u8` y hace falta cast (§1.2 de CORE) |
| `for c in s[0]` | `INVALID_PROGRAM(SYNTAX)` — un índice no es lugar (§4.3) |
| `s[0] = 66` dentro del cuerpo | `INVALID_PROGRAM(NOT_ASSIGNABLE)` — los `str` son inmutables desde v0.3 (`CORE_v0.3.md:40`), así que la dirección inversa del alias **no es construible**: la única que la regla tiene que garantizar es que escribir `c` no toca el lugar. Medido el 2026-11-02 01:31 UTC y fijado por `test_es_copia_y_ademas_el_lugar_no_se_puede_escribir`, no por la matriz sellada de la sonda (sus doce filas no tenían esta forma) |
| cabecera `0.4` | `INVALID_PROGRAM(SYNTAX)` — `for` es reservada solo desde `0.5` (V3) |
| `s[7]` con `str<8> = "hola"` | `ERROR(INDEX_OUT_OF_BOUNDS)` a los 3 pasos — la regla de rango es la de v0.3 §2.4, y el `while` gemelo falla igual |

Por qué se adopta y no se rechaza: el desugaring vive en el parser (`Parser.for_stmt`) y no
mira tipos; el checker solo ve un `let` sintético sin anotación (§4.1). Rechazar el `str`
obligaría a etiquetar los nodos sintéticos, y el `while` gemelo escrito a mano seguiría siendo
legal — o sea el `for` dejaría de ser azúcar, que es la invariantе que V2 fijó con pasos,
traza e IR iguales (§4.7).

**Corrección sobre lo que decía esta sección.** Hasta hoy afirmaba «su `while` gemelo escrito
a mano cuesta lo mismo (**24 pasos** los dos)» y «sobre `str<4> = "hola"` da
`104 111 108 97`». El segundo dato es cierto y verificado (con capacidad exacta `str<4>` el
literal entra y salen los cuatro bytes), pero el primero estaba mal atribuido, y la razón es
medible: los 24 son de la matriz de *forma constante* de `tools/v05_spec_probe.py` **§5**, cuyo
programa recorre dentro de una **función** (`fn recorre(s: str<4>)` llamada desde `main`, con
su marco y su `return len(s)`). El programa que esta sección citaba —el recorrido todo dentro
de `main`, que es la forma de `444`— gasta **22** pasos, y su gemelo también. Medido el mismo
día en las dos formas: `24` con llamada, `22` sin ella, misma salida y misma traza en el par de
cada forma. La igualdad con el gemelo se mantiene; lo que estaba transcrito de memoria era el
número, y es el hallazgo 1 de `docs/EVIDENCE_MATRIX.md` reproduciéndose dentro del spec. De ahí
que los números de arriba estén citados por corrida.

### 4.5 La variable del `for`

Es una **copia** del elemento (principio CORE §1.2, sin aliasing): reasignarla dentro
del cuerpo no toca el arreglo — caso `405_for_copia`, que además ejerce V4.
`break`, `continue` y `return` se comportan exactamente como en `while` (medido:
`continue` avanza, `break` sale, `return` sale del `fn`). Un nombre del `for` que ya
está visible es `INVALID_PROGRAM(DUPLICATE_NAME)`, la misma regla de `let` (CORE §4,
sin shadowing) — medido.

### 4.6 El índice sintético

`Parser.fresh_index` produce `foridx{n}` eligiendo `n` fuera del conjunto
de identificadores del módulo, y avanza el contador por cada `for`: tres `for` en un
módulo dan `foridx0`, `foridx1`, `foridx2` (medido en la traza). Un fuente que
declare `let foridx0: i32 = 7;` no colisiona — el azúcar toma otro nombre y la
variable del programista conserva su valor (medido: `emits=["8","9"]`,
`return 7`). Consecuencia honesta: **el nombre aparece en las trazas y en la IR**, así
que comparar la traza de un `for` con la de su gemelo exige normalizarlo; el test
`tests/test_v05_core.py:ForAzucar.test_la_traza_stmt_es_la_traza_del_gemelo` lo hace.
`at` de todas las sentencias sintéticas es la línea del `for` **[P1]**, medido.

### 4.7 Equivalencia exigida (gate F2.4 ítem 2)

Para cada `for` del corpus, el `while` gemelo de
`programs/conformance_v0.5/gemelos/` debe coincidir en `status`, `code`, `emits`,
`return`, **`steps`** y en la traza `stmt` línea a línea salvo los `at`. Pasos
medidos: `402` 18, `403` 23, `404` 38, `405` 20 y —con los casos de N1— `444` 22, `445` 27,
`446` 22, cada uno igual a su gemelo. La prueba
fija como número los de `403`–`405` y `444`–`446` (`PASOS_EXIGIDOS` en `tests/test_v05_core.py`) y
`402` entra solo por la igualdad con su gemelo inline — que es la exigencia real, porque
el número absoluto no es normativa. El azúcar no añade capacidades: la IR del `for` es
idéntica a la del gemelo tras podar posiciones y el nombre del índice.

## 5. V4 — los parámetros son locales mutables

Texto normativo pedido por D1 (la implementación lo hacía desde siempre; **cero**
casos del corpus lo otorgaban). Se añade a `CORE.md` §4, junto a «`let` declara una
variable mutable»:

> Los parámetros son variables locales mutables del marco de la llamada. Todo paso es
> **por copia**, así que asignar a un parámetro no afecta al llamador.

Medido, con el llamador comprobado después de la llamada:

| forma en el cuerpo del `fn` | efecto en el llamador |
|---|---|
| `n = n / 2;` (entero) | ninguno: `emits=["42","21"]`, `return 21` |
| `p.x = 99;` (campo de struct) | `q.x` conserva su valor |
| `v[0] = 7;` (elemento de arreglo) | `xs[0]` conserva su valor |
| `s = s + "!";` (str, requiere ensanchamiento) | `ay!` dentro, afuera intacto |
| `for x in xs { x = x + 1; … }` | el arreglo no cambia (es `405`) |

`407_parametro_reasignable` fija el primer renglón: `HALTED`, `emits=["42","21"]`,
8 pasos, mismo resultado con cabecera `0.4` (D1 ya funcionaba; lo que falta es texto).

## 6. V5 — `qname` como tipo de elemento

Delta sobre v0.3 §3.1 / v0.4 §3:

```ebnf
elem_type = "bool" | int_type | dec_type | str_type | IDENT | qname ;
```

`[reporte.Linea; 3]` es un tipo de arreglo cuyo elemento es un struct de un módulo
importado. **No es un cambio de comportamiento**: enlaza hoy, y `408_qname_arreglo`
(raíz `0.5`, módulo `0.5`) lo ejecuta. El texto existe para que la spec congelada no
sea más estricta que la implementación. Aristas medidas:

| programa | resultado |
|---|---|
| `[linea.Linea; 2]` con `import linea;` | `HALTED` (recorre los dos elementos) |
| `fn f(x: [linea.Linea; 2])` — `qname` en parámetro | `HALTED` |
| `qname` sin `import` del módulo en **este** archivo | `UNKNOWN_NAME` (v0.4 §4) |
| `import` de un archivo que no existe | `UNKNOWN_MODULE` |
| struct no `pub` usado con prefijo | `NOT_PUBLIC` |
| `[linea; 2]` (el módulo no es un tipo) | `UNKNOWN_NAME` |
| `[[linea.Linea; 2]; 2]` | `SYNTAX` — siguen sin existir arreglos de arreglos (v0.3 §3.1) |

## 7. V6 y V6-bis — `str` escrito sin capacidad

Regla: `str` **sin capacidad** es un tipo con la capacidad **diferida**; solo puede
aparecer en un parámetro (`fn p(s: str)`) o en el retorno (`fn f() -> str`), y solo
con familia `v05`. La capacidad la fija el **sitio de llamada**: en el parámetro, la
del tipo real del argumento; en el retorno, la esperada en la posición de llamada. El
frontend monomorfiza: por cada clave `(nombre, anchos de parámetros [, r<ancho de
retorno>])` hace una copia del `fn` con los tipos ya concretos (`make_clone`, `specialize.py`) y
reescribe la llamada al nombre de la copia (`spec_name`). **La
definición pelada nunca se chequea**: lo que se chequea es cada copia, con tipos
corrientes de v0.3. Ningún backend conoce V6.

- **Sin centinela.** `ContextStrT` (`types.py`) es un tipo, no un número: `0`,
  `-1`, `None` y `MAX_STR` significan lo de siempre. `type_size` lanza
  `AssertionError` si alguien la mide e `ir.py:ty_to_json` no la conoce: una
  capacidad diferida que llega a la IR es un bug, no un dato.
- **Fuera de esas dos posiciones sigue siendo `SYNTAX`**: `let`, campo de struct,
  `cast`, arreglo (`425`), y dentro de un parámetro con cabecera `0.3`/`0.4` (`426`).
  V6 no relaja ninguna semántica anterior.
- **Sin expectativa no hay ancho por defecto**: `doble("ab");` como sentencia (`432`)
  o como `emit` (`433`) es `TYPE_MISMATCH` en el llamado; `fn main() -> str` (`436`) y
  un parámetro pelado de `main` (`424`) se rechazan — `main` no tiene sitio de
  llamada, sus argumentos vienen de stdin.
- **Fail-closed en las dos direcciones.** Si el cuerpo exige un ancho mayor que el
  resuelto (`let t: str<4> = s` con `s` instanciado en `str<5>`), es
  `TYPE_MISMATCH` estático al chequear la copia (`422`, `431`). Si el desborde solo se
  ve al ejecutar, es `ERROR(OVERFLOW)` con cero `emits` (`416`, `418`, `430`).
  Ninguna de las dos trunca. El ensanchamiento ordinario de v0.3 (`str<4>` dentro de
  una expectativa `str<8>`) sigue siendo legal y no es regla nueva.
- **Transmisión**: la capacidad viaja de llamado a copia y de copia a copia, y la
  recursión se ve a sí misma porque la clave ya está registrada al chequear el cuerpo
  (`413`, `420`). Un literal sin contexto aporta su propia capacidad (`"hi"` ⇒
  `str<2>`, `""` ⇒ `str<1>` por `max(len, 1)` de v0.3) — `412`.
- **Orden de los errores**: una copia se chequea en el sitio de su primera llamada, no
  en su posición de fuente; el `at` reportado sigue siendo el de la definición
  original (`413`).
- **Lo que se descarta**: una definición contextual que nadie llama no tiene
  capacidad que resolver y se quita del programa después de especializar (`419`). Es
  la única concesión del diseño y está fijada por un caso.
- **Los nombres** (`pad.8`, `geo.pad.8.16`, `pad.8.r16`) son segmentos adicionales del
  nombre calificado, así que la codificación de `backends/base.py:fn_ident`
  (longitud prefijada, inyectiva) los vuelve identificadores legales sin saber nada
  de V6, y dos resoluciones distintas no colisionan entre sí ni con un nombre de
  usuario (`414`/`415` son el mismo programa con las llamadas invertidas).
- **Cuesta AST, no pasos**: a **forma constante**, el azúcar añade definiciones al AST
  y cero pasos en la ejecución (`411` y `423` coinciden con sus gemelos `0.4` en las
  cinco columnas y en `steps`). La calificación importa: el primer gemelo de `429` se
  escribió con una forma distinta —`emit f(…)` directo en vez de `let` + `emit`— y
  daba 7 pasos contra 9. La diferencia eran los `let`, no la especialización.
  `for c in s` volvió a caer en la misma trampa: la igualdad de pasos solo vale con
  la forma igual, y el número que §4.4 citaba estaba mal atribuido a esta matriz (hoy
  `444` y su gemelo dan **22 = 22**, medido el 2026-11-01).
- **Tope P4 (cerrada el 2026-11-02).** La monomorfización es **silenciosa** sin
  cota, y el conteo es **multiplicativo en las ranuras**: dos parámetros con ocho
  anchos cada uno son 64 copias. La regla es **256 resoluciones por definición
  dentro de un programa** (`specialize.py:MAX_CLONES_PER_DEFINITION`, contado en
  `checker.py:spec_counts`): la resolución 257 se rechaza en tiempo estático con
  `SPEC_LIMIT`, el programa no baja a IR y ningún backend lo ve (`447`; `448`
  fija el piso legal con 16 = 4×4). La granularidad es por definición y no por
  programa porque el conteo es multiplicativo: un tope por programa castiga a
  quien escribe una función de dos parámetros contextuales frente a quien
  escribe diez de una.
- **Cota Z2 de anidamiento (cerrada el 2026-11-03).** `ast.MAX_EXPR_DEPTH = 64`
  (`isyco/ast.py`) es un literal del spec, no un ajuste del anfitrión, y se mide **dos
  veces** porque anidar tiene dos caras: `Parser.nivel` cuenta los niveles que le bajan
  frames (paréntesis, argumentos, prefijos) y `Checker.check` mide la cadena de nodos del
  AST antes de tocar nada recursivo —una suma izquierda de k términos se construye en un
  bucle y no le baja ni un frame al parser—. El nivel 65 se rechaza con `INVALID_PROGRAM` /
  **`SPEC_LIMIT`** nombrando el nivel y la cota en el mensaje, y el programa no baja a IR
  (`449`–`454` fijan los dos bordes de cada cara). Las cuatro caras llegan al borde con
  conteos distintos del fuente —63 pares, 64 prefijos `-`, 64 términos sumados, 63 términos
  `len(s)` con clon— y al **mismo nivel**, medido por la sonda (`tools/z2_guard_probe.py`).
  La regla es general, no es de V6; vive en §7 porque ahí está el clon que ponía la frontera
  baja (241 términos): con la guarda ese fuente se rechaza por `SPEC_LIMIT` en 27 ms y el
  `deepcopy` de `make_clone` ya no se alcanza por esta vía. El número deja aire medido: la
  forma legal más cara (63 pares de paréntesis) pide **716** frames de los 999 útiles,
  `python3 -m isyco ir` llega al frontend con **6**, un test del paquete con **10**, y la
  profundidad máxima de la población del repo sigue en **8** sobre 154 fuentes que bajan. El aire
  es para los llamantes **medidos**, y la limitación está escrita: con la guarda puesta, ese mismo
  fuente del tope legal sigue muriendo por `RecursionError` si quien llama trae 300 frames (C8 de
  la sonda). La cota garantiza que **el idioma** nombre el borde, no que la forma legal quepa en
  cualquier pila heredada. Decisión y evidencia: `docs/decisions/Z2_MAX_EXPR_DEPTH.md`.
  **Corrección fechada (2026-11-12, Z2-b):** esa limitación se cerró sin tocar la regla ni el
  número. `isyco/pila.py` reserva la pila de todo recorrido acotado por la cota contada desde el
  llamante (32 frames por nivel), y el tope legal baja con 0, 300 y 3 000 frames encima
  (`evidence/z2_pila/run_2026-11-12T024856Z.json`, P1–P7). No es normativo: es holgura del
  anfitrión de referencia. Decisión: `docs/decisions/Z2B_PILA_PROPIA.md`.
- **Cota Z3 de anidamiento de sentencias de control (cerrada el 2026-11-12).**
  `ast.MAX_STMT_DEPTH = 64` (`isyco/ast.py`) es un literal del spec, paralelo a
  `MAX_EXPR_DEPTH`. Un **nivel** es un `if` o un `while` en la cadena que encierra a una
  sentencia; el `for` es azúcar de `while` (V2) y cuenta como uno; el cuerpo de una función es
  nivel 0; y **un `else if` cuenta un nivel más**, porque es un `if` dentro del `else` del
  anterior aunque el fuente se lea plano. El nivel 65 se rechaza con `INVALID_PROGRAM` /
  **`SPEC_LIMIT`** nombrando el nivel y la cota, y el programa no baja a IR (`455`–`458` fijan
  los dos bordes del `if` anidado y de la cadena `else if`). Se mide en `Parser.control` y en
  `Checker.check` (`stmt_depth`, iterativo); aquí las dos guardas cuentan lo mismo. La regla es
  general y vive en el camino compartido: aplica a toda versión, y ninguna fuente `0.1`–`0.4`
  del repo la roza (la población anida como máximo 4). Antes no había cota: 676 `if` anidados
  bajaban y 677 morían por `RecursionError`. No acota la **cantidad** de sentencias hermanas.
  Con las dos cotas nombradas el coste de pila de una llamada queda acotado, y la referencia
  reserva pila por llamada en función de ellas (no normativo). Decisión y evidencia:
  `docs/decisions/Z3_MAX_STMT_DEPTH.md`, `evidence/z2_pila/run_2026-11-12T042036Z.json`.
- **El techo del toolchain no es el techo del idioma.** Con el tope puesto, C y
  Rust compilan todas las filas que la sonda genera antes del tope —256 copias
  con una y con dos ranuras, 216 con tres, 256 con cuatro—; **el emisor de
  octubre, en Zig, no**: su evaluación en tiempo de compilación agotaba un tope
  interno y abortaba (`error: evaluation exceeded 1000 backwards branches`), y
  la frontera dependía de la **aridad** de la definición, no solo del número de
  copias. Medido por bisección (`tools/v05_p4_probe.py --bisect-zig`): aridad 1
  no falla dentro del tope, aridad 2 compila 250 y revienta en 252, aridad 3 en
  164/168, aridad 4 en 120/128. **Medido el 2026-11-03 que esa frontera era del
  emisor, no de Zig ni del idioma**
  (`evidence/z1_ceiling/run_2026-11-03T035753Z.json`): Zig cobra **una** rama de
  evaluación por instanciación de `str` y el emisor cobraba **dos**, porque cada
  sitio instanciaba además su propio tipo. Con un alias `const StrN = IsyStr(N);`
  por ancho y `@setEvalBranchQuota(1000 + 8·sitios)` como primera sentencia de
  todo cuerpo que instancia `str`, compilan las ocho formas medidas —hasta 2048
  instanciaciones en una firma—, coincidiendo con la referencia y con C, y el
  gate completo sale `PASS` (`evidence/backends/gate_2026-11-03T040610Z.json`).
  O sea que P4 no afirma que 256 copias compilen en todas partes, afirma que el
  frontend no las acepta sin decir por qué — y lo que la medición compra es que
  **tampoco** promete coste: 512 sitios cuestan 18 s de compilación y 1024 en
  cuatro ranuras, 60,8 s; y la aridad no está topada, así que el producto
  `256 clones × aridad` sigue siendo construible más allá de lo medido. La
  garantía tiene además un límite conocido por el otro lado, y **ese sí está nombrado
  desde el 2026-11-03**: en materia de **profundidad de expresión** el frontend cortaba a
  los 242 términos `len(s)` con `RecursionError` de Python —sin `SPEC_LIMIT`, sin número y
  sin por qué—; hoy corta en el nivel 65 con `SPEC_LIMIT` (**Z2**, bullet arriba y
  `docs/decisions/Z2_MAX_EXPR_DEPTH.md`). Las cuatro fronteras de la bisección
  se conservan sin retocar: son el registro de la corrida que abrió **Z1**, hoy
  abierta como política y sin testigo concreto.

## 8. V7 — capacidades por contenido, no por etiqueta

Dos preguntas que estaban mezcladas:

| pregunta | dónde vive | qué decide |
|---|---|---|
| `SCHEMA_CAN_EXPRESS` | `module["schema"]` (`lower`, `ir.py`) | qué puede representar el contenedor |
| `PROGRAM_REQUIRES` | `features_of(módulo)` (`backends/base.py`) | qué exige **este** programa |

`UNSUPPORTED` tiene que señalar una capacidad que este programa exige. `ir0.2` solo
se añade si el contenido usa `str` o `struct` —los únicos tipos que no caben en
`isy-ir/0.1`, misma relación con la que `ir_validate` ya acepta el módulo—, así que un
programa `0.5` puramente numérico sigue siendo ejecutable por un backend que no
implementa `0.2` (COBOL es el canario precisamente por eso). El átomo `emit_array` es
nuevo: emitir un arreglo es una relajación de v0.3, no un tipo `0.2`, y COBOL no lo
implementa — concederlo por la etiqueta tapaba el hueco con `ir0.2`, una capacidad
que el programa no pedía (`253`, `441` → `UNSUPPORTED(emit_array)`).

Regla de contrato que se deriva: **un hueco del emisor es un bug, no una capacidad.**
`327_qualified_call_stmt` reveló que COBOL no declaraba el hueco `{prefijo}RET` para
funciones `void`, aunque el proemio y el epílogo lo escriben; se arregló
`CobolEmitter.fn_unit` (`isyco/backends/cobol.py`) en vez de inventar una capacidad «COBOL no sabe llamadas
void». El defecto era previo y alcanzable fuera de v0.5 (canario `439`, `isyco 0.1`).

## 9. Corpus, gate y no regresión

- `programs/conformance_v0.5/` tiene **58 casos** (401–458, 54 de archivo suelto y 4
  directorios de módulos), con los `expected` escritos a mano entre el 2026-10-30 y el
  2026-11-12, **antes** de tocar `isyco/` en cada decisión. El directorio está en
  `CORPORA` (`isyco/conformance.py`) desde `57f38bc`, así que el gate de backends pasó
  de 170 a **212** casos; `443` (alta 2026-11-01) sube la población del gate a **213**,
  `444`–`446` (N1, alta el mismo día) a **216**, `447`/`448` (P4, alta 2026-11-02) a
  **218**, `449`–`454` (Z2, alta 2026-11-03) a **224** y `455`–`458` (Z3, alta 2026-11-12) a **228**. Los tres de N1 van con su `while` gemelo
  en `gemelos/`, que `load_corpus` no cuenta (`load_corpus`).
  Recibos de la corrida de 212, los tres con `git_head=57f38bc`: referencia `212/212`
  (`evidence/conformance/run_2026-11-01T033345Z.json`), IR `424/424` comparaciones
  iguales sobre 145 programas bajados (`evidence/ir/gate_2026-11-01T013721Z.json`) y
  backends `verdict=PASS` (`evidence/backends/gate_2026-11-01T015245Z.json`): C, Rust,
  Zig y pydecimal `212/212` con `8 484` corridas diferenciales y cero diferencias más
  `1 270` del diferencial de strings; COBOL `146/212` con 66 `UNSUPPORTED` nombrados.
  Recibos de la corrida de 213, los cuatro con `git_head=a4f608c` y en una sola corrida en
  lote, todos `PASS`: referencia `213/213`
  (`evidence/conformance/run_2026-11-01T074055Z.json`), IR `426/426` sobre los mismos 145
  programas bajados —`443` no baja: se comparan sus dos rechazos—
  (`evidence/ir/gate_2026-11-01T074055Z.json`), C en las cuatro combinaciones con sanitizers
  `213/213` (`evidence/c/gate_2026-11-01T074655Z.json`) y backends con C, Rust, Zig y
  pydecimal `213/213` y COBOL `147/213` con los mismos 66 `UNSUPPORTED`
  (`evidence/backends/gate_2026-11-01T082046Z.json`).
  Recibos de la corrida de **216**, los tres primeros en un solo lote con
  `git_head=2499fae` (el sello de la sonda con la matriz de N1): referencia `216/216`
  (`evidence/conformance/run_2026-11-01T210445Z.json`, sha
  `62da1207c9d6330d…`), IR `432/432` sobre **148**
  programas bajados —los tres casos nuevos sí bajan—
  (`evidence/ir/gate_2026-11-01T210450Z.json`, sha `8473534c44e35c5c…`) y C `PASS` con
  `216/216` en las cuatro combinaciones
  (`evidence/c/gate_2026-11-01T211424Z.json`, sha `3ba9864e0714c69f…`); F5 `PASS` con
  C, Rust, Zig y pydecimal `216/216` y COBOL `147/216` **con 69 `UNSUPPORTED`** —los tres
  de N1 entran con `ir0.2,str`— (`evidence/backends/gate_2026-11-01T225011Z.json`, sha
  `63d7a9b4954c468d…`, `git_head=6c00225`; su corrida gemela en `2499fae` salió `FAIL` por
  un `TIMEOUT` del arnés y el recibo queda preservado). Cada uno con su stdout crudo
  sellado al lado y sus hashes en el `SHA256SUMS.txt` del directorio.
  Recibos del lote de **218** (P4), los cuatro gates con `git_head=14b19a9` y todos `PASS`:
  referencia `218/218` (`evidence/conformance/run_2026-11-02T070428Z.json`), IR `436/436`
  sobre **149** programas bajados —`448` baja, `447` se compara por su rechazo—
  (`evidence/ir/gate_2026-11-02T070428Z.json`), C `218/218` en las cuatro combinaciones
  (`evidence/c/gate_2026-11-02T072103Z.json`) y backends con c, rust, zig y pydecimal
  `218/218` y COBOL `148/218` con 70 `UNSUPPORTED` nombrados
  (`evidence/backends/gate_2026-11-02T081912Z.json`). No regresión medida hoja por hoja
  contra el lote de 216 e indexada por la identidad del renglón —el caso, y caso más nivel de traza
  en F3, que ocupa dos renglones por caso—: de las 2 727 hojas compartidas de F2 solo difieren
  `total`, `passed` y el sello del recibo (`generated_utc`, `git_head`), y de las 3 462 de F3 los
  tres contadores y ese mismo sello; F4 y F5, cotejados igual, salen con 14 de 42 y 39 de 398
  hojas distintas, todo contadores, campos de costo y sello. La sonda de P4 es el recibo
  que fija la regla y el techo del toolchain —**medido el 2026-11-03 que ese techo era
  del emisor de Zig y no del idioma: ver §7 y la fila Z1 de §11**—: **R2
  `evidence/v05_p4/run_20261102T085025Z.json`**, `RELEASE_GATE` con `git_head=d363e7c`. La
  corrida del lote (**R1** `run_20261102T081925Z.json`, `203f579`) salió `EVIDENCE_ONLY` porque
  la documentación de este lote estaba a medio editar mientras corría —`isyco/` y `tools/` no
  tenían ninguna modificación—; se conservó sin retocar y R2 la repite hoja por hoja: 1 135
  hojas compartidas, 118 distintas, de las cuales 114 son campos de tiempo y 4 el propio sello.
  Recibos del lote de **224** (Z2), los cuatro gates con `git_head=7022ae4`, árbol de
  código limpio y `veredicto_arbol=RELEASE_GATE` en los cuatro, salidos de **una sola cadena**
  en el orden F2, F3, F4, F5: referencia `224/224`
  (`evidence/conformance/run_2026-11-03T232115Z.json`, sha `35c881ea…`), IR `448/448` sobre
  **152** programas bajados —los tres `al_tope` bajan, los tres `pasa_tope` se comparan por
  su rechazo— (`evidence/ir/gate_2026-11-03T232115Z.json`, sha `eb006123…`), C `224/224` en
  las cuatro combinaciones (`evidence/c/gate_2026-11-03T232116Z.json`, sha `b09233e0…`) y
  backends con c, rust, zig y pydecimal `224/224` y COBOL `153/224` con 71 `UNSUPPORTED`
  nombrados (`evidence/backends/gate_2026-11-03T232750Z.json`, sha `cb29cbde…`). No regresión
  medida hoja por hoja contra el lote de 218, con el índice del renglón —el caso, y caso más
  nivel de traza en F3—: F2 deja 2 786 compartidas, 4 hojas distintas (el sello y
  `total`/`passed` `218→224`), 72 altas y **0 bajas**; F3, 3 500 compartidas, 5 distintas,
  96 altas (los doce renglones nuevos) y **0 bajas**; F4, 63 compartidas y 19 distintas
  —todo contadores y sello; 0 altas porque F4 no guarda renglones por caso—; F5, 448
  compartidas, 42 distintas, 2 altas (el renglón `453_len_pelado_al_tope` dentro del
  `UNSUPPORTED` de cobol) y 4 bajas, que son el `--extra-case` que este lote no llevó, no
  capacidad perdida. La sonda del después es `tools/z2_guard_probe.py` con su recibo
  `evidence/z2_guard/run_2026-11-04T001913Z.json` (sha `5a295289…`, `RELEASE_GATE` sobre el
  mismo `7022ae4`, C1–C8 `DEMONSTRADO`), corrido en el segundo en que F5 terminó de escribir.
  Recibos del lote de **228** (Z2-b y Z3), los cuatro gates con `git_head=1cb56ce`, árbol de
  código limpio y `RELEASE_GATE`: referencia `228/228`
  (`evidence/conformance/run_2026-11-12T042323Z.json`), IR `456/456` sobre **154** programas
  bajados —`455` y `457` bajan, `456` y `458` se comparan por su rechazo—
  (`evidence/ir/gate_2026-11-12T042323Z.json`), C `228/228` en las cuatro combinaciones
  (`evidence/c/gate_2026-11-12T042330Z.json`) y backends con c, rust, zig y pydecimal
  `228/228` y COBOL `157/228` con los mismos 71 `UNSUPPORTED`
  (`evidence/backends/gate_2026-11-12T042934Z.json`). No regresión medida hoja por hoja contra
  el lote de 224, esta vez con herramienta y recibo en vez de a mano
  (`tools/lote_diff.py` → `evidence/lotes/run_2026-11-12T150933Z.json`, `RELEASE_GATE`): F2,
  2 858 compartidas, 5 distintas (sello, `total`/`passed` y la versión de Python), 48 altas y
  **0 bajas**; F3, 3 596 compartidas, 5 distintas, 64 altas y **0 bajas**; F4, 63 compartidas y
  19 distintas; F5, 450 compartidas y 44 distintas —todo sello, contadores, costo y toolchain,
  ninguna hoja de resultado—. El sabotaje de la herramienta (un resultado cambiado y un caso
  borrado) sale `REGRESION`. **Límite de ese cotejo:** el lote de 224 salió del anfitrión de
  Danny (Python 3.12.3, rustc 1.98.1) y el de 228 de un contenedor (Python 3.13.18, rustc
  1.97.0); que coincidan hoja por hoja entre dos anfitriones es dato a favor, pero el lote de
  228 **no se ha repetido en el anfitrión de Danny**.
- **No regresión:** ningún programa `0.1`–`0.4` cambia. Medido por recabezado
  (`401`/`406` siguen en `UNKNOWN_NAME` en 0.1/0.2 y `TYPE_MISMATCH` en 0.3/0.4;
  `402`–`405` siguen en `SYNTAX`; `426`/`437` siguen en `SYNTAX`), por el brazo viejo
  reconstruido del commit previo —FIEL en los 118 módulos del corpus congelado— y por
  el gate de backends sobre el corpus congelado, que no registró diferencias.
  Prueba: `tools/v05_revalida_probe.py` y `tools/v7_capability_probe.py`.
- Poblaciones explícitas: las suites que afirman un conteo sobre el corpus congelado
  lo recorren por su nombre (`CONGELADO` en `tests/test_backends.py`, `FROZEN` en
  `tools/v7_capability_probe.py`) en vez de `load_all`, porque meter v0.5 en `CORPORA`
  cambió el tamaño de esa población. Un conteo sin población nombrada es una
  afirmación sin prueba.
- **El instrumento no define semántica.** Desde el arnés endurecido (2026-11-02) un fallo del
  banco de pruebas se registra como dato y no aborta la corrida: cada pierna de los gates lleva
  una lista hermana `harness` con `TOOLCHAIN_BUILD_FAIL` o `HARNESS_INTERNAL`, una pierna que no
  terminó se escribe `not_run`, una corrida abortada deja `abortado` con su traceback y el recibo
  se sella en los tres casos. Nada de eso mueve la frontera de lo que el idioma acepta: `448`
  (16 clones) y la forma de 256 clones son dos puntos distintos de la misma regla —el tope de
  `SPEC_LIMIT` lo decide el frontend, antes de la IR—, mientras que lo que el compilador de un
  backend haga con un programa ya aceptado es propiedad del backend y lo fija `spec/BACKEND.md`
  §5 cláusula 6. El caso de 256 clones **no** entra al corpus por eso: corre con
  `--extra-case` y deja su propio recibo.

## 10. Fuera de alcance de v0.5

| bloqueo | por qué no entra |
|---|---|
| B4 estado entre llamadas / variables de unidad | toca CORE §1.2 (sin aliasing) y §4 (sin globales); el work-around existe y está medido |
| B5 efectos de lectura (reloj, ambiente, stdin, archivos) | es una decisión de alcance del lenguaje, merece su propio documento |
| B7 anchos enteros mixtos | regla de coerción sobre 6 tipos con `ovf` distinto; con V1 el dolor medido desaparece |
| B8 texto decimal no canónico (`"199.9"` ⇒ `BAD_FORMAT`) | cambiar `ERROR(BAD_FORMAT)` es cambiar la forma canónica de v0.3 §10.1 y los cinco backends; va a v0.6 |
| B9 valor ausente / arreglos que crecen | `null`/optional exige forma canónica de entrada y salida; los arreglos dinámicos rompen §1.1 (sin heap) |
| aritmética de capacidad `str<N+k>` | **no hace falta**: `str<N> + str<M>` ya suma capacidades (`Checker.str_binary`: con tipo esperado devuelve ese tipo; sin él, `str<min(N+M, MAX_STR)>`) y con contexto la capacidad esperada, así que `pad` corre hoy en los cinco backends |
| `for` sobre expresiones, literales o índices | §4.3; un literal sin tipo esperado es `AMBIGUOUS_LITERAL` |
| métodos (`a.len`), reexportar, alias de import, importar nombres sueltos | v0.3 §9 y v0.4 §8 los siguen excluyendo |

## 11. Preguntas abiertas y qué falta antes de congelar

| id | estado | qué falta |
|---|---|---|
| P1 (`at` de las sentencias sintéticas del `for`) | **cerrado por medición** | — (es la línea del `for`; el gate compara trazas salvos `at`) |
| P2 (`for` sobre un literal de arreglo) | **cerrado: no** | — (`SYNTAX`, §4.3) |
| P3 (nombre de la especialización y su efecto en `program_sha256` y las trazas) | **cerrado por medición** | `program_sha256` es el SHA del archivo principal (v0.4 §6 P6) y **no se mueve**: medido en `411`, `417` y `420`, los tres iguales al `sha256sum` del `.isy`. Lo que sí cambia es la traza: `411` muestra `main`, `pad.2`, `pad.7` y nunca `pad` a secas — la especialización es visible en el nombre, no en la identidad. Los nombres viajan por la codificación inyectiva de `fn_ident` (longitud prefijada), que no colisiona con un nombre de usuario |
| P4 (cota de especializaciones por programa) | **cerrada el 2026-11-02: 256 por definición dentro del programa, `SPEC_LIMIT`** | La regla está en §7 y la decisión con su evidencia en `docs/decisions/P4_SPEC_LIMIT.md`. La base con la que se eligió el número quedó sellada antes: `tools/v05_p4_probe.py` recalculaba el censo desde `Checker.specs` sobre la población del gate y medía la forma — **33 clones** en 19 de los 46 casos (27 V6 + 6 V6-bis, 13 definiciones), 4 por programa, 2 por definición **dentro de un programa** pero 7 de `doble` **en el corpus**; una ranura con K anchos da K clones, dos W², tres W³, 20 sitios con el mismo ancho dan 1 clon (`evidence/v05_p4/run_20261101T234407Z.json`, `RELEASE_GATE` sobre `6ebb00d`; las dos corridas anteriores siguen válidas para su población: `run_20261101T154040Z.json` —`2938c01`, 32 en 18/43— y `run_20261101T062234Z.json` —`52f5564`, sobre 42—). Con la decisión dentro, la sonda re-mide sobre **48** casos: **49 clones en 20 programas**, 14 definiciones, y el máximo **sin** los casos de tope sigue en **2** (`evidence/v05_p4/run_20261102T081925Z.json` —R1, `EVIDENCE_ONLY` porque la documentación del lote estaba a medio editar; la misma corrida sobre el árbol commiteado es R2 `run_20261102T085025Z.json`, `RELEASE_GATE`, idéntica hoja por hoja salvo tiempos y el sello—). Los dos casos que la fijan: `447` (la 257 se rechaza en el frontend, no baja a IR) y `448` (16 = 4×4 copias, legal). Lo que la medición **no** compró: techo de toolchain — Zig revienta con 256 copias de una definición de dos ranuras mientras C y Rust las compilan, y **Z1** pregunta si eso es frontera del idioma o del backend. **Corregido el 2026-11-03:** esas fronteras eran del emisor de Zig, no del idioma ni del toolchain — ver la fila Z1 y §7 |
| Z1 (¿el techo de un toolchain es parte del idioma?) | **abierta desde 2026-11-02; sin testigo concreto desde 2026-11-03 — no es decisión de semántica** | Medida la frontera el 2026-11-02 (`evidence/v05_p4/run_20261102T085025Z.json` §6 y su bisección: aridad 2 compila 250 y revienta en 252, aridad 3 en 164/168, aridad 4 en 120/128, aridad 1 no falla dentro de la cota) y **medido el 2026-11-03 que esas cuatro fronteras eran del emisor, no de Zig** (`evidence/z1_ceiling/run_2026-11-03T035753Z.json`, diez claims `DEMONSTRADO`): Zig cobra **una** rama de evaluación por instanciación de `str` y el emisor cobraba **dos**. Con `const StrN = IsyStr(N);` por ancho y `@setEvalBranchQuota(1000 + 8·sitios)` por cuerpo compilan las ocho formas medidas —hasta 2048 instanciaciones en una firma—, coinciden con la referencia y con C, y el gate completo sale `PASS` (`evidence/backends/gate_2026-11-03T040610Z.json`). No se movió ninguna cota. Lo que queda por decidir es si el idioma hereda el **coste** de un toolchain (18 s para 512 sitios, 60,8 s para el caso extra) y en qué capa viviría ese dato si se eligiera nombrarlo —hoy `PROGRAM_REQUIRES` (V7) describe contenido, no coste de compilación—; §7 tiene la limitación escrita |
| Z2 (¿el frontend tiene un techo de profundidad de expresión?) | **cerrada el 2026-11-03: 64 niveles, `SPEC_LIMIT`** | La regla está en §7 y la decisión con su evidencia en `docs/decisions/Z2_MAX_EXPR_DEPTH.md`. Lo que se midió antes de decidir (`evidence/z2_depth/run_2026-11-03T074629Z.json`, E1–E10 `RELEASE_GATE`): una cadena izquierda de 241 términos `len(s)` bajaba a IR y 242 subían `RecursionError` de Python contra el límite de fábrica, el borde bajo lo ponía el `copy.deepcopy` de `make_clone` (985 de 999 frames), la referencia normativa lo pagaba igual por las tres rutas y el número dependía del llamante (241 limpio → 166 con 300 frames). La guarda va **en dos puntos con un solo número** porque anidar tiene dos caras que no cuentan lo mismo —`Parser.nivel` para lo que le cuesta frames y `Checker.check` con `expr_depth` para la cadena de nodos del AST, que una suma izquierda construye en un bucle sin bajarle ni un frame al parser—, y las cuatro caras llegan al **mismo nivel 64** con conteos de fuente distintos (63 pares, 64 prefijos, 64 términos, 63 términos con clon: C1). Los seis casos `449`–`454` fijan los dos bordes, `tests/test_depth.py` ejerce el sabotaje en las dos direcciones, y la sonda `tools/z2_guard_probe.py` (C1–C8) sella el estado después: población sin rozar (8 sobre 154), precio de la forma más cara 716 frames de 999 con llamantes reales de 6 y 10, y el clon ya inalcanzable. **Lo que queda dicho sin adornos:** de las tres salidas del preview se hizo la (a); quitar la recursión de enmedio y envolver las cinco bajadas de gate fuera de `harness.intento` **no se hicieron**. Y la cota no borraba el muro: con 300 frames del llamante, el fuente del tope legal seguía muriendo por `RecursionError` (C8). **Corregido el 2026-11-12 (Z2-b):** el paquete reserva su propia pila contada desde el llamante y el tope legal baja con 0, 300 y 3 000 frames encima (`docs/decisions/Z2B_PILA_PROPIA.md`, P1–P7 de `evidence/z2_pila/run_2026-11-12T024856Z.json`); medido hasta 3 000, no demostrado para cualquier pila |
| Z3 (¿el anidamiento de sentencias de control tiene cota?) | **cerrada el 2026-11-12: 64 niveles, `SPEC_LIMIT`** | La regla está en §7. `evidence/z2_pila/run_2026-11-12T042036Z.json` (P8–P12); `455`–`458`; `docs/decisions/Z3_MAX_STMT_DEPTH.md` |
| **[D-new]** `for` sobre `str` (N1) | **cerrada el 2026-11-01: adoptada, por caso y por texto** | §4.4 tiene la regla escrita (lugar de `str` ⇒ `len(s)` vueltas, variable `u8` copia, cota = longitud del valor y no la capacidad) y tres casos con su gemelo: `444_for_sobre_str` (22/22), `445_for_str_pelado_stdin` (27/27, N1 × V6 con el `str` pelado) y `446_for_copia_str` (22/22, copia sin alias); trazas `stmt` e IR podada idénticas y `features_of` sin átomo nuevo. La población del corpus pasa de 43 a 46 casos y la del gate de 213 a 216. Decisión: `docs/decisions/N1_FOR_SOBRE_STR.md` |
| **[D-new]** diagonal `0.5` de M4 (N2) | **cerrado por caso: `443`** | `programs/conformance_v0.5/443_m4_modulo_v04/` (raíz `0.5` + módulo `0.4` ⇒ `INVALID_PROGRAM(VERSION_MISMATCH)`), con sus dos controles medidos en el README del directorio: `0.5/0.5` con los mismos archivos da `HALTED` `return 2` en 4 pasos —lo único defectuoso es la cabecera— y `0.4/0.5` da `VERSION_MISMATCH`, o sea que la regla sigue siendo simétrica. Alta el 2026-11-01; la población del corpus pasa de 42 a 43 casos |
| **[D-new]** el `let` sin anotación (N3) | **cerrado por texto** | escrito en §4.1 como excepción acotada al `let` con anotación de CORE §4: solo el `let x` sintético del `for`, y toma el tipo del **elemento** (rama `A.Let` de `Checker.stmt`). No es inferencia general, medido: `let x = 1;` es `SYNTAX` con `0.4` y con `0.5`. Las cuatro formas están en la sonda §3 (`let_anotacion`) con sus tres sabotajes |
| congelar | **revisado el 2026-11-12: falta solo la aprobación** | Lo que el borrador pedía, punto por punto. (1) **`expected` que se superan: ninguno nuevo.** El único caso que afirmaba algo que v0.5 vuelve falso es `322_header_v05` (v0.4), y ya está en `programs/conformance_v0.4/SUPERSEDED.json` desde que se implementó V6; ningún caso de `conformance_v0.5/` afirma que `isyco 0.6` sea `SYNTAX` —eso lo fija `tests/test_versions.py`—, así que congelar no deja ningún `expected` por superar. (2) **Gate F2.4**, los seis ítems de la propuesta §5: pasos de los gemelos (`PASOS_EXIGIDOS`), capacidades (V1/V2 sin átomo nuevo), cinco backends con sus tres sabotajes están en los recibos del lote de 228 y en las decisiones de `docs/decisions/`. Los ítems 4 y 6 no tenían recibo en su forma literal y se midieron el 2026-11-12 (`tools/v05_gate_f24_probe.py` → `evidence/v05_gate_f24/run_2026-11-12T151303Z.json`, `RELEASE_GATE` sobre `1e31abc`): la criba recabezada a `0.5` da en COBOL lo mismo que la referencia y que el `expected` a mano (`25 97 21`), y `does_the_work` sobre un `for` pasa en los cinco backends, cada uno con su sabotaje detectado. **Desviación que queda escrita:** el ítem 4 pedía que la criba «produzca `isy-ir/0.1`» y baja rotulada `isy-ir/0.2`; V7 dejó la etiqueta y derivó la exigencia del contenido (§0, §8). Si eso se acepta o no es parte de lo que se aprueba al congelar. (3) **Texto:** las referencias a líneas de código se cambiaron por símbolos y las cifras de corpus y lote se pusieron al día (58 casos, 228). (4) **Lo que queda es de Danny:** la aprobación explícita —rito de v0.3 y v0.4—, que además ratifica tres números que hoy son propuesta del implementador (`MAX_EXPR_DEPTH = 64`, `MAX_STMT_DEPTH = 64` con el `else if` contando nivel, y 256 clones por definición ya decidido por él). Z1 no bloquea: es política de toolchain. Al aprobar: cambiar el estado a `FROZEN v0.5`, agregar el hash a `spec/SHA256SUMS.txt` y no volver a tocar el archivo |

## 12. Tabla de claims de este borrador

| Claim | Status |
|---|---|
| V1, V2, V6, V6-bis y V7 están implementados, con gate y evidencia | **DEMONSTRATED** — `docs/decisions/` de cada uno, cada uno con su recibo `RELEASE_GATE` sobre su commit |
| V3 y V4 y V5 son texto sobre comportamiento ya medido | **DEMONSTRATED** el comportamiento (`402`–`405` recabezados, `407`, `408` y las aristas de §6); el texto es este documento |
| La versión se decide en un solo sitio | **DEMONSTRATED** — `versions.py`; 13 llamadas a `has()`, cero literales de versión como decisión (`grep` de §0) |
| M4 generalizada: misma versión que la raíz, en las dos direcciones | **DEMONSTRATED** — por sonda en las 8 combinaciones (§0) **y** por corpus: `308_version_mismatch` (raíz `0.4`, módulo `0.3`) y `443_m4_modulo_v04` (raíz `0.5`, módulo `0.4`), alta 2026-11-01 con sus dos controles medidos |
| El `let` sin anotación existe solo como azúcar del `for`, y toma el tipo del elemento | **DEMONSTRATED** — rama `A.Let` de `Checker.stmt`, en un solo sitio; `let x = 1;` es `SYNTAX` con `0.4` y con `0.5` (cuatro formas en la sonda §3), y `402` ejerce el tipo del elemento (`dec<8,2>` sobre `[dec<8,2>; 2]`) |
| `for` sobre un `str` es correcto y barato | **DEMONSTRATED** el 2026-11-01 — era `NOT_DEMONSTRATED` porque ningún caso lo fijaba; ahora son `444`–`446` con sus gemelos (22/27/22 pasos, trazas e IR iguales, ninguna capacidad nueva) y la regla escrita en §4.4 |
| Ningún programa `0.1`–`0.4` cambia de resultado, schema ni traza | **DEMONSTRATED** — §9 (recabezados, brazo viejo FIEL en 118 módulos, gate de backends sin diferencias) |
| Los cinco backends ejecutan el corpus v0.5 con sus capacidades declaradas | **DEMONSTRATED** para los casos que no piden `str`/`struct`/`emit_array`; COBOL responde `UNSUPPORTED` nombrando la capacidad que falta, medido en `tools/v7_capability_probe.py` |
| P4 (límite de especializaciones) tiene número y error | **DEMONSTRATED** el 2026-11-02 — era `NOT_DEMONSTRATED` a propósito porque la cota es decisión. Regla fijada por `447`/`448` en el gate de 218, por los nueve tests de `tests/test_specialize.py::TopePorDefinicion` (255 y 256 legales, 257 `SPEC_LIMIT`, conteo por definición y no por programa) y por dos sabotajes en `tests/test_reference.py`. **No** está demostrado que 256 sea el óptimo: lo que la sonda mide es la población con la que se decidió (2 por definición sin los casos de tope) y el techo del toolchain, que no coincide — ver Z1 |
| Z2 (techo de profundidad de expresión) tiene número, error y dos guardas | **DEMONSTRATED** el 2026-11-03 — era la fila `NOT_DEMONSTRATED` del preview: había techo medido pero nada lo nombraba. Ahora `ast.MAX_EXPR_DEPTH = 64` se ejercita en `Parser.nivel` y en `Checker.check` (`expr_depth`), el nivel 65 es `SPEC_LIMIT` antes de la IR, y `449`–`454` fijan los dos bordes de las tres caras del corpus. **No** está demostrado que 64 sea el óptimo, y C8 de `tools/z2_guard_probe.py` midió en contra que la cota garantizara cabida en cualquier pila; eso lo cerró Z2-b el 2026-11-12 (fila siguiente) |
| Z2-b: lo legal no depende de la pila del llamante | **DEMONSTRATED** hasta 3 000 frames del llamante — `isyco/pila.py`, P1–P7 de `evidence/z2_pila/run_2026-11-12T024856Z.json` y `tests/test_depth.py::LoLegalCabe`. **NOT_DEMONSTRATED** para cualquier pila, y que 32 frames por nivel basten para toda forma de la gramática: es holgura medida del anfitrión de referencia, no norma |
| Z3 (anidamiento de sentencias de control) tiene número, error y dos guardas | **DEMONSTRATED** el 2026-11-12 — `ast.MAX_STMT_DEPTH = 64` en `Parser.control` y `Checker.check` (`stmt_depth`), nivel 65 `SPEC_LIMIT` antes de la IR, `455`–`458` en los cinco backends, P8–P12 de `evidence/z2_pila/run_2026-11-12T042036Z.json`. **NOT_DEMONSTRATED**: que 64 sea el óptimo, que nadie necesite una cadena `else if` de 65 ramas, y que los binarios de los backends aguanten la recursión del peor programa legal (se midieron la referencia y el intérprete de IR) |
| El corpus v0.5 está dentro del gate de release | **DEMONSTRATED** — el lote más reciente, `evidence/backends/gate_2026-11-12T042934Z.json` (`verdict=PASS`, 228 casos, `git_head=1cb56ce`), cotejado hoja por hoja contra el de 224 sin bajas ni hojas de resultado distintas (`evidence/lotes/run_2026-11-12T150933Z.json`); la entrada original fue `gate_2026-11-01T015245Z.json` (`verdict=PASS`, `git_head=57f38bc`, árbol de código limpio) y sigue válida para su población |
| Las aristas que el corpus no fija están medidas, no en prosa | **DEMONSTRATED** por sonda — `tools/v05_spec_probe.py`: M4 en 8 combinaciones (§0), léxico de V3 en 4 (§2), el `let` sin anotación en 4 formas (§4.1), 11 formas del iterando (§4.3), cuatro programas a forma constante y su control de forma (§4.4 y §7), P3 sobre `411`/`417`/`420` (§11). Sello `evidence/v05_spec/run_20261101T153344Z.json` (sha `067fbf1b…`, `RELEASE_GATE` sobre `a4ef362`, árbol de código limpio); la primera versión, sin la matriz del `let`, es `run_20261101T043007Z.json` (sha `ad8d7c29…`, `RELEASE_GATE` sobre `a9a17bc`) y las cinco matrices comunes dan **byte a byte iguales** al comparar los dos `.txt`; un PASS con el árbol sucio se registraría como `EVIDENCE_ONLY` |
