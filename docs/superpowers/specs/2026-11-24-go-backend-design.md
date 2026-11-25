# Backend Go completo — diseño aprobado

Danny eligió Go completo con `math/big` el 2026-11-24.

## Intención y límites
Añadir `--via go` al contrato ISY_BACKEND/1 existente. El frontend y la IR siguen
siendo comunes; el binario Go calcula los resultados. No se cambia el core ni se
promete una ventaja de rendimiento. No hay dependencias externas a la biblioteca
estándar de Go. No se publica ni se empuja sin instrucción de Danny.

## Alternativas
Se consideraron tipos nativos con cobertura parcial, o cobertura completa con
`math/big`; Danny eligió la segunda para preservar cálculos intermedios exactos.

## Representación
Los números usan punteros a `big.Int` tratados como valores inmutables: cada
operación escribe en un receptor nuevo. Los decimales son enteros escalados.
Los arreglos Go de tamaño fijo y structs se copian por valor; las hojas numéricas
pueden compartir punteros porque nunca se mutan. Los strings son inmutables y
comprueban capacidad al construir/cortar/concatenar/convertir. El estado de pasos,
profundidad y emits viaja por contexto. Se preservan evaluación izquierda a
derecha, cortocircuito y salida parcial en errores. JSON de agregados conserva
orden de campos de la declaración. Go compila un archivo autónomo por programa.

## Verificación
Corpus con expected independientes, comparación de status/code/emits/return/steps,
diferenciales numéricos y de texto, cambio de entrada y tres sabotajes:
half_even_as_half_up, div_floor, str_concat_truncates. Evidencia nueva sellada con
SHA-256. Los límites no medidos se declaran NOT_DEMONSTRATED.
