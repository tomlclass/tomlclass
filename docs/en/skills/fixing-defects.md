# Skill: Fixing Defects

Use when a test fails, an invariant breaks, or an error surfaces. Method: root cause first — patch-on-patch workarounds are forbidden (past regressions came from exactly that).

## 1. Reproduce and localize

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto --tb=long -x
```

- Read the failure's file/line; open the module under `src/tomlclass/` and the pipeline stage it belongs to (`parser → nodes → engine_set/del → render → schema/pydantic`).
- Trace upstream **and** downstream before editing: a rendering bug may be a parser span bug; a schema bug may be an engine mutation bug.

## 2. Check the invariants first

Before hypothesizing, check the four invariants (see [Invariants](../reference/invariants.md)) — most defects in this codebase are one of:

| Symptom | Likely stage | Typical cause |
|---|---|---|
| untouched text changed in output | render / parser | span drifted, node marked dirty spuriously |
| comment lost or duplicated | render / `nodes.py` | trivia not carried or attached twice |
| schema default leaked into the file | `schema.py` diff walk | snapshot compared against the wrong base |
| CRLF turned into LF (or `\r` written raw) | load / render | newline translation, unescaped `\r` in a generated string |

## 3. Write the failing test first

Core-module changes (`parser`, `nodes`, `engine_set`, `render`, `schema`) require a pytest case covering the exact defect **and its neighbors** (same code path, adjacent node kinds, boundary values). Add it under the matching `tests/unit/test_regressions_*` file or a topic file — see [Testing](testing.md).

## 4. Fix at the architectural level

- Fix the defect where it lives in the pipeline, not where the symptom shows.
- Every `Table`/`Array` mutator must keep routing through the engine (`engine_set`/`engine_del`) — never bypass it with raw dict/list writes.
- Do not special-case a test input in library code.

## 5. Verify the full chain

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto      # full suite
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""   # 3.10 gate
uv run ruff check src/ tests/ scripts/
uv run basedpyright src/tomlclass
```

All four must be clean. For array/AoT-heavy fixes, also re-run the round-trip and edit suites explicitly (`tests/unit/test_roundtrip.py`, `test_edit.py`, `test_regressions_021d.py`) — they assert idempotent double-`dumps()` and splice behavior at every nesting level.

## 6. Record the outcome

- User-visible fix → `CHANGELOG.md` under the current version entry ([Updating documentation](updating-docs.md)).
- If the fix invalidates a doc statement or a playbook here, update that doc in the same change.
