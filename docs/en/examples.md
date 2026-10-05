# Examples

End-to-end scenarios; every snippet runs as-is.

## Safely update a third-party TOML (pyproject-style)

You only want to bump a version or flip a flag in a file owned by another tool — without destroying its comments:

```python
import tomlclass

tomlclass.update("pyproject.toml", {
    "project.version": "1.0.0",
    "tool.mytool.cache": True,       # creates [tool.mytool] if absent
})
```

Every untouched line — other tools' comments, odd spacing, key order — is byte-identical afterwards.

For anything more surgical, use the engine directly:

```python
doc = tomlclass.load("pyproject.toml")

doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, the
                                                     # "click" comment survives
doc["tool"]["mytool"] = {"cache": True}              # rendered as a [tool.mytool] block
doc.save("pyproject.toml")
```

## App config: first run to steady state

A typical application lifecycle: ship a commented template on first run, validate and merge on later runs, write back only what changed.

```python
from pathlib import Path

from tomlclass import Config, Field

class Server(Config):
    """HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)


class App(Config):
    """Application configuration."""

    name: str = "demo"
    debug: bool = False
    server: Server


CONFIG = Path("app.toml")


def load_config() -> App:
    if not CONFIG.exists():
        CONFIG.write_text(App.template(), encoding="utf-8")  # first run: commented template
    return App.load(CONFIG, env_prefix="APP")                # validate + defaults + env overrides


app = load_config()
app.debug = True
app.save(CONFIG)  # diff write-back: only debug changed; user comments survive
```

What the user sees when a value is invalid:

```
ValidationError: 1 validation error(s): server.port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

The description comes straight from the schema docstring — the error points at the documented constraint, not just a number.

## Batch edits with full control

```python
import tomlclass

doc = tomlclass.load("app.toml")

doc.set_path("server.port", 9090)          # change; comment on that line survives
doc.set_path("logging.level", "debug")     # creates the [logging] table
doc.set_comment("server.port", "exposed")  # replace the comment too
doc.save("app.toml")                       # one atomic write
```

## Arrays of tables (AoT)

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})  # append: rendered as a new block
doc["products"] = [{"name": "sofa"}]      # whole replace: old elements removed
```

## tomllib migration

```python
data = tomlclass.loads(text)   # plain dict (same convention as tomllib.loads)
data = tomlclass.load(fp)      # binary file object (same convention as tomllib.load)

# Upgrade to lossless editing when needed:
doc = tomlclass.load("pyproject.toml")  # path argument -> Document
```

## Env overrides and hot reload

```python
# APP_SERVER__PORT=9000 overrides server.port (__ separates path segments)
server = Server.load("server.toml", env_prefix="APP")

# Hot reload (optional dependency watchfiles); stop_event stops from another thread.
# Validation failures keep the previous good instance and watching continues.
Server.watch("server.toml", callback, stop_event=event)
```

## Schema migration

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
