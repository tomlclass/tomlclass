"""
tomlclass exception hierarchy.

Integrates with stdlib conventions:

- :class:`TOMLParseError` subclasses :class:`ValueError` (the same contract as
  :class:`tomllib.TOMLDecodeError`), so ``except ValueError`` keeps working.
- :class:`TOMLTypeError` subclasses :class:`TypeError` — raised when a value
  cannot be represented in TOML (``None``, functions, arbitrary objects …).
- :class:`ConfigError` / :class:`ValidationError` power the annotation layer;
  :class:`ValidationError` aggregates *all* offending fields instead of
  failing on the first one.
"""

from __future__ import annotations

from typing import Any


class TOMLError(Exception):
    """
    Base class for every error raised by tomlclass.
    """


class TOMLParseError(TOMLError, ValueError):
    """
    A TOML document failed to parse.

    Also a :class:`ValueError` (stdlib convention, mirroring
    :class:`tomllib.TOMLDecodeError`).

    :param message: human-readable failure description
    :param offset: character offset into the source (``None`` for semantic errors)
    :param line: 1-based line number (``None`` for semantic errors)
    :param col: 1-based column number (``None`` for semantic errors)
    :param segment: the offending source line, trimmed
    """

    def __init__(
        self,
        message: str,
        offset: int | None = None,
        line: int | None = None,
        col: int | None = None,
        segment: str = "",
    ) -> None:
        if line is not None:
            loc = f" (line {line}, column {col})"
            body = f"{message}{loc}:\n    {segment}"
        else:
            body = message
        super().__init__(body)
        self.message = message
        self.offset = offset
        self.line = line
        self.col = col
        self.segment = segment


class TOMLTypeError(TOMLError, TypeError):
    """
    A value cannot be represented in TOML.

    :param message: human-readable description
    :param path: dotted key path the value was assigned to, if known
    :param value: the offending value
    """

    def __init__(self, message: str, *, path: tuple[str, ...] | None = None, value: Any = None) -> None:
        loc = f" at '{'.'.join(path)}'" if path else ""
        super().__init__(f"{message}{loc}")
        self.message = message
        self.path = path
        self.value = value


class FieldError:
    """
    A single schema violation.

    :param path: dotted key path of the offending field
    :param message: human-readable description
    """

    __slots__ = ("message", "path")

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"

    def __repr__(self) -> str:
        return f"FieldError({self.path!r}, {self.message!r})"


class ConfigError(TOMLError, ValueError):
    """
    Base class for annotation-layer errors.
    """


class ValidationError(ConfigError):
    """
    Schema validation failed; aggregates every offending field.

    :param errors: list of :class:`FieldError`
    """

    def __init__(self, errors: list[FieldError]) -> None:
        self.errors = errors
        summary = "; ".join(str(e) for e in errors[:5])
        more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
        super().__init__(f"{len(errors)} validation error(s): {summary}{more}")
