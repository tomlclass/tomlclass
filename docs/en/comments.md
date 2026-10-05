# Comments

A comment belongs to the key it trails; table comments live on the header line, addressed by the table path.

## Engine

```python
doc = tomlclass.parse('port = 8000  # the port\n')

doc.comment("port")               # -> "the port" (None when absent)
doc.set_comment("port", "API port")
doc.set_comment("port", None)     # remove (with leading whitespace)
```

- Replacement keeps the original leading whitespace; removal strips it cleanly
- Deleting a key removes its trailing comment; standalone full-line comments stay in place

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
