# Examples

The snippets below can be copied and run as-is.

## Editing a third-party TOML (pyproject-style)

```python
import tomlclass

doc = tomlclass.parse(pyproject_text)

doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, the
                                                     # "click" comment survives
doc["tool"]["mytool"] = {"cache": True}              # rendered as a [tool.mytool] block
```

## App config read/write

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp) / "server.toml"
    cfg.write_text("port = 8080  # exposed\n", encoding="utf-8")

    server = Server.load(cfg)
    server.port = 9090
    server.save(cfg)
    # Result: only the port line changed, the "# exposed" comment survives
```

## Arrays of tables (AoT)

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})             # append: rendered as a new block
doc["products"] = [{"name": "sofa"}]                 # whole replace: old elements removed
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
# DEMO_SERVER__PORT=9000 overrides server.port
server = Server.load(cfg, env_prefix="DEMO")

# Hot reload (optional dependency watchfiles); stop_event stops from another thread
Server.watch("server.toml", callback, stop_event=event)
```

## Schema migration

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
