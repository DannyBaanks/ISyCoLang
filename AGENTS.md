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
8. Repo **privado** (decisión de Danny, 2026-10-28), con remoto **privado**
   `DannyBaanks/ISyCoLang` desde 2026-11-03 (pedido por Danny; el remoto creado el
   2026-10-28 se borró a su pedido). Sin remoto público: no publicar contenido ni
   cambiar la visibilidad sin que Danny lo pida. La limpieza que pide el estándar
   §21 está **abierta** y medida en `docs/PUBLICACION.md`: el correo personal en la
   metadata de los 131 commits, y rutas de workstation en 19 líneas de cinco
   recibos fijados por su `SHA256SUMS.txt` —limpiarlos rompe el sello, y reescribir
   la historia deja de resolver los `git_head` que citan los recibos—. Antes de
   cualquier publicación hay que elegir una de las dos salidas de ese documento.
