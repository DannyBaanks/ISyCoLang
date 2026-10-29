# ISyCoLang — reglas para agentes

1. Lee `ROADMAP.md` y trabaja solo en la fase cuya dependencia ya pasó su gate.
2. Rige `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`. Si algo no está
   demostrado: `NOT_DEMONSTRATED`.
3. `docs/origin/` es inmutable; verifica con `sha256sum -c docs/origin/SHA256SUMS.txt`.
4. La semántica normativa es el intérprete de referencia (desde F2). Ningún
   backend define comportamiento.
5. Toda suite diferencial lleva `expected` independiente y un backend saboteado.
6. `~/Development/ISyCo` (monorepo) es solo lectura desde aquí. Nunca modificar
   `workspace/assembly`.
7. Evidencia nueva → `evidence/<tema>/` con archivo nuevo por corrida (nunca
   sobrescribir) y su SHA-256.
8. Repo **privado** (decisión de Danny, 2026-10-28). Remoto privado:
   `origin` = https://github.com/DannyBaanks/ISyCoLang. Push solo a
   `origin/main`; nunca crear un remoto público ni publicar contenido sin que
   Danny lo pida.
