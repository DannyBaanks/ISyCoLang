# Corpus de conformidad v0.1

Un programa `.isy` por propiedad y, al lado, su `.expect.json`:

```json
{"claim": "...", "input": [...], "limits": {...opcional...},
 "expected": {"status": "...", "code": null, "emits": [...], "return": null}}
```

- Los `expected` se calcularon **a mano a partir de `spec/CORE.md`** y se
  commitearon **antes** de que existiera el intérprete de referencia (ver
  `git log` de esta carpeta). Si el intérprete no coincide, se revisa primero
  contra la spec y nunca se cambia el `expected` para que pase.
- La equivalencia compara `status`, `code`, `emits` y `return` (spec §10.2).
- `SHA256SUMS.txt` congela el corpus.
