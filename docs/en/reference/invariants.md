# Invariants Reference

The four must-never-break guarantees. Property-tested in `tests/property/test_invariants.py`; conformance-pinned in `tests/integration/test_toml_test.py`.

| # | Invariant | Statement | Enforced by |
|---|---|---|---|
| 1 | **Round-trip axiom** | An unmodified document's `dumps()` is byte-identical to its source. Any change that alters untouched output is a defect. | `tests/unit/test_roundtrip.py`, property tests, toml-test valid files (byte-exact) |
| 2 | **Comment preservation** | Comments, key ordering and formatting survive every read-edit-save cycle. Array splices keep per-element comments; AoT and table edits keep section comments. | property tests, `test_edit.py`, `test_compat.py` (comment API), toml-test round-trips |
| 3 | **Defaults never persist** | Schema defaults merged in memory are never written to the file — including fields absent from the file and elements inside `[[aot]]` arrays. | property tests (defaults case), `test_schema.py`, `test_pydantic.py` |
| 4 | **CRLF fidelity** | Files are read without universal-newline translation; generated lines follow the file's line endings; CR inside assigned string values is escaped, not written raw. | property tests (CRLF case), `test_regressions_021c.py` fixtures (`write_bytes`/`newline=""`) |

## How to read a violation

- Violation of 1 → suspect span drift or a spuriously-dirty node (`parser.py`, `render.py`).
- Violation of 2 → trivia handling in `nodes.py` / `render.py`; check both splice paths (arrays) and section paths (AoT/tables).
- Violation of 3 → the diff walk in `schema.py` (`_apply_diff`, `_diff_config_aot`) or the snapshot base in `pydantic.py`.
- Violation of 4 → any read path not using `read_bytes()`, or a generated string containing a raw `\r`.

## Related guarantees (weaker than invariants, still contracts)

- `dumps()` is idempotent: `dumps(parse(dumps(doc))) == dumps(doc)` (asserted in edit/regression suites).
- Atomic writes: `Document.save` / `Config.save` write via tempfile + `os.replace` — a failed save never truncates the file.
- Untouched-`dumps()` is approximately O(1); edit cost scales with edit size, not document length (see [Architecture](architecture.md#why-preservation-is-byte-exact)).

When a change touches core modules (`parser`, `nodes`, `engine_set`, `render`, `schema`), add or update pytest cases for the exact defect and its neighbors, and re-run the full gates in [Verification](verification.md).
