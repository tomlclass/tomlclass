[**English**](README.md) | [简体中文](README.zh-CN.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

A TOML 1.0/1.1 parser with lossless editing, plus typed configuration classes.

Parsing produces an editable document tree: unmodified text round-trips byte-for-byte, and edits rewrite only the lines they touch — comments, ordering and formatting survive. On top of that, schemas declared as Python classes give you commented templates, validation and diff-based write-back.

The configuration semantics come from the [ErisPulse](https://github.com/ErisPulse/ErisPulse) framework's config system.

> **Versioning**: pre-1.0. Minor bumps may add APIs; existing APIs stay backward compatible.

<p>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/pypi/v/tomlclass?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/tomlclass/actions/workflows/code-quality-check.yml"><img src="https://img.shields.io/github/actions/workflow/status/wsu2059q/tomlclass/code-quality-check.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/tomlclass/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge" alt="Ruff"></a>
</p>

<br clear="both">

---

## Capabilities

- **Typed config with schema** — declare the structure as annotated classes: commented templates, aggregated validation, diff-based write-back, env overrides, hot reload
- **Lossless editing** — unmodified documents round-trip byte-for-byte; edits rewrite only the touched lines. Full official toml-test coverage: both the 1.0 and 1.1 manifests pass (205/474 + 214/467, live-pinned)
- **Comment access** — read, replace and delete comments per key, on tables, dotted keys and array-of-tables elements; optional injection of schema descriptions
- **TOML 1.1 semantics, selectable** — 1.1 rules on by default; `toml_version="1.0"` restores strict 1.0 rejection where your code depends on it
- **tomllib-compatible entry points** — `loads` / `load` follow the stdlib calling convention; `dump` / `load_path` and a from-scratch builder (`document()` / `table()` / `aot()`) complete the surface

**Not a fit** if you only need to read TOML into plain dicts at maximum speed — use [tomllib](https://docs.python.org/3/library/tomllib.html) (stdlib) or [tomli](https://github.com/hukkin/tomli) for that. tomlclass trades parse headroom (≈3× tomli 2.5 in the in-repo measurement) for editability and schema tooling. Conversely, if you need schema validation **and** comments that survive write-back, this is currently the only library that does both.

## Conformance & performance

Verified against the **official toml-test suite** — both manifests, live-pinned at toml-test v2.2.0, run in CI on Linux, Windows and macOS:

| Check | Result |
|---|---|
| toml-test files-toml-1.0.0 (strict 1.0 mode) | 205/205 valid · 474/474 invalid rejected |
| toml-test files-toml-1.1.0 (default 1.1 mode) | 214/214 valid · 467/467 invalid rejected |

Speed measured with [toml-bench](https://github.com/pwwang/toml-bench) (load / dump over 5000 iterations on one machine; 0.3.0 adds no parse regression — within ±4% of 0.1.0 on the [in-repo baseline](scripts/bench/BASELINE.md)):

| Library | rtoml corpus | tomli corpus |
|---|---|---|
| rtoml 0.11 (Rust) | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib (CPython) | 3.39s / — | 2.15s / — |
| tomlclass 0.2.1 | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

## Installation

```bash
pip install tomlclass
```

## Usage

### Declarative config

```python
from typing import Annotated
from tomlclass import Config, Field

class Server(Config):
    """HTTP server settings."""

    host: str = Field("127.0.0.1", description="the bind address")
    port: Annotated[int, Field(ge=1, le=65535)] = 8000


server = Server.load("server.toml")  # read + validate + merge defaults
server.port = 9000
server.save("server.toml")           # only changed keys are written
Server.template()                    # commented starter template from the schema
```

### Parse and edit

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, comments kept
doc.set_comment("project.version", "bumped")          # comments are first-class
text = doc.dumps()                                   # only touched lines change
```

### One-call value update

```python
tomlclass.update("pyproject.toml", {"project.version": "1.0.0", "tool.x.y": True})
````

## Documentation

- [Engine](docs/en/engine.md) — parse, edit, path addressing, version selection, comment API, errors, boundaries
- [Config](docs/en/config.md) — schema declaration, template, load/save semantics, validation
- [Comments](docs/en/comments.md) — comment addressability, injection modes
- [Migration](docs/en/migration.md) — from tomlkit, and from tomlclass 0.2.x
- [Examples](docs/en/examples.md) — end-to-end scenarios
- [Contributor skills](docs/en/skills/index.md) — task playbooks (quick start, defects, API, testing, docs, release)
- [Reference sheets](docs/en/reference/index.md) — architecture, invariants, verification gates, API surface

## Requirements

Python ≥ 3.10, no third-party dependencies.

## License

[MIT](LICENSE)
