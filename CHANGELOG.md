# Changelog

All releases follow [Semantic Versioning](https://semver.org/).

> **How to read this log**
> Each release is grouped into typed sections. Read the "Removed" and "Changed" sections of a release before upgrading.

> **Contributing entries**
> To add an entry for a new release, append it under the matching version number with the date and the main contributor. If an entry for the topic already exists, update it to its final state — do not append process notes (see "Writing rules" below).

---

## Rules

### Required information

1. **Contributor**: every change is attributed as `@GithubUsername`
2. **Change type**: sections follow the type taxonomy below
3. **Date**: release dates use the `YYYY/MM/DD` format

### Writing rules

The log records the **net difference between release states**, not the development process:

1. **Final state only**: multiple changes to the same topic within one release update the existing entry to its final state — no "later fixed / no longer…" process notes
2. **In-version fixes are not listed separately**: a defect introduced and fixed within the same release is folded into the feature entry it belongs to
3. **Reverts leave no trace**: features introduced and reverted before release are not recorded
4. **No trivia**: test-only additions, repository moves and internal tweaks without user impact are omitted
5. **Merge per topic**: multiple doc/test updates to the same module are merged into one entry
6. **Short summaries**: the **summary** is 2–3 sentences stating the release theme and the 1–3 largest changes; **upgrade notes** and **notes** give conclusions and actions only

### Change types

| Type | Label | Description | Example |
|------|-------|-------------|---------|
| Added | Added | New features, APIs or modules | New command system |
| Improved | Improved | Performance, UX or code improvements | Optimized memory usage |
| Changed | Changed | Behavior, config or API changes (non-breaking) | Adjusted default setting |
| Fixed | Fixed | Bug fixes | Fixed null pointer exception |
| Removed | Removed | Deleted features, APIs or modules | Removed deprecated API |
| Deprecated | Deprecated | Features planned for removal | Method scheduled for removal |
| Refactored | Refactored | Internal refactoring (no public API change) | Refactored loader architecture |
| Security | Security | Security fixes or hardening | Fixed permission vulnerability |

### Example format

```markdown
  ## [version] - 2025/08/20
  > Released

  **Summary**
  Two to three sentences on the release theme and the 1–3 largest changes.

  **Upgrade notes**
  - Recommended: upgrade / optional / skip
  - Reasons

  **Notes**
  - Important upgrade considerations
  - Deprecations
  - Compatibility changes

  ### Added

  - By [Contributor](https://github.com/contributor)
    - `module` feature description:
      - point 1
      - point 2

  ### Improved

  - @username
    - Optimized module performance
```

---

## [0.3.1] - Pending
> Pending release

**Summary**
Contract-and-consistency patch plus the first pydantic interop: comment reads now cover source comments everywhere, path and nesting errors fold into the documented `ValueError`/`TOMLParseError` contract, the `extra` option is validated and honored per mode — and `BaseModel` subclasses gain lossless TOML load/save with pydantic keeping full ownership of validation.

### Added

- @wsu2059q
  - `pydantic`: `TomlModel` (optional `tomlclass[pydantic]` extra) — a `BaseModel` base that loads from and saves to TOML losslessly; validation is delegated to pydantic (`model_validate`), tomlclass owns parsing, diffing and rendering; nested models become `[tables]`, `list[Model]` becomes `[[aot]]`, `Field(description=...)` and docstrings drive `template()`

### Fixed

- @wsu2059q
  - `engine`: `Table.comments[key]` reads source comments, not just runtime overrides — the whole view protocol (`in` / `len` / `iter` / `del`) covers both; source comments materialize byte-exact and render unchanged
  - `engine`: out-of-range `[int]` path indexes raise `ValueError` instead of `IndexError`, restoring the documented path-error contract
  - `engine`: documents nested deeper than 200 levels raise `TOMLParseError` instead of `RecursionError`, closing the last path that escaped the error contract
  - `engine`: editing a runtime-appended array element renders the new value instead of raising `IndexError`, keeping the parsed siblings' element comments
  - `engine`: `*= n` on an array or array-of-tables renders every copy (previously memory doubled while the output silently kept the old text); `*= 0` empties the array per list semantics
  - `engine`: appending or inserting an element that already belongs to an array-of-tables raises `TOMLTypeError` instead of rendering that element twice
  - `engine`: editing a runtime-appended array-of-tables element no longer emits its lines a second time
  - `engine`: `Table.popitem` follows the dict LIFO contract and registers the deletion on save (previously it popped the first key and left the line rendered)
  - `config`: the `extra` mode is validated at class definition — invalid values (including `"Forbid"`) raise `ConfigError` instead of silently disabling strictness
  - `config`: `extra="allow"` now exposes unknown keys on the instance and in `to_dict()` (previously `allow` and `ignore` behaved identically)
  - `config`: self-referencing annotations (`children: list["Node"]`) resolve correctly; `env_prefix="APP_"` (trailing underscore) now behaves identically to `"APP"`

## [0.3.0] - 2026/10/08
> Released

**Summary**
Maturity release: the public API is generalized around a unified path grammar (quoted keys, `[int]` AoT indexing), a complete Document mapping protocol, a from-scratch construction API, addressable comments on every target, and an extended declarative Config layer — with parser conformance verified against both official toml-test manifests on every commit.

**Upgrade notes**
- Recommended for new projects; existing code should review the breaking surface below (complete list in the [migration guide](docs/en/migration.md)).
- Non-ASCII bare keys are rejected per the official v1.1.0 spec — quote them.
- `import tomlclass.document` no longer works (`tomlclass.document()` is a constructor now).
- `to_dict()` returns standard-library datetime objects; `Table` mutators now affect rendered output.

### Added

- @wsu2059q
  - `engine`: unified path grammar across `find` / `set_path` / `comment` / `set_comment` / `update` — quoted keys (`"a.b"`), `[int]` array-of-tables indexing (`it[0].n`); unindexed AoT segments project on reads and broadcast on writes, indexed ones address exactly
  - `engine`: full `MutableMapping` protocol on `Document` (value-based `==`, `keys`/`items`/`pop`/`setdefault`/`|`, …) and a hardened `Table` surface with `to_dict()` and string-keyed `comments[key]` — every dict mutator routes through the edit engine
  - `engine`: construction API `document()` / `table()` / `inline_table()` / `aot()` / `comment()` / `nl()` plus `dump(obj, fp)` and `load_path(path)`; `unwrap()` / `as_string()` / `add()` provide tomlkit-shaped aliases
  - `engine`: comments are addressable on tables, dotted keys, API-created keys and AoT element fields; `Table.comments[key]` reads and writes them as strings
  - `config`: `dict[str, X]`, `Enum` and `Annotated[X, Field(...)]` annotations, `Field(default_factory=...)`, `Config.to_dict()` / `reload()`, `validate_assignment` and `extra` class options, same-line docstring field comments, wrapped template comments
  - `tests`: property-based coverage (hypothesis) for the four invariants — byte-exact round-trip, comment survival, defaults-never-persist, CRLF fidelity

### Fixed

- @wsu2059q
  - `engine`: a value missing after `=` raises `TOMLParseError` instead of `IndexError`, honoring the error contract on every entry point
  - `engine`: writing a key into an implicit parent table (`[db.pool]` present, `[db]` never declared) renders a proper `[db]` block — previously the dotted line landed inside the last defined block's scope, silently changing the key's meaning
  - `engine`: newly created root-level tables render at the end of the file instead of right after the first key-value line
  - `engine`: bare keys are ASCII-only in both TOML versions, matching the official TOML v1.1.0 spec (non-ASCII keys use quotes)
  - `config`: `template()` renders `Enum` defaults as their raw member values — previously plain `Enum` fields crashed template generation and `IntEnum` fields produced invalid TOML

### Changed

- @wsu2059q
  - `tests`: the toml-test conformance suite covers both official manifests (`files-toml-1.0.0` under strict 1.0 and `files-toml-1.1.0` under 1.1) against a live, pinned toml-test checkout instead of a vendored snapshot with a hand-maintained whitelist; CI fetches it and runs the full suite on Linux, Windows and macOS
  - `engine`: `to_dict()` returns standard-library `datetime` / `date` / `time` objects instead of private parser subclasses
  - `engine`: `Table.update` / `setdefault` / `pop` / `popitem` / `clear` route through the edit engine and now affect the rendered output (previously they mutated memory only)
  - `engine`: malformed dotted paths raise `ValueError` instead of silently mismatching

### Removed

- @wsu2059q
  - `engine`: the `tomlclass.document` submodule name — `tomlclass.document()` is now the from-scratch constructor; import `tomlclass._document` if the module object is needed

## [0.2.1] - 2026/10/06
> Released

**Summary**
Editing-correctness release: fixes how arrays (single-level, nested, CRLF, mixed operation sequences) and chained same-key replacements land on save, plus type-conversion and persistence fixes in the annotation layer.

**Upgrade notes**
- Recommended. Fixes concentrate on edit/save paths; nothing was removed. Two behavior changes to note:
- `sort()` / `reverse()` on an array of tables now raise `NotImplementedError` — they previously reordered memory without ever rendering; replace the AoT wholesale via `doc[key] = [...]` instead.
- A dotted path that passes through an `[[aot]]` segment addresses **every** element: `find("it.n")` returns the list of per-element values, `set_path()` / `update()` assign into every element. Address a single element via `doc["it"][i]`.

**Notes**
- Env overrides gained a compatible `PREFIX__FIELD` form; the existing `PREFIX_FIELD` form is unaffected.

### Fixed

- @wsu2059q
  - `engine`: array edits, appends, insertions and clears now land correctly across single-level, nested, CRLF and mixed operation sequences — siblings and element comments are preserved
  - `engine`: chained same-key replacements (scalar ↔ table ↔ array) keep only the final definition, without duplicate definitions or leftover blocks
  - `engine`: newly appended AoT elements land at the end of the array (previously inserted before the last element on multi-element arrays)
  - `engine`: AoT element APIs follow list semantics — `insert(index, element)` renders the new element as a block at the given position (the index was ignored and every insert landed at the end), `extend()` and `+=` render their new elements (AoT extensions existed only in memory and were silently dropped on save), and a user-built `Table` passed as an element no longer re-emits its construction-time entries
  - `engine`: `aot[index] = {...}` replaces the element in place, rendering a block at its position (previously raised `IndexError`); `sort()` / `reverse()` on an AoT raise `NotImplementedError` instead of silently reordering memory without rendering
  - `engine`: assigning a table or AoT back to its own key (`doc[k] += items`, `t = doc["t"]; doc["t"] = t`) is a no-op — previously it wiped the entry or emitted a duplicate header; replacing an AoT with a list containing its own elements raises instead of silently dropping them
  - `engine`: files are read without universal-newline translation, preserving CRLF across the whole cycle; generated lines follow the file's line endings
  - `config`: `Field(coerce=True)` conversions take effect; `list[Config]` elements load as instances and per-element edits persist; in-place `List` mutations persist
  - `config`: `i18n_resolver` overrides on subclasses are honored; `Literal` enum validation implemented (with strict bool/int distinction)
  - `config`: `template()` emits type-correct placeholders for required non-string fields
  - `config`: `comments` injection covers `[[aot]]` element fields
  - `engine`: `find()` resolves AoT paths — a `[[products]]` segment projects the rest of the path over the elements (`find("products.name")` returns the list of values, `None` for elements missing the key), and `set_path()` broadcasts into every element; `InlineTable` accepts initial mappings and renders inline; non-string keys no longer raise `TypeError`

## [0.2.0] - 2026/10/06
> Released

**Summary**
Selectable TOML semantics: every parse-facing entry point accepts a `toml_version` parameter (1.1 by default, 1.0 for strict legacy rejection), and a rtoml-style `none_value` sentinel round-trips `None` through TOML strings.

**Upgrade notes**
- Optional. Skip if you do not use version selection or None sentinels.

**Notes**
- Default semantics remain TOML 1.1 (unchanged since 0.1.2); code relying on rejecting 1.0-invalid input must pass `toml_version="1.0"`.

### Added

- @wsu2059q
  - `engine`: `toml_version` parameter on `parse` / `loads` / `load` / `update` / `Config.load`
  - `config`: `none_value` sentinel parameter on `dumps` / `loads` / `load` / `update`

## [0.1.3] - 2026/10/06
> Released

### Fixed

- @wsu2059q
  - `engine`: escape-produced CR LF inside multiline basic strings is no longer normalized away

## [0.1.2] - 2026/10/06
> Released

### Added

- @wsu2059q
  - `engine`: TOML 1.1 features — `\e` / `\xHH` escapes, seconds omitted from times, newlines and trailing commas in inline tables, non-ASCII bare keys (548/548 on the toml-test 1.5.0 TOML-1.1 manifest)
  - `engine`: `dumps()` accepts a plain `Mapping`

## [0.1.1] - 2026/10/05
> Released

### Added

- @wsu2059q
  - `engine`: `update()` and `Document.set_path()` for one-call lossless updates
  - `config`: `FieldError.description` on validation errors

### Changed

- @wsu2059q
  - `config`: validation messages state constraints in plain language

### Fixed

- @wsu2059q
  - `engine`: writing back a nested table absent from the file no longer emits invalid TOML

## [0.1.0] - 2026/10/04
> Released

**Summary**
Initial release: lossless TOML 1.0 editing engine plus typed config annotations, zero third-party dependencies.

**Notes**
- First release; no upgrade path.

### Added

- @wsu2059q
  - `engine`: lossless editing — parse → edit → dumps byte-for-byte; full toml-test 1.0 conformance (208 valid / 501 invalid)
  - `config`: `Config` / `Field` declarative layer — templates, aggregated validation, diff write-back, env overrides, hot reload
  - Performance: parse ≤2× tomli, 5.8–6.4× faster than tomlkit; unedited dumps ≈ O(1)
