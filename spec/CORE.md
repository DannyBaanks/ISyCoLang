# ISyCoLang — Semántica del core v0.1

**Estado:** `DRAFT` (fase F1). Pasa a `FROZEN v0.1` cuando Danny revise las
decisiones abiertas de §13. Después de congelada, cualquier cambio es un
documento `CORE_v0.2.md`, nunca una edición silenciosa.

Esta spec es **normativa** para el intérprete de referencia (F2) y para todo
backend. Si un backend y esta spec no coinciden, el backend está mal. Si la spec
no dice algo, ese comportamiento es `INVALID_PROGRAM` o no está soportado; nunca
"lo que haga el backend".

---

## 1. Principios de diseño de v0.1

1. **Pequeño:** sin heap, sin punteros, sin strings, sin flotantes, sin
   closures ni genéricos. Lo que quede fuera se agrega en versiones posteriores
   solo si hay evidencia de que hace falta.
2. **Sin aliasing:** todos los valores, incluidos los arreglos, se pasan y
   asignan **por copia**. Así, los conjuntos de lectura y escritura de cada
   función se conocen estáticamente (base para F9 dataflow).
3. **Numéricos por contrato:** cada tipo numérico declara cómo se comporta en el
   límite (overflow, redondeo). No existe "el entero de la máquina".
4. **Determinista:** mismo programa + misma entrada + mismos límites ⇒ mismo
   resultado y misma traza, byte a byte.
5. **Todo error tiene nombre:** no hay comportamiento indefinido.

---

## 2. Formato canónico del archivo

| propiedad | valor |
|---|---|
| extensión | `.isy` |
| encoding | UTF-8, sin BOM; fin de línea LF (`CRLF` ⇒ `INVALID_PROGRAM(ENCODING)`) |
| identificadores | ASCII: `[A-Za-z_][A-Za-z0-9_]*` |
| comentarios | `#` hasta fin de línea |
| cabecera | la primera línea no vacía y no comentario debe ser `isyco 0.1` |
| unidad | un archivo = un programa; debe definir `fn main` |
| identidad | `program_sha256` = SHA-256 de los bytes del archivo |

### 2.1 Gramática (EBNF)

```ebnf
file        = header { fn_decl } ;
header      = "isyco" "0.1" ;

fn_decl     = "fn" IDENT "(" [ param { "," param } ] ")" [ "->" type ] [ effects ] block ;
param       = IDENT ":" type ;
effects     = "!" "emit" ;

type        = "bool" | int_type | dec_type | arr_type ;
int_type    = INT_ALIAS | "int" "<" BITS "," SIGN "," OVF ">" ;
INT_ALIAS   = "i8" | "i16" | "i32" | "i64" | "u8" | "u16" | "u32" | "u64" ;
BITS        = "8" | "16" | "32" | "64" ;
SIGN        = "signed" | "unsigned" ;
OVF         = "trap" | "wrap" | "sat" ;
dec_type    = "dec" "<" NAT "," NAT [ "," ROUND ] ">" ;
ROUND       = "half_even" | "half_up" | "down" | "exact" ;
arr_type    = "[" scalar_type ";" NAT "]" ;
scalar_type = "bool" | int_type | dec_type ;

block       = "{" { stmt } "}" ;
stmt        = "let" IDENT ":" type "=" expr ";"
            | lvalue "=" expr ";"
            | "if" expr block [ "else" ( block | if_stmt ) ]
            | "while" expr block
            | "break" ";" | "continue" ";"
            | "return" [ expr ] ";"
            | "emit" expr ";"
            | call ";" ;
if_stmt     = "if" expr block [ "else" ( block | if_stmt ) ] ;
lvalue      = IDENT [ "[" expr "]" ] ;

expr        = or_expr ;
or_expr     = and_expr { "or" and_expr } ;
and_expr    = not_expr { "and" not_expr } ;
not_expr    = "not" not_expr | cmp_expr ;
cmp_expr    = add_expr [ CMP add_expr ] ;            (* no asociativo *)
CMP         = "==" | "!=" | "<" | "<=" | ">" | ">=" ;
add_expr    = mul_expr { ( "+" | "-" ) mul_expr } ;
mul_expr    = unary { ( "*" | "/" | "%" ) unary } ;
unary       = "-" unary | postfix ;
postfix     = primary { "[" expr "]" | "as" type } ;
primary     = INT_LIT | DEC_LIT | "true" | "false" | IDENT | call
            | "(" expr ")" | "[" expr { "," expr } "]" | "[" expr ";" NAT "]" ;
call        = IDENT "(" [ expr { "," expr } ] ")" ;

INT_LIT     = DIGIT { DIGIT | "_" } ;
DEC_LIT     = DIGIT { DIGIT } "." DIGIT { DIGIT } ;
```

Palabras reservadas: `isyco fn let if else while break continue return emit
and or not true false as bool int dec signed unsigned trap wrap sat half_even
half_up down exact` y los alias `i8 … u64`. El carácter `@` queda reservado
para anotaciones de F6 (`@numeric`, `@backend`); en v0.1 su presencia es
`INVALID_PROGRAM(RESERVED)`.

---

## 3. Tipos y valores

### 3.1 `bool`

`true`, `false`. Operadores `and`, `or` (cortocircuito, izquierda a derecha),
`not`, `==`, `!=`. No hay conversión con enteros.

### 3.2 Enteros `int<N, signo, ovf>`

- Rango: con signo `[-2^(N-1), 2^(N-1)-1]` (complemento a dos); sin signo `[0, 2^N-1]`.
- Los alias `i8 … u64` son `int<N, …, trap>`.
- El modo `ovf` define qué pasa cuando el **resultado matemático exacto** de una
  operación cae fuera del rango:

| ovf | resultado |
|---|---|
| `trap` | `ERROR(OVERFLOW)` |
| `wrap` | el resultado exacto módulo 2^N, reinterpretado en el rango |
| `sat` | el extremo del rango más cercano |

Operaciones (ambos operandos del **mismo tipo**; si no, `INVALID_PROGRAM(TYPE_MISMATCH)`):

| op | semántica exacta |
|---|---|
| `a + b`, `a - b`, `a * b` | resultado matemático exacto, luego regla `ovf` |
| `a / b` | cociente **truncado hacia cero**; `b = 0` ⇒ `ERROR(DIV_ZERO)` en todos los modos; `MIN / -1` aplica la regla `ovf` |
| `a % b` | `a - (a / b) * b` (signo del dividendo); `b = 0` ⇒ `ERROR(DIV_ZERO)`; `MIN % -1 = 0` |
| `-a` | `0 - a` con la regla `ovf` (en sin signo, `-a` con `a ≠ 0` es overflow) |
| comparaciones | orden numérico, resultado `bool` |

### 3.3 Decimales `dec<p, s, redondeo>`

- Valor = entero `m` escalado: `m / 10^s`, con `|m| ≤ 10^p - 1`.
- Restricciones: `1 ≤ p ≤ 18`, `0 ≤ s ≤ p`; si no, `INVALID_PROGRAM(DEC_PARAMS)`.
  (18 dígitos caben en un `i64`; ver decisión D3.)
- El redondeo por defecto es `half_even`.
- **Regla de una sola rondeada:** toda operación calcula el resultado racional
  exacto y redondea **una vez** a la escala `s` con el modo del tipo:

| modo | regla |
|---|---|
| `half_even` | al más cercano; empate al dígito par |
| `half_up` | al más cercano; empate alejándose de cero |
| `down` | truncar hacia cero |
| `exact` | si hace falta redondear ⇒ `ERROR(INEXACT)` |

- Si el resultado redondeado tiene más de `p` dígitos ⇒ `ERROR(OVERFLOW)`.
  Los decimales **siempre** atrapan el overflow; no hay `wrap` ni `sat`.
- Operaciones: `+ - * /` y comparaciones entre operandos del mismo tipo; `/`
  entre cero ⇒ `ERROR(DIV_ZERO)`. No hay `%` decimal en v0.1.

### 3.4 Arreglos `[T; N]`

- `T` escalar, `1 ≤ N ≤ 65536`. Longitud fija y parte del tipo.
- Índice de cualquier tipo entero; fuera de `[0, N-1]` ⇒ `ERROR(INDEX_OUT_OF_BOUNDS)`.
- Literales: `[e1, …, eN]` (exactamente N elementos) o `[e; N]`.
- Asignación y paso de parámetros **por copia**. No hay `==` entre arreglos.

### 3.5 Literales

Un literal no tiene tipo propio: **toma el tipo esperado** por el contexto
(anotación del `let`, parámetro, el otro operando, tipo de retorno, destino de
`as`). Sin contexto ⇒ `INVALID_PROGRAM(AMBIGUOUS_LITERAL)`. Si no cabe en el
tipo ⇒ `INVALID_PROGRAM(LITERAL_OUT_OF_RANGE)`. Un `DEC_LIT` con más decimales
que `s` ⇒ `INVALID_PROGRAM(LITERAL_SCALE)`: los literales nunca se redondean
en silencio. `DEC_LIT` en contexto entero ⇒ `TYPE_MISMATCH`.

### 3.6 Conversiones `e as T`

Solo explícitas. No hay conversiones implícitas.

| de → a | regla |
|---|---|
| int → int | valor exacto; fuera de rango ⇒ regla `ovf` del tipo destino |
| int → dec | exacto; más de `p` dígitos ⇒ `ERROR(OVERFLOW)` |
| dec → int | trunca hacia cero, luego regla `ovf` del destino |
| dec → dec | reescala con el modo de redondeo del **destino**, luego chequeo de `p` |
| con `bool` o arreglos | `INVALID_PROGRAM(BAD_CAST)` |

---

## 4. Estado, nombres y alcance

- **Estado de ejecución** = pila de marcos de llamada (cada uno con sus
  variables locales), la secuencia de salida y los contadores de límites. No
  hay variables globales ni memoria compartida.
- `let` declara una variable mutable visible hasta el fin de su bloque.
  Toda variable se declara con tipo e inicializador.
- Redeclarar un nombre visible en la misma función ⇒
  `INVALID_PROGRAM(DUPLICATE_NAME)`, aunque esté en un bloque interno (sin shadowing).
- Usar un nombre no declarado ⇒ `INVALID_PROGRAM(UNKNOWN_NAME)`.

## 5. Control

- **Quién lleva el PC:** el intérprete, siguiendo la estructura de bloques. No
  hay `goto` ni saltos computados; todo flujo es `if`, `while`, `break`,
  `continue`, `return` y llamadas.
- `if` y `while` exigen una condición `bool`.
- `break`/`continue` fuera de un `while` ⇒ `INVALID_PROGRAM(BAD_LOOP_CONTROL)`.
- Una función con tipo de retorno debe retornar en **todos** los caminos,
  comprobado de forma conservadora (un `while` se considera que puede no
  ejecutarse) ⇒ si no, `INVALID_PROGRAM(MISSING_RETURN)`.

## 6. Funciones, llamadas y efectos

- Llamada por valor; argumentos evaluados de izquierda a derecha.
- Se permite recursión, limitada por `max_call_depth` (§8).
- Sobrecarga y funciones con nombre repetido ⇒ `INVALID_PROGRAM(DUPLICATE_NAME)`.
- **Efectos:** el único efecto de v0.1 es la salida, `emit`. Una función que
  emite, o que llama a una función que emite, debe declarar `!emit`; si no,
  `INVALID_PROGRAM(UNDECLARED_EFFECT)`.
- Una función sin `!emit` es **pura**: su resultado depende solo de sus
  argumentos. Por eso un backend puede reordenarla, memoizarla o ejecutarla en
  paralelo sin cambiar el resultado observable. Es la condición que F9 necesita.

## 7. Orden de evaluación

Estricto, de **izquierda a derecha**, en todas las expresiones y argumentos.
En `a[i] = e` se evalúa primero `i` y después `e`. El primer error que ocurra en
ese orden es el que se reporta. Esto fija qué salida parcial existe cuando hay
error (§9).

## 8. Límites

Los límites son parte del contrato de ejecución y se registran en el resultado.

| límite | default | cuenta |
|---|---|---|
| `max_steps` | 1 000 000 | +1 por sentencia ejecutada, por evaluación de condición de `while` y por llamada |
| `max_call_depth` | 256 | profundidad de la pila de llamadas (`main` = 1) |
| `max_emits` | 100 000 | número de `emit` |
| `timeout_ms` | 60 000 | tiempo de reloj del host; **no** es semántica |

Superar un límite ⇒ `LIMIT_REACHED(<límite>)`. Cambiar un límite solo puede
mover un resultado entre `HALTED` y `LIMIT_REACHED`; nunca puede cambiar los
valores calculados. `TIMEOUT` lo reporta el host y no se compara entre backends.

## 9. Terminación y errores

| status | cuándo | código |
|---|---|---|
| `HALTED` | `main` retornó | — |
| `ERROR` | error en ejecución | `OVERFLOW`, `DIV_ZERO`, `INEXACT`, `INDEX_OUT_OF_BOUNDS` |
| `LIMIT_REACHED` | se superó un límite | `max_steps`, `max_call_depth`, `max_emits` |
| `INVALID_PROGRAM` | error de lectura, parseo, tipos o efectos antes de ejecutar | los códigos en mayúsculas de §2–§6, más `SYNTAX`, `ENCODING`, `NO_MAIN`, `BAD_INPUT` |
| `TIMEOUT` | el host cortó por reloj | — |

- Los errores **no se pueden atrapar**: v0.1 no tiene excepciones.
- La salida emitida **antes** de un `ERROR` o `LIMIT_REACHED` forma parte del
  resultado y los backends deben reproducirla igual (decisión D5).
- `INVALID_PROGRAM` nunca produce salida: el programa no empieza a correr.

## 10. Entrada y salida

- **Entrada:** los argumentos de `main`, como un arreglo JSON de **strings**
  canónicos (§10.1), por ejemplo `["12", "3.50", "true", ["1","2","3"]]`. Si el
  número o el tipo no coinciden ⇒ `INVALID_PROGRAM(BAD_INPUT)`. Usar strings
  evita perder precisión con los números de JSON.
- **Salida:** cada `emit e` agrega a la secuencia de salida la forma canónica de
  `e`. `e` debe ser escalar (`emit` de un arreglo ⇒ `TYPE_MISMATCH`).
- **Valor de retorno** de `main`: forma canónica, o `null` si `main` no retorna valor.

### 10.1 Forma canónica de un valor

| tipo | forma |
|---|---|
| bool | `true` / `false` |
| entero | base 10, `-` solo si es negativo, sin ceros a la izquierda, `0` sin signo |
| decimal | base 10 con **exactamente** `s` decimales; `0.00` sin signo; si `s = 0`, sin punto |
| arreglo (solo en entrada) | arreglo JSON de formas canónicas |

### 10.2 Documento de resultado

JSON canónico (claves ordenadas, sin espacios, UTF-8):

```json
{"emits":["3","2","1"],"limits":{"max_call_depth":256,"max_emits":100000,"max_steps":1000000},
 "code":null,"input_sha256":"…","program_sha256":"…","return":null,
 "schema":"isyco.result/0.1","status":"HALTED","steps":17}
```

Dos ejecuciones son **equivalentes** si coinciden `status`, `code`, `emits` y
`return`. `steps` se compara solo entre el intérprete de referencia y sus
reejecuciones: un backend nativo no tiene por qué contar pasos, pero sí debe
reportar `LIMIT_REACHED(max_steps)` exactamente cuando la referencia lo haría,
o declarar ese límite como `UNSUPPORTED`.

## 11. Traza

Una línea JSON canónica por evento, en orden:

```json
{"step":4,"fn":"main","at":"7:5","kind":"assign","name":"n","value":"2"}
```

- `kind` ∈ `enter`, `return`, `assign`, `branch`, `loop_test`, `emit`, `error`, `limit`.
- `at` = `línea:columna` de la sentencia en el archivo.
- Niveles: `none`, `stmt` (este formato) y `full` (añade `locals` antes y
  después). `trace_sha256` = SHA-256 del archivo de traza.
- La traza es la semántica observable de la referencia. Los backends que
  produzcan traza deben producir la **misma**; los que no, lo declaran.

## 12. Las diez preguntas del core (gate F1)

| # | pregunta | respuesta en v0.1 |
|---|---|---|
| 1 | ¿Cómo se representa el estado? | pila de marcos con locales tipadas + secuencia de salida + contadores (§4) |
| 2 | ¿Quién controla el PC? | el intérprete, por estructura de bloques; no hay saltos computados (§5) |
| 3 | ¿Saltos y condiciones? | `if`/`else` con condición `bool` (§5) |
| 4 | ¿Bucles? | `while` + `break`/`continue`, limitado por `max_steps` (§5, §8) |
| 5 | ¿Acceso a memoria? | solo locales y arreglos de tamaño fijo por copia, con índice verificado (§3.4) |
| 6 | ¿Qué es detenerse? | `HALTED` solo cuando `main` retorna; los cortes por límite son otro status (§9) |
| 7 | ¿Errores? | códigos con nombre, no se pueden atrapar, conservan la salida parcial (§9) |
| 8 | ¿Entrada y salida? | argumentos de `main` como strings canónicos; `emit` como único efecto (§10) |
| 9 | ¿Qué garantiza la composición? | funciones por valor con efectos declarados; las puras se pueden reordenar (§6) |
| 10 | ¿Qué pasa si cambia el backend? | nada observable: la equivalencia está definida en §10.2 y la spec manda sobre todos los backends |

## 13. Decisiones abiertas (requieren a Danny)

| id | decisión | propuesta | alternativa |
|---|---|---|---|
| D1 | palabras reservadas | inglés ASCII, neutral para herramientas y backends | español (estilo PITÓN) o capa de alias encima |
| D2 | división entera | truncar hacia cero (C, Rust, Zig, Go, Java, COBOL) | piso (Python) |
| D3 | precisión decimal máxima | `p ≤ 18`, cabe en `i64` | `p ≤ 38` (`i128`; más fiel a COBOL, más caro) |
| D4 | flotantes | fuera de v0.1; IEEE 754 estricto en v0.2 | incluirlos ya |
| D5 | salida parcial al fallar | es observable y se compara | descartarla al fallar |
| D6 | lenguaje del intérprete de referencia | Python, legible y con `fractions`/`decimal` como oráculo | Rust o Zig |
| D7 | recursión | permitida con `max_call_depth` | prohibida en v0.1 |

## 14. Ejemplo ilustrativo (no forma parte del corpus)

```text
isyco 0.1

# Interés simple redondeado al centavo, con contrato decimal explícito.
fn interes(capital: dec<12,2>, tasa: dec<6,4>, dias: i32) -> dec<12,2> {
    let anual: dec<12,2> = capital * (tasa as dec<12,2>);
    return anual * (dias as dec<12,2>) / 365.00;
}

fn main(capital: dec<12,2>, tasa: dec<6,4>) !emit {
    let d: i32 = 30;
    while d <= 90 {
        emit interes(capital, tasa, d);
        d = d + 30;
    }
}
```

Este ejemplo deja ver un problema que la spec tiene que atrapar:
`tasa as dec<12,2>` redondea la tasa a 2 decimales **antes** de multiplicar
(0.0525 se vuelve 0.05). Es correcto según §3.6, y por eso las conversiones son
explícitas: el redondeo queda escrito en el programa en lugar de esconderse. El
corpus de F2 debe incluir este caso.
