"""
Single-pass TOML 1.0/1.1 parser producing a lossless CST.

Technique: character-dispatch scanning in one pass over the source (the
approach tomli proved viable for pure-Python speed), with precompiled-regex
chunk matching for trivia, comments, keys and string bodies — no per-character
Python loops on the hot path. Every node records a source span; the span *is*
the style, so untouched nodes cost only two integers.

The parser emits ``parts`` — an ordered, gap-free list of ``(start, end,
kind, payload)`` tuples covering the entire source — which the renderer
splices:

- ``("trivia", None)``                      — whitespace/newlines/comments
- ``("kv", (block, phys_path))``            — a ``key = value`` line
- ``("header", (table, aot|None))``         — a ``[table]`` / ``[[table]]`` line

Semantic rules implemented per TOML 1.0, with the TOML 1.1 additions
(``\\e`` and ``\\x`` escapes, seconds omitted from times, newlines and
trailing commas inside inline tables, non-ASCII bare keys):

- duplicate keys/tables are errors; tables defined by dotted keys are *sealed*
  (a later ``[table]`` header may not define them, but deeper headers may)
- super-tables auto-created by deeper headers may be defined afterwards
- inline tables are closed; dotted keys cannot descend into arrays or into
  tables explicitly defined by a ``[table]`` header (toml-lang#846)
- ``[[aot]]`` appends elements; ``[aot.sub]`` targets the last element
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any

from .errors import TOMLParseError
from .nodes import Array, ArrayOfTables, InlineTable, Table

_BARE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_DIGITS = frozenset("0123456789")

_TRIVIA_RE = re.compile(
    r"(?:[ \t\n]+|\r\n|(?:#[^\n\r\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*(?:\r?\n|\Z)))*"
)
_INLINE_WS_RE = re.compile(r"[ \t]*")
_COMMENT_RE = re.compile(r"[^\n\r\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*")
_BARE_KEY_RE = re.compile(r"[A-Za-z0-9_\-\u0080-\U0010ffff]+")
_BARE_KEY_RE_10 = re.compile(r"[A-Za-z0-9_-]+")
_STR_CHUNK_RE = re.compile(r'[^\\"\x00-\x08\x0a-\x1f\x7f]+')          # \t allowed, no " no \
_MLSTR_CHUNK_RE = re.compile(r'[^\\"\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+')  # \t \n \r allowed
_LSTR_CHUNK_RE = re.compile(r"[^'\x00-\x08\x0a-\x1f\x7f]+")           # literal, no '
_MLSTR_LIT_CHUNK_RE = re.compile(r"[^'\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")  # \t \n \r allowed

_DT_OFFSET = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?(?:([Zz])|([+-])(\d{2}):(\d{2}))"
)
_DT_LOCAL = re.compile(r"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?")
_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_TIME = re.compile(r"(\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?")

# TOML 1.0 variants: seconds are mandatory (group indices match the 1.1 forms)
_DT_OFFSET_10 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(\.\d+)?(?:([Zz])|([+-])(\d{2}):(\d{2}))"
)
_DT_LOCAL_10 = re.compile(r"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(\.\d+)?")
_TIME_10 = re.compile(r"(\d{2}):(\d{2}):(\d{2})(\.\d+)?")

_INT_DEC = re.compile(r"[+-]?(0|[1-9](?:_?[0-9])*)\Z")
_INT_HEX = re.compile(r"0x[0-9A-Fa-f](?:_?[0-9A-Fa-f])*")
_INT_OCT = re.compile(r"0o[0-7](?:_?[0-7])*")
_INT_BIN = re.compile(r"0b[01](?:_?[01])*")
_FLOAT = re.compile(r"[+-]?(0|[1-9](?:_?[0-9])*)(\.[0-9](?:_?[0-9])*)?([eE][+-]?[0-9](_?[0-9])*)?\Z")
_NUMBER_TOKEN = re.compile(r"[0-9A-Za-z_+.eE-]+")

_ESCAPES = {'"': '"', "\\": "\\", "b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r"}


class _DateTime(datetime):
    """
    Offset/local datetime that remembers the exact source spelling.
    """

    __slots__ = ("toml_raw",)

    def __new__(  # type: ignore[misc]
        cls,
        y: int, mo: int, d: int, hh: int, mm: int, ss: int,
        micro: int, tz: tzinfo | None, raw: str,
    ) -> _DateTime:
        self = datetime.__new__(cls, y, mo, d, hh, mm, ss, micro, tz)
        self.toml_raw = raw
        return self


class _Date(date):
    """
    Local date that remembers the exact source spelling.
    """

    __slots__ = ("toml_raw",)

    def __new__(cls, y: int, m: int, d: int, raw: str) -> _Date:
        self = date.__new__(cls, y, m, d)
        self.toml_raw = raw
        return self


class _Time(time):
    """
    Local time that remembers the exact source spelling.
    """

    __slots__ = ("toml_raw",)

    def __new__(cls, hh: int, mm: int, ss: int, micro: int, raw: str) -> _Time:
        self = time.__new__(cls, hh, mm, ss, micro)
        self.toml_raw = raw
        return self


class Parser:
    """
    Parse TOML source into a CST :class:`Table` tree plus render parts.

    :param source: TOML text
    :param version: ``"1.1"`` (default) or ``"1.0"`` — 1.0 mode rejects the
        1.1 additions (``\\e`` / ``\\x`` escapes, seconds omitted from times,
        newlines and trailing commas inside inline tables, non-ASCII bare keys)
    """

    def __init__(self, source: str, version: str = "1.1") -> None:
        if version not in ("1.0", "1.1"):
            raise TOMLParseError(f"unsupported TOML version {version!r} (use '1.0' or '1.1')")
        self.v11 = version == "1.1"
        self._bare_key_re = _BARE_KEY_RE if self.v11 else _BARE_KEY_RE_10
        self._dt_offset_re = _DT_OFFSET if self.v11 else _DT_OFFSET_10
        self._dt_local_re = _DT_LOCAL if self.v11 else _DT_LOCAL_10
        self._time_re = _TIME if self.v11 else _TIME_10
        self.s = source
        self.n = len(source)
        self.i = 0
        self.parts: list[tuple[int, int, str, Any]] = []
        self.root = Table(span=(0, self.n), kind="root")
        self.cur: Table = self.root
        self._last_sealed: Table | None = None
    # low-level                                                          #

    def error(self, message: str, at: int | None = None) -> TOMLParseError:
        offset = self.i if at is None else at
        line = self.s.count("\n", 0, offset) + 1
        last_nl = self.s.rfind("\n", 0, offset)
        col = offset - last_nl
        nxt = self.s.find("\n", offset)
        segment = self.s[last_nl + 1 : nxt if nxt != -1 else self.n]
        return TOMLParseError(message, offset, line, col, segment[:80])

    def peek(self, ahead: int = 0) -> str:
        pos = self.i + ahead
        return self.s[pos] if pos < self.n else ""

    def skip_inline_ws(self) -> None:
        s = self.s
        n = self.n
        i = self.i
        while i < n and (s[i] == " " or s[i] == "	"):
            i += 1
        self.i = i

    def skip_comment(self) -> None:
        m = _COMMENT_RE.match(self.s, self.i + 1)
        assert m is not None  # star pattern always matches
        self.i = m.end()

    def consume_newline(self) -> bool:
        if self.i < self.n and self.s[self.i] == "\n":
            self.i += 1
            return True
        if self.i + 1 < self.n and self.s[self.i] == "\r" and self.s[self.i + 1] == "\n":
            self.i += 2
            return True
        return False

    def skip_trivia(self) -> None:
        m = _TRIVIA_RE.match(self.s, self.i)
        assert m is not None  # star pattern always matches
        self.i = m.end()

    def expect(self, ch: str) -> None:
        if self.i < self.n and self.s[self.i] == ch:
            self.i += 1
            return
        raise ValueError(f"expected {ch!r}")

    def _at_line_end(self) -> bool:
        return self.i >= self.n or self.s[self.i] in ("\n", "\r")
    # document loop                                                      #

    def parse(self) -> Table:
        s = self.s
        n = self.n
        parts = self.parts
        while True:
            t0 = self.i
            self.skip_trivia()
            parts.append((t0, self.i, "trivia", None))
            if self.i >= n:
                break
            item_start = self.i
            self._last_sealed = None
            if s[item_start] == "[":
                kind, payload = self.parse_header()
            else:
                kind, payload = self.parse_keyval()
            parts.append((item_start, self.i, kind, payload))
            if self._last_sealed is not None:
                self._last_sealed._anchor = len(parts) - 1
        return self.root
    # keys                                                               #

    def parse_key_path(self) -> list[str]:
        self.skip_inline_ws()
        keys = [self.parse_key()]
        s = self.s
        while True:
            self.skip_inline_ws()
            if self.i < self.n and s[self.i] == ".":
                self.i += 1
                self.skip_inline_ws()
                keys.append(self.parse_key())
            else:
                return keys

    def parse_key(self) -> str:
        start = self.i
        c = self.s[start] if start < self.n else ""
        if c == '"':
            if self.s.startswith('"""', start):
                raise ValueError("multiline strings are not valid keys")
            value = self.parse_basic_string()
        elif c == "'":
            if self.s.startswith("'''", start):
                raise ValueError("multiline strings are not valid keys")
            value = self.parse_literal_string()
        else:
            m = self._bare_key_re.match(self.s, start)
            if m is None:
                raise ValueError(
                    f"invalid key character {c!r}" if c else "unexpected end of input"
                )
            value = m.group()
            if "\ufeff" in value:
                # a BOM is never a key character, even where non-ASCII is allowed
                raise ValueError("byte order mark in bare key")
            self.i = m.end()
        return value
    # headers                                                            #

    def parse_header(self) -> tuple[str, Any]:
        start = self.i
        self.i += 1  # '['
        is_aot = self.peek() == "["
        if is_aot:
            self.i += 1
        keys = self.parse_key_path()
        self.skip_inline_ws()
        self.expect("]")
        if is_aot:
            self.expect("]")
        self.skip_inline_ws()
        if self.peek() == "#":
            self.skip_comment()
        if not self._at_line_end():
            raise ValueError("expected end of line after table header")
        table, aot = self.apply_header(keys, is_aot, (start, self.i))
        if is_aot:
            return "header", (table, aot)
        return "header", (table, None)

    def _navigate_for_header(self, keys: list[str]) -> Table:
        """
        Return the table that will contain the final header key.
        """
        current = self.root
        walked: tuple[str, ...] = ()
        for part in keys[:-1]:
            walked += (part,)
            existing = current._raw_get(part)
            if existing is None:
                fresh = Table(kind="header")  # implicit super-table; may be header-defined later
                # implicit tables record their path: pending_tables hosted
                # on them need the full prefix when rendered
                fresh._header_keys = walked
                current._raw_set(part, fresh)
                current = fresh
                continue
            if isinstance(existing, ArrayOfTables):
                if not existing or not isinstance(existing[-1], Table):
                    raise ValueError(f"cannot descend into empty array-of-tables {part!r}")
                current = existing[-1]
                continue
            if isinstance(existing, Table):
                if existing.inline:
                    raise ValueError(f"cannot descend into inline table {part!r}")
                if not existing._header_keys:
                    existing._header_keys = walked
                current = existing
                continue
            raise ValueError(f"key {part!r} is not a table")
        return current

    def apply_header(
        self, keys: list[str], is_aot: bool, span: tuple[int, int]
    ) -> tuple[Table, ArrayOfTables | None]:
        parent = self._navigate_for_header(keys)
        name = keys[-1]
        existing = parent._raw_get(name)

        if is_aot:
            if existing is None:
                aot = ArrayOfTables(span=span)
                aot._header_keys = tuple(keys)
                parent._raw_set(name, aot)
            elif isinstance(existing, ArrayOfTables):
                aot = existing
                aot._header_keys = tuple(keys)
            else:
                raise ValueError(f"cannot redefine {name!r} as an array of tables")
            table = Table(span=span, kind="aot")
            table.defined = True
            table._header_keys = tuple(keys)
            table._aot = aot
            aot.append_table(table)
            self.cur = table
            return table, aot

        if existing is None:
            table = Table(span=span, kind="header")
            parent._raw_set(name, table)
        elif isinstance(existing, Table) and not existing.defined and not existing.sealed and not existing.inline:
            # implicit super-table created earlier by a deeper header — legal to define now
            table = existing
            table.span = span
        else:
            raise ValueError(f"table {name!r} already defined")
        table.defined = True
        table._header_keys = tuple(keys)
        self.cur = table
        return table, None
    # key = value                                                        #

    def parse_keyval(self) -> tuple[str, Any]:
        keys = self.parse_key_path()  # trailing inline ws already consumed
        s = self.s
        # hot path: inline the '=' check and whitespace skip (method calls
        # here cost ~5% of total parse time on kv-heavy documents)
        if self.i >= self.n or s[self.i] != "=":
            raise ValueError("expected '=' after key")
        self.i += 1
        i = self.i
        n = self.n
        while i < n and (s[i] == " " or s[i] == "\t"):
            i += 1
        self.i = i
        phys = tuple(keys)
        vstart = self.i
        value = self.parse_value((self.cur, phys))
        vend = self.i
        i = self.i
        while i < n and (s[i] == " " or s[i] == "\t"):
            i += 1
        self.i = i
        comment_start = self.i  # points at "#" when a comment follows
        if self.i < n and s[self.i] == "#":
            self.skip_comment()
        if self.i < n and s[self.i] not in ("\n", "\r"):
            raise ValueError("expected end of line after key/value pair")
        self.assign_kv(keys, value)
        self.cur.entry_spans[phys] = (vstart, vend, comment_start)
        return "kv", (self.cur, phys)

    def assign_kv(self, keys: list[str], value: Any) -> tuple[str, ...]:
        table: Table = self.cur
        phys: tuple[str, ...] = ()
        for part in keys[:-1]:
            phys += (part,)
            existing = table._raw_get(part)
            if isinstance(existing, Table):
                if existing.inline:
                    raise ValueError(f"cannot extend inline table {part!r}")
                if existing.defined:
                    # toml-lang#846: dotted keys may not add to a table that was
                    # explicitly defined by a [table] header
                    raise ValueError(
                        f"cannot extend table {part!r} defined by a [table] header with dotted keys"
                    )
                table = existing
                self._last_sealed = existing if existing.sealed else None
                continue
            if isinstance(existing, Array):
                raise ValueError(f"dotted keys cannot extend array {part!r}")
            if existing is not None:
                raise ValueError(f"duplicate key {part!r}")
            fresh = Table(kind="dotted")
            fresh.sealed = True
            fresh._block = self.cur
            fresh._phys = phys
            table._raw_set(part, fresh)
            table = fresh
            self._last_sealed = fresh
        name = keys[-1]
        if name in table:
            raise ValueError(f"duplicate key {name!r}")
        table._raw_set(name, value)
        return (*phys, name)
    # values                                                             #

    def parse_value(self, owner: tuple[Table, tuple[str, ...]] | None = None) -> Any:
        s = self.s
        c = s[self.i] if self.i < self.n else ""
        if c == '"':
            return self.parse_basic_string()
        if c == "'":
            return self.parse_literal_string()
        if c == "t":
            if s.startswith("true", self.i):
                self.i += 4
                return True
            raise ValueError("invalid boolean")
        if c == "f":
            if s.startswith("false", self.i):
                self.i += 5
                return False
            raise ValueError("invalid boolean")
        if c == "[":
            return self.parse_array(owner)
        if c == "{":
            return self.parse_inline_table()
        if c in _DIGITS or c in "+-" or c in ("i", "n"):
            return self.parse_number_or_datetime()
        raise ValueError(f"invalid value character {c!r}")

    # -- strings --------------------------------------------------------- #

    def _check_str_char(self, ch: str, allow_nl: bool) -> None:
        if ch in ("\n", "\r"):
            if not allow_nl:
                raise ValueError("newline in single-line string")
            return
        if (ord(ch) < 0x20 and ch != "\t") or ch == "\x7f":
            raise ValueError("control character in string")

    def parse_basic_string(self) -> str:
        s = self.s
        n = self.n
        if s.startswith('"""', self.i):
            return self.parse_multiline_basic()
        self.i += 1
        out: list[str] = []
        while True:
            m = _STR_CHUNK_RE.match(s, self.i)
            if m is not None and m.end() > self.i:
                out.append(m.group())
                self.i = m.end()
            if self.i >= n:
                raise ValueError("unterminated string")
            ch = s[self.i]
            if ch == '"':
                self.i += 1
                return "".join(out)
            if ch == "\\":
                out.append(self.parse_escape(multiline=False))
                continue
            if ch in ("\n", "\r"):
                raise ValueError("newline in single-line string")
            raise ValueError("control character in string")

    def parse_escape(self, multiline: bool) -> str:
        self.i += 1  # backslash
        ch = self.peek()
        if ch in _ESCAPES:
            self.i += 1
            return _ESCAPES[ch]
        if ch in ("u", "U"):
            width = 4 if ch == "u" else 8
            hexpart = self.s[self.i + 1 : self.i + 1 + width]
            if len(hexpart) != width or any(c not in _HEX_DIGITS for c in hexpart):
                raise ValueError("invalid unicode escape")
            code = int(hexpart, 16)
            if code > 0x10FFFF:
                raise ValueError("unicode escape out of range")
            if 0xD800 <= code <= 0xDFFF:
                raise ValueError("surrogate escape in string")
            self.i += 1 + width
            return chr(code)
        if self.v11:
            if ch == "e":
                self.i += 1
                return "\x1b"
            if ch == "x":
                # TOML 1.1: \xHH — exactly two hex digits, codepoint 0..255
                hexpart = self.s[self.i + 1 : self.i + 3]
                if len(hexpart) != 2 or any(c not in _HEX_DIGITS for c in hexpart):
                    raise ValueError("invalid hex escape")
                self.i += 3
                return chr(int(hexpart, 16))
        if multiline and ch in (" ", "\t", "\n", "\r"):
            j = self.i
            saw_newline = False
            while j < self.n and self.s[j] in (" ", "\t", "\n", "\r"):
                if self.s[j] in ("\n", "\r"):
                    saw_newline = True
                j += 1
            if saw_newline:
                self.i = j
                return ""
            raise ValueError("invalid escape: backslash followed by whitespace")
        raise ValueError(f"invalid escape \\{ch}")

    def parse_multiline_basic(self) -> str:
        s = self.s
        n = self.n
        self.i += 3
        self.consume_newline()
        out: list[str] = []
        while True:
            if s.startswith('"""', self.i):
                extra = 0
                while extra < 2 and self.peek(3 + extra) == '"':
                    extra += 1
                out.append('"' * extra)
                self.i += 3 + extra
                # raw CRLF was already normalized per-chunk above; escape-produced
                # CR LF (e.g. \x0d\x0a) must survive untouched
                return "".join(out)
            m = _MLSTR_CHUNK_RE.match(s, self.i)
            if m is not None and m.end() > self.i:
                chunk = m.group()
                if "\r\n" in chunk:
                    chunk = chunk.replace("\r\n", "\n")
                if "\r" in chunk:
                    raise ValueError("bare carriage return in string")
                out.append(chunk)
                self.i = m.end()
                continue
            if self.i >= n:
                raise ValueError("unterminated multiline string")
            ch = s[self.i]
            if ch == "\\":
                out.append(self.parse_escape(multiline=True))
                continue
            if ch == '"':
                # a lone quote (1-2) is content; the closer check above handled """
                out.append('"')
                self.i += 1
                continue
            if ch == "\r":
                if self.peek(1) != "\n":
                    raise ValueError("bare carriage return in string")
                out.append("\n")
                self.i += 2
                continue
            raise ValueError("control character in string")

    def parse_literal_string(self) -> str:
        s = self.s
        n = self.n
        if s.startswith("'''", self.i):
            return self.parse_multiline_literal()
        self.i += 1
        m = _LSTR_CHUNK_RE.match(s, self.i)
        if m is None:
            if self.i < n and s[self.i] == "'":
                self.i += 1
                return ""
            raise ValueError("unterminated string")
        end = m.end()
        if end >= n:
            raise ValueError("unterminated string")
        if s[end] == "'":
            self.i = end + 1
            return m.group()
        if s[end] in ("\n", "\r"):
            raise ValueError("newline in single-line string")
        raise ValueError("control character in string")

    def parse_multiline_literal(self) -> str:
        s = self.s
        self.i += 3
        self.consume_newline()
        out: list[str] = []
        while True:
            if s.startswith("'''", self.i):
                extra = 0
                while extra < 2 and self.peek(3 + extra) == "'":
                    extra += 1
                out.append("'" * extra)
                self.i += 3 + extra
                return "".join(out)  # literal chunks normalized raw CRLF above
            m = _MLSTR_LIT_CHUNK_RE.match(s, self.i)
            if m is not None and m.end() > self.i:
                chunk = m.group()
                if "\r\n" in chunk:
                    chunk = chunk.replace("\r\n", "\n")
                if "\r" in chunk:
                    raise ValueError("bare carriage return in string")
                out.append(chunk)
                self.i = m.end()
                continue
            if self.i >= self.n:
                raise ValueError("unterminated multiline string")
            ch = s[self.i]
            if ch == "'":
                # a lone quote (1-2) is content; the closer check above handled '''
                out.append("'")
                self.i += 1
                continue
            if ch == "\r":
                if self.peek(1) != "\n":
                    raise ValueError("bare carriage return in string")
                out.append("\n")
                self.i += 2
                continue
            raise ValueError("control character in string")

    # -- numbers / datetimes --------------------------------------------- #

    def parse_number_or_datetime(self) -> Any:
        s = self.s
        i = self.i
        # cheap pre-guards: datetimes need '-' at +4 (date) or ':' at +2 (time)
        c4 = s[i + 4 : i + 5]
        if c4 == "-":
            m = self._dt_offset_re.match(s, i)
            if m and (m.end() >= self.n or s[m.end()] not in _DIGITS):
                self.i = m.end()
                return self._build_datetime(m, offset=True)
            m = self._dt_local_re.match(s, i)
            if m and (m.end() >= self.n or s[m.end()] not in _DIGITS):
                self.i = m.end()
                return self._build_datetime(m, offset=False)
            m = _DATE.match(s, i)
            if m and (m.end() >= self.n or s[m.end()] not in _DIGITS):
                self.i = m.end()
                try:
                    return _Date(int(m[1]), int(m[2]), int(m[3]), m.group(0))
                except ValueError as exc:
                    raise ValueError(f"invalid date: {exc}") from exc
        elif s[i + 2 : i + 3] == ":":
            m = self._time_re.match(s, i)
            if m and (m.end() >= self.n or s[m.end()] not in _DIGITS):
                self.i = m.end()
                return self._build_time(m)

        j = i
        sign = ""
        if s[j] in "+-":
            sign = s[j]
            j += 1
        if s.startswith("inf", j):
            self.i = j + 3
            return float("-inf" if sign == "-" else "inf")
        if s.startswith("nan", j):
            self.i = j + 3
            return float("nan")
        if not sign and s[j : j + 2] in ("0x", "0o", "0b"):
            m = _INT_HEX.match(s, i) if s[j + 1] == "x" else (
                _INT_OCT.match(s, i) if s[j + 1] == "o" else _INT_BIN.match(s, i)
            )
            if m is None:
                raise ValueError(f"invalid integer {s[i:j + 2]!r}")
            token = m.group()
            nxt = s[m.end() : m.end() + 1]
            if nxt and nxt in _BARE_CHARS:
                raise ValueError(f"invalid integer {s[i : m.end() + 1]!r}")
            self.i = m.end()
            return self._int_from_token(token)
        m = _NUMBER_TOKEN.match(s, i)
        if m is None:
            raise ValueError(f"invalid value character {s[i]!r}")
        token = m.group()
        self.i = m.end()
        return self._number_from_token(token)

    def _int_from_token(self, token: str) -> int:
        body = token.replace("_", "")
        try:
            if token.startswith("0x"):
                if not _INT_HEX.fullmatch(token):
                    raise ValueError
                return int(body, 16)
            if token.startswith("0o"):
                if not _INT_OCT.fullmatch(token):
                    raise ValueError
                return int(body, 8)
            if token.startswith("0b"):
                if not _INT_BIN.fullmatch(token):
                    raise ValueError
                return int(body, 2)
            if not _INT_DEC.fullmatch(token):
                raise ValueError
            return int(body)
        except ValueError as exc:
            raise ValueError(f"invalid integer {token!r}") from exc

    def _number_from_token(self, token: str) -> int | float:
        if "." in token or "e" in token or "E" in token:
            if not _FLOAT.fullmatch(token):
                raise ValueError(f"invalid float {token!r}")
            return float(token.replace("_", ""))
        return self._int_from_token(token)

    def _build_datetime(self, m: re.Match[str], offset: bool) -> _DateTime:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        hh, mm = int(m[4]), int(m[5])
        ss = int(m[6]) if m[6] is not None else 0  # TOML 1.1: seconds optional
        frac = m[7] or ""
        micro = int((frac[1:] + "000000")[:6]) if frac else 0
        tz: tzinfo | None = None
        if offset:
            if m[8]:
                tz = timezone.utc
            else:
                oh, om = int(m[10]), int(m[11])
                if oh > 23 or om > 59:
                    raise ValueError(f"invalid timezone offset {m[10]}:{m[11]}")
                sign = -1 if m[9] == "-" else 1
                tz = timezone(sign * timedelta(hours=oh, minutes=om))
        raw = m.group(0)
        try:
            # TOML allows second = 60 (leap second); represent as :59 internally,
            # the raw spelling is preserved for faithful rendering
            if ss > 60:
                raise ValueError(f"second {ss} out of range")
            value = _DateTime(y, mo, d, hh, mm, min(ss, 59), micro, tz, raw)
        except ValueError as exc:
            raise ValueError(f"invalid datetime: {exc}") from exc
        return value

    def _build_time(self, m: re.Match[str]) -> _Time:
        ss = int(m[3]) if m[3] is not None else 0  # TOML 1.1: seconds optional
        frac = m[4] or ""
        micro = int((frac[1:] + "000000")[:6]) if frac else 0
        raw = m.group(0)
        try:
            return _Time(int(m[1]), int(m[2]), ss, micro, raw)
        except ValueError as exc:
            raise ValueError(f"invalid time: {exc}") from exc

    # -- arrays / inline tables ------------------------------------------- #

    def parse_array(self, owner: tuple[Table, tuple[str, ...]] | None) -> Array:
        start = self.i
        self.i += 1
        arr = Array()
        arr._owner = owner
        spans: list[tuple[int, int]] = []
        while True:
            self.skip_trivia()  # arrays allow whitespace/comments/newlines
            if self.peek() == "]":
                self.i += 1
                break
            if self.i >= self.n:
                raise ValueError("unterminated array")
            vstart = self.i
            value = self.parse_value(owner)
            if isinstance(value, Array):
                value._parent_array = arr  # nested: render climbs to the outermost array
            spans.append((vstart, self.i))
            list.append(arr, value)
            self.skip_trivia()
            if self.peek() == ",":
                self.i += 1
                continue
            if self.peek() == "]":
                self.i += 1
                break
            raise ValueError("expected ',' or ']' in array")
        arr.span = (start, self.i)
        arr.spans = list[tuple[int, int] | None](spans)
        return arr

    def parse_inline_table(self) -> InlineTable:
        start = self.i
        self.i += 1
        table = InlineTable()
        if self.v11:
            self.skip_trivia()  # TOML 1.1: newlines and comments allowed inside
        else:
            self.skip_inline_ws()
        if self.peek() == "}":
            self.i += 1
            table.span = (start, self.i)
            return table
        while True:
            keys = self.parse_key_path()  # trailing inline ws already consumed
            self.expect("=")
            self.skip_inline_ws()
            value = self.parse_value()
            self._assign_inline(table, keys, value)
            if self.v11:
                self.skip_trivia()
            else:
                self.skip_inline_ws()
            if self.peek() == ",":
                self.i += 1
                if self.v11:
                    self.skip_trivia()
                    if self.peek() == "}":
                        # TOML 1.1: trailing comma allowed
                        self.i += 1
                        break
                continue
            if self.peek() == "}":
                self.i += 1
                break
            raise ValueError("expected ',' or '}' in inline table")
        table.span = (start, self.i)
        return table

    def _assign_inline(self, table: InlineTable, keys: list[str], value: Any) -> None:
        target: Table = table
        for part in keys[:-1]:
            existing = target._raw_get(part)
            if isinstance(existing, Table):
                # descending is legal only into sub-tables created by dotted
                # keys of this literal — not into directly assigned values
                if existing.inline and not existing.sealed:
                    raise ValueError(f"cannot overwrite inline table {part!r}")
                target = existing
                continue
            if existing is not None:
                raise ValueError(f"duplicate key {part!r}")
            fresh = InlineTable()
            fresh.sealed = True  # dotted-created: may be descended into again
            target._raw_set(part, fresh)
            target = fresh
        name = keys[-1]
        if target._raw_get(name) is not None:
            raise ValueError(f"duplicate key {name!r}")
        target._raw_set(name, value)


def parse_source(source: str, version: str = "1.1") -> tuple[Table, list[tuple[int, int, str, Any]]]:
    """
    Parse *source*; return ``(root_table, parts)``.

    Internal :class:`ValueError` signals are converted into
    :class:`~tomlclass.errors.TOMLParseError` with precise positions.
    """
    parser = Parser(source, version)
    try:
        root = parser.parse()
    except ValueError as exc:
        raise parser.error(str(exc)) from None
    return root, parser.parts
