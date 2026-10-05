# Changelog

All notable changes to this project are documented in this file.

## Format

- Entry format: `## [x.y.z] - YYYY/MM/DD`, grouped by type (Added / Changed / Fixed / Breaking), with the contributor marked as `@GithubUsername`
- Multiple changes to the same topic are folded into their existing entry as the final state; no iterative "later fixed / no longer..." entries
- Changes introduced and reverted within the same version are not listed separately
- Test-only additions and internal tweaks without user impact are omitted
- The summary states the version theme and the 1-3 largest changes; upgrade notes give only conclusions and actions

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
