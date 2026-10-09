# tomlclass Docs

tomlclass is a TOML configuration library: a lossless editing engine plus typed config annotations. Zero third-party dependencies, Python ≥ 3.10.

Two layers, each usable on its own:

- **Engine** — parse any TOML 1.0/1.1 document, edit it, write it back with every comment, key order and formatting quirk intact.
- **Annotations** — declare a config schema as Python classes to get a commented template, aggregated validation and diff-based write-back.

## 60-second tour

Change one value without touching anything else:

```python
import tomlclass

tomlclass.update("app.toml", {"server.port": 9090})
# only that line changed — comments, ordering and formatting all intact
```

Or manage a config file through a schema:

```python
from tomlclass import Config

class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")  # parse + validate + merge defaults
server.port = 9090
server.save("server.toml")           # diff write-back: only changed keys are written
```

## Contents

| Doc | Contents |
|---|---|
| [Engine](engine.md) | parse, edit, `update()`, comment API, errors |
| [Config](config.md) | schema declaration, template, load/save semantics, validation errors |
| [Comments](comments.md) | comment ownership, injection modes |
| [Examples](examples.md) | end-to-end scenarios: pyproject updates, app config lifecycle, AoT, hot reload |
| [Migration](migration.md) | from tomlkit, and from tomlclass 0.2.x |

Contributor-facing: [Skills](skills/index.md) (task playbooks) and [Reference](reference/index.md) (architecture and fact sheets).

## Installation

```bash
pip install tomlclass
```
