"""
CST value containers for the tomlclass engine.

Model (design doc §3.1):

- Every node records its source span. Untouched nodes render by slicing the
  original source — style is the source text itself, costing nothing.
- Touched nodes render from their current Python value with canonical
  formatting (``format_value``).
- ``Table`` doubles as the mutable user-facing mapping. Tables created by
  dotted keys are *sealed* (a ``[table]`` header may not later define them)
  and know the physical block (``_block``) that hosts their entries, plus the
  dotted path (``_phys``) relative to that block.
"""

from __future__ import annotations

import math
from typing import Any, SupportsIndex

from .errors import TOMLTypeError

__all__ = [
    "Array",
    "ArrayOfTables",
    "InlineTable",
    "Table",
    "format_key",
    "format_value",
    "render_inline",
]

_BARE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


class Table(dict):  # type: ignore[type-arg]
    """
    A TOML table; also the mutable user-facing mapping.

    :param span: ``(start, end)`` span of this table's header line
    :param kind: ``"root"`` / ``"header"`` / ``"aot"`` / ``"dotted"`` / ``"inline"``
    """

    __slots__ = (
        "_anchor",
        "_aot",
        "_block",
        "_header_keys",
        "_phys",
        "array_appends",
        "comments",
        "dead",
        "defined",
        "deleted",
        "dirty",
        "entry_spans",
        "inline",
        "kind",
        "pending",
        "pending_tables",
        "sealed",
        "span",
    )

    def __init__(self, span: tuple[int, int] = (0, 0), kind: str = "header") -> None:
        super().__init__()
        self.span = span
        self.kind = kind
        self.defined = False       # explicitly defined by a [table] header
        self.sealed = False        # created via dotted keys; a header may not define it
        self.inline = False
        self.dead = False          # subtree removed via `del`; its parts render as nothing
        self._anchor: int | None = None    # part index after which this dotted table's entries render
        self._block: Table | None = None   # physical block hosting entries (dotted tables only)
        self._phys: tuple[str, ...] = ()   # dotted path relative to the physical block
        self._header_keys: tuple[str, ...] = ()
        self._aot: ArrayOfTables | None = None
        self.pending: list[tuple[tuple[str, ...], Any]] = []     # (phys path, value) added via API
        self.pending_tables: list[tuple[tuple[str, ...], Table]] = []  # (phys path, sub-table)
        self.array_appends: dict[tuple[str, ...], Array] = {}    # phys path -> array with spliced appends
        self.dirty: dict[tuple[str, ...], Any] = {}              # phys path -> current value
        self.deleted: set[tuple[str, ...]] = set()
        # phys path -> (value start, value end, comment start; comment_start == line end means no comment)
        self.entry_spans: dict[tuple[str, ...], tuple[int, int, int]] = {}
        self.comments: dict[tuple[str, ...], str | None] = {}  # phys path -> comment override (schema injection)

    # -- raw access for the parser (bypasses engine hooks) ---------------- #

    def _raw_set(self, key: str, value: Any) -> None:
        dict.__setitem__(self, key, value)

    def _raw_get(self, key: str) -> Any:
        return dict.get(self, key)

    # -- user-facing mapping (records edits for the renderer) ------------- #

    def __setitem__(self, key: str, value: Any) -> None:
        from .engine_set import engine_set

        stored = engine_set(self, (key,), value)
        dict.__setitem__(self, key, stored)

    def __delitem__(self, key: str) -> None:
        from .engine_set import engine_del

        engine_del(self, (key,))
        dict.__delitem__(self, key)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict.__repr__(self)})"


class InlineTable(Table):
    """
    An inline table (``{ x = 1 }``). Closed: cannot be extended later.
    """

    __slots__ = ()

    def __init__(self, span: tuple[int, int] = (0, 0)) -> None:
        super().__init__(span=span, kind="inline")
        self.inline = True


class Array(list):  # type: ignore[type-arg]
    """
    A TOML array.

    Mutations through the list API switch the array to canonical rendering and
    mark the owning key/value entry dirty (via ``_owner``).
    """

    __slots__ = ("_appended", "_owner", "dirty", "span", "spans")

    def __init__(self, span: tuple[int, int] = (0, 0), spans: list[tuple[int, int] | None] | None = None) -> None:
        super().__init__()
        self.span = span
        self.spans: list[tuple[int, int] | None] = spans if spans is not None else []
        self.dirty = False
        self._owner: tuple[Table, tuple[str, ...]] | None = None
        self._appended: list[Any] = []  # clean-array append: spliced into source, not re-rendered

    def _touch(self) -> None:
        self.dirty = True
        if self._owner is not None:
            block, path = self._owner
            block.dirty[path] = self

    def append(self, object: Any) -> None:
        if not self.dirty and self._owner is not None:
            # clean-array append: splice into the source so existing elements and comments stay byte-exact
            block, path = self._owner
            self._appended.append(object)
            list.append(self, object)
            block.array_appends[path] = self
            return
        self._touch()
        self.spans.append(None)
        list.append(self, object)

    def extend(self, iterable: Any) -> None:  # type: ignore[override]
        self._touch()
        items = list(iterable)
        self.spans.extend([None] * len(items))
        list.extend(self, items)

    def insert(self, index: SupportsIndex, object: Any) -> None:
        self._touch()
        self.spans.insert(index, None)
        list.insert(self, index, object)

    def pop(self, index: SupportsIndex = -1) -> Any:
        self._touch()
        self.spans.pop(index)
        return list.pop(self, index)

    def clear(self) -> None:  # type: ignore[override]
        self._touch()
        self.spans.clear()
        list.clear(self)

    def remove(self, value: Any) -> None:
        self._touch()
        index = list.index(self, value)
        self.spans.pop(index)
        list.pop(self, index)

    def __setitem__(self, index: Any, value: Any) -> None:
        self._touch()
        if isinstance(index, slice):
            self.spans[index] = [None] * len(list(value))
        else:
            self.spans[index] = None
        list.__setitem__(self, index, value)

    def __delitem__(self, index: Any) -> None:
        self._touch()
        del self.spans[index]
        list.__delitem__(self, index)

    def __iadd__(self, iterable: Any) -> Array:  # type: ignore[override]
        self.extend(iterable)
        return self


class ArrayOfTables(Array):
    """
    An array created by ``[[table]]`` headers; elements are Tables.

    Appending plain dicts defers them as pending elements, rendered as new
    ``[[table]]`` blocks after the last parsed element.
    """

    __slots__ = ("pending_elements",)

    def __init__(self, span: tuple[int, int] = (0, 0)) -> None:
        super().__init__(span=span)
        self.pending_elements: list[dict[str, Any]] = []

    def append_table(self, table: Table) -> Table:
        list.append(self, table)
        return table

    def append(self, object: Any) -> None:
        if isinstance(object, Table):
            super().append(object)
        else:
            self.pending_elements.append(object)


def _escape_basic(s: str) -> str:
    out: list[str] = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\t":
            out.append("\t")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20 or ch == "\x7f":
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return "".join(out)


def format_key(key: str) -> str:
    """
    Render a key: bare when possible, otherwise a quoted basic string.
    """
    if key and all(c in _BARE_CHARS for c in key):
        return key
    return '"' + _escape_basic(key) + '"'


def render_inline(value: Any) -> str:
    """
    Canonical inline rendering for any TOML value.
    """
    if value is None:
        raise TOMLTypeError("None cannot be represented in TOML", value=value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + _escape_basic(value) + '"'
    if isinstance(value, Table):
        body = ", ".join(f"{format_key(k)} = {render_inline(value[k])}" for k in value)
        return "{" + (f" {body} " if body else "") + "}"
    if isinstance(value, Array):
        return "[" + ", ".join(render_inline(v) for v in value) + "]"
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if hasattr(value, "toml_raw"):  # engine datetime nodes: exact source spelling
        return str(value.toml_raw)
    if hasattr(value, "isoformat"):  # plain datetime/date/time from user code
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(render_inline(v) for v in value) + "]"
    if isinstance(value, dict):
        body = ", ".join(f"{format_key(str(k))} = {render_inline(value[k])}" for k in value)
        return "{" + (f" {body} " if body else "") + "}"
    raise TOMLTypeError(f"cannot serialize {type(value).__name__} as TOML", value=value)


def format_value(value: Any) -> str:
    """
    Canonical rendering used for values edited through the API.

    Strings containing newlines render as multi-line strings. When the
    content itself contains triple-double quotes and needs no escapes, a
    multi-line literal string is used instead. Anything else renders inline.
    """
    if isinstance(value, str) and "\n" in value:
        if '"""' in value and "'''" not in value and "\\" not in value:
            # content conflicts with triple-double quotes: use a multi-line literal string instead
            return "'''\n" + value + "'''"
        body = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        return '"""\n' + body + '"""'
    return render_inline(value)
