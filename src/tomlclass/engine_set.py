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
from .nodes import _MAX_VALUE_DEPTH, ArrayOfTables, InlineTable, Table, format_value


def _subtree_height(value: Any) -> int:
    """
    Maximum container nesting depth of an API-supplied value (a scalar is 1).

    Iterative on purpose: measuring a runaway-deep value must not itself
    overflow the interpreter stack.
    """
    best = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        best = max(best, depth)
        if isinstance(node, Table):
            stack.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, (ArrayOfTables, list, tuple)):
            stack.extend((v, depth + 1) for v in node)
        elif isinstance(node, dict):
            stack.extend((v, depth + 1) for v in node.values())
    return best


def _reject_oversized(path: tuple[str, ...], value: Any) -> None:
    """
    API-supplied containers deeper than the engine limit raise at assignment
    time — render-time recursion must never surface as RecursionError.
    """
    if len(path) + _subtree_height(value) > _MAX_VALUE_DEPTH:
        raise TOMLTypeError(
            f"maximum value nesting depth exceeded ({_MAX_VALUE_DEPTH}) —"
            " build the structure as [tables] instead",
            path=path,
            value=value,
        )


def _pending_set(pending: dict[tuple[str, ...], Any], path: tuple[str, ...], value: Any) -> None:
    """
    Insert-or-move-to-tail in a block's pending mapping — the semantics the
    list-era filter+append pair implemented, at O(1).
    """
    pending.pop(path, None)
    pending[path] = value


def _drop_pending_aot(block: Table, path: tuple[str, ...]) -> None:
    """
    A delete or re-assignment retires any constructed-aot registration at
    *path* — the flush loop would otherwise keep rendering its [[blocks]].
    """
    if block.pending_aots:
        block.pending_aots = [(p, a) for (p, a) in block.pending_aots if p != path]

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
        _pending_set(table.pending, rel, value)
        table.deleted.discard(rel)
        return value

    # entries added through a pending (not yet rendered) header table collect
    # on that table itself — host-relative dotted lines would land outside
    # the block that owns them. Table/dict values keep the general path
    # (they register as nested pending tables).
    if (
        len(rel) == 1
        and table._block is not None
        and table is not table._block
        and not table.sealed
        and not table.defined
        and table.kind == "header"
        and not isinstance(value, (Table, dict))
    ):
        _pending_set(table.pending, rel, value)
        table.deleted.discard(rel)
        return value

    block = table._block if table._block is not None else table
    path = table._phys + rel
    block.array_appends.pop(path, None)  # any re-assignment invalidates a prior clean-append record
    existing = table._raw_get(rel[0]) if len(rel) == 1 else None

    if existing is value and isinstance(value, (Table, ArrayOfTables)):
        # `doc[k] = doc[k]` / `doc[k] += items`: the object already lives in
        # the tree and its in-place edits are registered — re-processing it
        # here would wipe it (whole replacement clears the very list it would
        # iterate) or emit a duplicate header
        return value

    if isinstance(existing, Table) and not isinstance(value, Table):
        if not isinstance(existing, InlineTable):
            # a header / dotted-key / aot structure replaced by a non-table
            # value: remove the old structure, then register the fresh value.
            # An inline table stays: its kv line renders the scalar in place.
            # When the replaced structure was itself pending (no source lines),
            # the scalar line it originally replaced must stay deleted —
            # restore the marker engine_del cannot know about.
            had_source_line = path in block.entry_spans or path in block.deleted
            engine_del(table, rel)
            if not had_source_line:
                block.deleted.add(path)
            existing = None
    elif isinstance(existing, ArrayOfTables) and not isinstance(value, list):
        had_source_line = path in block.entry_spans or path in block.deleted
        engine_del(table, rel)
        if not had_source_line:
            block.deleted.add(path)
        existing = None

    if isinstance(value, InlineTable):
        # explicit InlineTable values render inline at the value position —
        # never as a [header] block (fresh assignment or whole replacement)
        format_value(value)
        block.dirty[path] = value
        block.deleted.discard(path)
        _drop_pending_aot(block, path)
        if path not in block.entry_spans:
            _pending_set(block.pending, path, value)
        return value

    if isinstance(value, Table):
        if value._block is not None or value.kind == "root":
            raise TOMLTypeError(
                "cannot reassign a table that already belongs to a document",
                path=path,
                value=value,
            )
        _reject_oversized(path, value)
        if existing is not None and not isinstance(existing, (Table, ArrayOfTables)):
            # a scalar entry is being replaced by a [table]: the old line must
            # not coexist with the new header
            if path in block.entry_spans:
                block.deleted.add(path)
            block.dirty.pop(path, None)
            block.pending.pop(path, None)
            _drop_pending_aot(block, path)
        # new [sub]table: register a pending header block
        value._block = block
        value._phys = path
        value.kind = "header"
        block.pending_tables.append((path, value))
        return value

    if isinstance(value, dict):
        _reject_oversized(path, value)
        if isinstance(existing, InlineTable):
            # whole replacement of an inline value: re-render the line in place
            format_value(value)
            block.dirty[path] = value
            block.deleted.discard(path)
            return value
        if existing is not None and not isinstance(existing, (Table, ArrayOfTables)):
            # scalar entry replaced by a [table]: drop the old line
            if path in block.entry_spans:
                block.deleted.add(path)
            block.dirty.pop(path, None)
            block.pending.pop(path, None)
            _drop_pending_aot(block, path)
        # plain dicts become [table] blocks (use InlineTable explicitly for inline)
        sub = Table(kind="header")
        for k, v in value.items():
            sub[k] = v
        block.pending_tables.append((path, sub))
        return sub

    if isinstance(value, ArrayOfTables):
        _reject_oversized(path, value)
        if isinstance(existing, ArrayOfTables):
            # replacing an existing aot with a constructed one: adopt its
            # elements into the object that stays in the tree
            for element in list(existing):
                if isinstance(element, Table):
                    mark_dead(element)
            list.clear(existing)
            existing._appended_elements.clear()
            existing._inserted_elements.clear()
            for element in list(value):
                existing.append(element)
            return existing
        # a constructed aot on a fresh key: keep the object in the tree and
        # register it as pending — its elements render as [[blocks]] at the
        # block tail, and later appends re-render with it
        if existing is not None:
            # scalar / array / inline value replaced by [[blocks]]: the old
            # value line must not coexist with the new headers
            if path in block.entry_spans:
                block.deleted.add(path)
            block.dirty.pop(path, None)
            block.pending.pop(path, None)
            _drop_pending_aot(block, path)
        # no deleted.discard here: a line deleted earlier stays deleted —
        # the [[blocks]] render at the tail, never by splicing that line
        block.pending_aots.append((path, value))
        return value

    if isinstance(existing, ArrayOfTables) and isinstance(value, list):
        _reject_oversized(path, value)
        # whole replacement: old parsed elements die, new dicts become element
        # tables rendered by the aot tail anchor (idempotent across dumps)
        own = {id(element) for element in existing}
        if any(id(item) in own for item in value if isinstance(item, Table)):
            raise TOMLTypeError(
                "cannot replace an array-of-tables with a list containing its own "
                "elements; mutate it in place (append/insert) or build new dicts",
                path=path,
            )
        for element in list(existing):
            if isinstance(element, Table):
                mark_dead(element)
        list.clear(existing)
        existing._appended_elements.clear()
        existing._inserted_elements.clear()
        for item in value:
            existing.append(item)
        return existing  # keep the aot object in the tree — a plain list would evict it

    # eager serializability check — None, functions, arbitrary objects raise here
    format_value(value)
    block.dirty[path] = value
    block.deleted.discard(path)
    _drop_pending_aot(block, path)
    if path not in block.entry_spans:
        # a replacement of a previously pending entry must overwrite it,
        # not append a second line for the same key
        _pending_set(block.pending, path, value)
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
        table.pending.pop(rel, None)
        table.deleted.discard(rel)
        return

    # pending header tables collect their own entries (mirror of the
    # engine_set redirect); table/array values keep the general path
    if (
        len(rel) == 1
        and table._block is not None
        and table is not table._block
        and not table.sealed
        and not table.defined
        and table.kind == "header"
        and not isinstance(table._raw_get(rel[0]), (Table, ArrayOfTables))
    ):
        table.pending.pop(rel, None)
        table.deleted.discard(rel)
        return

    block = table._block if table._block is not None else table
    path = table._phys + rel
    target = table._raw_get(rel[0])

    if isinstance(target, ArrayOfTables):
        for element in list(target):
            if isinstance(element, Table):
                mark_dead(element)
    elif isinstance(target, Table):
        mark_dead(target)
        if target.sealed and target._block is not None:
            # dotted-key table: its entries live on the hosting block as
            # phys-prefixed kv lines — those lines must be deleted too
            host = target._block
            for sp in host.entry_spans:
                if sp[: len(path)] == path:
                    host.deleted.add(sp)

    if path in block.entry_spans:
        block.deleted.add(path)
    block.dirty.pop(path, None)
    block.array_appends.pop(path, None)
    block.pending.pop(path, None)
    _drop_pending_aot(block, path)
    block.pending_tables = [(p, t) for (p, t) in block.pending_tables if p != path]


def mark_dead(table: Table) -> None:
    """
    Mark a parsed table subtree dead — its parts render as nothing.
    """
    table.mark_dead()
