# Comments

A comment belongs to the key it trails; table comments live on the header line, addressed by the
table path; array-of-tables element fields are addressed with an index.

## Addressability

Every target below works with `doc.comment(path)` / `doc.set_comment(path, text | None)`:

| Target | Path | Notes |
|---|---|---|
| key-value line | `server.port` | replacement keeps the original leading whitespace; `None` strips it cleanly |
| table header line | `server` | `[db] # note` — spliced in place, appended when absent |
| dotted-key leaf | `a.b` | resolved to the physical dotted line |
| API-created key | `t.fresh` | renders on the generated `key = value  # comment` line |
| AoT element field | `products[0].name` | explicit index required — an unindexed AoT segment is ambiguous and resolves to `None` |

Standalone layout lines attach through `doc.add(tomlclass.comment("text"))` / `doc.add(tomlclass.nl())`.

## Engine

```python
doc = tomlclass.parse('port = 8000  # the port\n')

doc.comment("port")               # -> "the port" (None when absent)
doc.set_comment("port", "API port")
doc.set_comment("port", None)     # remove (with leading whitespace)
```

- Replacement keeps the original leading whitespace; removal strips it cleanly
- Deleting a key removes its trailing comment; standalone full-line comments stay in place
- Every entry above survives read-edit-save cycles, including comments on API-created keys

## Annotation layer: parameterized injection

The `comments` parameter of `Config.load` controls whether schema descriptions are injected as comments:

| Mode | Behavior |
|---|---|
| `"none"` (default) | File kept exactly as written |
| `"missing"` | Inject the docstring description only for keys that have no comment and exist in the file |
| `"all"` | Rewrite comments for all schema fields present in the file |

Invariants: defaults never materialize (keys not in the file are not injected); unknown keys and their comments are preserved as-is.

## Multi-line strings

String values containing newlines render as multi-line strings: `"""` is preferred; when the content conflicts with `"""` and needs no escapes, `'''` is used instead. The opener sits alone on the first line — content starts on the next line, even when the content is a single line.
