# Skill: Quick Start

First fifteen minutes in this repository: green toolchain, orientation, and a safe first change.

## 0. Prerequisites

Git and [uv](https://docs.astral.sh/uv/) — uv manages the Python toolchain itself (3.10+), so there is no virtualenv to juggle. Nothing else: the library has zero runtime dependencies; the extras pull pytest, ruff and basedpyright.

## 1. Green baseline (about two minutes)

```bash
uv sync --extra test --extra lint
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto
```

Expected on a clean checkout (2026-10): **287 passed, 6 skipped**. The six skips are the toml-test conformance module without a `.toml-test/` checkout — by design, not a failure.

The full battery before every hand-off:

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto                                 # full suite
uv run ruff check src/ tests/ scripts/                                                      # lint
uv run basedpyright src/tomlclass                                                           # types
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""    # 3.10 gate
```

Drop `-n auto` when bisecting a flaky test. The 3.10 gate is mandatory — several releases shipped with 3.10-only import bugs.

## 2. Orientation in sixty seconds

| You want to change… | Go to |
|---|---|
| what TOML syntax is accepted | `src/tomlclass/parser.py` |
| node/edit semantics, what a mutation touches | `src/tomlclass/nodes.py`, `src/tomlclass/engine_set.py` |
| how edited output renders | `src/tomlclass/render.py` |
| `Document` API, path grammar, `dumps`/`save` | `src/tomlclass/_document.py` |
| schema, `Config`/`Field`, validation, diff write-back | `src/tomlclass/schema.py` (pydantic interop: `pydantic.py`) |
| error types and messages | `src/tomlclass/errors.py` |
| tests | `tests/unit/` (topic + regression), `tests/property/` (invariants), `tests/integration/` (conformance) |
| benchmarks | `scripts/bench/` — manual tool, never run by pytest or CI |
| user docs | `docs/en/` **and** `docs/zh-CN/` — always both |

Structural detail lives in [Architecture](../reference/architecture.md).

## 3. The laws you must not break

1. **Round-trip**: an unmodified document's `dumps()` is byte-identical to its source.
2. **Comment preservation**: comments, ordering and formatting survive every read-edit-save cycle.
3. **Defaults never persist**: in-memory schema defaults are never written to the file.
4. **CRLF fidelity**: no newline translation on read; generated lines follow the file's endings.

Plus the routing rule: every `Table`/`Array` mutator must go through the engine hooks (`engine_set`/`engine_del`) — a raw dict/list write makes memory and output diverge. Full detail: [Invariants](../reference/invariants.md).

## 4. Your first change, end to end

1. Reproduce: `uv run pytest tests -q --no-cov -p no:cacheprovider --tb=long -x` (or write the failing case).
2. Find the pipeline stage the defect belongs to, not the stage where the symptom appears — [Fixing defects](fixing-defects.md).
3. Fix it at that layer; no patch-on-patch workarounds.
4. Add the pytest case for the exact defect **and its neighbors** — [Testing](testing.md).
5. Run all four gates above; all must be clean.
6. Update the affected docs in both languages, and `CHANGELOG.md` for user-visible changes — [Updating documentation](updating-docs.md).
7. Commit: one topic, one-line subject; no amend or force-push unless the user asks — see `AGENTS.md`.

## 5. Traps that cost an afternoon

| Trap | Reality |
|---|---|
| `.venv/Scripts/python.exe` (old docs, old habits) | No `.venv` in the repo — run everything through `uv run …` |
| Looking for the benchmark under `tests/` | It moved to `scripts/bench/`; it is a manual tool, not a test |
| Looking for `.zcode/verify_*.py` matrices | They no longer exist; the property + regression suites are their successor |
| `import tomllib` in a test that must pass on 3.10 | Use `from tests._compat import tomllib` |
| Writing fixtures with `write_text(text)` | Use `write_bytes` or `write_text(..., newline="")` — translation hides CRLF defects |
| Adding a mutator that touches the underlying dict/list | Route it through `engine_set`/`engine_del` or memory and output diverge |
| Editing only `docs/en/` | `docs/zh-CN/` is maintained in lockstep |
| Hand-tuning a number in a performance table | Those numbers are measured; re-run `scripts/bench/bench.py` and follow `scripts/bench/BASELINE.md` |

## 6. Where to go next

| | |
|---|---|
| Playbooks | [Fixing defects](fixing-defects.md) · [Extending the API](extending-api.md) · [Testing](testing.md) · [Updating documentation](updating-docs.md) · [Releasing](releasing.md) |
| Fact sheets | [Architecture](../reference/architecture.md) · [Invariants](../reference/invariants.md) · [Verification gates](../reference/verification.md) · [API surface](../reference/api-surface.md) |
| Repository rules | `AGENTS.md` (root) |
