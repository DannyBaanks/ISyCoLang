# spec/

Los cuatro núcleos congelados son los que están en `SHA256SUMS.txt`; lo demás se lee
pero no está sellado, y nada de aquí define la semántica ejecutada — esa es el
intérprete de referencia (`AGENTS.md` §4).

- `CORE.md`: semántica del core v0.1 (F1, FROZEN v0.1; hash en `SHA256SUMS.txt`).
- `CORE_v0.2.md`: cambios C1–C3 de v0.2 (FROZEN); la cabecera elige la versión.
- `CORE_v0.3.md`: `str`, `slice`, `chr`, `len` y structs (FROZEN; S1–S8).
- `CORE_v0.4.md`: módulos — `import`, `pub` (FROZEN; M1–M4 y las [P] aprobadas el mismo
  día, 2026-10-29). La IR no cambia: los imports se resuelven en el frontend.
- `CORE_v0.5_propuesta.md`: `PROPUESTA` (2026-10-30) — las siete decisiones numeradas
  V1–V7 con opciones, recomendación y las preguntas [P]. Con sus correcciones fechadas
  (§7 y §8), que es donde se midió que «aritmética de capacidades» no hacía falta.
- `CORE_v0.5.md`: `BORRADOR` (2026-11-01) — el texto normativo de V1–V7 ya implementado,
  con las aristas medidas y los sitios del código donde vive cada regla. **No congelado**:
  no entra en `SHA256SUMS.txt` hasta que Danny diga, y le quedan abiertas P4, N1 y N2 (§11).
- `ERRATA_v0.1.md`: interpretaciones de v0.1 (resueltas por v0.2).
- `IR.md`: forma de ISY-IR — v0.1 y, desde CORE v0.3, v0.2 (§9). Normativa para backends.
- `BACKEND.md`: contrato `ISY_BACKEND/1` (F5): qué recibe y qué entrega un backend, cómo
  declara capacidades (§2, ya con la regla V7 de leer el contenido del programa), el
  protocolo y el costo medido de los binarios nativos (§3), qué lo hace conforme (§5) y
  su dominio declarado por backend (§6, con los límites de COBOL).

Las líneas de código citadas derivan con cada commit. Cuando un documento cita una que ya
no está en esa línea, la fuente es el **símbolo**, no el número: se comprueba con
`grep -n 'def features_of' isyco/backends/base.py` y no con el documento.
