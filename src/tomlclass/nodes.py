"""
CST value containers for the tomlclass engine.

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
from collections.abc import MutableMapping
from typing import Any, SupportsIndex

from .errors import TOMLTypeError

__all__ = [
    "Array",
    "ArrayOfTables",
    "InlineTable",
    "Table",
    "Trivia",
    "comment",
    "format_key",
    "format_value",
    "nl",
    "render_inline",
]

_BARE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


class Trivia(str):
    """
    A standalone line attachable via :meth:`Table.add` / ``Document.add``:
    :func:`comment` builds a ``# text`` line, :func:`nl` a blank line.
    """

    __slots__ = ()


def comment(text: Any) -> Trivia:
    """
    Build a standalone ``# text`` line for :meth:`Table.add`.
    """
    return Trivia(f"# {text}")


def nl() -> Trivia:
    """
    Build a standalone blank line for :meth:`Table.add`.
    """
    return Trivia("")


class _CommentView(MutableMapping[str, Any]):
    """
    String-keyed view over a table's entry comments (``table.comments["port"]``).
    Multi-segment bookkeeping keys stay internal (``Table._comments``).
    """

    __slots__ = ("_table",)

    def __init__(self, table: Table) -> None:
        self._table = table

    def __getitem__(self, key: str) -> Any:
        value = self._table._comments.get((key,))
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        if not isinstance(key, str):
            raise TypeError(f"comment keys must be strings, got {type(key).__name__}")
        self._table._comments[(key,)] = value

    def __delitem__(self, key: str) -> None:
        if (key,) not in self._table._comments:
            raise KeyError(key)
        del self._table._comments[(key,)]

    def __iter__(self):
        for phys in self._table._comments:
            if len(phys) == 1:
                yield phys[0]

    def __len__(self) -> int:
        return sum(1 for phys in self._table._comments if len(phys) == 1)

    def __repr__(self) -> str:
        return repr({k: self._table._comments[(k,)] for k in self})


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
        "_comments",
        "_header_comment_span",
        "_header_keys",
        "_phys",
        "array_appends",
        "dead",
        "defined",
        "deleted",
        "dirty",
        "entry_spans",
        "inline",
        "kind",
        "pending",
        "pending_aots",
        "pending_tables",
        "pending_trivia",
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
        self._header_comment_span: tuple[int, int] | None = None  # "# ..." span on the header line, if any
        # phys path -> comment override (string-keyed view: .comments)
        self._comments: dict[tuple[str, ...], str | None] = {}
        self.pending: list[tuple[tuple[str, ...], Any]] = []     # (phys path, value) added via API
        self.pending_tables: list[tuple[tuple[str, ...], Table]] = []  # (phys path, sub-table)
        self.pending_aots: list[tuple[tuple[str, ...], ArrayOfTables]] = []  # (phys path, constructed aot)
        self.pending_trivia: list[str] = []                      # standalone comment/blank lines (pre-rendered)
        self.array_appends: dict[tuple[str, ...], Array] = {}    # phys path -> array with spliced appends
        self.dirty: dict[tuple[str, ...], Any] = {}              # phys path -> current value
        self.deleted: set[tuple[str, ...]] = set()
        # phys path -> (value start, value end, comment start; comment_start == line end means no comment)
        self.entry_spans: dict[tuple[str, ...], tuple[int, int, int]] = {}

    @property
    def comments(self) -> _CommentView:
        """
        String-keyed view of this table's entry comments
        (``table.comments["port"] = "text"``; ``del`` removes the override).
        """
        return _CommentView(self)

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

    # -- hooked mapping surface ------------------------------------------- #
    # the inherited dict methods bypass __setitem__/__delitem__ (and with
    # them the edit bookkeeping); route every mutator through the hooks so
    # in-memory state and rendered output can never diverge

    def update(self, *args: Any, **kwargs: Any) -> None:
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key not in self:
            self[key] = default
        return self[key]

    def pop(self, key: str, *default: Any) -> Any:
        try:
            value = dict.__getitem__(self, key)
        except KeyError:
            if default:
                return default[0]
            raise
        del self[key]
        return value

    def popitem(self) -> tuple[str, Any]:
        key = next(iter(self))
        value = dict.__getitem__(self, key)
        del self[key]
        return key, value

    def clear(self) -> None:
        for key in list(self):
            del self[key]

    def to_dict(self) -> dict[str, Any]:
        """
        Plain nested dict of this subtree (standard-library datetime objects).
        """
        from ._document import _to_plain

        return _to_plain(self)

    def add(self, key_or_item: Any, value: Any = None) -> None:
        """
        Attach a key or a standalone trivia line (``comment(...)`` / ``nl()``).
        Setting an existing key raises ``KeyError`` (tomlkit ``add`` semantics).
        """
        if isinstance(key_or_item, Trivia):
            self.pending_trivia.append(str(key_or_item))
            return
        if key_or_item in self:
            raise KeyError(f"key {key_or_item!r} already exists")
        self[key_or_item] = value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict.__repr__(self)})"

    def mark_dead(self) -> None:
        """
        Mark this table and its sub-tables dead — their parts render as
        nothing. ``ArrayOfTables`` inherits it; individual elements are marked
        by ``ArrayOfTables.pop`` / ``clear`` and by wholesale replacements.
        """
        self.dead = True
        for value in self.values():
            if isinstance(value, Table):
                value.mark_dead()


class InlineTable(Table):
    """
    An inline table (``{ x = 1 }``). Closed: cannot be extended after it is
    assigned into a document.

    :param items: optional initial mapping — ``InlineTable({"x": 1})``
        populates the table at construction time
    :param span: source span (engine-internal)
    """

    __slots__ = ()

    def __init__(self, items: Any = None, span: tuple[int, int] = (0, 0)) -> None:
        super().__init__(span=span, kind="inline")
        self.inline = True
        if items:
            for key, value in items.items():
                dict.__setitem__(self, key, value)  # raw: construction precedes document attachment


class Array(list):  # type: ignore[type-arg]
    """
    A TOML array.

    Mutations through the list API switch the array to canonical rendering and
    mark the owning key/value entry dirty (via ``_owner``).
    """

    __slots__ = ("_appended", "_dirty_indices", "_owner", "_parent_array", "dirty", "span", "spans")

    def __init__(self, span: tuple[int, int] = (0, 0), spans: list[tuple[int, int] | None] | None = None) -> None:
        super().__init__()
        self.span = span
        self.spans: list[tuple[int, int] | None] = spans if spans is not None else []
        self.dirty = False
        self._owner: tuple[Table, tuple[str, ...]] | None = None
        self._parent_array: Array | None = None  # enclosing array when nested
        self._appended: list[Any] = []  # clean-array append: spliced into source, not re-rendered
        # None = structurally mutated, re-render canonically; a set = only
        # these element indices were assigned, render by splicing their spans
        self._dirty_indices: set[int] | None = set()

    def _touch(self) -> None:
        self.dirty = True
        if self._owner is not None:
            block, path = self._owner
            block.dirty[path] = self

    def _touch_whole(self) -> None:
        """Structural mutation: per-element spans are no longer trustworthy."""
        if self._dirty_indices is not None:
            self._dirty_indices = None
        self._touch()

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

    def extend(self, iterable: Any) -> None:
        self._touch_whole()
        items = list(iterable)
        self.spans.extend([None] * len(items))
        list.extend(self, items)

    def insert(self, index: SupportsIndex, object: Any) -> None:
        self._touch_whole()
        self.spans.insert(index, None)
        list.insert(self, index, object)

    def pop(self, index: SupportsIndex = -1) -> Any:
        self._touch_whole()
        self.spans.pop(index)
        return list.pop(self, index)

    def clear(self) -> None:
        self._touch_whole()
        self.spans.clear()
        list.clear(self)

    def remove(self, value: Any) -> None:
        self._touch_whole()
        index = list.index(self, value)
        self.spans.pop(index)
        list.pop(self, index)

    def sort(self, /, **kwargs: Any) -> None:
        self._touch_whole()
        list.sort(self, **kwargs)

    def reverse(self) -> None:
        self._touch_whole()
        list.reverse(self)

    def __setitem__(self, index: Any, value: Any) -> None:
        self._touch()
        if isinstance(index, slice):
            self._touch_whole()
            self.spans[index] = [None] * len(list(value))
            list.__setitem__(self, index, value)
            return
        if self._dirty_indices is None:
            list.__setitem__(self, index, value)
            return
        i = int(index)
        if i < 0:
            i += len(self)
        if self.spans[i] is None:
            # an appended element was edited: no source text to splice into
            self._dirty_indices = None
        else:
            self._dirty_indices.add(i)  # keep the span — render splices in place
        list.__setitem__(self, i, value)

    def __delitem__(self, index: Any) -> None:
        self._touch_whole()
        del self.spans[index]
        list.__delitem__(self, index)

    def __iadd__(self, iterable: Any) -> Array:  # type: ignore[override]
        self.extend(iterable)
        return self


class ArrayOfTables(Array):
    """
    An array created by ``[[table]]`` headers; elements are Tables.

    Appending a mapping converts it to an element table rendered as a fresh
    ``[[block]]`` after the last parsed element; ``insert`` renders before the
    element at the given position. The render is idempotent.
    """

    __slots__ = ("_appended_elements", "_header_keys", "_inserted_elements", "pending_elements")

    def __init__(self, span: tuple[int, int] = (0, 0)) -> None:
        super().__init__(span=span)
        self.pending_elements: list[dict[str, Any]] = []
        self._header_keys: tuple[str, ...] = ()
        self._appended_elements: list[Table] = []
        # runtime insert()s: (anchor, element) — anchor is the parsed element
        # the new block renders before (None = tail, alongside _appended_elements).
        # Consumed by render.py's "aot_ins" anchors / _flush_aot_appended;
        # changing the shape here means changing the renderer too.
        self._inserted_elements: list[tuple[Table | None, Table]] = []

    def append_table(self, table: Table) -> Table:
        table._aot = self
        table._header_keys = self._header_keys
        list.append(self, table)
        return table

    def _coerce_element(self, data: Any) -> Table:
        if isinstance(data, Table):
            data._aot = self
            data._header_keys = self._header_keys
            data.kind = "aot"
            # a user-built table records construction-time assignments as
            # pending entries; an aot element renders from its items directly,
            # so keeping them would emit every value a second time
            data.pending.clear()
            data.pending_tables.clear()
            return data
        if not isinstance(data, dict):
            raise TOMLTypeError(
                f"cannot use {type(data).__name__} as an array-of-tables element",
                value=data,
            )
        element = Table(kind="aot")
        element._header_keys = self._header_keys
        element._aot = self
        element.defined = True
        for key, value in data.items():
            format_value(value)  # eager serializability check
            dict.__setitem__(element, key, value)  # raw: the tail anchor renders these
        return element

    def append(self, object: Any) -> None:
        element = self._coerce_element(object)
        list.append(self, element)
        self._appended_elements.append(element)

    def _is_added(self, element: Table) -> bool:
        for appended in self._appended_elements:
            if appended is element:
                return True
        return any(el is element for _anchor, el in self._inserted_elements)

    def insert(self, index: SupportsIndex, object: Any) -> None:
        element = self._coerce_element(object)
        i = index.__index__()
        n = len(self)
        if i < 0:
            i += n
        i = min(max(i, 0), n)
        # the block renders before the first parsed element at or after the
        # insertion point (appended elements are skipped — they all live at
        # the tail); None anchors to the tail
        anchor: Table | None = None
        for j in range(i, n):
            if not self._is_added(self[j]):
                anchor = self[j]
                break
        list.insert(self, i, element)
        self._inserted_elements.append((anchor, element))

    def extend(self, iterable: Any) -> None:
        # route through append: AoT elements render as [[blocks]] via the
        # append bookkeeping, never through the inline-array pipeline
        for item in iterable:
            self.append(item)

    def __setitem__(self, index: Any, value: Any) -> None:
        if isinstance(index, slice):
            raise NotImplementedError(
                "slice assignment on an array-of-tables is not supported; use del + insert"
            )
        i = index.__index__()
        if i < 0:
            i += len(self)
        if not 0 <= i < len(self):
            raise IndexError("array-of-tables assignment index out of range")
        element = self._coerce_element(value)
        old = self[i]
        if element is old:
            return
        # the old element's parts are suppressed; the new block renders at the
        # same position — before the next parsed element, or at the tail
        old.mark_dead()
        anchor = None
        for j in range(i + 1, len(self)):
            if not self._is_added(self[j]):
                anchor = self[j]
                break
        list.__setitem__(self, i, element)
        self._inserted_elements.append((anchor, element))

    def sort(self, /, **kwargs: Any) -> None:
        raise NotImplementedError(
            "sorting an array-of-tables is not supported; replace it wholesale instead"
        )

    def reverse(self) -> None:
        raise NotImplementedError(
            "reversing an array-of-tables is not supported; replace it wholesale instead"
        )

    def pop(self, index: SupportsIndex = -1) -> Any:
        i = index.__index__()
        if i < 0:
            i += len(self)
        element = list.pop(self, i)
        if element in self._appended_elements:
            self._appended_elements.remove(element)
        else:
            element.mark_dead()
        self._inserted_elements = [
            (anchor, el) for anchor, el in self._inserted_elements if el is not element
        ]
        return element

    def remove(self, value: Any) -> None:
        for i, element in enumerate(list(self)):
            if element == value:
                self.pop(i)
                return
        raise ValueError("ArrayOfTables.remove(x): x not in list")

    def clear(self) -> None:
        for element in list(self):
            if isinstance(element, Table):
                element.mark_dead()
        self._appended_elements.clear()
        self._inserted_elements.clear()
        list.clear(self)

    def __delitem__(self, index: Any) -> None:
        self.pop(index)


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
    if not isinstance(key, str):
        key = str(key)  # API-assigned non-str keys (ints, bools) render canonically
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
    Carriage returns are always escaped — a raw CR inside a multi-line string
    would be normalized away by conforming parsers on re-read.
    """
    if isinstance(value, str) and "\n" in value:
        if '"""' in value and "'''" not in value and "\\" not in value and "\r" not in value:
            # content conflicts with triple-double quotes: use a multi-line literal string instead
            return "'''\n" + value + "'''"
        body = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        body = body.replace("\r", "\\r")  # keep CR through the parse round-trip
        return '"""\n' + body + '"""'
    return render_inline(value)
