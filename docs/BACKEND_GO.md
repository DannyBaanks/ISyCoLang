# Backend Go

`python3 -m isyco run precio.isy --via go --input '["19.99","3"]'`

Requiere Python 3 y `go` en PATH. Verificado con Go 1.23.1 en Linux amd64.
El emisor `isyco/backends/go.py` recibe la misma ISY-IR validada que los otros
backends y genera un archivo Go autónomo, compilado con `go build`. Solo usa la
biblioteca estándar; el ejecutable no necesita Python ni el repo para calcular.
La CLI sí usa Python para el frontend, la validación de entradas y el driver.

## Representación y contratos

- Enteros y decimales: `*big.Int` tratados como valores inmutables. Cada suma,
  resta, producto, división o negación tiene un receptor nuevo. No hay operaciones
  de punto flotante. Los decimales son enteros escalados y se redondean una vez.
- Los cuatro modos decimales y `trap`/`wrap`/`sat` se aplican al resultado exacto;
  incluso `u64*u64` conserva todos los bits intermedios antes del ajuste.
- Arreglos Go `[N]T` y structs se copian por valor. Las hojas numéricas pueden
  compartir punteros porque el runtime nunca los muta. La igualdad numérica usa
  `Cmp`, no identidad de punteros; la igualdad de agregados es recursiva.
- `string` representa ASCII inmutable; se controla la capacidad declarada al
  convertir, ensanchar, concatenar y cortar. Los índices se comprueban como
  `big.Int` antes de reducirlos a índices de máquina.
- Pasos, profundidad y emits viajan en un contexto explícito. El protocolo E/R/X
  conserva salida parcial ante errores. Los agregados usan JSON compacto con
  escalares canónicos como strings y campos en orden de declaración.
- Las expresiones que pueden fallar se materializan en temporales en orden de
  evaluación. `and`/`or` usan ramas para conservar cortocircuito.

## Pruebas y límites

El gate común es `python3 tools/backend_gate.py --only go`. Compara el corpus,
los diferenciales numéricos y de strings, la prueba de trabajo real y los tres
sabotajes (`half_even_as_half_up`, `div_floor`, `str_concat_truncates`).
Los tests propios viven en `tests/test_backend_go.py`.

No produce trazas del runtime. Las capacidades declaradas cubren el core actual;
no añade concurrencia ni interoperabilidad con paquetes Go al lenguaje fuente.
El GC, el runtime y las asignaciones de `math/big` tienen costo: ventaja de
velocidad/memoria frente a otros backends, otras versiones de Go y otros sistemas
operativos son NOT_DEMONSTRATED. Los límites de recursos físicos y del compilador
siguen existiendo; un fallo del toolchain pertenece al arnés, no al programa.

## Evidencia verificada

Go: 228/228, 8484 corridas numéricas y 1270 de strings sin diferencias; los tres sabotajes detectados.

Recibo [del gate](../evidence/backends/gate_2026-11-25T004354Z.json), PASS sobre código commiteado
(`git_head=926c63f0a263939c4a4b155445c313cdca744e86`, `RELEASE_GATE`), y stdout crudo adyacente.
SHA-256 del recibo: `56de350caad154fcf1c86b51fa73faace97ba574c5d39f5717c590cda83eacd9`.
Comando: `python3 tools/backend_gate.py --only go`; se selló primero en una
raíz externa de evidencia mediante `ISYCO_EVIDENCE_ROOT`, luego se copiaron
los dos artefactos sin cambiar sus bytes al directorio público.

El corpus también se comprobó contra sus expected independientes con
`python3 -m unittest discover -s tests -p test_backend_go.py`. El gate se
concentra en Go; los recibos previos de los demás backends se conservan.

Suite general: [recibo de validación](../evidence/backends/go_suite_2026-11-25T005341Z.json) y
stdout íntegro adyacente. La matriz dinámica se enfocó en Go mediante
`ISYCO_TEST_BACKENDS=go`; los skips de otros backends están explícitos.
