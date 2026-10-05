# tomlclass Agent Guidelines

You must follow these rules:

## Code Changes
- 1. When modifying source code, verify the upstream/downstream supply chain is intact (parser → engine hooks → render loop → annotation layer).
- 2. Follow the existing docstring style (reStructuredText-style `:param:` fields, concise module docstrings) when adding method or module comments.
- 3. Public API changes (exported symbols, class attributes, method signatures) require updating in sync:
  - the `__all__` list in `src/tomlclass/__init__.py`
  - the docstrings of every affected public method
- 4. Behavioral changes (lossless round-trip, comment preservation, diff write-back) must be checked against the invariants below before pushing.
- 5. Root-cause fixes only: locate the actual defect and fix it at the architectural level. Patch-on-patch workarounds are forbidden — several past regressions came from exactly that.

## Invariants (must never break)
- 6. **Round-trip axiom**: an unmodified document's `dumps()` is byte-identical to its source. Any change that alters untouched output is a defect.
- 7. **Comment preservation**: comments, key ordering and formatting survive every read-edit-save cycle. Array splices keep per-element comments; AoT and table edits keep section comments.
- 8. **Defaults never persist**: schema defaults merged in memory are never written to the file — including fields absent from the file, and elements inside `[[aot]]` arrays.
- 9. **CRLF fidelity**: files are read without universal-newline translation; generated lines follow the file's line endings; CR inside assigned string values is escaped, not written raw.

## Testing & Checks
- 10. After any change, run the full suite: `.venv/Scripts/python.exe -m pytest tests -q --no-cov -p no:cacheprovider` (870+ tests). Also run `.venv310/Scripts/python.exe -m pytest tests/unit -p no:cacheprovider -o addopts=""` (Python 3.10 gate — several releases shipped with 3.10-only import bugs).
- 11. Changes to core modules (parser, nodes, engine_set, render, schema) require new or updated pytest cases covering the exact defect and its neighbors.
- 12. Array/AoT editing changes require the verification matrices (`.zcode/verify_matrix.py`, `.zcode/verify_batch3.py`) to pass: all nesting levels, all operation orders, idempotent double-dumps.
- 13. Run `ruff check src/ tests/` and `basedpyright src/tomlclass` — both must be clean.

## Test Conventions
- 14. Test comments stay objective and describe behavior — never reference issue numbers, tracker IDs or AI review labels.
- 15. New test files that need `tomllib` on Python 3.10 must import it via `from tests._compat import tomllib` (the stdlib module does not exist on 3.10; a plain `import tomllib` breaks CI).
- 16. Tests writing fixture files must use explicit bytes (`write_bytes`) or `write_text(..., newline="")` — platform line-ending translation masks CRLF defects on Windows.
- 17. Mutable schema defaults (`items: list[Item] = []`) require a `# noqa: RUF012` comment with the reason: the mutable default is the test subject.

## Documentation
- 18. Only `README.md`, `README.zh-CN.md`, `README.pypi.md`, `docs/en` and `docs/zh-CN` are maintained. No other languages exist — do not create them.
- 19. README structure is fixed: logo → intro → ErisPulse attribution → versioning note → badges → Capabilities (≤5 bullets) → "not a fit" boundary paragraph → Conformance & performance (toml-bench data) → Installation → Usage (parse/edit first; `update()` after) → Documentation → Requirements → License. Keep the tone objective; no marketing claims.
- 20. `docs/en/engine.md` documents the TOML version boundary (1.1 default, `toml_version="1.0"` strict mode) and None handling (`none_value` sentinel). Keep these sections in sync across `docs/zh-CN`.
- 21. User-visible changes must update `CHANGELOG.md` under the current version entry, following its "Writing rules" section: final state only, no process notes, no in-version fix history, merged per topic, summary ≤3 sentences.

## Git Flow
- 22. While a release is pending, all work is amended into the single `init` commit and force-pushed (`git reset --soft $(git rev-list --max-parents=0 HEAD)` → amend → force push). `.zcode/` stays untracked — never commit it, never add it to `.gitignore`.
- 23. After a release ships, switch to normal segmented commits with one-line subjects (no amend), one topic per commit.
- 24. Releases require explicit user approval — never create a GitHub Release or tag without it.

## Release Checklist

- 25. When releasing:
  - `pyproject.toml` and `src/tomlclass/__init__.py` version numbers finalized
  - CHANGELOG current version entry: flip `> Pending release` → `> Released`, date finalized
  - Both Python gates green (3.14 + 3.10), ruff and basedpyright clean
  - Squash to the single `init` commit if not already, force push, then create the GitHub Release/tag (triggers PyPI publish)
  - Update the toml-bench performance tables if the engine changed
