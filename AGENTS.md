# tomlclass Agent Guidelines

Rules for working in this repository. Every rule reflects the current state of the repo — when reality and this file disagree, fix the file in the same change.

## Project Map

| Path | Role |
|---|---|
| `src/tomlclass/` | The library. Zero runtime dependencies, Python ≥ 3.10. |
| `tests/unit/`, `tests/property/`, `tests/integration/` | pytest suite; property tests encode the four invariants below. |
| `tests/corpus/` | Pinned TOML snippets for offline 1.1 round-trip tests. |
| `tests/integration/test_toml_test.py` | Official toml-test conformance (needs a `.toml-test/` checkout; skips offline). |
| `scripts/bench/` | Manual benchmark script (`bench.py`, not collected by pytest) + `BASELINE.md` results. |
| `docs/en/`, `docs/zh-CN/` | User documentation, bilingual mirrors — change both. |
| `docs/{en,zh-CN}/skills/` | Contributor playbooks: quick start, defect fixing, API extension, testing, docs, release. |
| `docs/{en,zh-CN}/reference/` | Fact sheets: architecture, invariants, verification gates, API surface. |
| `CHANGELOG.md` | Release log; follow its "Writing rules" section. |

## Commands

The toolchain is uv; the same commands run in CI (`.github/workflows/code-quality-check.yml`).

```bash
uv sync --extra test --extra lint                                   # one-time setup
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto         # full suite
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""   # 3.10 gate
uv run ruff check src/ tests/ scripts/                               # lint
uv run basedpyright src/tomlclass                                   # types
uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500   # benchmark
```

Run the suite, ruff and basedpyright after every change; all must be clean. The 3.10 gate is mandatory — several releases shipped with 3.10-only import bugs.

## Architecture

The data flow is a strict pipeline; changes must keep the whole chain consistent:

**parser → nodes (CST) → engine_set/del (edit hooks) → render → annotation layer (`schema.py`, `pydantic.py`)**

- Untouched nodes store only source spans; rendering slices the original text. That is why preservation is byte-exact and why edited values re-render canonically.
- Every `Table`/`Array` mutator routes through the engine — memory and output cannot diverge. Do not bypass `engine_set`/`engine_del` with raw dict/list writes.

## Invariants (must never break)

1. **Round-trip axiom**: an unmodified document's `dumps()` is byte-identical to its source. Any change that alters untouched output is a defect.
2. **Comment preservation**: comments, key ordering and formatting survive every read-edit-save cycle. Array splices keep per-element comments; AoT and table edits keep section comments.
3. **Defaults never persist**: schema defaults merged in memory are never written to the file — including fields absent from the file and elements inside `[[aot]]` arrays.
4. **CRLF fidelity**: files are read without universal-newline translation; generated lines follow the file's line endings; CR inside assigned string values is escaped, not written raw.

`tests/property/test_invariants.py` exercises all four; `tests/integration/test_toml_test.py` pins the conformance counts. Core-module changes (parser, nodes, engine_set, render, schema) need pytest cases covering the exact defect and its neighbors.

## Code Conventions

- Root-cause fixes only: locate the actual defect and fix it at the architectural level. Patch-on-patch workarounds are forbidden.
- Docstrings use reStructuredText-style `:param:` / `:raises:` fields and concise module docstrings.
- Public API changes (exported symbols, class attributes, method signatures) require updating in sync: the `__all__` list in `src/tomlclass/__init__.py` and the docstrings of every affected public method.
- Prefer class methods over module-level orphan functions when the functionality naturally lives on a class. Exception: module-level functions mirroring the tomlkit API surface (`document`, `table`, `comment`, `nl`, …) exist for compatibility.

## Test Conventions

- Test comments stay objective and describe behavior — never reference issue numbers, tracker IDs or AI review labels.
- Tests needing `tomllib` on Python 3.10 import it via `from tests._compat import tomllib` (stdlib `tomllib` does not exist on 3.10).
- Tests writing fixture files use explicit bytes (`write_bytes`) or `write_text(..., newline="")` — platform line-ending translation masks CRLF defects on Windows.
- Mutable schema defaults in tests (`items: list[Item] = []`) carry `# noqa: RUF012` with the reason: the mutable default is the test subject.

## Documentation

- Maintained surfaces: `README.md`, `README.zh-CN.md`, `README.pypi.md`, `docs/en/`, `docs/zh-CN/` (user docs, skills, reference). No other languages.
- README structure is fixed: logo → intro → ErisPulse attribution → versioning note → badges → Capabilities (≤5 bullets, schema/config layer first) → "not a fit" boundary → Conformance & performance → Installation → Usage (declarative `Config` first; parse/edit and `update()` after) → Documentation → Requirements → License. Objective tone, no marketing.
- `docs/en/engine.md` documents the TOML version boundary (1.1 default, `toml_version="1.0"` strict mode) and None handling (`none_value` sentinel) — keep these sections in sync with `docs/zh-CN/engine.md`.
- User-visible changes update `CHANGELOG.md` under the current version entry per its "Writing rules": final state only, no process notes, in-version fixes folded in, merged per topic, summary ≤ 3 sentences.
- Contributor knowledge lives in `docs/en/skills/` + `docs/zh-CN/skills/` (task playbooks) and `docs/en/reference/` + `docs/zh-CN/reference/` (architecture, invariants, verification gates, API surface) — keep both languages and both sets consistent with the code they describe.

## Git Flow

- One topic per commit, one-line subject. Do not amend or force-push by default; the pending-release squash mode (`git reset --soft $(git rev-list --max-parents=0 HEAD)` → amend → force push) is used only when the user explicitly requests it.
- Releases require explicit user approval — never create a GitHub Release or tag without it. Before one: versions finalized in `pyproject.toml` and `src/tomlclass/__init__.py`, CHANGELOG entry flipped to Released with its date, both Python gates green, ruff and basedpyright clean.
