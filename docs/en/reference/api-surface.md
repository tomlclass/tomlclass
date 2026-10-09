# Public API Surface Reference

What `tomlclass` exports and how the entry points behave. Source of truth: `src/tomlclass/__init__.py` (`__all__`) and the docstrings; `tests/unit/test_version.py` pins metadata consistency. Verified 2026-10.

## Version

`0.3.0` (`__version__` in `src/tomlclass/__init__.py`, mirrored in `pyproject.toml`). Pre-1.0 policy: minor bumps may add APIs; existing APIs stay backward compatible.

## Exports (`__all__`)

| Group | Symbols |
|---|---|
| Parsing / rendering | `parse`, `loads`, `load`, `load_path`, `dumps`, `dump`, `update` |
| Document | `Document` |
| Annotation layer | `Config`, `Field` |
| Construction helpers | `document`, `table`, `inline_table`, `aot`, `comment`, `nl` |
| Node types | `Table`, `Array`, `ArrayOfTables`, `InlineTable` |
| Errors | `TOMLError`, `TOMLParseError`, `TOMLTypeError`, `ConfigError`, `FieldError`, `ValidationError` |
| Metadata | `__version__` |

Optional: `tomlclass.pydantic.TomlModel` (extra `pydantic`), hot reload via `Config.watch` (extra `watchfiles`).

## Entry-point contracts

| Entry | Input → Output | Notes |
|---|---|---|
| `parse(source, *, toml_version="1.1")` | str → `Document` | lossless; 1.0 mode is strict |
| `loads(source, *, toml_version, none_value)` | str → dict | tomllib-compatible; `none_value` sentinel decodes `None` |
| `load(path_or_fp, *, toml_version, none_value)` | path → `Document`; binary file object → dict | dual-mode |
| `load_path(path)` | path → `Document` | always lossless |
| `dumps(obj, *, none_value)` | `Document` → str (verbatim when unedited); Mapping → str (canonical); `None` raises `TOMLTypeError` without a sentinel | `none_value` only on the Mapping path |
| `dump(obj, fp, *, none_value)` | into a text/binary file object | mirrors `dumps` |
| `update(path, updates, *, toml_version, none_value)` | dotted-key mapping; atomic write; returns the `Document` | file object raises `TypeError`; any bad value → nothing written |

All parse-facing entry points accept `toml_version` (`"1.1"` default, `"1.0"` strict legacy).

## Document essentials

- Full `MutableMapping` protocol; value-based `==`; `|` merge operators.
- Path grammar (one grammar for `find` / `set_path` / `comment` / `set_comment` / `update`): bare keys, quoted keys (`"a.b"`), `[int]` AoT indexing. Unindexed AoT traversal projects on reads, broadcasts on writes; indices never auto-create. Malformed paths raise `ValueError` everywhere.
- Comment API: `doc.comment(path)` / `doc.set_comment(path, text | None)`; AoT fields need an index (`products[0].name`).
- `save()` is atomic (tempfile + `os.replace`); `dumps()` idempotent.
- Closed for editing: inline tables (reassign the whole value), dotted-key tables (sealed, new keys render as dotted lines). AoT reordering (`sort`/`reverse`) unsupported — replace wholesale.

## Annotation layer essentials

- `Config`: docstring → template comments; `App()` defaults-only, `App.load(path, env_prefix=...)` validated + env overrides, `App.template()` commented template, `App.validate_dict(raw)` aggregated errors, `app.save()` diff write-back, `app.to_dict()`, `app.reload()`, `Config.migrate(old)` with `_migrate_key_map`.
- Class options: `extra` (`"allow"` default / `"ignore"` / `"forbid"`), `validate_assignment`.
- `Field` constraints: `ge / le / gt / lt / pattern / min_length / max_length / coerce`; `Annotated[X, Field(...)]` equivalent; i18n description dicts.
- Supported annotations: `bool/int/float/str/datetime/date/time`, `Optional`/unions, `Literal`, `list[X]`, `list[Config]` (AoT), nested `Config`, `dict[str, X]`, `Enum`, `Annotated`. Anything else → "unsupported annotation".
- View semantics: defaults never persist; unknown keys preserved (strict mode errors); diff write-back; `None` on an Optional field deletes the key on save.

## Errors

| Error | Base | Raised for |
|---|---|---|
| `TOMLError` | `Exception` | hierarchy root |
| `TOMLParseError` | `TOMLError`, `ValueError` | syntax/semantic parse failure; carries `line`/`col`/`offset`/`segment` |
| `TOMLTypeError` | `TOMLError`, `TypeError` | non-representable values (e.g. `None` without `none_value`) — at assignment time, not render time |
| `ConfigError` | `TOMLError`, `ValueError` | schema-layer misuse |
| `FieldError` | — (dataclass-like) | one violation: `path`, message, optional `description` |
| `ValidationError` | `ConfigError` | aggregated `FieldError` list from `validate_dict`/`load` |
