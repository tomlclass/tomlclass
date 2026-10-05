<p align="center">
  <img src="https://raw.githubusercontent.com/wsu2059q/tomlclass/main/.github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>

# tomlclass

Lossless TOML editing and typed configuration in one zero-dependency package.

Change one value in a config file without breaking a single comment; declare schemas as Python classes to get commented templates, aggregated validation and diff-based write-back.

The configuration semantics come from the [ErisPulse](https://github.com/ErisPulse/ErisPulse) framework's config system.

> **Versioning**: tomlclass is pre-1.0 and does not strictly follow SemVer yet. Before the project stabilizes, minor version bumps may include new API additions — existing APIs will remain backward compatible.

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

- **Lossless editing engine**: TOML 1.0/1.1 parse and write-back; the only library with a perfect 187/187 on toml-test 1.5.0 valid tests. Untouched documents render byte-identical to input
- **TOML 1.1 with a version dial**: `\e` / `\x` escapes, seconds-optional times, newlines and trailing commas in inline tables, non-ASCII bare keys — on by default; pass `toml_version="1.0"` to `parse` / `loads` / `load` / `update` / `Config.load` for strict legacy rejection semantics
- **None your way**: opt-in rtoml-style `none_value` sentinel — `dumps(data, none_value="@None")` and `loads(text, none_value="@None")` round-trip `None` through TOML strings
- **One-line updates**: `tomlclass.update("app.toml", {"server.port": 9090})` — read, change, atomically write back; comments, ordering and formatting survive everywhere else
- **Typed config**: declare the schema as classes — docstrings become template comments, validation aggregates all errors with each field's documented intent, defaults are merged in memory and never written back
- **Comment operations**: read, replace and delete comments per key; schema descriptions can be injected as comments (three strategies)
- **tomllib compatible**: `loads` / `load` follow the stdlib calling convention — migrating costs nothing

> **TOML version boundary**: the 1.1 additions above are accepted by default. If your code relies on *rejecting* 1.0-invalid input (e.g. `13:37` times), switch to `toml_version="1.0"` — the same files then raise `TOMLParseError`.

## Conformance & performance

Measured with [toml-bench](https://github.com/pwwang/toml-bench) (toml-test 1.5.0 + CPython tomllib test data; speed = load/dump over 5000 iterations on one machine, tomlclass 0.2.0 — methodology in the [benchmark baseline](https://github.com/wsu2059q/tomlclass/blob/main/tests/bench/BASELINE.md)):

| Check | tomlclass 0.2.0 |
|---|---|
| toml-test 1.5.0 valid (187 files) | **187/187 — the only library with a perfect score** |
| toml-test 1.5.0 TOML-1.1 manifest (548 files) | **548/548** |
| CPython tomllib test data | **12/12 valid, 50/50 invalid** |

Speed (load / dump, 5000 iterations):

| Library | rtoml corpus | tomli corpus |
|---|---|---|
| rtoml 0.11 (Rust) | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib (CPython) | 3.39s / — | 2.15s / — |
| **tomlclass 0.2.0** | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

Lossless editing pays for bookkeeping: loads run ~2.5–2.8× tomli, dumps ~2.6–3.2× tomli_w — and 12–14× faster than tomlkit.

## Installation## Installation

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

- [Engine](https://github.com/wsu2059q/tomlclass/blob/main/docs/en/engine.md) — parse, edit, `update()`, comment API, errors
- [Config](https://github.com/wsu2059q/tomlclass/blob/main/docs/en/config.md) — schema declaration, template, load/save semantics, validation errors
- [Comments](https://github.com/wsu2059q/tomlclass/blob/main/docs/en/comments.md) — comment ownership, injection modes
- [Examples](https://github.com/wsu2059q/tomlclass/blob/main/docs/en/examples.md) — end-to-end scenarios
- [Performance](https://github.com/wsu2059q/tomlclass/blob/main/docs/en/performance.md) — measured baseline

Docs are also available in [简体中文](https://github.com/wsu2059q/tomlclass/blob/main/docs/zh-CN/index.md).

## Requirements

Python ≥ 3.10, no third-party dependencies.

## License

[MIT](https://github.com/wsu2059q/tomlclass/blob/main/LICENSE)
