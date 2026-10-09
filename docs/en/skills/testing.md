# Skill: Testing

How the test suite is organized, how to run it, and where new tests go.

## Layout

| Path | Content |
|---|---|
| `tests/unit/` | Topic and regression files (see map below) — the bulk of the suite |
| `tests/property/` | Hypothesis tests for the four invariants over random documents/mutations |
| `tests/integration/` | Official toml-test conformance; needs `.toml-test/` (CI fetches v2.2.0), skips offline |
| `tests/corpus/` | Five valid TOML 1.1 files vendored from toml-test 1.5.0 for offline round-trip |
| `scripts/bench/` | Manual benchmark script + `BASELINE.md`; **not** collected by pytest |

## Unit file map

| File | Covers |
|---|---|
| `test_api_030.py` | 0.3.0 surface: path grammar, `Document` mapping protocol, construction API, comment addressability, extended `Config` |
| `test_api_modes.py` | `toml_version` / `none_value` modes |
| `test_compat.py` | tomllib-compatible entry points + comment API |
| `test_edit.py` | Edit semantics: dirty splicing, pending entries, deletion, AoT |
| `test_pydantic.py` | Optional `tomlclass.pydantic` interop (skips without pydantic) |
| `test_regressions_021*.py` (a–d) | Batched regression suites by fix wave |
| `test_roundtrip.py` | Round-trip axiom, byte-identical `dumps()` |
| `test_schema.py` | Template, validation, load/save diff semantics |
| `test_toml11.py` | TOML 1.1 additions + vendored corpus |
| `test_update.py` | `tomlclass.update()` and `Document.set_path` |
| `test_user_scenarios.py` | End-to-end user calls, semantic + byte assertions |
| `test_version.py` | Package metadata (`__version__`, `__all__` consistency) |

## Run

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto                                 # full suite
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""   # 3.10 gate
uv run pytest tests/unit/test_edit.py -q --no-cov -p no:cacheprovider                      # one file
```

Baseline (2026-10): 287 passed, 6 skipped offline. The skips are the toml-test integration module without its checkout — green by design. `-n auto` matches CI; drop it when debugging a flaky interaction.

## Where new tests go

1. **Defect fix** → the matching `test_regressions_*` batch file, or a new `test_regressions_0XX.py` when a new wave starts; cover the exact defect **and its neighbors**.
2. **New feature/API** → topic file (`test_api_030.py` style) or a new topic file; include error paths and 3.10 compatibility.
3. **Invariant-adjacent change** → extend `tests/property/test_invariants.py` strategies if a new node kind or mutation class appears.

## Conventions

- `from tests._compat import tomllib` whenever a test needs `tomllib` on 3.10.
- Fixture files are written with `write_bytes` or `write_text(..., newline="")` — never rely on platform newline translation.
- Mutable schema defaults in tests carry `# noqa: RUF012` with the reason (the mutable default is the test subject).
- Test comments describe behavior objectively — no issue numbers, tracker IDs or AI review labels.
- No new test may require network access; conformance data comes from the pinned `.toml-test/` checkout or the vendored corpus.
