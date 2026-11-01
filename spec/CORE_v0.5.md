# ISyCoLang — Semántica del core v0.5

**Estado:** `BORRADOR` (2026-11-01). **No congelada**: congelar es decisión de Danny,
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
  fuera de `versions.py` son *defaults*, `ast.py:221` y `parser.py:22`.

  | sitio | qué habilita |
  |---|---|
  | `lexer.py:67,69,71` | palabras de v0.3, `import`/`pub`, `for` |
  | `parser.py:30,34,38` | sintaxis de v0.3, de módulos, de v0.5 |
  | `parser.py:15` | el conjunto de cabeceras admitidas (`SUPPORTED_VERSIONS`) |
  | `parser.py:418` | enteros/decimales polimórficos (v0.2) |
  | `checker.py:69,70,289` | reglas de tipos v0.3, reglas v0.5, hint polimórfico |
  | `ir.py:229` | número de schema que el contenedor puede expresar |
  | `__main__.py:51`, `modules.py:34` | leer el programa como `Bundle` (carpeta + imports) |

- **La IR no cambia.** `isy-ir/0.1` y `isy-ir/0.2` son las únicas formas; V1, V2, V4,
  V5 y V6 son frontend. Lo que decide a cuál se baja es el **contenido** (§8), no la
  cabecera — V7 revierte exactamente esa dependencia, que la propuesta §7 y el
  dogfood §7 señalaron como defecto.
- **M4 se generaliza.** v0.4 §1 decía «todos los módulos son `isyco 0.4`». La regla
  es ahora: **todo módulo de un programa tiene la misma versión que la raíz**; una
  diferencia ⇒ `INVALID_PROGRAM(VERSION_MISMATCH)` (`isyco/modules.py:48`). Medido en
  las ocho combinaciones de raíz ∈ {0.4, 0.5} × módulo ∈ {0.2, 0.3, 0.4, 0.5}: solo
  las diagonales `0.4/0.4` y `0.5/0.5` ejecutan (`return 7`, `HALTED`); las seis
  restantes son `VERSION_MISMATCH`. Mezclar familias quedaría sin respuesta sobre qué
  semántica gana, así que se rechaza por ambos lados. **Falta el caso de corpus**
  que fije la diagonal `0.5` y los dos cruces con raíz `0.5` (§10).

## 1. Decisiones

| id | qué admite | dónde vive la regla | documento de medición |
|---|---|---|---|
| V1 | `len(a)` de un arreglo | `checker.py:326-334` (tipo) y `checker.py:37,55,103` (resolución) | `docs/decisions/V1_LEN_ARREGLO.md` |
| V2 | `for x in a { … }` | `lexer.py:19` y `lexer.py:71-72` (reserva), `parser.py:267-268` (despacho), `parser.py:317-351` (expansión), `parser.py:245-246` (aplanado), `checker.py:204-209` (el `let` sintético) | `docs/decisions/V2_FOR_AZUCAR.md` |
| V3 | `in` sigue sin reservarse; `for` solo desde `0.5` | `lexer.py:19` (`KEYWORDS_V05`) | idem V2, §Control anti-fake |
| V4 | el parámetro es una local mutable del marco | `CORE.md` §4 (esta sección lo pone por escrito) | §5 abajo |
| V5 | `qname` como tipo de elemento de arreglo | v0.4 §3 (EBNF) | §6 abajo |
| V6 | `str` sin capacidad en parámetros | `types.py:78`, `specialize.py:31,49` | `docs/decisions/V6_CONTEXTUAL_STR.md` |
| V6-bis | `str` sin capacidad en el retorno | idem (la clave agrega `r<n>`) | `docs/decisions/V6B_CONTEXTUAL_RETURN.md` |
| V7 | capacidades derivadas del contenido | `backends/base.py:97-134` | `docs/decisions/V7_CONTENT_CAPABILITIES.md` |

## 2. Léxico (V3)

- `for` es palabra reservada **solo con cabecera `0.5`**. Con `0.4`,
  `let for: i32 = 5;` sigue siendo legal y corre (`HALTED`, `return 5`); con `0.5` es
  `SYNTAX`. Medido.
- `in` **no se añade nunca a la lista de reservadas**: es un token contextual que
  el parser exige como `IDENT` con el texto `"in"` (`parser.py:329-330`). Con `0.4` y
  con `0.5`, `let in: i32 = 5;` es legal y corre. Reservarla habría cambiado el
  significado de programas existentes y viola la promesa del encabezado.

## 3. V1 — `len` de un arreglo

`len(a)` con `a: [T; N]` devuelve `N` con tipo `i64` (misma familia que `len(s)` de
v0.3 §2.4; no «el tipo del índice»: B7 sigue sin arreglar, §9). La regla tiene dos
mitades y las dos son de frontend:

1. **Chequeo** (`checker.py:326-334`): con familia `v05`, `len` de un `ArrT` es
   `i64`; sin `v05` es `TYPE_MISMATCH` — el `len` de v0.3 es solo de strings.
2. **Resolución** (`static_len`, aplicado en `checker.py:103` después de chequear):
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

(`parser.py:317-351`; la expansión está en el **parser**, no en el lowering, para que
`steps`, límites y trazas queden definidos sin regla nueva. El `-1` es `IntLit`, no
`Unary` — CORE v0.2 C2 ya define `-1` como un solo literal, y construirlo con el operador
dejaba un `{"k": "neg"}` en la IR que el `while` escrito a mano no tiene.)

**El `let` sin anotación es una excepción acotada, no inferencia [N3].** CORE §4 exige
anotación en todo `let`, y v0.5 no la afloja: la única sentencia del lenguaje que puede
llevar `let` sin tipo escrito es el `let x = <lugar>[foridx{n}];` que inyecta el azúcar de
arriba. La regla normativa es «el `let` sintético del `for` toma el tipo del
**elemento** del iterando», y vive en un solo sitio: `checker.py:205-209` — si `Let.type`
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
(`parser.py:245-246` aplana). Eso es seguro porque `foridx{n}` no puede aparecer en un
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
| cabecera `0.4` | `INVALID_PROGRAM(SYNTAX)` — `for` es reservada solo desde `0.5` (V3) |
| `s[7]` con `str<8> = "hola"` | `ERROR(INDEX_OUT_OF_BOUNDS)` a los 3 pasos — la regla de rango es la de v0.3 §2.4, y el `while` gemelo falla igual |

Por qué se adopta y no se rechaza: el desugaring vive en el parser (`parser.py:317-351`) y no
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

`fresh_index` (`parser.py:353`) produce `foridx{n}` eligiendo `n` fuera del conjunto
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
fija `23`, `38` y `20` como número (`PASOS_EXIGIDOS` en `tests/test_v05_core.py:105`) y
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
retorno>])` hace una copia del `fn` con los tipos ya concretos (`specialize.py:49`) y
reescribe la llamada al nombre de la copia (`spec_name`, `specialize.py:31`). **La
definición pelada nunca se chequea**: lo que se chequea es cada copia, con tipos
corrientes de v0.3. Ningún backend conoce V6.

- **Sin centinela.** `ContextStrT` (`types.py:78`) es un tipo, no un número: `0`,
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

## 8. V7 — capacidades por contenido, no por etiqueta

Dos preguntas que estaban mezcladas:

| pregunta | dónde vive | qué decide |
|---|---|---|
| `SCHEMA_CAN_EXPRESS` | `module["schema"]` (`ir.py:229`) | qué puede representar el contenedor |
| `PROGRAM_REQUIRES` | `features_of(módulo)` (`backends/base.py:97`) | qué exige **este** programa |

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
`isyco/backends/cobol.py:907` en vez de inventar una capacidad «COBOL no sabe llamadas
void». El defecto era previo y alcanzable fuera de v0.5 (canario `439`, `isyco 0.1`).

## 9. Corpus, gate y no regresión

- `programs/conformance_v0.5/` tiene **46 casos** (401–446, 42 de archivo suelto y 4
  directorios de módulos), con los `expected` escritos a mano entre el 2026-10-30 y el
  2026-11-01, **antes** de tocar `isyco/` en cada decisión. El directorio está en
  `CORPORA` (`isyco/conformance.py:13`) desde `57f38bc`, así que el gate de backends pasó
  de 170 a **212** casos; `443` (alta 2026-11-01) sube la población del gate a **213** y
  `444`–`446` (N1, alta el mismo día) a **216**. Los tres nuevos van con su `while` gemelo
  en `gemelos/`, que `load_corpus` no cuenta (`isyco/conformance.py:17-41`).
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

## 10. Fuera de alcance de v0.5

| bloqueo | por qué no entra |
|---|---|
| B4 estado entre llamadas / variables de unidad | toca CORE §1.2 (sin aliasing) y §4 (sin globales); el work-around existe y está medido |
| B5 efectos de lectura (reloj, ambiente, stdin, archivos) | es una decisión de alcance del lenguaje, merece su propio documento |
| B7 anchos enteros mixtos | regla de coerción sobre 6 tipos con `ovf` distinto; con V1 el dolor medido desaparece |
| B8 texto decimal no canónico (`"199.9"` ⇒ `BAD_FORMAT`) | cambiar `ERROR(BAD_FORMAT)` es cambiar la forma canónica de v0.3 §10.1 y los cinco backends; va a v0.6 |
| B9 valor ausente / arreglos que crecen | `null`/optional exige forma canónica de entrada y salida; los arreglos dinámicos rompen §1.1 (sin heap) |
| aritmética de capacidad `str<N+k>` | **no hace falta**: `str<N> + str<M>` ya suma capacidades (`str_binary`, `checker.py:435-448`: con tipo esperado devuelve ese tipo; sin él, `str<min(N+M, MAX_STR)>`) y con contexto la capacidad esperada, así que `pad` corre hoy en los cinco backends |
| `for` sobre expresiones, literales o índices | §4.3; un literal sin tipo esperado es `AMBIGUOUS_LITERAL` |
| métodos (`a.len`), reexportar, alias de import, importar nombres sueltos | v0.3 §9 y v0.4 §8 los siguen excluyendo |

## 11. Preguntas abiertas y qué falta antes de congelar

| id | estado | qué falta |
|---|---|---|
| P1 (`at` de las sentencias sintéticas del `for`) | **cerrado por medición** | — (es la línea del `for`; el gate compara trazas salvos `at`) |
| P2 (`for` sobre un literal de arreglo) | **cerrado: no** | — (`SYNTAX`, §4.3) |
| P3 (nombre de la especialización y su efecto en `program_sha256` y las trazas) | **cerrado por medición** | `program_sha256` es el SHA del archivo principal (v0.4 §6 P6) y **no se mueve**: medido en `411`, `417` y `420`, los tres iguales al `sha256sum` del `.isy`. Lo que sí cambia es la traza: `411` muestra `main`, `pad.2`, `pad.7` y nunca `pad` a secas — la especialización es visible en el nombre, no en la identidad. Los nombres viajan por la codificación inyectiva de `fn_ident` (longitud prefijada), que no colisiona con un nombre de usuario |
| P4 (cota de especializaciones por programa) | **abierto a propósito, con la base sellada** | falta la decisión (el número y su nombre), no la medición. `tools/v05_p4_probe.py` recalcula el censo desde `Checker.specs` sobre la población del gate y mide la forma: **32 clones** en 18 de los 43 casos (26 V6 + 6 V6-bis), 4 por programa, 2 por definición **dentro de un programa** pero 7 de `doble` **en el corpus**; una ranura con K anchos da K clones, dos ranuras W², tres W³, y 20 sitios con el mismo ancho dan 1 clon. Sin techo ni error nombrado hasta 2048 clones: el crecimiento es silencioso. Recibo `evidence/v05_p4/run_20261101T154040Z.json` (`RELEASE_GATE` sobre `2938c01`), que **re-mide** el censo con `443` dentro: mismos 32 clones, mismos 18 programas con clones y las tres curvas byte a byte iguales; `443` aporta 0 clones y pasa a engrosar los 12 casos que rechaza el frontend. La corrida anterior, sobre 42, es `run_20261101T062234Z.json` (`RELEASE_GATE` sobre `52f5564`) y sigue válida para su población |
| **[D-new]** `for` sobre `str` (N1) | **cerrada el 2026-11-01: adoptada, por caso y por texto** | §4.4 tiene la regla escrita (lugar de `str` ⇒ `len(s)` vueltas, variable `u8` copia, cota = longitud del valor y no la capacidad) y tres casos con su gemelo: `444_for_sobre_str` (22/22), `445_for_str_pelado_stdin` (27/27, N1 × V6 con el `str` pelado) y `446_for_copia_str` (22/22, copia sin alias); trazas `stmt` e IR podada idénticas y `features_of` sin átomo nuevo. La población del corpus pasa de 43 a 46 casos y la del gate de 213 a 216. Decisión: `docs/decisions/N1_FOR_SOBRE_STR.md` |
| **[D-new]** diagonal `0.5` de M4 (N2) | **cerrado por caso: `443`** | `programs/conformance_v0.5/443_m4_modulo_v04/` (raíz `0.5` + módulo `0.4` ⇒ `INVALID_PROGRAM(VERSION_MISMATCH)`), con sus dos controles medidos en el README del directorio: `0.5/0.5` con los mismos archivos da `HALTED` `return 2` en 4 pasos —lo único defectuoso es la cabecera— y `0.4/0.5` da `VERSION_MISMATCH`, o sea que la regla sigue siendo simétrica. Alta el 2026-11-01; la población del corpus pasa de 42 a 43 casos |
| **[D-new]** el `let` sin anotación (N3) | **cerrado por texto** | escrito en §4.1 como excepción acotada al `let` con anotación de CORE §4: solo el `let x` sintético del `for`, y toma el tipo del **elemento** (`checker.py:205-209`). No es inferencia general, medido: `let x = 1;` es `SYNTAX` con `0.4` y con `0.5`. Las cuatro formas están en la sonda §3 (`let_anotacion`) con sus tres sabotajes |
| congelar | — | aprobación explícita de Danny (rito de v0.3 y v0.4), agregar `CORE_v0.5.md` a `spec/SHA256SUMS.txt`, y decidir qué `expected` del corpus se superan al congelar (precedente: `SUPERSEDED.json`) |

## 12. Tabla de claims de este borrador

| Claim | Status |
|---|---|
| V1, V2, V6, V6-bis y V7 están implementados, con gate y evidencia | **DEMONSTRATED** — `docs/decisions/` de cada uno, cada uno con su recibo `RELEASE_GATE` sobre su commit |
| V3 y V4 y V5 son texto sobre comportamiento ya medido | **DEMONSTRATED** el comportamiento (`402`–`405` recabezados, `407`, `408` y las aristas de §6); el texto es este documento |
| La versión se decide en un solo sitio | **DEMONSTRATED** — `versions.py`; 13 llamadas a `has()`, cero literales de versión como decisión (`grep` de §0) |
| M4 generalizada: misma versión que la raíz, en las dos direcciones | **DEMONSTRATED** — por sonda en las 8 combinaciones (§0) **y** por corpus: `308_version_mismatch` (raíz `0.4`, módulo `0.3`) y `443_m4_modulo_v04` (raíz `0.5`, módulo `0.4`), alta 2026-11-01 con sus dos controles medidos |
| El `let` sin anotación existe solo como azúcar del `for`, y toma el tipo del elemento | **DEMONSTRATED** — `checker.py:205-209` en un solo sitio; `let x = 1;` es `SYNTAX` con `0.4` y con `0.5` (cuatro formas en la sonda §3), y `402` ejerce el tipo del elemento (`dec<8,2>` sobre `[dec<8,2>; 2]`) |
| `for` sobre un `str` es correcto y barato | **DEMONSTRATED** el 2026-11-01 — era `NOT_DEMONSTRATED` porque ningún caso lo fijaba; ahora son `444`–`446` con sus gemelos (22/27/22 pasos, trazas e IR iguales, ninguna capacidad nueva) y la regla escrita en §4.4 |
| Ningún programa `0.1`–`0.4` cambia de resultado, schema ni traza | **DEMONSTRATED** — §9 (recabezados, brazo viejo FIEL en 118 módulos, gate de backends sin diferencias) |
| Los cinco backends ejecutan el corpus v0.5 con sus capacidades declaradas | **DEMONSTRATED** para los casos que no piden `str`/`struct`/`emit_array`; COBOL responde `UNSUPPORTED` nombrando la capacidad que falta, medido en `tools/v7_capability_probe.py` |
| P4 (límite de especializaciones) tiene número | **NOT_DEMONSTRATED** a propósito — el censo y la forma del crecimiento están medidos y sellados (`evidence/v05_p4/run_20261101T062234Z.json`); la cota es decisión de Danny |
| El corpus v0.5 está dentro del gate de release | **DEMONSTRATED** — `gate_2026-11-01T015245Z.json` (`verdict=PASS`, `git_head=57f38bc`, árbol de código limpio) |
| Las aristas que el corpus no fija están medidas, no en prosa | **DEMONSTRATED** por sonda — `tools/v05_spec_probe.py`: M4 en 8 combinaciones (§0), léxico de V3 en 4 (§2), el `let` sin anotación en 4 formas (§4.1), 11 formas del iterando (§4.3), cuatro programas a forma constante y su control de forma (§4.4 y §7), P3 sobre `411`/`417`/`420` (§11). Sello `evidence/v05_spec/run_20261101T153344Z.json` (sha `067fbf1b…`, `RELEASE_GATE` sobre `a4ef362`, árbol de código limpio); la primera versión, sin la matriz del `let`, es `run_20261101T043007Z.json` (sha `ad8d7c29…`, `RELEASE_GATE` sobre `a9a17bc`) y las cinco matrices comunes dan **byte a byte iguales** al comparar los dos `.txt`; un PASS con el árbol sucio se registraría como `EVIDENCE_ONLY` |
