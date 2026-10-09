# Architecture Reference

Facts about the `src/tomlclass/` codebase. Verified against the source on 2026-10; keep in sync when the code changes.

## Module map

| Module | Lines* | Role |
|---|---|---|
| `parser.py` | ~880 | Text → CST. Produces the node tree plus `parts`, the ordered list of source spans. Enforces TOML 1.1 by default and strict 1.0 on `toml_version="1.0"`. |
| `nodes.py` | ~640 | CST node types: `Table`, `InlineTable`, `Array`, `ArrayOfTables`, `Trivia` (standalone comment/blank lines). Carries `(start, end)` source spans; mutators are the engine hooks. |
| `engine_set.py` | ~260 | `engine_set` / `engine_del` / `mark_dead`: every mutation flows through here; decides what gets spliced, re-rendered or deleted. |
| `render.py` | ~450 | Canonical rendering of dirty nodes; untouched output comes from slicing the source, not from stored formatting. |
| `_document.py` | ~540 | `Document`: `MutableMapping` facade over the root table, path grammar (`find`/`set_path`/`comment`/`set_comment`), `dumps`/`save` (atomic tempfile + `os.replace`). |
| `schema.py` | ~1110 | Annotation layer: `Config`/`Field`, docstring → template comments, validation with aggregated errors, env overrides, diff write-back, hot reload, migration. |
| `pydantic.py` | ~430 | Optional interop (`TomlModel`): pydantic validates, tomlclass owns lossless load/save with element-wise AoT diff. |
| `errors.py` | ~120 | `TOMLError` hierarchy (see [API surface](api-surface.md#errors)). |
| `__init__.py` | ~320 | Public API re-exports, `__all__`, module-level entry points (`parse`/`loads`/`load`/`dumps`/`dump`/`update`/`load_path`, construction helpers). |

\* line counts are approximate; check `wc -l` before quoting them elsewhere.

## The pipeline

```
source text
   │  parser.py (1.1 default / 1.0 strict)
   ▼
CST: Table / Array / ArrayOfTables nodes, each with source spans
   │  Document._document.py (MutableMapping + path grammar)
   ▼  mutations
engine_set.py  — engine_set / engine_del / mark_dirty
   │
   ▼  dumps()/save()
render.py — untouched nodes: slice source verbatim; dirty nodes: canonical render
   │
   ▼
schema.py / pydantic.py — validation & diff write-back on top of the same Document
```

## Why preservation is byte-exact

Untouched nodes store **no formatting data at all** — only their `(start, end)` span. Rendering slices the original text, so "preserving" untouched output is just *not touching it*. Only edited nodes materialize canonical render output. Consequences:

- unedited `dumps()` is cheap and trivially idempotent (double-`dumps()` is asserted in tests);
- edit cost scales with edit size, not document length;
- any code path that rebuilds an untouched node is a defect (see [Invariants](invariants.md)).

## Edit routing rule

Every `Table`/`Array` mutator (`__setitem__`, `append`, `insert`, `pop`, …) routes through the engine hooks. This is what keeps the in-memory tree and rendered output from diverging — the reason `Table.update/setdefault/...` silently skipping the engine was a real 0.3.0 bug (fixed; see `docs/en/migration.md`). Adding a mutator that writes the underlying dict/list directly reintroduces that class of bug.

## Data boundary notes

- Files are read via `read_bytes()` — no universal-newline translation, CRLF stays CRLF; generated lines follow the file's endings; `\r` inside assigned strings is escaped.
- TOML has no null: `None` raises `TOMLTypeError` unless `none_value` sentinel mode is used; Optional schema fields delete their key on save.
- Non-ASCII bare keys are rejected per the official v1.1.0 spec — quoted keys are first-class everywhere (path grammar included).
