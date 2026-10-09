# Skill: Releasing

Cutting a release. **Releases require explicit user approval — never create a GitHub Release or tag without it.**

## Release gates (all must be green)

1. `uv run pytest tests -q --no-cov -p no:cacheprovider -n auto` — full suite
2. `uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""` — 3.10 gate (several releases shipped with 3.10-only import bugs; this gate exists because of them)
3. `uv run ruff check src/ tests/ scripts/` and `uv run basedpyright src/tomlclass` — clean
4. Optional but required when the engine changed: benchmark re-run and `scripts/bench/BASELINE.md` / README performance tables updated per its methodology.

## Pre-flight checklist

- [ ] Version finalized in **both** `pyproject.toml` (`[project].version`) and `src/tomlclass/__init__.py` (`__version__`) — `test_version.py` keeps them pinned together.
- [ ] `CHANGELOG.md` current entry: content merged per topic (final state only), `> Pending release` flipped to `> Released` with the `YYYY/MM/DD` date — after user approval.
- [ ] Docs surfaces updated (README mirrors, `docs/en` + `docs/zh-CN`, migration page if the release has breaking changes).
- [ ] `uv build` produces a clean sdist/wheel (sanity check before tagging).

## Publish flow

1. Get explicit user approval for the release.
2. Commit the release state (one topic: the release).
3. Create the GitHub Release/tag on `main` — this triggers `.github/workflows/pypi-publish.yml` (it runs on `release` events and `workflow_dispatch`), which publishes to PyPI. No manual `twine` step.
4. Verify the CI run is green and the new version appears on PyPI.

## Git flow around releases

- Default: normal segmented commits, one topic per commit, one-line subjects, no amend/force-push.
- Pending-release squash mode (history rewritten into the single `init` commit, then force-pushed) is used **only when the user explicitly requests it** for that release.

## After the release

- Start the next `CHANGELOG.md` entry as `## [x.y.z] - Pending` when the first post-release change lands.
- If the engine changed and budgets in `BASELINE.md` are stale, schedule a re-baseline (see its "Re-baselining" notes).
