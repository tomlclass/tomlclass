"""
Optional pydantic v2 interop: keep your ``BaseModel`` — validators,
converters, JSON Schema and the whole pydantic ecosystem — and gain
tomlclass's lossless TOML write-back.

    from typing import Annotated
    from pydantic import BaseModel, Field
    from tomlclass.pydantic import TomlModel

    class Server(TomlModel):
        \"\"\"HTTP server settings.\"\"\"

        host: str = Field("127.0.0.1", description="the bind address")
        port: Annotated[int, Field(ge=1, le=65535)] = 8000

    server = Server.load("server.toml")   # pydantic validates
    server.port = 9000
    server.save("server.toml")            # tomlclass diffs: comments and
                                          # untouched lines survive
    Server.template()                     # commented starter template

Validation is fully delegated to pydantic (``model_validate``); tomlclass
only owns parsing, diffing and rendering. Requires ``pydantic>=2``
(``pip install tomlclass[pydantic]``).

All helpers live on :class:`TomlModel` (rule 17a): they operate on models,
not on standalone values.
"""

from __future__ import annotations

import enum
import types
import unicodedata
from pathlib import Path
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, PrivateAttr

from ._document import Document
from .errors import ConfigError
from .nodes import ArrayOfTables, format_value
from .parser import parse_source

__all__ = ["TomlModel"]

_ABSENT = object()

_MAX_COMMENT_WIDTH = 98


class _TomlDocState:
    """Per-instance toml session state (document + baseline + path)."""

    __slots__ = ("doc", "path", "snapshot")

    def __init__(self, doc: Document, snapshot: dict[str, Any], path: Path | None) -> None:
        self.doc = doc
        self.path = path
        self.snapshot = snapshot


class TomlModel(BaseModel):
    """
    A :class:`pydantic.BaseModel` that loads from and saves to TOML files
    losslessly (comments, ordering and formatting preserved; diff-based
    write-back).

    Validation is pydantic's — validators, converters and constraints behave
    exactly as in any BaseModel. tomlclass owns the file: parsing, diffing
    and rendering. Field descriptions (``Field(description=...)`` and
    docstrings) become the comments in :meth:`template`.

    Limitations (v1): attribute assignment is not re-validated; unknown-key
    handling follows pydantic's own ``model_config``; ``save()`` requires a
    prior :meth:`load`; multi-member unions (``Union[Server, Client]``) are
    not model-aware — such fields are saved as inline tables and omitted from
    :meth:`template` (single models behind ``Optional``/``Annotated`` are
    fully supported).
    """

    _toml_state: _TomlDocState | None = PrivateAttr(default=None)

    # -- io ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: str | Path) -> TomlModel:
        """
        Parse *path*, validate through pydantic and bind the document for
        :meth:`save`.
        """
        raw = Path(path).read_bytes()
        text = raw.decode("utf-8")  # no newline translation: CRLF stays intact
        root, parts = parse_source(text)
        doc = Document(text, root, parts)
        data = doc.to_dict()
        instance = cls.model_validate(data)
        instance._toml_state = _TomlDocState(doc, data, Path(path))
        return instance

    def save(self, path: str | Path) -> None:
        """
        Diff the instance against the loaded file and write only the changes
        (atomically). Comments and untouched lines survive. ``None`` on a
        loaded field deletes the key (TOML has no null). Defaults that never
        made it into the file stay out — the same rule as ``Config.save``.
        """
        state = self._state_of()
        current = self._plain_tree(self.model_dump())
        self._apply_diff(state.doc, state.snapshot, current, (), type(self))
        state.doc.save(path)
        state.path = Path(path)
        # the file (old content + applied changes) is the new baseline — the
        # full model dump would smuggle never-persisted defaults into the
        # next diff (same rule as Config.save)
        state.snapshot = state.doc.to_dict()

    # -- template ------------------------------------------------------------ #

    @classmethod
    def template(cls) -> str:
        """
        Generate the commented TOML template from field descriptions and
        defaults. Stable for a given model.
        """
        out: list[str] = []
        cls._emit_model_template(cls, [], out, (cls,))
        return "\n".join(out) + ("\n" if out else "")

    # -- session state ------------------------------------------------------- #

    def _state_of(self) -> _TomlDocState:
        state = self._toml_state
        if state is None:
            raise ConfigError(
                f"{type(self).__name__} is not bound to a TOML document — use .load()"
            )
        return state

    # -- diff application ------------------------------------------------------ #

    @staticmethod
    def _apply_diff(
        doc: Document,
        snapshot: dict[str, Any],
        current: dict[str, Any],
        prefix: tuple[Any, ...],
        model: type[BaseModel],
    ) -> None:
        # the model rides along so every nesting level can recompute its own
        # field defaults and list[Model] item defaults — precomputed maps
        # only cover the top level and silently leak in nested tables
        defaults = TomlModel._model_defaults(model)

        def full(key: str) -> tuple[Any, ...]:
            return (*prefix, key)

        def dotted(key: str) -> str:
            return TomlModel._dotted(full(key))

        for key, value in current.items():
            old = snapshot.get(key, _ABSENT)
            dflt = defaults.get(key, _ABSENT)
            field = model.model_fields.get(key)
            annotation = field.annotation if field is not None else None
            sub_model = TomlModel._model_of(annotation)
            item_model = TomlModel._model_of_list(annotation)
            if isinstance(value, dict):
                if sub_model is not None and isinstance(old, dict):
                    TomlModel._apply_diff(doc, old, value, full(key), sub_model)
                    continue
                if dflt is not _ABSENT and isinstance(dflt, dict) and TomlModel._same_tree(value, dflt):
                    continue  # never-persisted nested default stays out
                doc.set_path(dotted(key), value)  # new table (or replaces a scalar/array)
                continue
            if isinstance(value, list):
                if item_model is not None and isinstance(old, list):
                    TomlModel._apply_list_diff(doc, full(key), old, value, item_model)
                    continue
                if old is _ABSENT and dflt is not _ABSENT and TomlModel._same_tree(value, dflt):
                    continue  # never-persisted default stays out
                doc.set_path(dotted(key), value)  # scalar/inline arrays: canonical replace
                continue
            if old is _ABSENT and dflt is not _ABSENT and TomlModel._same(value, dflt):
                continue  # never-persisted default stays out
            if old is _ABSENT or not TomlModel._same(old, value):
                if value is None:
                    TomlModel._delete_path(doc, full(key))  # None on a loaded key: delete
                else:
                    doc.set_path(dotted(key), value)
        for key in snapshot:
            if key not in current:
                TomlModel._delete_path(doc, full(key))

    @staticmethod
    def _apply_list_diff(
        doc: Document,
        full: tuple[Any, ...],
        old: Any,
        new: list[Any],
        item_model: type[BaseModel],
    ) -> None:
        """
        Diff a list assignment. Lists of tables (``[[aot]]``) diff
        element-wise — per-field edits splice in place so element comments
        and formatting survive; appended/removed elements go through the
        engine's append/pop. Any non-table element (or a non-list baseline)
        replaces wholesale: inline arrays re-render canonically.
        """
        dotted = TomlModel._dotted(full)
        old_list = old if isinstance(old, list) else None
        if old_list is None:
            doc.set_path(dotted, new)  # new array (or replaces a scalar/table)
            return
        if not all(isinstance(item, dict) for item in new) or not all(
            isinstance(item, dict) for item in old_list
        ):
            if old_list != new:
                doc.set_path(dotted, new)  # scalar/inline arrays: canonical replace
            return
        aot = doc.find(dotted)
        if not isinstance(aot, ArrayOfTables) or len(aot) != len(old_list):
            # the tree and the snapshot disagree — fall back to wholesale
            doc.set_path(dotted, new)
            return
        shared = min(len(old_list), len(new))
        for i in range(shared):
            TomlModel._apply_diff(doc, old_list[i], new[i], (*full, i), item_model)
        for _ in range(len(old_list) - len(new)):
            aot.pop()
        for i in range(len(old_list), len(new)):
            aot.append(new[i])

    @staticmethod
    def _delete_path(doc: Document, path: tuple[str, ...]) -> None:
        node: Any = doc.root
        for key in path[:-1]:
            if not isinstance(node, dict) or key not in node:
                return  # nothing at that path: nothing to delete
            node = node[key]
        key = path[-1]
        if isinstance(node, dict) and key in node:
            # every branch of the tree is a Table (dict subclass whose
            # __delitem__ runs engine_del) — the line leaves the output
            del node[key]

    # -- value canonicalization ------------------------------------------------ #

    @staticmethod
    def _plain_tree(value: Any) -> Any:
        """Model dump -> plain nested dict/list with TOML-representable leaves."""
        if isinstance(value, BaseModel):
            return {k: TomlModel._plain_tree(v) for k, v in dict(value).items()}
        if isinstance(value, dict):
            return {k: TomlModel._plain_tree(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [TomlModel._plain_tree(v) for v in value]
        return TomlModel._enum_value(value)

    @staticmethod
    def _enum_value(value: Any) -> Any:
        while isinstance(value, enum.Enum):
            value = value.value
        return value

    @staticmethod
    def _same(old: Any, new: Any) -> bool:
        # NaN != NaN, so plain == would rewrite unchanged nan fields on every save
        if isinstance(old, float) and isinstance(new, float) and old != old and new != new:  # noqa: PLR0124
            return True
        return old == new

    @staticmethod
    def _same_tree(a: Any, b: Any) -> bool:
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(TomlModel._same_tree(a[k], b[k]) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(
                TomlModel._same_tree(x, y) for x, y in zip(a, b, strict=True)
            )
        return TomlModel._same(a, b)

    @staticmethod
    def _dotted(path: tuple[Any, ...]) -> str:
        parts: list[str] = []
        for seg in path:
            if isinstance(seg, int):
                parts[-1] += f"[{seg}]"
            else:
                parts.append(str(seg))
        return ".".join(parts)

    # -- model-field reflection ------------------------------------------------ #

    @staticmethod
    def _unwrap(tp: Any) -> Any:
        """Strip Annotated[..., ...] metadata and Optional (single-member Union)."""
        if getattr(tp, "__metadata__", None):
            tp = tp.__origin__
        origin = get_origin(tp)
        if origin is Union or origin is types.UnionType:
            args = [a for a in get_args(tp) if a is not type(None)]
            if len(args) == 1:
                tp = args[0]
        return tp

    @staticmethod
    def _model_of(tp: Any) -> type[BaseModel] | None:
        tp = TomlModel._unwrap(tp)
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            return tp
        return None

    @staticmethod
    def _model_of_list(tp: Any) -> type[BaseModel] | None:
        tp = TomlModel._unwrap(tp)
        origin = get_origin(tp)
        if origin is list:
            args = get_args(tp)
            if args:
                return TomlModel._model_of(args[0])
        return None

    @classmethod
    def _model_defaults(cls, model: type[BaseModel]) -> dict[str, Any]:
        """Effective per-field defaults; ``_ABSENT`` marks required fields."""
        out: dict[str, Any] = {}
        for name, field in model.model_fields.items():
            if field.is_required():
                out[name] = _ABSENT
                continue
            default = getattr(field, "default", _ABSENT)
            if default is _ABSENT or default is None:
                factory = getattr(field, "default_factory", None)
                default = factory() if factory is not None else None
            out[name] = cls._plain_tree(cls._enum_value(default))
        return out

    @staticmethod
    def _template_default(field: Any) -> Any:
        """
        ``_ABSENT`` = no default at all (the caller renders the key commented
        out). An actual ``None`` default flows through — and is likewise
        commented out, since TOML has no null.
        """
        default = getattr(field, "default", _ABSENT)
        # explicit None stays None (rendered commented out) — see _model_defaults
        if default is _ABSENT or default is None:
            factory = getattr(field, "default_factory", None)
            if factory is not None:
                default = factory()
        return TomlModel._enum_value(default)

    # -- template emission ------------------------------------------------------- #

    @staticmethod
    def _emit_model_template(
        model: type[BaseModel],
        path: list[str],
        out: list[str],
        seen: tuple[type[BaseModel], ...],
    ) -> None:
        summary = (model.__doc__ or "").strip().splitlines()
        has_summary = bool(summary and summary[0].strip())
        if path:
            out.append("")
            if has_summary:
                out.extend(TomlModel._wrap(summary[0].strip()))
            out.append(f"[{'.'.join(path)}]")
        elif has_summary:
            out.extend(TomlModel._wrap(summary[0].strip()))
        TomlModel._emit_model_fields(model, path, out, seen)

    @staticmethod
    def _emit_model_fields(
        model: type[BaseModel],
        path: list[str],
        out: list[str],
        seen: tuple[type[BaseModel], ...],
    ) -> None:
        for name, field in model.model_fields.items():
            if field.description:
                out.extend(TomlModel._wrap(field.description))
            annotation = field.annotation
            if TomlModel._is_model_list(annotation) or TomlModel._is_model(annotation):
                continue  # nested tables / aot lists emit below
            default = TomlModel._template_default(field)
            if default is None:
                out.append(f"# {name} =")
                continue
            out.append(f"{name} = {format_value(default)}")
        for name, field in model.model_fields.items():
            annotation = field.annotation
            inner = TomlModel._model_of(annotation) or TomlModel._model_of_list(annotation)
            if inner is None or inner in seen:
                continue
            if TomlModel._is_model_list(annotation):
                out.append("")
                out.append(f"[[{'.'.join([*path, name])}]]")
                TomlModel._emit_model_fields(inner, [*path, name], out, (*seen, inner))
                continue
            TomlModel._emit_model_template(inner, [*path, name], out, (*seen, inner))

    @staticmethod
    def _is_model(tp: Any) -> bool:
        return TomlModel._model_of(tp) is not None

    @staticmethod
    def _is_model_list(tp: Any) -> bool:
        return TomlModel._model_of_list(tp) is not None

    # -- comment wrapping ---------------------------------------------------- #

    @staticmethod
    def _disp_len(text: str) -> int:
        return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)

    @staticmethod
    def _wrap(text: str, prefix: str = "# ", width: int = _MAX_COMMENT_WIDTH) -> list[str]:
        if not text:
            return []
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if TomlModel._disp_len(prefix) + TomlModel._disp_len(candidate) > width and current:
                lines.append(prefix + current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(prefix + current)
        return lines
