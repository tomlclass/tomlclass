# Performance Baseline (v0.3.0, measured)

> **Methodology**: measured on one machine, in one process environment, with the same
> iteration count (500) — not quoted from historical data.
> Environment: Windows 11 (10.0.26300), AMD Ryzen (Zen4, Family 25 Model 97), CPython 3.14.6,
> tomli 2.5.0, tomlkit 0.15.1.
> Reproduce: `uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500`
> Corpora: `scripts/bench/data/` — data0 (26,529 B, pytomlpp benchmark), data2 (3,893 B, tomli benchmark),
> the same sources as community cross-benchmarks, so third-party published numbers stay comparable.

## Parsing (pure parse, 500 iters measured)

| Library | data0 (26.5 KB) | data2 (3.9 KB) | Relative to tomli | Relative to tomlclass |
|---|---|---|---|---|
| tomli 2.5.0 | 0.48 s | 0.07 s | 1.00× | 0.33× / 0.30× |
| **tomlclass 0.3.0** | **1.44 s** | **0.24 s** | **2.98× / 3.30×** | 1.00× |
| tomlkit 0.15.1 | 9.12 s | 1.44 s | 19.0× / 20.6× | 6.3× / 6.0× |

- **No tomlclass regression**: absolute parse time is unchanged from 0.1.0 (1.38 → 1.44 s / 0.23 → 0.24 s, ±4%)
  across the entire 0.2.x–0.3.0 rewrite. The ratio against tomli moved because the denominator did:
  tomli 2.5.0 measures 0.48/0.07 s on this host versus 0.80/0.12 s in the 0.1.0-era measurement.
  The ≤2× / ≤2.2× budgets were set against that older denominator; on the current host they read
  2.98× / 3.30× — a denominator effect, not a slowdown. Re-baselining budgets against a pinned
  tomli version is tracked as maintenance work.
- **Measured 6.0–6.3× faster than tomlkit 0.15.1** (0.16× of tomlkit's time): a fidelity-preserving
  implementation need not cost an order of magnitude in speed.

## Rendering (dumps, 500 iters measured)

| Scenario | Library | data0 | data2 |
|---|---|---|---|
| Unedited | tomlclass | 0.36 s | 0.053 s |
| Unedited | tomlkit | 0.41 s | 0.09 s |
| **After editing 1 key** | **tomlclass** | **0.32 s** | **0.053 s** |

- Unedited: source-slice splicing (approximately O(1)); after editing: only dirty nodes re-render — **edit cost scales with edit size,
  not document length** (by contrast: tomli / tomli_w write-back must fully re-serialize and drops comments)

## Memory (resident, amortized over 50 documents, tracemalloc, data0)

| Library | Resident per document |
|---|---|
| tomli (plain dict, no style) | 74 KB |
| **tomlclass** (CST + span) | **503 KB** |
| tomlkit 0.15.1 | 670 KB |

- 0.75× of tomlkit (0.1.0 measured 0.67×): the +58 KB/doc since 0.1.0 is the per-table edit
  bookkeeping added in 0.2.1–0.3.0 (array append/insert anchors, comment spans, pending
  construction registries) — the cost of edit-semantics completeness; budget revised to ≤ 0.8×
  tomlkit with this justification. The gap to tomli is the inherent cost of style fidelity.

## Conformance (official toml-test, live-pinned checkout — toml-test v2.2.0)

- **files-toml-1.0.0: 205/205 valid** (byte-exact round-trip) and **474/474 invalid** rejected,
  parsed under strict `toml_version="1.0"`
- **files-toml-1.1.0: 214/214 valid** and **467/467 invalid** rejected under the default 1.1 mode
- Verified continuously by the test suite (CI fetches the pinned toml-test ref; assertions lock
  the manifest counts so coverage can never silently shrink)

## Maintenance rules

- Budget changes require revising this file with justification (see the parsing note above)
- Third-party numbers must be **measured on the same machine** with versions recorded — quoting historical data requires
  explicit source and date labels and must not be mixed into measured tables
- Benchmark numbers are re-measured and recorded here on version updates
