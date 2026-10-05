"""
Edit hooks backing :meth:`Table.__setitem__` / :meth:`Table.__delitem__`.

Assignments do not mutate rendered text directly; they register the change on
the *physical block* that hosts the entry, and the renderer picks it up:

- ``block.dirty[path]``       — edited entries, spliced into their line
- ``block.pending[path]``     — new entries, rendered after the block's last
  parsed entry (values assigned to existing keys only go to ``dirty``)
- ``block.pending_tables``    — newly created ``[sub]`` tables
- ``block.deleted[path]``     — entries removed via ``del``

Validation happens eagerly: values that cannot be represented in TOML raise
:class:`TOMLTypeError` at assignment time, not at render time.
"""

from __future__ import annotations

from typing import Any

from .errors import TOMLTypeError
from .nodes import ArrayOfTables, Table, format_value

__all__: list[str] = []


def engine_set(table: Table, rel: tuple[str, ...], value: Any) -> Any:
    """
    Register the edit; return the object that must be stored in the tree.
    """
    if table.inline:
        path = table._phys + rel
        raise TOMLTypeError(
            "inline tables are closed; reassign the whole value instead",
            path=path,
            value=value,
        )

    # new keys on sealed (dotted) tables render as dotted lines anchored to
    # their own last physical line — register on the sealed table itself
    if table.sealed and table._block is not None and rel[0] not in table:
        table.pending.append((rel, value))
        table.deleted.discard(rel)
        return value

    block = table._block if table._block is not None else table
    path = table._phys + rel

    if isinstance(value, Table):
        if value._block is not None or value.kind == "root":
            raise TOMLTypeError(
                "cannot reassign a table that already belongs to a document",
                path=path,
                value=value,
            )
        # new [sub]table: register a pending header block
        value._block = block
        value._phys = path
        value.kind = "header"
        block.pending_tables.append((path, value))
        block.deleted.discard(path)
        return value

    if isinstance(value, dict):
        # plain dicts become [table] blocks (use InlineTable explicitly for inline)
        from .nodes import Table as _Table

        sub = _Table(kind="header")
        for k, v in value.items():
            sub[k] = v
        block.pending_tables.append((path, sub))
        block.deleted.discard(path)
        return sub

    existing = table._raw_get(rel[0]) if len(rel) == 1 else None
    if isinstance(existing, ArrayOfTables) and isinstance(value, list):
        # whole replacement: old elements stop rendering,
        # new elements render as [[...]] blocks and are immediately readable

        for element in list(existing):
            if isinstance(element, Table):
                mark_dead(element)
        for item in value:
            if not isinstance(item, dict):
                raise TOMLTypeError(
                    "array-of-tables replacement accepts dicts only",
                    path=path,
                    value=item,
                )
        list.clear(existing)
        for item in value:
            list.append(existing, dict(item))
        existing.pending_elements = [dict(item) for item in value]
        block.deleted.discard(path)
        return value

    # eager serializability check — None, functions, arbitrary objects raise here
    format_value(value)
    block.dirty[path] = value
    block.deleted.discard(path)
    if path not in block.entry_spans:
        block.pending.append((path, value))
    return value


def engine_del(table: Table, rel: tuple[str, ...]) -> None:
    if table.inline:
        path = table._phys + rel
        raise TOMLTypeError(
            "inline tables are closed; reassign the whole value instead",
            path=path,
            value=None,
        )

    # engine-created keys on sealed tables: drop from their own pending
    if table.sealed and table._block is not None and rel[0] not in table:
        table.pending = [(p, v) for (p, v) in table.pending if p != rel]
        table.deleted.discard(rel)
        return

    block = table._block if table._block is not None else table
    path = table._phys + rel
    target = table._raw_get(rel[0])

    if isinstance(target, ArrayOfTables):
        for element in target:
            if isinstance(element, Table):
                mark_dead(element)
    elif isinstance(target, Table):
        mark_dead(target)

    if path in block.entry_spans:
        block.deleted.add(path)
    block.dirty.pop(path, None)
    block.pending = [(p, v) for (p, v) in block.pending if p != path]
    block.pending_tables = [(p, t) for (p, t) in block.pending_tables if p != path]


def mark_dead(table: Table) -> None:
    """
    Mark a parsed table subtree dead — its parts render as nothing.
    """
    table.dead = True
    for value in table.values():
        if isinstance(value, Table):
            mark_dead(value)
