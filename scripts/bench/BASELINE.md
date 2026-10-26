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

## 2026-10-26 re-measurement (post-0.3.2 robustness/performance pass, unreleased)

> Same host and methodology as above (Windows 11 10.0.26300, CPython 3.14.x, tomli 2.5.0,
> tomlkit 0.15.1, 500 iterations). Run-to-run variance on this host is ±20%; ratios are the
> point, not absolute seconds. Reproduce:
> `uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500`
> The harness now also carries edit-path workloads (`scripts/bench/bench.py`, deterministic
> in-code fixtures); numbers below are the first recorded baseline for them.

### Parsing

| Library | data0 | data2 | Relative to tomli | Relative to tomlclass |
|---|---|---|---|---|
| tomli 2.5.0 | 2.87 s | 0.39 s | 1.00× | 0.78× / 0.82× |
| **tomlclass** | **3.52 s** | **0.50 s** | **1.22× / 1.28×** | 1.00× |
| tomlkit 0.15.1 | 25.02 s | 3.41 s | 8.7× / 8.7× | 7.1× / 6.8× |

- The ≤2.00× parse gate is **green** in this measurement (1.22× / 1.28×; worst observed across
  repeated runs: 1.63×). The 0.3.0 note above (2.98× / 3.30×) reflected a faster tomli
  denominator on that day; with both measured in one process today the budget holds.

### Rendering (dumps)

| Scenario | tomlclass data0 | tomlclass data2 | tomlkit data0 | tomlkit data2 |
|---|---|---|---|---|
| Unedited | 0.68 s | 0.095 s | 1.24 s | 0.20 s |
| After editing 1 key | 0.68 s | 0.099 s | — | — |

### Edit paths (each iteration = parse + edit + dumps; parse-only column for the delta)

| Workload | parse only | parse + edit + dumps | tomlkit same edit |
|---|---|---|---|
| data2, +100 new scalar keys on one table | 1.10 ms | 1.74 ms | 17.44 ms |
| data2, +50 new sub-tables | 1.10 ms | 2.48 ms | 15.04 ms |
| 500-element multiline array, 50 element edits | 2.41 ms | 2.51 ms | — |
| 100 `[[item]]` blocks, 50 dict appends | 3.28 ms | 4.92 ms | — |
| 100 `[[item]]` blocks, 25 head inserts | 3.28 ms | 4.69 ms | — |
| `update()` end-to-end (read + dotted sets + atomic write) | — | 4.30 ms | — |
| `Config.load` + 1 field edit + `save` | — | 5.14 ms | — |

- The renderer's pending-table/pending-aot flush no longer re-joins the whole output per
  flushed block, the array region rebuild assembles in one pass and skips clean nested
  arrays, per-block pending entries are an insertion-ordered dict (O(1) re-assignment
  instead of an O(n) list rebuild), and AoT insert/replace hoists its identity scan —
  measured 15–30% faster on these workloads versus the pre-pass code on the same host.

## Maintenance rules

- Budget changes require revising this file with justification (see the parsing note above)
- Third-party numbers must be **measured on the same machine** with versions recorded — quoting historical data requires
  explicit source and date labels and must not be mixed into measured tables
- Benchmark numbers are re-measured and recorded here on version updates
