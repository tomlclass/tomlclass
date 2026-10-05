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

from .document import Document
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

__version__ = "0.1.3"

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
    "dumps",
    "load",
    "loads",
    "parse",
    "update",
]


def parse(source: str) -> Document:
    """
    Parse TOML text into a :class:`Document`.

    :param source: TOML text (must be valid TOML 1.0/1.1)
    :raises TOMLParseError: on any syntax or semantic error, with ``line`` /
        ``col`` / ``offset`` / ``segment`` attached
    """
    root, parts = parse_source(source)
    return Document(source, root, parts)


def loads(source: str) -> dict[str, Any]:
    """
    Parse TOML text into a plain dict — stdlib :mod:`tomllib` compatible.

    For lossless editing (comments, ordering, formatting) use :func:`parse`,
    which returns a :class:`Document`.

    :param source: TOML text
    :raises TOMLParseError: on any syntax or semantic error
    """
    return parse(source).to_dict()


def load(path: Any) -> Any:
    """
    Parse TOML — dual-mode entry point.

    - *path* (``str`` / ``os.PathLike``) → :class:`Document` — lossless,
      editable, atomic :meth:`Document.save`
    - binary file object (``open(path, "rb")``) → plain nested ``dict`` —
      stdlib :mod:`tomllib` compatible

    :raises TOMLParseError: on any syntax or semantic error
    """
    if hasattr(path, "read"):
        data = path.read()
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        return parse(text).to_dict()
    return parse(Path(path).read_text(encoding="utf-8"))


def dumps(doc: Document | Mapping[str, Any]) -> str:
    """
    Render TOML text.

    - a :class:`Document` renders losslessly: unchanged parts come from the
      source verbatim, edited parts re-render canonically
    - a plain ``Mapping`` is serialized by building a fresh document from
      its items (plain dicts become ``[table]`` blocks); keys that cannot be
      represented raise :class:`TOMLTypeError`
    """
    if isinstance(doc, Document):
        return doc.dumps()
    if isinstance(doc, Mapping):
        fresh = parse("")
        for key, value in doc.items():
            fresh[key] = value
        return fresh.dumps()
    if doc is None:
        raise TOMLTypeError("None cannot be represented in TOML", value=doc)
    raise TOMLTypeError(
        f"cannot serialize {type(doc).__name__} as a TOML document", value=doc
    )


def update(path: str | os.PathLike[str], updates: Mapping[str, Any]) -> Document:
    """
    Update values in a TOML file in one call, preserving everything else.

    Reads *path*, assigns each dotted key in *updates* (e.g.
    ``{"server.port": 9090}``), and atomically writes the file back. Comments,
    ordering and formatting survive everywhere except the touched lines;
    missing keys and intermediate tables are created. If any value fails,
    nothing is written.

    :param path: path to the TOML file
    :param updates: mapping of dotted key paths to TOML-representable values
    :returns: the updated :class:`Document` (also saved to *path*)
    :raises TypeError: if *path* is a file object — a real path is required
    :raises TOMLParseError: if the file is not valid TOML
    :raises TOMLTypeError: if a value cannot be represented in TOML (TOML has
        no null; delete keys through :class:`Document` instead)
    """
    if hasattr(path, "read"):
        raise TypeError("update() needs a filesystem path to write back to, not a file object")
    doc = parse(Path(path).read_text(encoding="utf-8"))
    for dotted, value in updates.items():
        doc.set_path(dotted, value)
    doc.save(path)
    return doc
