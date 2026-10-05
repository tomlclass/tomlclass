"""
The parsed document object: lossless CST + full mapping protocol + the
unified dotted-path grammar (bare / quoted keys, ``[int]`` AoT indexing).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import os
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Literal, NamedTuple

from .nodes import ArrayOfTables, InlineTable, Table
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


# -- value canonicalization ------------------------------------------------- #


def _std_datetime(value: Any) -> Any:
    """
    Engine datetime nodes (private subclasses carrying ``toml_raw``) convert
    to their standard-library equivalents so downstream code never sees a
    private type.
    """
    raw = getattr(value, "toml_raw", None)
    if raw is None:
        return value
    raw = str(raw)
    try:
        if isinstance(value, dt.datetime):
            iso = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
            return dt.datetime.fromisoformat(iso)
        if isinstance(value, dt.date):
            return dt.date.fromisoformat(raw)
        if isinstance(value, dt.time):
            return dt.time.fromisoformat(raw)
    except ValueError:
        return value
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, Table):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (ArrayOfTables, list)):
        return [_to_plain(v) for v in value]
    return _std_datetime(value)


def _prune_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _prune_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_prune_none(v) for v in value]
    return value


def plain_dict(doc: Document) -> dict[str, Any]:
    """
    tomllib-style plain-dict conversion of a whole :class:`Document`.
    """
    return _to_plain(doc.root)


# -- path grammar ------------------------------------------------------------


class _Segment(NamedTuple):
    key: str
    indices: tuple[int, ...]


# -- the document ------------------------------------------------------------


class Document(Mapping[str, Any]):
    """
    A parsed TOML document: lossless CST + full mapping protocol + atomic save.
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

    def __reversed__(self) -> Iterator[str]:
        return reversed(self.root)

    def get(self, key: str, default: Any = None) -> Any:
        return self.root.get(key, default)

    def keys(self):
        return self.root.keys()

    def values(self):
        return self.root.values()

    def items(self):
        return self.root.items()

    def update(self, *args: Any, **kwargs: Any) -> None:
        self.root.update(*args, **kwargs)

    def pop(self, key: str, *default: Any) -> Any:
        return self.root.pop(key, *default)

    def popitem(self) -> tuple[str, Any]:
        return self.root.popitem()

    def setdefault(self, key: str, default: Any = None) -> Any:
        return self.root.setdefault(key, default)

    def clear(self) -> None:
        self.root.clear()

    def copy(self) -> dict[str, Any]:
        return self.to_dict()

    def __eq__(self, other: object) -> Any:
        if isinstance(other, Document):
            return self.to_dict() == other.to_dict()
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return NotImplemented

    __hash__ = None  # mutable

    def __or__(self, other: Any) -> Any:
        if not isinstance(other, Mapping):
            return NotImplemented
        merged = Document("", Table(kind="root"), [])
        for key, value in {**self.to_dict(), **dict(other)}.items():
            merged[key] = value
        return merged

    def __ror__(self, other: Any) -> Any:
        if not isinstance(other, Mapping):
            return NotImplemented
        merged = Document("", Table(kind="root"), [])
        for key, value in {**dict(other), **self.to_dict()}.items():
            merged[key] = value
        return merged

    def __ior__(self, other: Any) -> Document:
        if not isinstance(other, Mapping):
            raise TypeError(f"unsupported operand type for |=: {type(other).__name__}")
        self.update(other)
        return self

    def add(self, key_or_item: Any, value: Any = None) -> None:
        """
        Attach a key or a standalone trivia line (``comment(...)`` / ``nl()``).
        Setting an existing key raises ``KeyError`` (tomlkit ``add`` semantics).
        """
        self.root.add(key_or_item, value)

    def __repr__(self) -> str:
        return f"Document({dict.__repr__(self.root)})"

    # -- path engine ------------------------------------------------------- #

    @staticmethod
    def _split_path(path: str) -> list[_Segment]:
        """
        Parse ``a.b."c d"[0].e`` into segments: bare keys, quoted keys (dots
        inside quotes are literal), and ``[int]`` array-of-tables indexing.
        Syntax errors raise ``ValueError``.
        """
        if not isinstance(path, str):
            raise ValueError(f"invalid path {path!r}")
        segments: list[_Segment] = []
        i, n = 0, len(path)
        while True:
            if i >= n:
                raise ValueError(f"invalid path {path!r}: empty segment")
            ch = path[i]
            if ch in ('"', "'"):
                quote = ch
                i += 1
                buf: list[str] = []
                closed = False
                while i < n:
                    c = path[i]
                    if quote == '"' and c == "\\":
                        nxt = path[i + 1] if i + 1 < n else ""
                        if nxt in ('"', "\\"):
                            buf.append(nxt)
                            i += 2
                            continue
                        raise ValueError(f"invalid path {path!r}: unsupported escape in key")
                    if c == quote:
                        i += 1
                        closed = True
                        break
                    buf.append(c)
                    i += 1
                if not closed:
                    raise ValueError(f"invalid path {path!r}: unterminated quoted key")
                key = "".join(buf)
            else:
                start = i
                while i < n and path[i] not in ".[":
                    i += 1
                key = path[start:i]
                if not key:
                    raise ValueError(f"invalid path {path!r}: empty segment")
            indices: list[int] = []
            while i < n and path[i] == "[":
                close = path.find("]", i)
                if close == -1:
                    raise ValueError(f"invalid path {path!r}: unterminated index")
                digits = path[i + 1 : close]
                if not (digits.isascii() and digits.isdigit()) or (len(digits) > 1 and digits[0] == "0"):
                    raise ValueError(f"invalid path {path!r}: bad index {digits!r}")
                indices.append(int(digits))
                i = close + 1
            segments.append(_Segment(key, tuple(indices)))
            if i >= n:
                return segments
            if path[i] != ".":
                raise ValueError(f"invalid path {path!r}: unexpected {path[i]!r}")
            i += 1

    @staticmethod
    def _find_path(node: Any, segments: list[_Segment]) -> Any:
        for i, seg in enumerate(segments):
            if not isinstance(node, Table) or seg.key not in node:
                return None
            node = node[seg.key]
            for idx in seg.indices:
                if not isinstance(node, ArrayOfTables) or idx >= len(node):
                    return None
                node = node[idx]
            if isinstance(node, ArrayOfTables):
                rest = segments[i + 1 :]
                if not rest:
                    return node  # terminal segment: the aot itself
                # project the remaining path over every element; elements
                # missing it contribute None — the result type never depends
                # on the element count
                return [Document._find_path(element, rest) for element in node]
        return node

    @staticmethod
    def _assign_into(target: Any, segments: list[_Segment], value: Any) -> None:
        """
        Navigate to the deepest table present along *segments* and assign the
        rest in one step; a segment naming an array of tables broadcasts the
        remaining path into **every** element. Missing intermediate tables are
        built bottom-up as plain nested dicts so the engine renders them as
        ``[table]`` blocks containing their entries. *segments* must not carry
        indices (indexed writes resolve exactly before reaching here).
        """
        target_table: Any = target
        parent: Table | None = None
        depth = 0
        while depth < len(segments):
            key = segments[depth].key
            child = target_table._raw_get(key) if isinstance(target_table, Table) else None
            if isinstance(child, ArrayOfTables):
                if depth == len(segments) - 1:
                    # final segment names the aot: replace it wholesale
                    break
                if not child:
                    return  # nothing to broadcast into
                for element in list(child):
                    Document._assign_into(element, segments[depth + 1 :], value)
                return
            if not isinstance(child, Table):
                break
            parent = target_table
            target_table = child
            depth += 1
        if depth == len(segments) and parent is not None:
            # the full path names an existing table: any new value replaces it
            # wholesale (the old header and entries are marked deleted first)
            del parent[segments[-1].key]
            parent[segments[-1].key] = value
            return
        if depth == len(segments) - 1:
            target_table[segments[-1].key] = value
            return
        payload: Any = {segments[-1].key: value}
        for seg in reversed(segments[depth + 1 : -1]):
            payload = {seg.key: payload}
        target_table[segments[depth].key] = payload

    # -- rendering --------------------------------------------------------- #

    def dumps(self) -> str:
        """
        Render the document. Unchanged documents round-trip byte-exactly.
        """
        return render_document(self._source, self._parts, self.root)

    def as_string(self) -> str:
        """
        tomlkit-compatible alias of :meth:`dumps`.
        """
        return self.dumps()

    def save(self, path: str | os.PathLike[str]) -> None:
        """
        Render and atomically write to *path* (tempfile + ``os.replace``).
        """
        atomic_write_text(path, self.dumps())

    # -- navigation / conversion ------------------------------------------ #

    def find(self, dotted_path: str) -> Any:
        """
        Return the value at *dotted_path*, or ``None``.

        Bare keys, quoted keys (``"a.b"``) and ``[int]`` array-of-tables
        indexing (``it[0].n``) combine freely. A path segment naming an array
        of tables without an index projects the remaining path over its
        elements (``find("it.n")`` returns the list of per-element values,
        with ``None`` for elements missing the key); the array itself is
        returned when it names the terminal segment.
        """
        return self._find_path(self.root, self._split_path(dotted_path))

    def set_path(self, dotted_path: str, value: Any) -> None:
        """
        Assign *value* at *dotted_path*, creating missing keys and
        intermediate ``[table]`` blocks along the way. A segment naming an
        array of tables broadcasts the remaining path into **every** element
        (``set_path("it.n", 0)`` sets ``n = 0`` in each element); with an
        explicit index (``it[0].n``) only that element is written, and keys
        along the indexed portion must already exist (``KeyError``/``IndexError``).
        ``None`` entries inside dict/list values are dropped first; a bare
        ``None`` raises :class:`TOMLTypeError` (TOML has no null — delete the
        key instead).
        """
        segments = self._split_path(dotted_path)
        if isinstance(value, (dict, list, tuple)):
            value = _prune_none(value)
        last_indexed = max((i for i, seg in enumerate(segments) if seg.indices), default=-1)
        if last_indexed == -1:
            self._assign_into(self.root, segments, value)
            return
        node: Any = self.root
        aot: ArrayOfTables | None = None
        last_idx = -1
        for seg in segments[: last_indexed + 1]:
            if not isinstance(node, Table) or seg.key not in node:
                raise KeyError(f"key {seg.key!r} not found (indexed paths are not auto-created)")
            node = node[seg.key]
            for idx in seg.indices:
                if not isinstance(node, ArrayOfTables):
                    raise KeyError(f"{seg.key!r} is not an array of tables")
                if idx >= len(node):
                    raise IndexError(f"element index {idx} out of range for {seg.key!r}")
                aot, last_idx = node, idx
                node = node[idx]
        rest = segments[last_indexed + 1 :]
        if rest:
            self._assign_into(node, rest, value)
        elif aot is not None:
            aot[last_idx] = value  # hooked: the element re-renders in place
        else:  # pragma: no cover - last_indexed >= 0 implies aot is set
            raise AssertionError("indexed navigation lost the array")

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to plain nested dicts (standard-library datetime objects).
        """
        return _to_plain(self.root)

    def unwrap(self) -> dict[str, Any]:
        """
        tomlkit-compatible alias of :meth:`to_dict`.
        """
        return self.to_dict()

    # -- comment API -------------------------------------------------------- #

    def _line_end(self, offset: int) -> int:
        nxt = self._source.find(chr(10), offset)
        return nxt if nxt != -1 else len(self._source)

    def comment(self, dotted_path: str) -> str | None:
        """
        Return the comment trailing *dotted_path* (without ``#``), or ``None``.

        Resolves key-value lines, table header lines (``[db] # note``),
        dotted-key leaves, API-created keys and array-of-tables element
        fields (``it[0].n``). Paths crossing an array of tables without an
        index are ambiguous and resolve to ``None``.
        """
        target = self._resolve_comment_target(self._split_path(dotted_path))
        if target is None:
            return None
        if target[0] == "header":
            table = target[1]
            if () in table._comments:
                return table._comments[()]  # None = original comment suppressed
            span = table._header_comment_span
            if span is None:
                return None
            text = self._source[span[0] : span[1]].strip()
            return text[1:].strip() if text.startswith("#") else None
        block, phys = target[1], target[2]
        if phys in block._comments:
            return block._comments[phys]  # None = original comment suppressed
        span = block.entry_spans.get(phys)
        if span is None:
            return None
        _vs, _ve, cs = span
        line_end = self._line_end(cs)
        text = self._source[cs:line_end].strip()
        return text[1:].strip() if text.startswith("#") else None

    def set_comment(self, dotted_path: str, comment: str | None) -> None:
        """
        Set (or clear with ``None``) the comment trailing *dotted_path*.
        Comments survive every read-edit-save cycle; unknown paths raise
        ``KeyError``.
        """
        target = self._resolve_comment_target(self._split_path(dotted_path))
        if target is None:
            raise KeyError(f"no such key: {dotted_path!r}")
        if target[0] == "header":
            table = target[1]
            if comment is None:
                table._comments[()] = None  # suppress the original comment
            else:
                table._comments[()] = comment
            return
        block, phys = target[1], target[2]
        block._comments[phys] = comment

    # -- comment resolution ---------------------------------------------- #

    def _resolve_comment_target(
        self, segments: list[_Segment]
    ) -> tuple[Literal["header"], Table] | tuple[Literal["entry"], Table, tuple[str, ...]] | None:
        """
        Resolve *segments* to a comment target:

        - ``("header", table)``       — the path names a table itself
        - ``("entry", block, phys)``  — the path names an entry line on *block*
        - ``None``                    — unresolvable (missing key / bad index)

        Real sub-tables are descended into; sealed (dotted-key) tables and inline
        tables are leaves — their physical lines live on the current block under
        the accumulated path, so the remaining segments flatten into it.
        """
        block: Table = self.root
        consumed: list[str] = []
        for i, seg in enumerate(segments):
            last = i == len(segments) - 1
            if seg.indices:
                if seg.key not in block:
                    return None
                node = block._raw_get(seg.key)
                if not isinstance(node, ArrayOfTables):
                    return None
                for idx in seg.indices:
                    if idx >= len(node):
                        return None
                    node = node[idx]
                if not isinstance(node, Table):
                    return None
                block = node
                consumed = []
                continue
            child = block._raw_get(seg.key) if seg.key in block else None
            if isinstance(child, Table) and not isinstance(child, InlineTable) and not child.sealed:
                # a real sub-table: descend (its entries are addressed relative to itself)
                if last:
                    return "header", child
                block = child
                consumed = []
                continue
            # leaf value, inline table, sealed dotted table or missing key: the
            # physical line (if any) lives on the current block under this path;
            # every segment along it must exist or the target is unresolvable
            if seg.key not in block:
                return None
            node = block._raw_get(seg.key)
            for s2 in segments[i + 1 :]:
                if not isinstance(node, Mapping) or s2.key not in node:
                    return None
                node = node[s2.key]
            phys = (*consumed, seg.key, *(s.key for s in segments[i + 1 :]))
            return "entry", block, phys
        return "header", block  # pragma: no cover - empty paths raise in _split_path
