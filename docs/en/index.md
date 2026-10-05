# tomlclass Docs

tomlclass is a TOML configuration library: a lossless editing engine plus typed config annotations. Zero third-party dependencies.

Writing a config file back keeps every comment and every bit of formatting intact; declare the structure as Python classes to get a commented template with validation. The configuration semantics come from the [ErisPulse](https://github.com/ErisPulse/ErisPulse) framework's config system.

## Contents

| Doc | Contents |
|---|---|
| [Engine](engine.md) | Document, editing, tomllib compatibility, errors |
| [Annotations](config.md) | Config, Field, view semantics, env overrides |
| [Comments](comments.md) | Ownership model, reading and replacing |
| [Examples](examples.md) | Common scenarios |
| [Performance](performance.md) | Baseline numbers and measurements |

## Installation

```bash
pip install tomlclass
```

Python ≥ 3.10, no third-party dependencies.

## Minimal example

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
text = doc.dumps()  # only touched lines change
```
