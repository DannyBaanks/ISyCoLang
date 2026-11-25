# Go Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compilar ISyCoLang a Go mediante ISY_BACKEND/1 con todas las capacidades actuales.
**Architecture:** Emisor independiente desde IR validada, runtime Go con math/big y contexto explícito. Driver y frontend existentes.
**Tech Stack:** Python 3, Go y biblioteca estándar.
**Spec:** docs/superpowers/specs/2026-11-24-go-backend-design.md

## Global Constraints
- Semántica normativa: referencia; no modificar docs/origin ni el core.
- math/big con receptores nuevos; agregados por valor.
- No dependencias externas ni resultados precalculados.
- Gate con expected independientes y backend saboteado; evidencia con SHA-256.

## Review Focus
- Aliasing numérico dentro de arreglos/structs copiados.
- Evaluación izquierda a derecha incluso si el segundo operando tiene llamadas.
- Rango de índices antes de convertir big.Int a índice de máquina.
- Serialización JSON con campos declarados, escapes y escalares como strings.
- Compilación Go con locales/temporales no usados y retornos en ramas.

### Task 1: Emisor y runtime
**Files:** Create isyco/backends/go.py; tests/test_backend_go.py.
**Interfaces:** GoBackend.emit(module, sabotage=None) -> str; compile_cmd(source,binary,extra_flags) -> list; BACKEND.run mantiene contrato existente.
- [ ] Escribir test de registro/ejecución que falle por backend ausente.
- [ ] Ejecutar unittest y observar el fallo.
- [ ] Implementar runtime y emisión de todos los nodos IR, tipos, casts, límites y sabotajes.
- [ ] Probar corpus existente y fixtures de aliasing/evaluación/índices/JSON.
- [ ] Commit con rutas explícitas.

### Task 2: Integración y prueba completa
**Files:** Modify isyco/backends/__init__.py, isyco/__main__.py; evidence/backends/ nuevos recibos.
**Interfaces:** registry()['go']; CLI --via go; gate común tools/backend_gate.py --only go.
- [ ] Registrar backend y actualizar ayuda.
- [ ] Ejecutar gate completo con diferenciales y sabotajes; exigir PASS sin harness failures.
- [ ] Ejecutar suite del proyecto; inspeccionar código generado y diff.
- [ ] Commit con rutas explícitas.

### Task 3: Entrega
**Files:** README.md, GUIA.md, spec/BACKEND.md, ROADMAP.md y docs/BACKEND_GO.md.
**Interfaces:** Comandos reales y enlaces a evidencia.
- [ ] Ejecutar ejemplo CLI y documentar su salida real.
- [ ] Documentar arquitectura, requisitos y límites medidos sin claims de velocidad.
- [ ] Revisar implementación completa, corregir hallazgos importantes y verificar.
- [ ] Commit con rutas explícitas; dejar rama local sin push.
