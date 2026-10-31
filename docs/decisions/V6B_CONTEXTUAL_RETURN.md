# Decisión V6-bis — `str` sin capacidad en el retorno (2026-10-31)

**Decisión:** la misma regla de V6, aplicada a la otra orilla. El `-> str` pelado no es
una cuerda infinita: es una capacidad **diferida que fija el contexto del llamado**. Se
especializa en el frontend, antes de la IR; ningún backend la conoce.

Nace de la fila §3 de `spec/CORE_v0.5_propuesta.md` y de la corrección §8: el dogfood
`06_biblioteca_texto.isy` resuelve los parámetros con V6, pero `empieza_con(s: str) -> bool`
no cubre `recorta(s: str) -> str` —una función que **devuelve** texto reutilizable a dos
anchos distintos obliga hoy a reescribir la definición entera.

## Qué se acepta y qué se rechaza

- `fn doble(s: str) -> str` es legal **solo con `isyco 0.5`** y **solo en el retorno**.
  Con cabecera 0.4 sigue siendo `SYNTAX` (`437`), y `str` pelado en un `let`, un `cast`,
  un arreglo o un campo de struct sigue siendo `SYNTAX` (`425`, heredado de V6).
- La capacidad del retorno es la **esperada en la posición de llamada**: un
  `let r: str<8> = doble(x)` fija `str<8>`; un `as str<8>` fija `str<8>`; otro retorno
  pelado transmite la suya (`435`: `eco` resuelve `str<8>` desde el `let` del `main` y
  se la pasa a `doble`).
- Sin expectativa no hay ancho **por defecto**. `doble("ab");` como sentencia (`432`) y
  `emit doble("ab");` (`433`) son `TYPE_MISMATCH` en el llamado. No se inventa `MAX_STR`,
  ni `None`, ni `0`, ni `65535`: la regla anti-centinela de V6 sigue intacta.
- `main` no tiene sitio de llamada, así que `fn main() -> str` se rechaza (`436`), igual
  que su parámetro pelado (`424`).

## Fail-closed en las dos direcciones

Es la regla pedida: `required_width <= expected_width → aprovecha`, `required_width >
expected_width → FAIL`, y **nunca truncate and continue**.

- Estático: `fn doble(s: str) -> str { let r: str<16> = s + s; return r; }` llamado con
  expectativa `str<8>` es `TYPE_MISMATCH` (`431`). Se rechaza antes de ejecutar, porque
  la copia `doble.8.r8` no puede construir una cadena de 16 para entregar 8.
- Dinámico: `return s + s` sin `let` intermedio, con expectativa `str<4>` y dos bytes de
  entrada, desborda al ejecutar → `ERROR(OVERFLOW)` y **cero `emits`** (`430`). El
  desborde no se recorta.
- Lo que sí pasa es el ensanchamiento ordinario de v0.3 (`str<4>` dentro de una
  expectativa `str<8>`): ninguna regla nueva.

## La clave lleva las dos orillas

`spec_name(nombre, anchos_de_parámetros, ancho_de_retorno)` añade un segmento `r<n>` al
final, así que la misma definición coexiste en dos resoluciones: `429` produce
`{doble.4.r8, doble.2.r4}` y `435` produce `{eco.4.r8, doble.4.r8}`. Los cuatro formatos
conviven con los identificadores ya codificados por `backends/base.py:fn_ident` (longitud
prefijada, inyectiva). Con retorno pelado pero parámetro fijo no hay ambigüedad posible:
el segmento `r` aparece solo si el retorno estaba pelado (`438`: `doble.8.r16`).

## Gemelo: el azúcar no añade pasos **si la forma es la misma**

`429` coincide con su gemelo `isyco 0.4` —dos definiciones `doble4`/`doble2` con anchos
escritos a mano, y el **mismo** `let` + `emit`— en status, code, emits, return y `steps`
(9 y 9): `tests/test_specialize.py:RetornoPelado.test_el_gemelo_escrito_a_mano_cuesta_dos_funciones`.

La medición tuvo una trampa que vale la pena dejar escrita: el primer gemelo se escribió
como `emit doble4("abcd");` —una sentencia menos por valor— y daba **7 pasos contra 9**.
La diferencia era **la forma del programa** (dos `let` de más), no la especialización. El
gemelo se reescribió con forma idéntica y los pasos coincidieron. La claims se mantiene
exacta: a forma constante, el azúcar añade dos definiciones en el AST y cero pasos en la
ejecución.

## Corpus

`programs/conformance_v0.5/429`–`438`, con los `expected` escritos a mano **antes** de
tocar `isyco/` (rito de `AGENTS.md` §5): cuatro ejecutables (`429` dos expectativas, `430`
`ERROR(OVERFLOW)`, `435` transmisión pelado→pelado, `438` entrada por stdin que fija el
parámetro y un `let` que fija el retorno) y seis rechazos (`431` estático, `432`/`433`
sin expectativa, `434` ciclo expectativa↔parámetro pelado, `436` `main`, `437` cabecera
0.4). El directorio sigue **fuera de `CORPORA`** hasta que V1–V5 estén implementados.

## Medición (base de P4, sin límite fijado)

`tools/v05_v6_probe.py` sobre los 28 casos 411–438: **28 clones en todo el corpus** (22 de
V6 + 6 de V6-bis), máximo **4 copias por programa** (`413`) y máximo **2 copias por
definición**, sin ningún caso que pida una tercera. No se fija ningún tope: P4 pide medir
antes de poner número.

## Diferencial sellado

`evidence/v05_v6/run_20261031T183542Z.json` (recibo `isyco.evidence/0.1`, 28 casos,
`corpus_hash`, versiones de las cinco toolchains, semilla `n/a`):

- **123 EQUIV y 17 UNSUPPORTED; cero DIVERGENT / BUILD_FAIL / RUNTIME_FAIL / INCONCLUSIVE.**
- c, pydecimal, rust y zig: EQUIV en los 28 casos, intérprete incluido.
- COBOL: 11 EQUIV (los rechazos estáticos, que resuelve el frontend compartido) y 17
  UNSUPPORTED. Los UNSUPPORTED siguen viniendo de la **etiqueta**, no del programa:
  `features_of` (`isyco/backends/base.py:96`) añade `ir0.2` porque el módulo baja con
  `schema: isy-ir/0.2`, y COBOL lo declara fuera de alcance
  (`isyco/backends/cobol.py:1504`). Ningún caso V6-bis cambia eso — es exactamente lo que
  V7 tiene que separar.

## Control anti-fake

- `str_concat_truncates`: **DETECTADO en c, pydecimal, rust y zig**, y ahora rompe **dos**
  en un retorno pelado. El corpus gana un segundo diente: truncar la concatenación ya no
  solo se ve en un `let`, también
  en un retorno pelado.
- `half_even_as_half_up` y `div_floor`: **VACÍOS** — ningún caso del corpus usa decimales
  ni división entera; no se venden como cobertura.
- Un cascos del sabotaje no cuenta como detección (se registra en `cascos`; en esta
  corrida, ninguno).
- `does_the_work` sigue pasando: la cadena de 32 bytes de `423` y la de 8 bytes que emite
  `429` (`"abcdabcd"`) **no están escritas en el código generado** — las arma el engine —,
  y cambiar la entrada de `428` (`adios`) cambia la salida (`5` en vez de `4`).
