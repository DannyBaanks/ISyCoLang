# ISyCoLang — Estudio de viabilidad (2026-10-28)

Modo: auditoría crítica + diseño conceptual. Sin implementación.
Insumos: `docs/origin/ROADMAP_V0_2026-09-03.md`, `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`
y una muestra del monorepo. Lo marcado "reportado" se leyó en informes del
repo y **no se re-ejecutó** para este estudio.

## 0. Muestra inspeccionada

| fuente | por qué | hallazgo |
|---|---|---|
| ISyCoLang | objeto de estudio | **ABSENT** en disco antes de este repo |
| WISA (`ISyCo/CoEvoLang/workload_isa`, `runtime/WISA_*.md`) | precedente de core fijo + semántica por template | core de 64 líneas sin conocimiento de backend; un segundo template cambia `EXEC score` sin tocar el core (reportado). `EXEC` "puede delegar a otra WISA": es el patrón de VM escondida que el V0 prohíbe |
| TRACE_MATH_V0 (`ISyCo/workspace/experiments/TRACE_MATH_V0`) | V0 §9 la usa como capa de composición | es una calculadora `+ Δ × %` sobre int64 checked + métricas U/R/D/L/C sobre trazas TMV0; no compone comportamientos. Tres versiones coexisten sin decisión (`FROZEN_STATE_2026-09-12.md`). PRECANON: vectores de métricas idénticos para trazas distintas |
| Code IR (`ISyCo/experiments0000/py_transpile_toy`) | camino fuente → IR → nativo | mundo cerrado, `UNSUPPORTED`, contrato `signed_fixed/32/trap`, veredicto `EQUIVALENT_WITHIN_DECLARED_DOMAIN` (Python vs Rust) |
| PITON (`ISyCo Git/PITON`) | compilador real CST → MIR → x86-64 | corpus v1–v3 casi 100 % EQUIV; stdlib real MIR 28/167, build 23/167 (reportado 2026-10-24): el backend nativo es caro aun con semántica prestada |
| Dataflow (`experiments0000/von_neumann_dataflow`, `dataflow_von_neumann`) | eje dataflow | persistente 112–3142× mejor que proceso-por-op; nunca mejor que in-process. Orden por datos 11/11 con escrituras disjuntas |
| Malbolge T24 (`GUS/04_EXPERIMENTS/GUS_TRIT_ALGEBRA_V0`) | sustitución de ops | invertir operandos de `crazy`: cierre 17 → 15, 18 709 diferencias. Misma firma, otra álgebra |
| E22 COBOL | numéricos | reconciliación byte a byte COBOL / Python / Rust / mixto: manda el contrato, no el lenguaje |
| ISyInfer | sustitución exacta vs aproximada | liga de paridad (bit-exacta) vs liga nativa (tolerancia declarada) |
| SEMIR, E29 | negativos | IR compacta: FAIL; "aprendizaje" de E29 comparaba texto idéntico bajo dos nombres |

## A. Veredicto

| pregunta | estado |
|---|---|
| Core de 3 slots como laboratorio por dominio | INFERRED viable con core reformulado (§C) |
| Lenguaje compilado general cuyo camino de ejecución son las 3 ops | INFERRED no viable sin perder lo buscado |
| Lenguaje compilado con lecciones de ISyCo, IR convencional, 3-ops como carril de análisis | INFERRED viable |
| Contradicciones V0 ↔ disco | TRACE_MATH (§9 V0), WISA como dominio matemático (§12 V0), exhaustivo L=8 (§7) |

Tensión de fondo: bases distintas por dominio ⇒ programas no portables;
propósito general ⇒ portabilidad. Conciliarlo exige una capa independiente del
pack, que convierte al pack en detalle de implementación.

## B. Arquitecturas

| | A. 3 ops directas | B. alto nivel → IR 3-ops | C. packs modulares | D. IR experimental |
|---|---|---|---|---|
| teórica | DEMONSTRATED en general (OISC); NOT_DEMONSTRATED nuestros packs | INFERRED sí si el pack es completo | INFERRED sí (sistemas de efectos) | INFERRED sí, acotado |
| prototipo | fácil | difícil: selección de instrucciones por pack = síntesis | medio | el más pequeño |
| nativo | fácil | malo: inflación tipo SUBLEQ, estructura perdida | normal | no es el objetivo |
| ergonomía | esolang | buena en fuente, mala en traza | buena | n/a |
| portabilidad entre packs | ninguna (T24) | por recompilación | por contrato | por experimento |
| riesgo capacidad oculta | alto si core laxo | muy alto (intrínsecos) | abandona "3" | controlable |
| conserva hipótesis 3 slots | sí | solo en IR | **no** | sí |
| mantenimiento | bajo | muy alto | medio | bajo |
| falsable | sí | difícil | sí | máximo |

ROADMAP V1 = C (ejecución, packs como librerías con efectos) + D (Lab) con A
como forma de los programas del Lab.

## C. Huecos del core de 3 slots (V0 §3)

`Step := Ωi(State, operands) -> State'` deja que una op toque todo el estado.

| # | tema | hueco | propuesta |
|---|---|---|---|
| 1 | estado | indefinido | (PC, memoria fija, colas E/S, status), dominio de valores del core |
| 2 | PC | core y ops lo reclaman | core PC+1; ops escriben PC solo con `control_effect` declarado |
| 3–4 | saltos/bucles | sin control-op no hay bucles | explícito: lo decide el pack |
| 5 | memoria | acotada/no acotada por experimento | fija por torneo; direccionamiento del core, igual para todos |
| — | DISPATCH | decodificación computada = cómputo | fija, finita, O(1) |
| — | operandos | ancho del inmediato = capacidad oculta | fijado por el core |
| 6 | halt | indefinido | `HALTED / LIMIT_REACHED / ERROR / INVALID_PROGRAM` |
| 7 | errores | indefinido | `ERROR(code)` del core |
| 8 | E/S | canal del core = capacidad gratis | decidir; si es del core, tareas de E/S fuera del ranking |
| 9 | COMPOSE | en runtime = 4ª op escondida | solo compilación, costo = largo expandido + hash |
| 10 | cambio de pack | sin regla | `pack_id` + hash de ops en el programa; mismatch = `INVALID_PROGRAM` |

**Atomicidad:** conjuntos de lectura/escritura estáticos y acotados; función
finita sobre esa ventana (tabla explícita, como `crazy`); sin iteración
dependiente del estado; sin leer el programa como dato salvo declarado; costo =
tamaño de tabla comprimida. Hidden-VM imposible por construcción.

**Control de pack nulo:** Ω0=Ω1=Ω2=NOP; todo lo que resuelve es capacidad del core.

## 6. Sustitución de packs

Segura solo si: (1) existe simulación τ: op de P → secuencia de P′ con
proyección observable conmutativa (exhaustivo en dominio finito o SMT acotado),
y se recompila; (2) equivalencia por programa en dominio declarado; (3) liga de
tolerancia para numérico aproximado. El pack se fija en compilación (parte del
ABI); cambio en runtime solo entre packs con simulación demostrada.

## 7. Síntesis y combinatoria

Programas de largo 1..8, 3 ops × k combinaciones de operandos, 220 packs, 14 tareas:

| k | programas/pack | ejecuciones totales |
|---|---|---|
| 2 | 2.0e6 | 6.2e9 |
| 4 | 4.7e8 | 1.4e12 |
| 8 | 1.2e11 | 3.5e14 |
| 16 | 2.9e13 | 8.9e16 |

Herramientas: enumeración bottom-up con poda por equivalencia observacional,
CEGIS con z3, e-graphs para derivaciones, superoptimización para costo.
Decidible: rectas en dominio finito (exhaustivo); con bucles y límite de pasos
(exponencial). Indecidible: equivalencia general (Rice). Igualdad de métricas o
de trazas en corpus ≠ equivalencia semántica (PRECANON de TRACE_MATH lo mostró).

## 8. Dataflow

Misma semántica secuencial vs dataflow si: efectos declarados, scheduler
respeta RAW/WAR/WAW, E/S con token de orden, sin direccionamiento indirecto
(o rastreo dinámico). Rendimiento: solo a grano grueso. Es estrategia de
backend, no semántica.

## 9. Numéricos

Contratos `int<N,wrap|trap|sat>`, `decimal<p,s,redondeo>`, `mod<M>`,
`ieee754<w,estricto>`, verificados contra referencia exacta (`fractions`,
`decimal`). COBOL no es mejor por ser COBOL; lo que valió en E22 fue la
reconciliación.

## 12. Riesgos y condiciones de abandono

| riesgo | señal | respuesta |
|---|---|---|
| capacidad oculta en el core | pack nulo resuelve tareas | reformular core |
| atomicidad ambigua | op aceptada que itera | ops como tablas |
| backends stub | pasan sin ejecutar | `test_engine_does_the_work` |
| explosión combinatoria | síntesis fuera de presupuesto | reducir k/L, poda, CEGIS |
| no determinismo | trazas difieren entre corridas | bloquear la fase |
| equivalencia general | tentación de "equivalente" a secas | solo dominio declarado |
| costo de backends > beneficio | backend sin ganancia medida | se retira, se documenta |
| depuración | errores no localizables | diferencial de 3 vías + sabotaje |

Abandonar el Lab si L1 o L6 fallan tras reformular. Reducir el compilador a
"IR + 1 backend" si F5 no consigue ≥ 2 backends conformes.
