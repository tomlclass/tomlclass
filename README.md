[**English**](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

Lossless TOML editing and typed configuration in one zero-dependency package.

Change one value in a config file without breaking a single comment; declare schemas as Python classes to get commented templates, aggregated validation and diff-based write-back.

<p>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/pypi/v/tomlclass?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/tomlclass/actions/workflows/code-quality-check.yml"><img src="https://img.shields.io/github/actions/workflow/status/wsu2059q/tomlclass/code-quality-check.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/tomlclass/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge" alt="Ruff"></a>
</p>

<br clear="both">

---

## Features

- **Lossless editing engine**: full-type TOML 1.0 parse and write-back; all 709 toml-test 1.0 cases pass. Untouched documents render byte-identical to input
- **One-line updates**: `tomlclass.update("app.toml", {"server.port": 9090})` — read, change, atomically write back; comments, ordering and formatting survive everywhere else
- **Typed config**: declare the schema as classes — docstrings become template comments, validation aggregates all errors with each field's documented intent, defaults are merged in memory and never written back
- **Comment operations**: read, replace and delete comments per key; schema descriptions can be injected as comments (three strategies)
- **tomllib compatible**: `loads` / `load` follow the stdlib calling convention — migrating costs nothing

## Why not tomlkit

tomlkit is the de facto standard for lossless editing, and this project's engine was built against it as a baseline. Where tomlclass wins:

| Dimension | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| Parse speed (same machine) | baseline | **5.8–6.4× faster** |
| Getting a plain dict | `parse(dumps(doc))` round trip | `to_dict()` builds it directly, zero round trip |
| Comment operations | buried in style objects, no per-key API | `doc.comment(key)` / `set_comment` as first-class citizens |
| Schema / template / validation | none — assemble it yourself | built into `Config` (template, aggregate validation, env overrides, migration) |
| Resident memory | baseline | **0.67×** |

Source: [performance baseline](tests/bench/BASELINE.md) (same machine, same iteration count).

## Installation

```bash
pip install tomlclass
```

## Usage

### Change one value, keep everything else

```python
import tomlclass

tomlclass.update("pyproject.toml", {"project.version": "1.0.0"})
# only that line changed — comments, ordering and formatting all intact
```

### Editing a TOML file (full control)

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, comments kept
text = doc.dumps()                                   # only touched lines change
```

### Declarative config

```python
from tomlclass import Config

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


server = Server.load("server.toml")  # read + validate + merge defaults
server.port = 9000
server.save("server.toml")           # only changed keys are written
```

## Documentation

- [Engine](docs/en/engine.md) — parse, edit, `update()`, comment API, errors
- [Config](docs/en/config.md) — schema declaration, template, load/save semantics, validation errors
- [Comments](docs/en/comments.md) — comment ownership, injection modes
- [Examples](docs/en/examples.md) — end-to-end scenarios
- [Performance](docs/en/performance.md) — measured baseline

## Requirements

Python ≥ 3.10, no third-party dependencies.

## License

[MIT](LICENSE)
