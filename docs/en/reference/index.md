# Reference

Fact sheets about this repository: how the code is organized, what the non-negotiable invariants are, which verification gates exist, and what the public API surface is. The [skills](../skills/index.md) are the playbooks; these are the facts they stand on.

| Sheet | Content |
|---|---|
| [Architecture](architecture.md) | module map, pipeline, preservation model |
| [Invariants](invariants.md) | the four must-never-break guarantees and where they are enforced |
| [Verification gates](verification.md) | every command that must pass, and what each one actually checks |
| [Public API surface](api-surface.md) | exported symbols, entry points, error taxonomy |

These sheets are derived from the code, not from memory: when a sheet and the code disagree, the code wins and the sheet gets fixed in the same change.
