# Decisión Z2-b — la pila del paquete se reserva contada desde el llamante (2026-11-12)

**Pedido de Danny (2026-11-12): cerrar el hueco que Z2 dejó escrito.** La decisión Z2
(`docs/decisions/Z2_MAX_EXPR_DEPTH.md`) nombró la cota de 64 niveles y dejó una fila `FALSO, y
medido`: *«la cota garantiza que la forma legal quepa en cualquier pila»*. El fuente del tope legal
bajaba con pila limpia y moría por `RecursionError` si quien llamaba traía 300 frames (C8 de
`evidence/z2_guard/run_2026-11-04T001913Z.json`). El idioma decidía el borde; el anfitrión seguía
decidiendo si lo legal cabía.

Lo que Danny decidió es **cerrar ese hueco**. Las elecciones de diseño de abajo —el mecanismo, el
número 32, y extenderlo a la ejecución— son de quien lo implementó y quedan a revisión suya.

## La regla

El límite de recursión de Python es **absoluto**: cuenta los frames del hilo entero, incluidos los
que ya traía quien llama. `isyco/pila.py` lo vuelve relativo:

- `reserva(n)` mide la profundidad en curso, sube el límite a `profundidad + n` si hace falta y lo
  restaura al salir. Nunca lo baja y no captura `RecursionError`.
- `@con_pila` aplica `reserva(frames_frontend())` a todo lo que **recorre un árbol acotado por la
  cota**: `modules.load_program`, `checker.check`, `ir.lower`, `ir_validate.validate`,
  `backends.base.features_of` y el `emit` de los cinco backends.
- `frames_frontend()` es `FRAMES_POR_NIVEL × ast.MAX_EXPR_DEPTH` = 32 × 64 = **2048** frames,
  leído de la cota viva.
- La ejecución (`interp.run`, `ir_interp.run_ir`) pide lo que ya pedía,
  `50 * max_call_depth + 1000`, ahora contado desde el llamante.

No es la salida (b) del preview de Z2 —«quitar la recursión»—: los recorridos siguen siendo
recursivos. Es la misma acomodación que la ejecución ya tenía, hecha relativa y extendida a los
recorridos que no la tenían.

## Lo que se encontró al medir

1. **El hueco era más ancho que el frontend.** La IR es un árbol: el validador, el censo de
   capacidades y los cinco emisores también bajan frames, y también morían con un llamante hondo.
   Z2 lo había medido solo en `compile_ir` e `interp.run`.
2. **La forma legal más cara no eran los paréntesis.** Z2 daba 716 frames para 63 pares. 63
   llamadas anidadas `f(f(…))` gastan **781** en todo el camino (12,2 por nivel). La sonda de la
   guarda no medía esa cara.
3. **La acomodación de la ejecución también era absoluta.** Con `max_call_depth = 256` el límite
   era 13 800; un llamante con 14 000 frames lo anulaba.

## Por qué 32

No sale de una medición de techo. La cara más cara medida gasta 12,2 frames por nivel; 32 es la
potencia de dos que deja más del doble. `tests/test_depth.py::LoLegalCabe.
test_el_presupuesto_dobla_el_coste_medido` falla si alguna de las cuatro caras que mide pasa de la
mitad del presupuesto. **No está demostrado que no exista una forma legal más cara**: se midieron
cinco caras, no todas las combinaciones de la gramática.

## Falsificación

- `test_sin_la_reserva_vuelve_el_muro_del_anfitrion`: con `FRAMES_POR_NIVEL = 0` y 300 frames del
  llamante, el tope legal vuelve a dar `RecursionError`.
- `test_el_validador_y_los_emisores_tambien_dependian_del_llamante`: el mismo sabotaje, recorrido
  por recorrido, sobre `features_of` y los cinco emisores.
- `test_la_ejecucion_tambien_cuenta_desde_el_llamante`: con `pila.profundidad` devolviendo 0
  (contar en absoluto) y 14 000 frames del llamante, la ejecución muere.
- El llamante de los tests y de la sonda es hostil: llega con **40 frames de aire**, no con pila
  de sobra.

## Claims

| claim | estado | dónde |
|---|---|---|
| El tope legal recorre todo el camino con 0, 300 y 3 000 frames del llamante, en cinco caras | **DEMONSTRATED** | P1 + `LoLegalCabe` |
| El nivel 65 sigue siendo `SPEC_LIMIT` con esos llamantes | **DEMONSTRATED** | P2 |
| Es la reserva la que lo consigue (frontend, censo y cinco emisores) | **DEMONSTRATED** | P3 + dos tests de sabotaje |
| La cara más cara medida gasta menos de la mitad del presupuesto | **DEMONSTRATED** | P4 (781 de 2048) |
| El límite del llamante queda como estaba, salga como salga | **DEMONSTRATED** | P5 |
| La ejecución cuenta desde el llamante | **DEMONSTRATED** | P6 |
| El caso exacto de C8 hoy baja | **DEMONSTRATED** | P7 |
| La forma legal cabe en **cualquier** pila | **NOT_DEMONSTRATED** | medido hasta 3 000 frames (14 000 en ejecución); no se midió el techo de la pila de C del proceso |
| 32 frames por nivel bastan para toda forma legal | **NOT_DEMONSTRATED** | cinco caras medidas |
| El anidamiento de **sentencias** tiene cota | **FALSO, y medido** | P8: 676 bloques `if` bajan, 677 dan `RecursionError` |

## Lo que Z2-b NO hace, y lo que abre (Z3)

No cambia ningún resultado del corpus, ningún fuente emitido ni ningún hash: solo cuánta pila hay
disponible mientras se recorre.

No topa el anidamiento de **sentencias**. `MAX_EXPR_DEPTH` acota expresiones; un `if` dentro de
otro no pasa por `Parser.nivel` ni por `expr_depth`. P8 lo deja medido: 676 bloques anidados bajan
y 677 mueren por `RecursionError`, igual con 0 que con 300 frames del llamante. Es el mismo
defecto que Z2 encontró —un borde sin número ni error nombrado— en otro eje, y con un agravante:
**ese número lo pone hoy el presupuesto de esta decisión**, no el idioma (sin la reserva y con el
límite de fábrica el borde estaba en 324/325). Queda abierta como **Z3**; si se resuelve como Z2,
la salida es otra cota nombrada con `SPEC_LIMIT`, y eso es decisión de Danny.

No re-corre los gates F2–F5: la reserva no toca qué se emite ni qué se ejecuta, y el recibo de
esta decisión es la sonda, no un lote nuevo.

## El sello

`evidence/z2_pila/run_2026-11-12T024856Z.json` (sha `f3e545fd…`): `RELEASE_GATE`,
`arbol_sucio_codigo: false` sobre `4917258`, P1–P8 `DEMONSTRADO`, trece fuentes al lado. Instrumento:
`tools/z2_pila_probe.py`, que no invoca ningún toolchain. Medido en un contenedor con Python
3.13.18; los recibos anteriores de Z2 son del host de Danny.
