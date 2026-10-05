# Config

Declare the config structure as classes: the docstring becomes the template comments, reads are validated, write-back touches only changed keys.

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
    name: str = Field("demo", min_length=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- The docstring's first paragraph becomes the table comment; `field:` sections become comments above keys (rendered as `#` lines in the template). Both multi-line and same-line formats work: `host: the bind address` is equivalent to a `host:` section
- Nested class = nested table; `list[T]` supports element validation; underscore-prefixed fields are excluded
- `Field` constraints: `ge / le / gt / lt / pattern / min_length / max_length / coerce`
- `Field(default_factory=list)` produces a fresh mutable default per instance (class-level `= []` defaults are shared — prefer the factory)
- `Annotated[int, Field(ge=1)]` declares options next to the type — equivalent to a class-level `Field`
- Field descriptions support i18n dicts: `Field(description={"i18n": key, "default": text})`

## Supported annotations

`bool / int / float / str / datetime / date / time`, `Optional[X]` and unions, `Literal[...]`,
`list[X]`, `list[Config]` (an `[[aot]]` — diffed per element field), nested `Config`,
**`dict[str, X]`** (round-trips as an inline table), **`Enum`** (stored as the member's value,
loaded back as the member) and **`Annotated[X, Field(...)]`**. Anything else reports an
"unsupported annotation" error.

## Entry points

```python
app = App()                        # pure defaults (in memory, no validation — use load() for validated instances)
app = App.load("app.toml")         # parse + validate + merge defaults
text = App.template()              # commented template (byte-stable per schema)
errors = App.validate_dict(raw)    # offline validation, aggregates all errors
app.save("app.toml")               # diff write-back (atomic)
app.to_dict()                      # plain nested dict (nested Config -> dicts, Enum -> values)
app.reload()                       # re-read the file this instance was loaded from
```

## Class options

Declared as annotated class attributes (an unannotated assignment would become a field):

```python
class App(Config):
    extra: ClassVar[str] = "forbid"              # "allow" (default) | "ignore" | "forbid" — unknown keys
    validate_assignment: ClassVar[bool] = True   # validate and coerce on attribute assignment

    name: str = "demo"
```

- `extra="forbid"` turns unknown keys into validation errors at `load` / `validate_dict`
- `validate_assignment=True` validates every `app.name = ...` assignment immediately
  (raises `ValidationError` on mismatch, applies `coerce` conversions)

## Validation errors

`validate_dict` and `load` aggregate **all** violations into one `ValidationError` instead of failing on the first. Each `FieldError` states the dotted path, what is wrong, and — when the field has a description — the field's documented intent:

```python
class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = Field(8000, ge=1, le=65535)


Server.validate_dict({"port": 70000})
# ValidationError: 1 validation error(s): port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

The message names the violated bound in plain language and points at the schema description, so the fix is usually obvious without opening the schema source.

## View semantics

1. Defaults never persist — the file only contains keys the user changed
2. Unknown keys are preserved (`strict=True` turns this into an error, propagated through nested tables)
3. Diff write-back — compared against the parse-time snapshot, only changed keys are written
4. `None` on an Optional field deletes the key on save (a no-op when the key was never in the file); `None` on a non-optional field raises `ConfigError` on save
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
