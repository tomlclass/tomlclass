# Performance Baseline (v0.1.0, measured)

> **Methodology**: measured on one machine, in one process environment, with the same
> iteration count (500) — not quoted from historical data.
> Environment: Windows 11 (10.0.26300), AMD Ryzen (Zen4, Family 25 Model 97), CPython 3.14.6,
> tomli 2.4.1, tomlkit 0.15.1.
> Reproduce: `uv run --with tomli --with tomlkit python tests/bench/bench.py --compare --iterations 500`
> Corpora: `tests/bench/data/` — data0 (26,529 B, pytomlpp benchmark), data2 (3,893 B, tomli benchmark),
> the same sources as community cross-benchmarks, so third-party published numbers stay comparable.

## Parsing (pure parse, 500 iters measured)

| Library | data0 (26.5 KB) | data2 (3.9 KB) | Relative to tomli | Relative to tomlclass |
|---|---|---|---|---|
| tomli 2.4.1 | 0.80 s | 0.12 s | 1.00× | 0.58× / 0.52× |
| **tomlclass 0.1.0** | **1.38 s** | **0.23 s** | **1.73× / 1.94×** | 1.00× |
| tomlkit 0.15.1 | 8.83 s | 1.33 s | 11.0× / 11.1× | 6.4× / 5.8× |

- Budget: parse ≤ 2× tomli on the large corpus (data0), ≤ 2.2× on the small corpus (data2) — **met** (1.73× / 1.94×). data2 (3.9 KB) is dominated by fixed per-call overhead, so its ratio amplifies naturally across machines (±0.3× observed between hosts); the large corpus is the primary gate.
- **Measured 5.8–6.4× faster than tomlkit 0.15.1**; the 2022 community cross-benchmark put that gap at ~19–20× (tomlkit has since improved) —
  which does not change the conclusion: a fidelity-preserving implementation need not cost 20× in speed

## Rendering (dumps, 500 iters measured)

| Scenario | Library | data0 | data2 |
|---|---|---|---|
| Unedited | tomlclass | 0.28 s | 0.051 s |
| Unedited | tomlkit | 0.41 s | 0.08 s |
| **After editing 1 key** | **tomlclass** | **0.29 s** | **0.052 s** |

- Unedited: source-slice splicing (approximately O(1)); after editing: only dirty nodes re-render — **edit cost scales with edit size,
  not document length** (by contrast: tomli / tomli_w write-back must fully re-serialize and drops comments)
- Provenance of the toml-test invalid numbers: the 500 entries come from the **official toml-test 1.0 manifest's invalid list**
  (vendored with the corpus and locked by a count assertion in the test suite), not self-made cases
- Rationale for the 0.7× memory budget: tomlkit carries a trivia/style object graph per value, while tomlclass stores only a
  `(start, end)` span plus the parsed value for untouched nodes — 0.67× is the delta of deliberately not building per-value style
  objects; compressing further requires arena/interning techniques (listed as future work)

## Memory (resident, amortized over 50 documents, tracemalloc)

| Library | Resident per document |
|---|---|
| tomli (plain dict, no style) | 74 KB |
| **tomlclass** (CST + span) | **445 KB** |
| tomlkit 0.15.1 | 669 KB |

- Budget ≤ 0.7× tomlkit — **met** (measured 0.67×); span + parsed value is the reasonable floor for a lossless CST,
  compressing further requires arena/interning techniques (listed as future work); the gap to tomli is the inherent cost of style fidelity

## Conformance (official toml-test 1.0 manifest, verified continuously by the test suite)

- **valid: all 208 .toml files** pass (including byte-exact round-trip)
- **invalid: all 500 .toml files** correctly rejected (manifest count locked by a test-suite assertion;
  comparison: tomlkit 0.15 official self-test reports 208/214 invalid — this baseline quotes the published number with its version noted)

## Maintenance rules

- The performance job verifies budgets per PR; budget changes require revising this file with justification
- Third-party numbers must be **measured on the same machine** with versions recorded — quoting historical data requires
  explicit source and date labels and must not be mixed into measured tables
- Benchmark numbers are re-measured and recorded here on version updates
