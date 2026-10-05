# Migration

## From 0.2.x to 0.3.0

0.3.0 generalizes the public API. Everything below is the complete breaking surface:

| Change | 0.2.x | 0.3.0 |
|---|---|---|
| Non-ASCII bare keys | accepted by default (1.1 draft behavior) | rejected per the official v1.1.0 spec — quote them (`"κ" = 1`) |
| `import tomlclass.document` | submodule | renamed to `tomlclass._document`; `tomlclass.document()` is now a constructor |
| `doc.to_dict()` datetimes | private `_Date`/`_DateTime` subclasses | standard `datetime`/`date`/`time` |
| `Table.update/setdefault/pop/popitem/clear` | silently skipped the edit engine (output unchanged) | routed through the engine — output reflects them |
| `doc.add(key, value)` | — | new; raises `KeyError` when the key exists |
| malformed dotted paths (`"a..b"`, `"a[01]"`) | silently mismatched | `ValueError` from every entry point |
| new root-level tables | rendered right after the first key-value line | rendered at the end of the file |
| implicit parent writes (`[db.pool]` + `doc["db"]["host"]`) | dotted line landed inside the wrong block (corrupted semantics) | proper `[db]` block at the end of the file |
| `find`/`set_path` quoted keys and `[int]` indexing | not recognized | first-class (see [Engine](engine.md#path-addressing)) |

New since 0.2.x: `document()` / `table()` / `inline_table()` / `aot()` / `comment()` / `nl()`,
`dump()` / `load_path()`, `unwrap()` / `as_string()` / `add()`, `Table.to_dict()` /
`Table.comments[key]`, `doc.comment("it[0].n")`, header and API-created-key comments,
`Config` `dict[str, X]` / `Enum` / `Annotated[X, Field(...)]` / `default_factory` / `to_dict()` /
`reload()` / `validate_assignment` / `extra`.

## From tomlkit

tomlclass covers the core editing surface with the same call shapes — and keeps your comments at a
fraction of the cost. Schema validation (`Config`/`Field`) has no tomlkit equivalent.

| tomlkit | tomlclass | Notes |
|---|---|---|
| `tomlkit.parse(text)` | `tomlclass.parse(text)` | returns `Document` (a full `MutableMapping`) |
| `tomlkit.loads` / `dumps` | `tomlclass.loads` / `dumps` | same conventions |
| `tomlkit.dump(o, fp)` / `load(fp)` | `tomlclass.dump(o, fp)` / `load(fp)` | `load` is dual-mode: a path returns a `Document` — prefer `load_path` |
| `doc.unwrap()` / `doc.as_string()` | same names | |
| `tomlkit.document()` / `table()` / `inline_table()` / `aot()` | `tomlclass.document()` / `table()` / `inline_table()` / `aot()` | |
| `tomlkit.comment("x")` / `nl()` | `tomlclass.comment("x")` / `nl()` | attach via `doc.add(...)`; `ws()` is not provided |
| `doc.add(key, value)` | same | raises `KeyError` when the key already exists |
| `doc["a"] = 1` | same | edits splice in place; untouched lines stay byte-identical |
| `doc.body` | — | edit through the mapping API or build with `document()`; comments for new keys via `set_comment` |
| `register_encoder` / item types (`item()`, `string()`, …) | — | not provided: values stay plain Python types |
