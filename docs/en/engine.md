# Engine

The engine targets any TOML 1.0 document: parse, read, edit, render, atomic save — with comments and formatting preserved byte-for-byte.

## Parse and render

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # parse from a file path -> Document
doc.dumps()                      # render to str: byte-identical to input when unedited
doc.save(path)                   # atomic write (tempfile + os.replace)
```

**Round-trip axiom**: `parse(text).dumps() == text` holds byte-for-byte, verified on every commit by the toml-test 1.0 suite (all 208 valid files round-trip exactly; all 501 invalid files are rejected).

## How preservation works

Untouched nodes store only their `(start, end)` span in the source; rendering slices the original text. Formatting is not recorded anywhere — it *is* the source text, and it survives by simply not being touched. Only when a node is edited does tomlclass materialize rendered output for it (canonical formatting), while everything else stays source-sliced.

Consequences: an unedited `dumps` is approximately O(1), the read path carries no formatting data at all, and edit cost scales with edit size rather than document length.

## tomllib compatibility

```python
data = tomlclass.loads(text)  # plain dict, same convention as tomllib.loads
data = tomlclass.load(fp)     # binary file object, same convention as tomllib.load
```

## Editing

```python
doc["project"]["version"] = "1.0.0"   # modify: only the value on that line changes
del doc["tool"]["old"]                # delete: trailing comment removed cleanly
doc["server"]["workers"] = 4          # new key: rendered after the table's last entry
doc["logging"] = {"level": "info"}    # new table: rendered as a [logging] block
doc["products"].append(...)           # array append: spliced in place, existing elements untouched
doc["products"] = [...]               # AoT whole replace: old elements removed, new ones as blocks
```

- Edited values use canonical rendering; untouched parts read directly from source slices
- Inline tables are closed: reassign the whole value instead of adding keys to them
- Tables created by dotted keys are sealed: keys added to them render as dotted lines anchored to their last physical line

### Dotted-path access

```python
doc.find("server.port")            # -> value or None
doc.set_path("server.port", 9090)  # assign; missing keys and intermediate tables are created
```

`set_path` builds missing tables as real `[table]` blocks containing their entries — never as a dotted line plus an empty header (which would define the table twice).

## One-call update

```python
tomlclass.update("app.toml", {"server.port": 9090, "name": "prod"})
```

Reads the file, applies every dotted-key assignment, atomically writes it back, and returns the `Document`. If any value cannot be represented in TOML, nothing is written. `None` is not a TOML value — delete keys through the mapping API (`del doc[...]`) instead.

## Comments

```python
doc.comment("server.port")            # -> "the port" (None when absent)
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # remove (with leading whitespace)
```

A comment belongs to the key it trails; table comments live on the header line, addressed by the table path. See [Comments](comments.md) for the full model.

## Errors

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` is a `ValueError` subclass. Assigning non-serializable values (`None`, functions, arbitrary objects) raises `TOMLTypeError` (a `TypeError` subclass) at assignment time, not at render time.
