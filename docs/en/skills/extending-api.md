# Skill: Extending the API

Use when adding or changing anything a user can call: exported functions, `Document`/node methods, `Config`/`Field` options, or the optional `tomlclass.pydantic` layer.

## 1. Design against the two layers

- **Engine layer** (`parse`/`loads`/`load`/`dumps`/`update`, `Document`, nodes): lossless, no schema knowledge. New mutators must route through the engine hooks — `engine_set` / `engine_del` in `src/tomlclass/engine_set.py` — so memory and output cannot diverge.
- **Annotation layer** (`Config`, `Field`, `tomlclass.pydantic.TomlModel`): builds on the engine. New field types/options extend `_FieldSpec` and the validators in `schema.py`; pydantic support mirrors them in `pydantic.py`.

Check the docs boundary before adding: the library is a config/TOML tool, not a general data framework. If it belongs in user code, say so instead of adding it.

## 2. Keep the sync contract

A public API change is not done until **all** of these move together:

1. Implementation, with reST docstrings (`:param:` / `:returns:` / `:raises:`).
2. `__all__` in `src/tomlclass/__init__.py` (new exported symbols only; `test_version.py` pins metadata).
3. Docstrings of every affected public method.
4. User docs: the matching page under `docs/en/` **and** `docs/zh-CN/` (see [Updating documentation](updating-docs.md)).
5. `CHANGELOG.md` under the current version.
6. Tests: new public surface gets cases in `tests/unit/test_api_030.py` (or a new topic file), including error paths.

## 3. Respect the type gates

- `basedpyright src/tomlclass` must stay at 0 errors — promoted rules in `pyproject.toml` (`reportReturnType`, `reportArgumentType`, optional-access rules, override/variable-override compatibility) are the contract.
- `ruff check src/ tests/ scripts/` is clean; imports stay lazy only where the existing code already does it (see the `PLC0415` ignore rationale in `pyproject.toml`).
- Python ≥ 3.10: no 3.11+-only syntax/stdlib without a `_compat` shim (`tests/_compat.py` is the pattern; runtime code uses `tomli`-free paths).

## 4. Preserve the entry-point conventions

- Dual-mode `load()` (path → `Document`, file object → dict) and `none_value` handling exist in every parse-facing entry point (`parse`, `loads`, `load`, `update`, `Config.load`). A new parse-facing entry point must accept `toml_version` (`"1.1"` default / `"1.0"` strict) and plumb `none_value` where dict output is involved.
- Errors: parse problems raise `TOMLParseError` (a `ValueError`), non-representable values raise `TOMLTypeError` **at assignment time** (a `TypeError`), schema issues aggregate into `ValidationError` with `FieldError` items. Do not leak raw exceptions through the public surface.
- Zero runtime dependencies — optional features go behind `optional-dependencies` extras (`pydantic`, `watch`) with graceful `importorskip`/`ImportError` handling.

## 5. Verify

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto
uv run ruff check src/ tests/ scripts/
uv run basedpyright src/tomlclass
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""
```

Then re-read the docs you touched as a user would: every snippet in the new doc section must run as-is against the new API.
