"""
The parsed document object.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .nodes import ArrayOfTables, Table
from .render import render_document

__all__ = ["Document", "atomic_write_text"]


def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """
    Atomically write *text* to *path* (same-dir tempfile + ``os.replace``).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        Path(tmp).replace(target)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


class Document:
    """
    A parsed TOML document: lossless CST + mapping access + atomic save.
    """

    def __init__(self, source: str, root: Table, parts: list[tuple[int, int, str, Any]]) -> None:
        self._source = source
        self.root = root
        self._parts = parts

    # -- mapping passthrough --------------------------------------------- #

    def __getitem__(self, key: str) -> Any:
        return self.root[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.root[key] = value

    def __delitem__(self, key: str) -> None:
        del self.root[key]

    def __contains__(self, key: object) -> bool:
        return key in self.root

    def __iter__(self) -> Iterator[str]:
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)

    def get(self, key: str, default: Any = None) -> Any:
        return self.root.get(key, default)

    # -- rendering --------------------------------------------------------- #

    def dumps(self) -> str:
        """
        Render the document. Unchanged documents round-trip byte-exactly.
        """
        return render_document(self._source, self._parts, self.root)

    def save(self, path: str | os.PathLike[str]) -> None:
        """
        Render and atomically write to *path* (tempfile + ``os.replace``).
        """
        atomic_write_text(path, self.dumps())

    # -- navigation / conversion ------------------------------------------ #

    def find(self, dotted_path: str) -> Any:
        """
        Return the value at *dotted_path* (``"a.b.c"``), or ``None``.
        """
        node: Any = self.root
        for part in dotted_path.split("."):
            if isinstance(node, Table) and part in node:
                node = node[part]
            else:
                return None
        return node

    def set_path(self, dotted_path: str, value: Any) -> None:
        """
        Assign *value* at *dotted_path* (``"a.b.c"``), creating missing keys
        and intermediate ``[table]`` blocks along the way. ``None`` entries
        inside dict/list values are dropped first; a bare ``None`` raises
        :class:`TOMLTypeError` (TOML has no null — delete the key instead).
        """
        _assign_path(self, dotted_path.split("."), value)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to plain nested dicts (datetimes stay as-is).
        """
        return _to_plain(self.root)

    # -- comment API -------------------------------------------------------- #

    def comment(self, dotted_path: str) -> str | None:
        """
        Return the comment trailing *dotted_path* (without ``#``), or None.

        Comments belong to the key they trail; table-level comments live on
        the header line and are addressed by the table's path.
        """
        parts = dotted_path.split(".")
        block = self._block_for(parts[:-1])
        if block is None:
            return None
        located = self._block_for(parts)
        if located is None:
            return None
        block, phys = located
        if phys in block.comments:  # set_comment override wins
            return block.comments[phys]
        span = block.entry_spans.get(phys)
        if span is None:
            return None
        _vs, _ve, cs = span
        line_end = self._line_end(cs)
        text = self._source[cs:line_end].strip()
        if not text.startswith("#"):
            return None
        return text[1:].lstrip() or None

    def set_comment(self, dotted_path: str, comment: str | None) -> None:
        """
        Replace (or, with ``None``, remove) the comment trailing *dotted_path*.
        """
        parts = dotted_path.split(".")
        located = self._block_for(parts)
        if located is None:
            raise KeyError(dotted_path)
        block, phys = located
        if phys not in block.entry_spans:
            raise KeyError(dotted_path)
        block.comments[phys] = comment

    def _block_for(self, parts: list[str]) -> tuple[Table, tuple[str, ...]] | None:
        """
        Resolve *parts* to (hosting block, block-relative path).
        """
        node: Any = self.root
        consumed: list[str] = []
        for part in parts:
            child = node[part] if isinstance(node, Table) and part in node else None
            if isinstance(child, Table):
                node = child
                consumed.append(part)
            else:
                # leaf value: the current table hosts the key; the rest of the path is the dotted key
                return node, tuple(parts[len(consumed):])
        return node, ()

    def _line_end(self, offset: int) -> int:
        nxt = self._source.find(chr(10), offset)
        return nxt if nxt != -1 else len(self._source)

    def __repr__(self) -> str:
        return f"Document({dict.__repr__(self.root)})"


def _to_plain(table: Table) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in table:
        value = table[key]
        if isinstance(value, Table):
            out[key] = _to_plain(value)
        elif isinstance(value, (ArrayOfTables, list)):
            out[key] = [_to_plain_value(v) for v in value]
        else:
            out[key] = value
    return out


def _to_plain_value(value: Any) -> Any:
    if isinstance(value, Table):
        return _to_plain(value)
    if isinstance(value, (ArrayOfTables, list)):
        return [_to_plain_value(v) for v in value]
    return value


def _prune_none(value: Any) -> Any:
    """
    Drop None entries from dicts/lists before handing values to the engine.
    """
    if isinstance(value, dict):
        return {k: _prune_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_prune_none(v) for v in value]
    return value


def _assign_path(doc: Document, parts: list[str], value: Any) -> None:
    """
    Navigate to the deepest table present along *parts* and assign the rest
    in one step. Missing intermediate tables are built bottom-up as plain
    nested dicts so the engine renders them as ``[table]`` blocks containing
    their entries — never as a dotted line plus an empty header, which would
    define the same table twice.
    """
    if isinstance(value, (dict, list, tuple)):
        value = _prune_none(value)
    target: Any = doc.root
    depth = 0
    while depth < len(parts) - 1:
        child = target._raw_get(parts[depth]) if isinstance(target, Table) else None
        if not isinstance(child, Table):
            break
        target = child
        depth += 1
    if depth == len(parts) - 1:
        target[parts[-1]] = value
        return
    payload: Any = {parts[-1]: value}
    for part in reversed(parts[depth + 1 : -1]):
        payload = {part: payload}
    target[parts[depth]] = payload


def plain_dict(doc: Document) -> dict[str, Any]:
    """
    tomllib-style plain-dict conversion of a whole :class:`Document`.
    """
    return _to_plain(doc.root)
