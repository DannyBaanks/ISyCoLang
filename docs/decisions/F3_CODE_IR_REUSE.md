# Decisión F3 — ¿reusar Code IR? (2026-10-28)

**Decisión:** reimplementar. Se reusan los **patrones**, no el código.

Leído: `~/Development/ISyCo/experiments0000/py_transpile_toy/code_semantics/`
(`model.py`, `canonical.py`, `validation.py`, `emitters/`, `frontends/`; 883 líneas).

| aspecto | Code IR | ISyCoLang necesita | ¿reusable? |
|---|---|---|---|
| modelo numérico | un `NumericModel` por módulo; tipo único `int` | contrato por tipo: `int<N,signo,ovf>`, `dec<p,s,rnd>` | no |
| decimales | no existen | `dec` con redondeo único | no |
| tipos extra | `string`, `map`, `ForRange`, `Augment`, `StringStartsWith` | fuera de v0.1 | no |
| división | `floor_divide` (Python) | truncada (D2) | no |
| pasos y límites | no existen | parte de la semántica (CORE §8) | no |
| JSON canónico (claves ordenadas, sin espacios) + SHA-256 | sí | sí | **patrón** |
| hash semántico sin metadata | sí | sí | **patrón** |
| validador de mundo cerrado con diagnósticos por ruta | sí | sí | **patrón** |
| emisores Rust/Python | atados a su modelo `int` | F4 empieza por C | no (se revisa en F5 para la ola de Rust) |

Ningún archivo de Code IR se copió ni se modificó.
