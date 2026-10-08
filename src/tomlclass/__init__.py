"""
tomlclass — annotation-driven TOML configuration with comment preservation.

Declare configuration as annotated classes; tomlclass renders commented TOML
templates, validates and fills values, and updates existing TOML files in
place while keeping user comments, ordering and formatting intact.

Public API:

- :func:`parse` / :func:`loads`  — parse TOML text into a :class:`Document`
- :func:`load`                   — parse a TOML file
- :func:`dumps`                  — render a :class:`Document` back to text
- :func:`update`                 — one-call lossless value update in a file
- :class:`Document`              — lossless CST document with mapping access
                                  and atomic :meth:`Document.save`
- :class:`Config` / :class:`Field` — the annotation layer
- :class:`TOMLError` hierarchy   — TOMLParseError / TOMLTypeError / ConfigError
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._document import Document
from .errors import (
    ConfigError,
    FieldError,
    TOMLError,
    TOMLParseError,
    TOMLTypeError,
    ValidationError,
)
from .nodes import Array, ArrayOfTables, InlineTable, Table
from .parser import parse_source
from .schema import Config, Field

__version__ = "0.3.0"

__all__ = [
    "Array",
    "ArrayOfTables",
    "Config",
    "ConfigError",
    "Document",
    "Field",
    "FieldError",
    "InlineTable",
    "TOMLError",
    "TOMLParseError",
    "TOMLTypeError",
    "Table",
    "ValidationError",
    "__version__",
    "aot",
    "comment",
    "document",
    "dump",
    "dumps",
    "inline_table",
    "load",
    "load_path",
    "loads",
    "nl",
    "parse",
    "table",
    "update",
]


def parse(source: str, *, toml_version: str = "1.1") -> Document:
    """
    Parse TOML text into a :class:`Document`.

    :param source: TOML text (must be valid TOML 1.0/1.1)
    :param toml_version: ``"1.1"`` (default) or ``"1.0"`` — 1.0 mode rejects
        the 1.1 additions (``\\e`` / ``\\x`` escapes, seconds omitted from
        times, newlines and trailing commas inside inline tables, non-ASCII
        bare keys)
    :raises TOMLParseError: on any syntax or semantic error, with ``line`` /
        ``col`` / ``offset`` / ``segment`` attached
    """
    root, parts = parse_source(source, toml_version)
    return Document(source, root, parts)


def _strings_to_none(obj: Any, sentinel: str) -> Any:
    if isinstance(obj, str):
        return None if obj == sentinel else obj
    if isinstance(obj, dict):
        return {k: _strings_to_none(v, sentinel) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strings_to_none(v, sentinel) for v in obj]
    return obj


def _none_to_strings(obj: Any, sentinel: str) -> Any:
    if obj is None:
        return sentinel
    if isinstance(obj, dict):
        return {k: _none_to_strings(v, sentinel) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_none_to_strings(v, sentinel) for v in obj]
    return obj


def _check_none_value(none_value: str | None) -> None:
    if none_value is not None and not isinstance(none_value, str):
        raise ValueError("none_value must be a string")


def loads(source: str, *, toml_version: str = "1.1", none_value: str | None = None) -> dict[str, Any]:
    """
    Parse TOML text into a plain dict — stdlib :mod:`tomllib` compatible.

    For lossless editing (comments, ordering, formatting) use :func:`parse`,
    which returns a :class:`Document`.

    :param source: TOML text
    :param toml_version: ``"1.1"`` (default) or ``"1.0"``
    :param none_value: when set (rtoml-style), strings exactly equal to it
        decode back as ``None`` — e.g. ``none_value="@None"`` turns
        ``k = "@None"`` into ``{"k": None}``
    :raises TOMLParseError: on any syntax or semantic error
    """
    _check_none_value(none_value)
    data = parse(source, toml_version=toml_version).to_dict()
    if none_value is not None:
        return _strings_to_none(data, none_value)
    return data


def load(path: Any, *, toml_version: str = "1.1", none_value: str | None = None) -> Any:
    """
    Parse TOML — dual-mode entry point.

    - *path* (``str`` / ``os.PathLike``) → :class:`Document` — lossless,
      editable, atomic :meth:`Document.save`
    - binary file object (``open(path, "rb")``) → plain nested ``dict`` —
      stdlib :mod:`tomllib` compatible

    :param toml_version: ``"1.1"`` (default) or ``"1.0"``
    :param none_value: applies to the dict-returning path only (see
        :func:`loads`); passing it with a path raises ``ValueError``
    :raises TOMLParseError: on any syntax or semantic error
    """
    _check_none_value(none_value)
    if hasattr(path, "read"):
        data = path.read()
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        out = parse(text, toml_version=toml_version).to_dict()
        if none_value is not None:
            return _strings_to_none(out, none_value)
        return out
    if none_value is not None:
        raise ValueError("none_value applies to dict output; a path returns a Document")
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8")  # read_bytes: no universal-newline translation (CRLF stays intact)
    return parse(text, toml_version=toml_version)


def dumps(doc: Document | Mapping[str, Any], *, none_value: str | None = None) -> str:
    """
    Render TOML text.

    - a :class:`Document` renders losslessly: unchanged parts come from the
      source verbatim, edited parts re-render canonically
    - a plain ``Mapping`` is serialized by building a fresh document from
      its items (plain dicts become ``[table]`` blocks); keys that cannot be
      represented raise :class:`TOMLTypeError`

    :param none_value: when set (rtoml-style), ``None`` values in a Mapping
        serialize as that string — e.g. ``none_value="@None"`` turns
        ``{"k": None}`` into ``k = "@None"``. Applies to the Mapping path
        only; passing it with a :class:`Document` raises ``ValueError``
    """
    _check_none_value(none_value)
    if isinstance(doc, Document):
        if none_value is not None:
            raise ValueError("none_value applies to Mapping input; a Document cannot contain None")
        return doc.dumps()
    if isinstance(doc, Mapping):
        fresh = parse("")
        for key, value in doc.items():
            fresh[key] = _none_to_strings(value, none_value) if none_value is not None else value
        return fresh.dumps()
    if doc is None:
        raise TOMLTypeError(
            "None cannot be represented in TOML — pass none_value='null' to dumps()/loads()/update(),"
            " or model absence with an Optional Config field (its key is deleted on save)",
            value=doc)
    raise TOMLTypeError(
        f"cannot serialize {type(doc).__name__} as a TOML document", value=doc
    )


def update(
    path: str | os.PathLike[str],
    updates: Mapping[str, Any],
    *,
    toml_version: str = "1.1",
    none_value: str | None = None,
) -> Document:
    """
    Update values in a TOML file in one call, preserving everything else.

    Reads *path*, assigns each dotted key in *updates* (e.g.
    ``{"server.port": 9090}``), and atomically writes the file back. Comments,
    ordering and formatting survive everywhere except the touched lines;
    missing keys and intermediate tables are created. If any value fails,
    nothing is written.

    :param path: path to the TOML file
    :param updates: mapping of dotted key paths to TOML-representable values
    :param toml_version: ``"1.1"`` (default) or ``"1.0"``
    :param none_value: when set, ``None`` values in *updates* serialize as
        that string (see :func:`dumps`)
    :returns: the updated :class:`Document` (also saved to *path*)
    :raises TypeError: if *path* is a file object — a real path is required
    :raises TOMLParseError: if the file is not valid TOML
    :raises TOMLTypeError: if a value cannot be represented in TOML
    """
    if hasattr(path, "read"):
        raise TypeError("update() needs a filesystem path to write back to, not a file object")
    _check_none_value(none_value)
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8")  # read_bytes: no universal-newline translation (CRLF stays intact)
    doc = parse(text, toml_version=toml_version)
    for dotted, value in updates.items():
        doc.set_path(dotted, _none_to_strings(value, none_value) if none_value is not None else value)
    doc.save(path)
    return doc


# -- construction API ---------------------------------------------------------


def document() -> Document:
    """
    Build a fresh, empty :class:`Document` from scratch.

    Assign keys (or :func:`table` / :func:`inline_table` / :func:`aot`
    values) and render with :meth:`Document.dumps` — standalone layout lines
    attach via :meth:`Document.add` with :func:`comment` / :func:`nl`.
    """
    return parse("")


def table() -> Table:
    """
    Build a detached :class:`Table` — assign into it, then set it on a
    document (it renders as a ``[table]`` block).
    """
    return Table()


def inline_table(items: Any = None) -> InlineTable:
    """
    Build an :class:`InlineTable` (optionally from a mapping), e.g.
    ``doc["point"] = inline_table({"x": 1})`` renders ``point = { x = 1 }``.
    """
    return InlineTable(items)


def aot() -> ArrayOfTables:
    """
    Build an empty :class:`ArrayOfTables` — ``append`` mappings to grow
    ``[[block]]`` sections.
    """
    return ArrayOfTables()


def comment(text: Any) -> Any:
    """
    Build a standalone ``# text`` line for :meth:`Document.add`.
    """
    from .nodes import comment as _comment

    return _comment(text)


def nl() -> Any:
    """
    Build a standalone blank line for :meth:`Document.add`.
    """
    from .nodes import nl as _nl

    return _nl()


# -- io ------------------------------------------------------------------------


def load_path(path: str | os.PathLike[str]) -> Document:
    """
    Load a TOML file as a lossless :class:`Document`.

    The explicit path-based entry point — unlike the dual-mode :func:`load`,
    it always returns a :class:`Document`.
    """
    if hasattr(path, "read"):
        raise TypeError("load_path() needs a filesystem path, not a file object (use load())")
    raw = Path(path).read_bytes()
    return parse(raw.decode("utf-8"))  # read_bytes: no universal-newline translation (CRLF stays intact)


def dump(obj: Document | Mapping[str, Any], fp: Any, *, none_value: str | None = None) -> None:
    """
    Render *obj* (:class:`Document` or ``Mapping``) into the file object *fp*.

    Both text-mode and binary-mode file objects are accepted; binary handles
    are written as UTF-8. Semantics mirror :func:`dumps`.

    :raises TOMLTypeError: if a value cannot be represented in TOML
    """
    _check_none_value(none_value)
    text = dumps(obj, none_value=none_value)
    if hasattr(fp, "buffer"):
        fp = fp.buffer
    if hasattr(fp, "mode") and "b" in getattr(fp, "mode", ""):
        fp.write(text.encode("utf-8"))
    else:
        fp.write(text)
