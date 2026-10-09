# Skills

Task playbooks for working **on this repository** (agents and new contributors). They encode how the project is actually built and verified; `../reference/` holds the underlying fact sheets (architecture, module map, verification gates).

New here? Start with the [quick start](quickstart.md).

| Skill | Use when |
|---|---|
| [Quick start](quickstart.md) | first time in the repo: setup, orientation, a safe first change |
| [Fixing defects](fixing-defects.md) | a test fails, a round-trip/comment invariant breaks, an error surfaces |
| [Extending the API](extending-api.md) | adding or changing exported functions, classes, methods, options |
| [Testing](testing.md) | running, organizing or adding tests |
| [Updating documentation](updating-docs.md) | changing README, docs pages, CHANGELOG or these skills/reference files |
| [Releasing](releasing.md) | cutting a version, updating the changelog, shipping to PyPI |

Ground rule: every playbook describes the repo as it is. When reality and a playbook disagree, fix the playbook in the same change — never work around the repo to satisfy the doc.
