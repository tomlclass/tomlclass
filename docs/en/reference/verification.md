# Verification Gates Reference

Every command that must pass, what it actually checks, and where the same check runs in CI. The toolchain is **uv**; all commands run from the repo root.

| Gate | Command | Checks | CI job |
|---|---|---|---|
| Full suite | `uv run pytest tests -q --no-cov -p no:cacheprovider -n auto` | all unit + property + integration tests (integration skips offline) | `pytest-check` (7-platform matrix, Python 3.10–3.14) |
| 3.10 gate | `uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""` | unit suite imports and passes on the oldest supported Python | covered by the matrix |
| Lint | `uv run ruff check src/ tests/ scripts/` | E/W/F/I/B/C4/UP/SIM/RET/PIE/RUF/PTH/PERF/FURB/PL/N per `pyproject.toml` | `ruff-check` (blocking, posts PR comment) |
| Types | `uv run basedpyright src/tomlclass` | 0 errors expected; promoted rules in `pyproject.toml` are the contract | `typecheck` |
| Conformance | automatic via the full suite with a `.toml-test/` checkout | official toml-test, both manifests pinned to `TOML_TEST_REF` (v2.2.0): 1.0 strict 205/474, 1.1 214/467 | fetched + run inside `pytest-check` |
| Security | `uv export ... \| uvx pip-audit -r requirements-audit.txt --strict` | dependency audit on locked deps | `security-audit` |
| Benchmark (manual) | `uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500` | parse/dump timing vs tomli/tomlkit; results go to `scripts/bench/BASELINE.md` | not in CI |

## Facts worth remembering

- Baseline offline run (2026-10, this repo, `-n auto`): **287 passed, 6 skipped** — the skips are the toml-test integration module without its checkout (by design, see `tests/integration/test_toml_test.py` docstring). The 3.10 gate: 281 passed, 1 skipped.
- `-o addopts=""` on the 3.10 gate strips the repo-level pytest addopts (coverage/timeout config assumes the main venv).
- `-n auto` (pytest-xdist) matches CI; drop it when bisecting a flaky test.
- `.toml-test/` and `.zcode/` are workspace-only and never committed (`.zcode/` is ignored via `.gitignore`; the old `.zcode/verify_*.py` matrices no longer exist — the property + regression suites are their successor).

## Release addition

Before a release, also run `uv build` for a clean sdist/wheel and complete the checklist in [Releasing](../skills/releasing.md).
