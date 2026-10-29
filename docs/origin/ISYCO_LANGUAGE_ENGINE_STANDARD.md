# ISyCo Language Engine Standard

> **Norma para lenguajes, esolangs y máquinas experimentales nuevas.**  
> Un lenguaje no se considera terminado porque tenga ejemplos que "funcionan".  
> Debe tener una **máquina ejecutable**, una **semántica observable** y una **ruta de evidencia reproducible**.

---

## 0. Regla principal

A partir de esta norma, todo lenguaje o sistema computacional nuevo debe intentar recorrer esta escalera:

```text
IDEA
  ↓
EXAMPLE
  ↓
EXECUTABLE
  ↓
DEMONSTRATED
  ↓
VERIFIED
  ↓
GOLDEN
```

No se permite saltar estados por narrativa.

Un ejemplo puede inspirar una afirmación.

Un motor puede ejecutar una afirmación.

La evidencia decide si la afirmación está demostrada.

---

# 1. Estados de madurez

## 1.1 `IDEA`

Existe una propuesta de semántica, sintaxis, máquina o comportamiento.

Puede haber pseudocódigo, notas, diagramas o prototipos.

**No implica ejecución.**

---

## 1.2 `EXAMPLE`

Existe al menos un caso ilustrativo que muestra la intención del lenguaje.

Ejemplos:

```text
hello.ext
counter.ext
truth_machine.ext
demo.ext
```

Un `EXAMPLE` sirve para enseñar.

**No es evidencia suficiente de una propiedad general.**

Prohibido inferir:

```text
un ejemplo corre
⇒ el lenguaje soporta todos los programas de esa clase
```

---

## 1.3 `EXECUTABLE`

El lenguaje tiene un motor genérico capaz de recibir programas externos y ejecutar su semántica.

Requisito mínimo:

```text
programa
   ↓
loader/parser
   ↓
engine/runtime
   ↓
estado + salida + trace
```

El motor debe aceptar **más de un programa** sin ser modificado para cada entrada.

No cuentan como engine:

- scripts que imprimen el resultado esperado;
- `if input == demo`;
- fixtures que calculan la respuesta en Python y luego la copian al estado;
- generadores que producen un archivo distinto para cada test ocultando la lógica fuera del lenguaje;
- wrappers cuyo host hace el trabajo semántico que se atribuye al lenguaje.

---

## 1.4 `DEMONSTRATED`

Una afirmación concreta está respaldada por:

```text
claim
+ programa
+ engine
+ parámetros
+ ejecución
+ resultado
+ evidencia preservada
```

Ejemplo:

```text
CLAIM:
  opcode MUK incrementa ACC en 1

PROGRAM:
  046_MUK.pkmc

ENGINE:
  host.py / runtime X

EXPECTED:
  ACC_final = ACC_initial + 1

OBSERVED:
  PASS
```

`DEMONSTRATED` aplica al **claim específico**, no automáticamente al lenguaje entero.

---

## 1.5 `VERIFIED`

La demostración fue comprobada por un mecanismo adicional independiente del camino principal.

Posibles verificadores:

- segundo runtime;
- oracle independiente;
- implementación de referencia;
- checker separado;
- hashes + replay;
- equivalencia de traces;
- cross-backend execution;
- property tests;
- conformance verifier.

Principio:

```text
ENGINE != VERIFIER
```

Siempre que sea razonable, el componente que produce el resultado no debe ser el único que certifica su corrección.

---

## 1.6 `GOLDEN`

Un contrato puede marcarse `GOLDEN` solamente cuando:

1. su semántica está congelada;
2. su representación canónica está definida;
3. su corpus de conformidad pasa;
4. existe evidencia reproducible;
5. los límites conocidos están documentados;
6. un rerun con la misma entrada reproduce el comportamiento esperado;
7. los cambios futuros deben tratar cualquier ruptura como cambio de contrato.

`GOLDEN` no significa "perfecto".

Significa:

> **este comportamiento es parte del contrato y ya no puede cambiar accidentalmente.**

---

# 2. Todo lenguaje debe tener un formato canónico

Cuando el sistema lo permita, cada lenguaje debe tener una extensión o representación propia.

Ejemplos:

```text
Malbolge      .mal
PokéCode      .pkmc
OtroLang      .xyz
```

La extensión no es decoración.

Debe identificar el **artefacto ejecutable real** del lenguaje.

La representación canónica debe especificar:

- encoding;
- gramática o loader;
- comentarios, si existen;
- terminación;
- entrada;
- salida;
- estado inicial;
- errores;
- límites;
- versión, si aplica.

Si el lenguaje no necesita formato textual, debe definir de todos modos una representación canónica equivalente.

---

# 3. Todo lenguaje debe tener un engine genérico

La forma pública recomendada es deliberadamente simple:

```text
Language/
├── README.md
├── engine/
│   └── engine.py        # o equivalente
├── programs/
├── tests/
├── evidence/
└── SPEC.md              # cuando la semántica ya lo amerite
```

También puede ser:

```text
host.py
runtime.rs
vm.c
engine.zig
```

No importa el lenguaje del host.

Importa la frontera:

```text
HOST
  administra archivos / stdin / stdout / procesos

ENGINE
  define la semántica del lenguaje
```

Regla:

> El host puede transportar la computación.  
> No debe inventar el resultado que atribuimos al lenguaje.

---

# 4. Engine público primero, integración ISyCo después

Cuando exista una implementación pública y una integración privada de ISyCo, deben mantenerse separadas.

## Fase pública

Debe contener solamente lo necesario para que cualquier persona pueda:

```text
clonar
↓
ejecutar
↓
inspeccionar
↓
reproducir
```

La versión pública debe ser autosuficiente y genérica.

No debe depender de conceptos internos privados para justificar que funciona.

---

## Fase ISyCo

Después, el motor público puede adaptarse a:

```text
workspace/assembly/<language>/
```

con contratos, gates, adapters, bootstrap u otras capas internas.

La relación correcta es:

```text
Public Engine
     ↓
ISyCo Adapter
```

No:

```text
Public Demo
     ↓
dependencia secreta en toda la infraestructura ISyCo
```

Un repo público debe seguir siendo ejecutable sin la arquitectura privada.

---

# 5. Corpus de conformidad obligatorio

Un lenguaje con operaciones discretas debe intentar tener un corpus de conformidad.

Ejemplo PokéCode:

```text
001_ABRA.pkmc
002_IVYSAUR.pkmc
...
151_MEW.pkmc
```

Cada artefacto debe probar una propiedad pequeña y explícita.

Formato conceptual recomendado:

```yaml
id: 046
name: MUK
claim: incrementa ACC
precondition:
  ACC: 0
program: 046_MUK.pkmc
expected:
  ACC: 1
  halt: true
```

El objetivo es poder formular:

```text
para cada operación op_i:
Engine(programa_i) == expected_i
```

El corpus debe incluir cuando aplique:

- operaciones válidas;
- operaciones límite;
- NOPs;
- errores esperados;
- instrucciones privilegiadas;
- terminación;
- input/output;
- branching;
- memoria;
- estado;
- condiciones adversariales.

---

# 6. Evidence before narrative

Toda afirmación importante debe poder bajar a artefactos observables.

Estructura recomendada:

```text
evidence/
├── manifest.json
├── runs/
├── traces/
├── hashes/
└── claims/
```

Un registro de evidencia debería guardar cuando aplique:

```text
claim_id
engine_version
program_hash
input_hash
seed
parameters
stdout
stderr
exit_code
final_state
trace_hash
expected
observed
verdict
timestamp
```

Principio:

```text
README != evidence
comentario != evidence
claim != evidence
```

README explica.

El runtime ejecuta.

La evidencia demuestra.

---

# 7. Never Guess

Si una propiedad no está respaldada por código, ejecución, prueba o evidencia:

```text
NOT_DEMONSTRATED
```

No usar equivalentes narrativos como:

```text
"seguramente"
"debería"
"parece suficiente"
"es básicamente"
"por construcción tiene que"
```

cuando el claim aún no ha sido medido.

---

# 8. Capability != Claim

Que el motor tenga ciertas primitivas no demuestra automáticamente propiedades globales.

Ejemplo:

```text
memoria
+ branching
+ loops
```

no autoriza por sí solo:

```text
TURING_COMPLETE
```

Para claims fuertes se requiere una reducción, construcción o demostración apropiada.

La existencia del engine transforma una propiedad de:

```text
PROPOSED
```

a como máximo:

```text
EXECUTABLE
```

hasta que exista evidencia específica.

---

# 9. El host no puede robarle el trabajo al lenguaje

Este es un fallo especialmente peligroso.

Patrón prohibido:

```python
resultado = resolver_en_python(programa)
engine.state["resultado"] = resultado
assert engine.state["resultado"] == esperado
```

Eso demuestra Python, no el lenguaje.

Prueba adversarial recomendada:

```text
1. construir/compilar el programa;
2. comprobar que el resultado todavía NO existe;
3. ejecutar el engine;
4. comprobar que el resultado aparece solamente después del runtime.
```

Nombre sugerido:

```text
test_engine_does_the_work
```

---

# 10. Tests por capas

El mínimo recomendado:

## A. Parser / loader

```text
archivo válido -> acepta
archivo inválido -> error definido
```

## B. Semántica de primitivas

Una prueba por operación o familia.

## C. Estado

Inicialización, mutación, persistencia y límites.

## D. Control

Branching, eventos, cadenas, loops, scheduling, etc.

## E. I/O

Entrada y salida reales del motor.

## F. Determinismo

Cuando corresponda:

```text
same program + same input + same seed
=
same result / same trace
```

## G. Adversarial

Entradas malformadas, loops infinitos, límites, aliases, underflow/overflow, targets inválidos, recursion/cycles, etc.

## H. Cross-runtime

Cuando exista más de un backend.

---

# 11. Los límites forman parte de la semántica

Todo engine debe documentar límites artificiales de seguridad o ejecución:

```text
max_steps
max_ticks
max_cycles
memory_limit
recursion_limit
chain_depth
timeout
```

Cortar una ejecución no equivale a terminarla.

Debe distinguirse:

```text
HALTED
LIMIT_REACHED
ERROR
INVALID_PROGRAM
TIMEOUT
```

Nunca:

```text
LIMIT_REACHED => HALTED
```

---

# 12. Semántica observable

Siempre que sea razonable, el engine debe producir una traza.

La traza no es sólo debugging.

Es una representación observable de:

```text
estado anterior
→ transición
→ estado posterior
```

Puede registrar:

```text
step
pc / event / node
operation
input
state_before
state_after
output
reason
```

Un claim sobre el comportamiento debe poder compararse contra la traza sin depender exclusivamente de una explicación humana.

---

# 13. Un ejemplo no puede convertirse silenciosamente en prueba

Todo repo debe separar explícitamente:

```text
examples/
tests/
evidence/
reference_models/
```

Si un modelo de referencia calcula cosas fuera del runtime, debe marcarse:

```text
REFERENCE_ONLY
```

No:

```text
VERIFIED
```

Si descubrimos después que una demostración antigua no era válida:

1. no borrar el hallazgo;
2. degradar correctamente el claim;
3. explicar por qué;
4. conservar el artefacto como referencia si sigue siendo útil;
5. añadir la prueba que habría detectado el error.

---

# 14. Los fixes deben reforzar contratos, no salvar narrativas

Cuando un experimento falle:

```text
bug
degeneración
semántica rota
claim demasiado fuerte
```

la corrección debe definirse independientemente del resultado deseado.

Prohibido:

```text
cambiar métrica porque dio negativo
cambiar definición porque 4D perdió
cambiar test porque el claim dejó de pasar
```

Correcto:

```text
definir contrato
↓
escribir test
↓
corregir implementación
↓
rerun
↓
aceptar el resultado
```

---

# 15. Estructura recomendada de un repo de lenguaje

```text
Language/
├── README.md
├── SPEC.md
├── LICENSE
├── NOTICE.md
│
├── engine/
│   ├── engine.*
│   └── parser.*
│
├── programs/
│   ├── examples/
│   └── conformance/
│
├── tests/
│   ├── test_parser.*
│   ├── test_semantics.*
│   ├── test_conformance.*
│   └── test_adversarial.*
│
├── evidence/
│   ├── manifest.json
│   ├── runs/
│   └── hashes/
│
└── reference_models/
```

No todos los proyectos necesitan exactamente estas carpetas.

Sí necesitan cubrir estas responsabilidades.

---

# 16. README mínimo obligatorio

Todo lenguaje público debe responder en menos de 90 segundos:

1. ¿Qué es?
2. ¿Qué lo hace distinto?
3. ¿Cuál es su formato?
4. ¿Cómo ejecuto un programa?
5. ¿Dónde vive el engine?
6. ¿Qué está demostrado?
7. ¿Qué NO está demostrado?
8. ¿Cómo corro los tests?
9. ¿Dónde está la evidencia?
10. ¿Cuáles son sus límites conocidos?

---

# 17. Claim table recomendada

```markdown
| Claim | Status | Evidence |
|---|---|---|
| Parser acepta formato canónico | VERIFIED | tests/parser |
| Runtime ejecuta opcode X | DEMONSTRATED | evidence/X |
| Todos los opcodes pasan corpus | VERIFIED | conformance report |
| Lenguaje es Turing-completo | NOT_DEMONSTRATED | — |
```

El estado debe describir exactamente lo que sabemos hoy.

---

# 18. Checklist para declarar un lenguaje "con motor"

Un proyecto sólo debe presentarse como **engine-backed** cuando:

- [ ] existe formato/representación canónica;
- [ ] existe loader/parser;
- [ ] existe engine genérico;
- [ ] el engine ejecuta múltiples programas sin modificación;
- [ ] host y semántica están claramente separados;
- [ ] existen tests de primitivas;
- [ ] existe al menos un corpus de conformidad;
- [ ] hay manejo explícito de errores y límites;
- [ ] hay trace o estado final observable cuando aplica;
- [ ] examples y evidence están separados;
- [ ] los claims fuertes tienen status explícito;
- [ ] `NOT_DEMONSTRATED` se usa cuando corresponde;
- [ ] el repo público funciona sin infraestructura privada de ISyCo.

---

# 19. Checklist para `DEMONSTRATED`

- [ ] claim concreto;
- [ ] programa/artefacto preservado;
- [ ] input preservado;
- [ ] versión del engine identificada;
- [ ] ejecución reproducible;
- [ ] expected definido antes de evaluar cuando sea posible;
- [ ] observed guardado;
- [ ] verdict explícito;
- [ ] hash/evidence preservados;
- [ ] no hay trabajo semántico oculto en el host.

---

# 20. Checklist para `VERIFIED`

Además de `DEMONSTRATED`:

- [ ] existe checker/oracle/backend independiente o propiedad equivalente;
- [ ] la verificación no reutiliza accidentalmente el mismo bug;
- [ ] rerun independiente coincide;
- [ ] casos adversariales relevantes pasan;
- [ ] límites del claim están documentados.

---

# 21. Regla de publicación

Un proyecto público debe revelar lo suficiente para reproducir su comportamiento, pero no necesita exponer arquitectura privada ajena a su contrato.

Separación:

```text
PUBLIC:
  lenguaje
  formato
  engine
  tests
  evidence
  docs

PRIVATE / ISyCo:
  adapters internos
  gates privados
  orquestación interna
  infraestructura no necesaria para reproducir el lenguaje
```

La publicación no debe depender de términos internos para entender el proyecto.

---

# 22. Filosofía operativa

Esta norma existe para evitar que nuestros sistemas queden como:

```text
"mira qué ejemplo tan raro"
```

y convertirlos en:

```text
"esta es una máquina;
este es su formato;
este es su contrato;
estos son sus programas;
esta es su evidencia;
intenta romperla."
```

La meta no es hacer repos más grandes.

La meta es convertir ideas en **máquinas ejecutables con semántica observable**.

---

# 23. Regla final

```text
ITERATE HARD.
CLAIM NOTHING YOU CANNOT SHOW.
PRESERVE EVERYTHING.
NEVER GUESS.
ENGINE BEFORE MYTHOLOGY.
EVIDENCE BEFORE NARRATIVE.
```

Cuando un lenguaje nuevo nazca, la primera pregunta ya no debe ser:

> "¿qué ejemplo hacemos?"

Debe ser:

> **"¿cuál es su máquina mínima ejecutable y cómo demostramos que ella —y no el host— hizo el trabajo?"**

---

## Status

```text
STANDARD: ACTIVE
SCOPE: new ISyCo languages / esolangs / experimental machines
VERSION: 1.0
```
