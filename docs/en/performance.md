# Performance

Baseline data, measurement methodology and maintenance rules: [BASELINE](../../tests/bench/BASELINE.md). Reproduce:

```bash
uv run --with tomli --with tomlkit python tests/bench/bench.py --compare --iterations 500
```

## Summary (measured at v0.1.0; 0.1.1 does not touch the engine hot paths)

| Metric | Value | Comparison |
|---|---|---|
| Parse | 1.73× / 1.94× tomli (two corpora) | 5.8–6.4× faster than tomlkit 0.15.1 |
| Unedited `dumps` | ~O(1) | source-slice splicing |
| Edited `dumps` | O(edit size) | only dirty nodes re-render |
| Resident memory | 0.67× tomlkit (budget ≤0.7×) | above tomli (the cost of fidelity) |
| Conformance | toml-test 1.0: all 208 valid files pass byte-exact, all 501 invalid files rejected | tomlkit invalid self-test: 208/214 |

## How it works

1. **Source-slice rendering**: untouched nodes render directly from `source[span]`; an unedited document's `dumps` is ~O(1)
2. **Materialize on edit**: formatting data is only built when a node is written — the read path pays zero style cost
3. **Single-pass character-dispatch parsing**: precompiled regex block matching, no per-character loops, no per-token regex storms
