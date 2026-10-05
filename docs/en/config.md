# Annotations

Declare the config structure as classes: the docstring is the template comments, reads are validated, write-back touches only changed keys.

## Declaration

```python
from tomlclass import Config, Field

class Server(Config):
    """
    HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = 8000


class App(Config):
    name: str = Field("demo", ge=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- The docstring's first paragraph becomes the table comment; `field:` sections become comments above keys (rendered as `#` lines in the template)
- Nested class = nested table; `list[T]` supports element validation; underscore-prefixed fields are excluded
- `Field` constraints: `ge / le / gt / lt / pattern / min_length / max_length / coerce`
- Field descriptions support i18n dicts: `Field(description={"i18n": key, "default": text})`

## Entry points

```python
app = App()                        # pure defaults (in memory)
app = App.load("app.toml")         # parse + validate + merge defaults
text = App.template()              # commented template (byte-stable per schema)
errors = App.validate_dict(raw)    # offline validation, aggregates all errors
app.save("app.toml")               # diff write-back (atomic)
```

## View semantics

1. Defaults never persist — the file only contains keys the user changed
2. Unknown keys are preserved (`strict=True` turns this into an error)
3. Diff write-back — compared against the parse-time snapshot, only changed keys are written
4. `None` on an Optional field = the key is deleted on save; `None` on a non-optional field raises `ConfigError` on save
5. Atomic write — tempfile + `os.replace`

## Env overrides and hot reload

```python
# MYAPP_SERVER__PORT=9000 overrides server.port (__ separates path segments,
# best-effort conversion to the annotated type)
app = App.load("app.toml", env_prefix="MYAPP")

# Hot reload: optional dependency watchfiles; validation failures keep the
# previous good instance and watching continues. stop_event stops it.
Server.watch("server.toml", callback, stop_event=event)
```

## Migration

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
