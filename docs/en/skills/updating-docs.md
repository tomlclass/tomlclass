# Skill: Updating Documentation

Which documentation surfaces exist, their structure, and the sync rules.

## Maintained surfaces

| Surface | Audience | Language rule |
|---|---|---|
| `README.md` / `README.zh-CN.md` | Project front page | mirror each other |
| `README.pypi.md` | PyPI page | English only; absolute GitHub links (it is rendered off-repo) |
| `docs/en/`, `docs/zh-CN/` | User docs | page-per-page mirrors: `index`, `engine`, `config`, `comments`, `examples`, `migration` |
| `docs/skills/`, `docs/reference/` | Agent/contributor playbooks and fact sheets | `docs/en/` is the source of truth; keep `docs/zh-CN/` in sync when the content is user-facing |
| `CHANGELOG.md` | Release log | English; structure below |

No other languages exist — do not create them.

## Structure locks

- **README order** is fixed: logo → intro → ErisPulse attribution → versioning note → badges → Capabilities (≤5 bullets, schema/config layer first) → "not a fit" boundary paragraph → Conformance & performance → Installation → Usage (declarative `Config` first; parse/edit and `update()` after) → Documentation → Requirements → License. Tone: objective, no marketing.
- **engine.md** must keep the TOML version boundary (1.1 default, `toml_version="1.0"` strict) and None handling (`none_value` sentinel) sections in sync across `docs/en` and `docs/zh-CN`.
- **Conformance numbers** (205/474, 214/467) are pinned to the toml-test ref in `tests/integration/test_toml_test.py` and CI. They change only together with `TOML_TEST_REF`.
- **Performance tables** change only with a re-run of the benchmark against `scripts/bench/BASELINE.md` methodology — never hand-edit a measured number.

## CHANGELOG rules

Update under the current version entry, following the file's own "Writing rules":

- final state only; no process notes; in-version fixes fold into their feature entry; reverts leave no trace; no trivia; merge per topic; summary ≤ 3 sentences; entries attributed `@GithubUsername`; dates `YYYY/MM/DD`.
- Release flip (`> Pending release` → `> Released` + date) happens only during the [release](releasing.md) flow.

## Skill/reference files

Playbooks under `docs/skills/` and fact sheets under `docs/reference/` describe the repo as it is. When a code change invalidates a statement there, update that file in the same change — stale operational docs are worse than none. Keep cross-links relative (`../reference/...`) so the set works from any viewer.

## Verification

Documentation-only changes still get checked:

```bash
uv run ruff check src/ tests/ scripts/          # untouched, but cheap
git diff --stat                        # confirm only intended files moved
```

Plus a manual pass: every code snippet you touched must run as-is, every internal link must resolve from the file you edited.
