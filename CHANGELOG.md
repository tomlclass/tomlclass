# Changelog

All notable changes to this project are documented in this file.

## Format

- Entry format: `## [x.y.z] - YYYY/MM/DD`, grouped by type (Added / Changed / Fixed / Breaking), with the contributor marked as `@GithubUsername`
- Multiple changes to the same topic are folded into their existing entry as the final state; no iterative "later fixed / no longer..." entries
- Changes introduced and reverted within the same version are not listed separately
- Test-only additions and internal tweaks without user impact are omitted
- The summary states the version theme and the 1-3 largest changes; upgrade notes give only conclusions and actions

## [0.1.3] - 2026/10/06

Conformance fix found by full JSON-semantic validation against toml-test 1.5.0.

### Fixed

- @wsu2059q
  - Escape-produced CR LF inside multiline basic strings (`\x0d\x0a`, `\u000d\u000a`) is no longer normalized away; only raw source newlines are normalized. The blanket post-parse `replace("\r\n", "\n")` clobbered characters that came from escapes — `valid/string/hex-escape.toml` was the visible casualty. toml-test 1.5.0: TOML-1.1 manifest 548/548 with full JSON-semantic comparison.

## [0.1.2] - 2026/10/06

TOML 1.1 support and a friendlier `dumps`.

**Summary**

tomlclass 0.1.2 implements the TOML 1.1 additions — `\e` and `\x` escapes, seconds omitted from times, newlines and trailing commas inside inline tables, and non-ASCII bare keys — scoring 548/548 on the official toml-test 1.5.0 TOML-1.1 manifest. `dumps()` now also accepts a plain `dict`, serializing it with the same engine (mapping-style APIs can switch to tomlclass without wrapping documents). Conformance to the TOML 1.0 manifest is unchanged except for the ten cases the 1.1 spec deliberately flips, which are now exercised as 1.1-valid.

**Upgrade notes**

- Files that are invalid under TOML 1.0 but valid under 1.1 (e.g. `17:45` times, trailing commas in inline tables, non-ASCII bare keys) now parse successfully. Code that relied on rejecting them must check the parsed structure instead.

### Added

- @wsu2059q
  - TOML 1.1: `\e` (ESC) and `\xHH` escapes in basic and multiline basic strings; `HH:MM` times and date-times with seconds omitted (rendering preserves the exact source spelling); newlines, comments and trailing commas inside inline tables; bare keys may contain non-ASCII characters (BOM excepted). Verified 548/548 against the toml-test 1.5.0 TOML-1.1 manifest.
  - `dumps()` accepts a plain `Mapping` alongside `Document`: the mapping is serialized through the engine (plain dicts become `[table]` blocks). `None` and non-mapping, non-Document inputs raise `TOMLTypeError` with the native message instead of an `AttributeError`.

### Changed

- @wsu2059q
  - Vendored toml-test corpus assertions updated: ten 1.0-invalid files that the 1.1 spec flips are now expected to parse; the five files the 1.5.0 TOML-1.1 manifest adds are vendored under `tests/corpus/toml-test-1.1/`.

## [0.1.1] - 2026/10/05

One-call updates and a documentation overhaul.

**Summary**

tomlclass 0.1.1 adds `tomlclass.update()` — read a file, assign dotted keys, atomically write it back with comments intact — and rewrites the documentation around end-to-end scenarios in all five languages. Validation errors now carry each field's schema description and state constraints in plain language. Fixes a write-back bug where saving a nested table absent from the file produced invalid TOML (a dotted key line plus an empty `[table]` header).

**Upgrade notes**

- Constraint-violation messages changed format (`value 70000 exceeds the maximum 65535` instead of `value 70000 > le(65535)`); code matching on the old message text must be updated. `FieldError` gains an optional `description` attribute; `path` / `message` semantics are unchanged.

### Added

- @wsu2059q
  - `tomlclass.update(path, updates)`: one-call lossless update — parses the file, applies each dotted-key assignment (missing keys and intermediate tables are created), atomically writes it back and returns the `Document`; nothing is written if any value cannot be represented in TOML.
  - `Document.set_path(dotted_path, value)`: engine-level dotted-path assignment behind `update()`.
  - `FieldError.description`: validation errors now include the field's description from the schema, pointing at the documented intent (the description is appended to the message text in parentheses).

### Changed

- @wsu2059q
  - Constraint-violation messages state the violated bound in plain language (`value 70000 exceeds the maximum 65535`, `length 2 is below the minimum 3`) instead of the internal comparison form (`value 70000 > le(65535)`).
  - Documentation rewritten around scenarios: safe pyproject updates, the app-config lifecycle (template → load → env → diff save), batch edits, AoT editing, hot reload, schema migration; the engine doc explains the span model; all five languages (en / ja / ru / zh-CN / zh-TW) refreshed.

### Fixed

- @wsu2059q
  - Writing back a nested table that was absent from the file no longer emits a dotted key line plus an empty `[table]` header (invalid TOML — the table was defined twice); it renders as a proper `[table]` block containing its entries.

## [0.1.0] - 2026/10/04

Initial release: engine, semantics and annotation layers.

**Summary**

tomlclass 0.1.0 provides a lossless TOML 1.0 engine and an annotation-based config layer. `parse -> edit -> dumps` round-trips byte-for-byte (the full toml-test 1.0 suite passes: 208 valid, 501 invalid). `Config` classes declare the schema and produce commented templates with aggregated validation. Parsing measures within 2x of tomli and 5.8-6.4x faster than tomlkit 0.15.1 on the same machine; `dumps` on an unedited document is approximately O(1). Zero third-party dependencies.

**Upgrade notes**

- First release; no upgrade path.

### Added

- @wsu2059q
  - Engine: single-pass character-dispatch parsing (precompiled regex block matching, no per-character loops), source-slice rendering, and a two-tier node model that materializes style data only on edit. Editing APIs (value changes, key/table creation, deletion, AoT append and whole replacement) preserve comments, ordering and formatting byte-for-byte. Untouched array `append` splices into the source, keeping existing elements and their comments intact. Atomic writes via tempfile + `os.replace`.
  - Error hierarchy: `TOMLError` base; `TOMLParseError` subclasses `ValueError` (matching `tomllib.TOMLDecodeError`) with `line` / `col` / `offset` / `segment`; `TOMLTypeError` subclasses `TypeError` and is raised when a value cannot be represented in TOML (`None`, functions, arbitrary objects).
  - Semantics: diff-based write-back (only changed keys are written), defaults merged in memory and never persisted, unknown keys preserved (`strict=True` rejects them, propagated through nested tables and unions), env overrides via `PREFIX__PATH` with best-effort type conversion, `None` on an Optional field deletes the key on save while `None` on a non-optional field raises `ConfigError`.
  - Annotation layer: `Config` / `Field` (nested classes as tables, docstring field sections as comments, `Literal` and numeric/length/pattern constraints, `coerce`), `template()` (byte-stable per schema), `validate_dict()` (aggregates all errors), `load()` (env prefix, `strict`, `comments` injection modes `none` / `missing` / `all`), `save()`, `watch()` (optional dependency watchfiles, `stop_event` supported), `migrate()` with `_migrate_key_map`.
  - Comment API: `Document.comment()` / `set_comment()` per key (comments are anchored to their key; replacement keeps the original leading whitespace, removal strips it), `to_dict()` builds a plain dict directly from the document, `find()` dotted-path lookup.
  - tomllib compatibility: `loads(text) -> dict` and `load(binary_fp) -> dict` follow the stdlib calling convention; `parse(text)` / `load(path) -> Document` keeps the lossless editing form.
  - Multi-line string rendering uses triple quotes with the opener alone on its first line; `'''` is used when the content conflicts with `"""` and needs no escapes.
  - Performance: parse within 2x of tomli (1.73x / 1.94x on two public benchmark corpora, same machine), 5.8-6.4x faster than tomlkit 0.15.1, unedited `dumps` approximately O(1), resident memory 0.67x tomlkit. Budgets are enforced in CI; baseline recorded in `tests/bench/BASELINE.md`.
  - Tests: the full toml-test 1.0 manifest (208 valid with semantic comparison plus byte-exact round-trip, 501 invalid rejected), round-trip axiom, style matrix, edit-semantics and schema-semantics tables; 765 tests total.
