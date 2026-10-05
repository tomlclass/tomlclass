# Engine

The engine targets any TOML 1.0 document: parse, read, edit, render, atomic save — with comments and formatting preserved byte-for-byte.

## Parse and render

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # parse from a file path
doc.dumps()                      # render to str: byte-identical to input when unedited
doc.save(path)                   # atomic write (tempfile + os.replace)
```

**Round-trip axiom**: `parse(text).dumps() == text` holds byte-for-byte, verified on every PR.

## tomllib compatibility

```python
data = tomlclass.loads(text)  # plain dict, same convention as tomllib.loads
data = tomlclass.load(fp)     # binary file object, same convention as tomllib.load
```

## Editing

```python
doc["project"]["version"] = "1.0.0"   # modify: only the value changes on that line
del doc["tool"]["old"]                # delete: comment and leading whitespace removed cleanly
doc["server"]["workers"] = 4          # new key: rendered after the table's last entry
doc["logging"] = {"level": "info"}    # new table: rendered as a [logging] block
doc["products"].append(...)           # array append: spliced in place, existing elements untouched
doc["products"] = [...]               # AoT whole replace: old elements removed, new ones as blocks
```

- Edits use canonical rendering: newly written values use standard formatting
- Untouched parts read directly from source slices
- Inline tables are closed: reassign the whole value instead

## Comments

```python
doc.comment("server.port")            # -> "the port" (None when absent)
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # remove (with leading whitespace)
```

A comment belongs to the key it trails; table comments live on the header line, addressed by the table path.

## Errors

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` is a `ValueError` subclass. Assigning non-serializable values (`None`, functions, …) raises `TOMLTypeError` (a `TypeError` subclass).
