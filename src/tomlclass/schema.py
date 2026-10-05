"""
The annotation layer: declare configuration as classes.

- :class:`Field` — per-field options (description, constraints, coercion)
- :class:`Config` — base class; nested ``Config`` subclasses become nested
  tables; class docstring field-sections become the comments of the generated
  template
- :meth:`Config.template`   — commented TOML template, byte-stable per schema
- :meth:`Config.load`       — parse + validate + fill (defaults merged in
  memory, never persisted)
- :meth:`Config.validate_dict` — offline validation, aggregates all errors
- :meth:`Config.save`       — diff-based write-back: only values that differ
  from the parsed snapshot are written; comments and unknown keys survive

Semantics: defaults never persist, unknown keys survive, comments are
anchored to their keys, saves are atomic, ``None`` assignment on an optional
field deletes the key on save.
"""

from __future__ import annotations

import re
import types
from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, ClassVar, get_args, get_origin, get_type_hints

from .document import Document, atomic_write_text
from .errors import ConfigError, FieldError, ValidationError
from .nodes import ArrayOfTables, Table, format_value
from .parser import parse_source

__all__ = ["Config", "Field"]

_MISSING = object()
_SCALARS = (bool, int, float, str, datetime, date, time)


class Field:
    """
    Per-field options.

    :param default: explicit default value (alternative to a class-level default)
    :param description: comment text; a plain string, or ``{"i18n": key,
        "default": text}`` — the resolver hook :data:`Config.i18n_resolver`
        may translate the key
    :param ge/le/gt/lt: numeric bounds
    :param pattern: regex applied to string values (``re.search``)
    :param min_length/max_length: length bounds for strings and lists
    :param coerce: allow lossless string<->number coercion
    """

    __slots__ = (
        "coerce",
        "default",
        "description",
        "ge",
        "gt",
        "le",
        "lt",
        "max_length",
        "min_length",
        "pattern",
    )

    def __init__(
        self,
        default: Any = _MISSING,
        *,
        description: str | dict[str, str] | None = None,
        ge: float | None = None,
        le: float | None = None,
        gt: float | None = None,
        lt: float | None = None,
        pattern: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        coerce: bool = False,
    ) -> None:
        self.default = default
        self.description = description
        self.ge = ge
        self.le = le
        self.gt = gt
        self.lt = lt
        self.pattern = pattern
        self.min_length = min_length
        self.max_length = max_length
        self.coerce = coerce


def _parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """
    Split a class docstring into (first paragraph, {field: description}).
    """
    if not doc:
        return "", {}
    lines = doc.strip().splitlines()
    summary_lines: list[str] = []
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    in_summary = True
    for line in lines:
        stripped = line.strip()
        header = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):", stripped)
        if header:
            in_summary = False
            current = sections.setdefault(header[1], [])
            continue
        if in_summary:
            if not stripped and summary_lines:
                in_summary = False
            elif stripped:
                summary_lines.append(stripped)
            continue
        if current is not None and stripped:
            current.append(stripped)
    return " ".join(summary_lines), {k: " ".join(v) for k, v in sections.items()}


def _is_config_type(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, Config)


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    origin = get_origin(tp)
    if origin in (types.UnionType, __import__("typing").Union):
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
        return tp, False
    return tp, False


class _FieldSpec:
    """
    Resolved schema information for one field.
    """

    __slots__ = ("default", "description", "field", "has_default", "name", "optional", "type")

    def __init__(self, name: str, tp: Any, field: Field | None, default: Any, description: str) -> None:
        self.name = name
        tp, optional = _unwrap_optional(tp)
        self.type = tp
        self.optional = optional
        self.field = field
        self.has_default = (field is not None and field.default is not _MISSING) or default is not _MISSING
        if field is not None and field.default is not _MISSING:
            self.default = field.default
        else:
            self.default = default
        self.description = description

    def nested(self) -> bool:
        return _is_config_type(self.type)


class _ConfigMeta(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        cls = super().__new__(mcs, name, bases, namespace)
        hints = get_type_hints(cls)
        doc_summary, doc_sections = _parse_docstring(namespace.get("__doc__"))
        fields: dict[str, _FieldSpec] = {}
        # inherit fields from Config bases
        for base in reversed(cls.__mro__[1:]):
            fields.update(getattr(base, "__schema_fields__", {}))
        for fname, tp in hints.items():
            if fname.startswith("_"):
                continue
            if get_origin(tp) is ClassVar:
                continue
            raw_default = namespace.get(fname, _MISSING)
            opts = raw_default if isinstance(raw_default, Field) else None
            default = _MISSING
            if isinstance(raw_default, Field):
                assert opts is not None  # narrows with isinstance above
                if opts.default is not _MISSING:
                    default = opts.default
            else:
                default = raw_default
            if opts is not None and opts.description is not None:
                description = opts.description
            else:
                description = doc_sections.get(fname, "")
            if isinstance(description, dict):
                description = Config.resolve_i18n(description)
            fields[fname] = _FieldSpec(fname, tp, opts, default, description)
        cls.__schema_fields__ = fields  # type: ignore[attr-defined]
        cls.__schema_summary__ = doc_summary  # type: ignore[attr-defined]
        return cls


class Config(metaclass=_ConfigMeta):
    """
    Base class for declarative TOML configuration.

    Subclass it, annotate fields, document them in the class docstring using
    ``field:`` sections — those comments become the generated template's
    comments. Nested ``Config`` subclasses become nested tables.
    """

    i18n_resolver: ClassVar[Callable[[str], str | None] | None] = None

    __schema_fields__: ClassVar[dict[str, _FieldSpec]]
    __schema_summary__: ClassVar[str]

    def __init__(self, **kwargs: Any) -> None:
        for fname, spec in self.__schema_fields__.items():
            if fname in kwargs:
                value = kwargs.pop(fname)
            elif spec.nested():
                value = spec.type()
            elif spec.has_default:
                value = spec.default
            else:
                value = None
            setattr(self, fname, value)
        for key in kwargs:
            raise AttributeError(f"unknown field {key!r} for {type(self).__name__}")
        self._doc: Document | None = None
        self._snapshot: dict[str, Any] | None = None
    # template                                                            #

    @classmethod
    def template(cls) -> str:
        """
        Generate the commented TOML template. Stable for a given schema.
        """
        out: list[str] = []
        _emit_table_template(cls, [], out)
        return "\n".join(out) + ("\n" if out else "")
    # validation                                                          #

    @classmethod
    def validate_dict(cls, data: dict[str, Any], strict: bool = False) -> list[FieldError]:
        """
        Validate a plain dict against the schema, aggregating all errors.
        """
        errors: list[FieldError] = []
        _validate_table(cls, data, [], errors, strict)
        return errors
    # load / save                                                         #

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        env_prefix: str | None = None,
        strict: bool = False,
        comments: str = "none",
        toml_version: str = "1.1",
    ) -> Config:
        """
        Parse *path*, validate and fill defaults.

        :param env_prefix: environment override — ``APP_SERVER__PORT``
            overrides ``server.port`` (``__`` separates path segments)
        :param strict: reject unknown keys instead of preserving them
        :param comments: schema comment injection — ``"none"`` keeps the file
            exactly as written; ``"missing"`` injects a field's description as
            its comment only when the key has none; ``"all"`` rewrites every
            schema field's comment (unknown keys and user comments elsewhere
            are untouched in every mode)
        :param toml_version: ``"1.1"`` (default) or ``"1.0"`` — see
            :func:`tomlclass.parse`
        :raises ValidationError: aggregated, on any schema violation
        """
        with Path(path).open(encoding="utf-8") as f:
            text = f.read()
        root, parts = parse_source(text, toml_version)
        doc = Document(text, root, parts)
        if comments != "none":
            mode_all = comments == "all"
            for fpath, description in _iter_descriptions(cls):
                if not description or doc.find(".".join(fpath)) is None:
                    continue  # key not in file: nothing to inject
                if mode_all or doc.comment(".".join(fpath)) is None:
                    doc.set_comment(".".join(fpath), description)
        data = _to_plain(doc.root)
        if env_prefix:
            _apply_env(cls, data, env_prefix)
        errors = cls.validate_dict(data, strict=strict)
        if errors:
            raise ValidationError(errors)
        instance = cls._from_data(data)
        instance._doc = doc
        instance._snapshot = _validated_snapshot(cls, data)
        return instance

    def save(self, path: str | Path) -> None:
        """
        Write changed values back to *path* (diff-based, atomic).

        - values equal to the parsed snapshot are not touched
        - defaults that never made it into the file are not written
        - ``None`` on an optional field deletes the key
        - comments and unknown keys survive untouched
        """
        if self._doc is None or self._snapshot is None:
            atomic_write_text(path, self.template())
            return
        _apply_diff(self, self._doc, self._snapshot, [])
        self._doc.save(path)

    @classmethod
    def watch(
        cls,
        path: str | Path,
        callback: Callable[[Config], None],
        *,
        env_prefix: str | None = None,
        strict: bool = False,
        stop_event: Any = None,
    ) -> None:
        """
        Reload on file change and invoke *callback* with the fresh instance.

        Requires the optional ``watchfiles`` package. Validation failures keep
        the previous instance and continue watching. Pass a ``threading.Event``
        as *stop_event* to stop the watcher from another thread.
        """
        try:
            from watchfiles import watch  # type: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError("Config.watch requires the optional 'watchfiles' package") from exc
        file = Path(path)
        for _changes in watch(file.parent, stop_event=stop_event):
            if not file.exists():
                continue
            try:
                instance = cls.load(file, env_prefix=env_prefix, strict=strict)
            except Exception:
                continue  # invalid intermediate state — keep serving the last good instance
            callback(instance)
    # internals                                                           #

    @classmethod
    def migrate(cls, old: Config) -> Config:
        """
        Build this config from another Config instance (schema migration).

        Values are carried over by field name; subclasses may override
        :meth:`_remigrate_keys` to rename or transform. Use the engine for
        anything that must preserve the original file byte-for-byte.
        """
        data = old._current_data()
        remap = getattr(cls, "_migrate_key_map", {})
        for old_key, new_path in remap.items():
            if old_key in data:
                value = data.pop(old_key)
                target = data
                for part in new_path.split(".")[:-1]:
                    target = target.setdefault(part, {})
                target[new_path.split(".")[-1]] = value
        errors = cls.validate_dict(data)
        if errors:
            raise ValidationError(errors)
        return cls._from_data(data)

    @classmethod
    def resolve_i18n(cls, description: dict[str, str]) -> str:
        key = description.get("i18n", "")
        resolved = cls.i18n_resolver(key) if (cls.i18n_resolver and key) else None
        return resolved if resolved is not None else description.get("default", key)

    @classmethod
    def _from_data(cls, data: dict[str, Any]) -> Config:
        instance = cls()
        for fname, spec in cls.__schema_fields__.items():
            if fname in data:
                value = data[fname]
                if spec.nested() and isinstance(value, dict):
                    value = spec.type._from_data(value)
                setattr(instance, fname, value)
        return instance

    def _current_data(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for fname in self.__schema_fields__:
            # nested Config instances stay as-is; _apply_diff walks into them
            out[fname] = getattr(self, fname, None)
        return out
# template generation                                                    #


def _emit_table_template(cls: type[Config], path: list[str], out: list[str]) -> None:
    if path:
        out.append("")
        header = f"[{'.'.join(_key_render(p) for p in path)}]"
        if cls.__schema_summary__:
            out.extend(_wrap_comment(cls.__schema_summary__))
        out.append(header)
    elif cls.__schema_summary__:
        out.extend(_wrap_comment(cls.__schema_summary__))
    for fname, spec in cls.__schema_fields__.items():
        if spec.description:
            out.extend(_wrap_comment(spec.description))
        if spec.nested():
            continue
        default = _zero_value(spec.type) if not spec.has_default else spec.default
        if default is None:
            # optional field left unset: keep the documented option commented out
            out.append(f"# {_key_render(fname)} =")
            continue
        out.append(f"{_key_render(fname)} = {format_value(default)}")
    for fname, spec in cls.__schema_fields__.items():
        if spec.nested():
            _emit_table_template(spec.type, [*path, fname], out)


def _zero_value(tp: Any) -> Any:
    origin = get_origin(tp)
    if origin is list:
        return []
    return ""


def _key_render(name: str) -> str:
    from .nodes import format_key

    return format_key(name)


def _wrap_comment(text: str, prefix: str = "# ") -> list[str]:
    return [f"{prefix}{text}"] if text else []
# validation                                                             #


def _validate_table(
    cls: type[Config],
    data: dict[str, Any],
    path: list[str],
    errors: list[FieldError],
    strict: bool,
) -> None:
    known = set(cls.__schema_fields__)
    if strict:
        errors.extend(FieldError(".".join([*path, key]), "unknown key") for key in data if key not in known)
    for fname, spec in cls.__schema_fields__.items():
        fpath = [*path, fname]
        if fname not in data:
            if not spec.has_default and not spec.nested() and not spec.optional:
                errors.append(FieldError(".".join(fpath), "required field missing", spec.description or None))
            continue
        value = data[fname]
        _validate_value(spec, value, fpath, errors, strict=strict)


def _validate_value(
    spec: _FieldSpec, value: Any, fpath: list[str], errors: list[FieldError], strict: bool = False
) -> None:
    opts = spec.field
    here = ".".join(fpath)
    description = spec.description or None
    if value is None:
        if not spec.optional:
            errors.append(
                FieldError(here, "value is null; TOML has no null — use a default or remove the key", description)
            )
        return

    tp = spec.type
    if _is_config_type(tp):
        if not isinstance(value, dict):
            errors.append(FieldError(here, f"expected a table, got {type(value).__name__}", description))
            return
        _validate_table(tp, value, fpath, errors, strict=strict)
        return

    origin = get_origin(tp)
    if origin is list:
        (item_tp,) = get_args(tp) or (Any,)
        if not isinstance(value, list):
            errors.append(FieldError(here, f"expected an array, got {type(value).__name__}", description))
            return
        for i, item in enumerate(value):
            item_spec = _FieldSpec(spec.name, item_tp, None, _MISSING, "")
            _validate_value(item_spec, item, [*fpath, str(i)], errors, strict=strict)
    elif origin is not None and origin in (types.UnionType, __import__("typing").Union):
        sub_errors: list[str] = []
        for arg in get_args(tp):
            if arg is type(None):
                continue
            probe = _FieldSpec(spec.name, arg, None, _MISSING, "")
            probe_errors: list[FieldError] = []
            _validate_value(probe, value, fpath, probe_errors, strict=strict)
            if not probe_errors:
                return
            sub_errors.extend(e.message for e in probe_errors)
        errors.append(FieldError(here, "no union member matched: " + " | ".join(sub_errors), description))
        return
    else:
        value, ok = _check_type(spec, value, fpath, errors)
        if not ok:
            return

    if opts is None:
        return
    _check_constraints(opts, value, here, errors, description)


def _check_type(spec: _FieldSpec, value: Any, fpath: list[str], errors: list[FieldError]) -> tuple[Any, bool]:
    here = ".".join(fpath)
    tp = spec.type
    opts = spec.field
    coerce = opts.coerce if opts is not None else False
    description = spec.description or None

    if tp is bool:
        if isinstance(value, bool):
            return value, True
        errors.append(FieldError(here, f"expected boolean, got {type(value).__name__}", description))
        return value, False
    if tp is int:
        if isinstance(value, bool):
            errors.append(FieldError(here, "expected integer, got boolean", description))
            return value, False
        if isinstance(value, int):
            return value, True
        if coerce and isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
            return int(value), True
        errors.append(FieldError(here, f"expected integer, got {type(value).__name__}", description))
        return value, False
    if tp is float:
        if isinstance(value, bool):
            errors.append(FieldError(here, "expected float, got boolean", description))
            return value, False
        if isinstance(value, (int, float)):
            return float(value), True
        if coerce and isinstance(value, str) and re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", value.strip()):
            return float(value), True
        errors.append(FieldError(here, f"expected float, got {type(value).__name__}", description))
        return value, False
    if tp is str:
        if isinstance(value, str):
            return value, True
        if coerce and isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value), True
        errors.append(FieldError(here, f"expected string, got {type(value).__name__}", description))
        return value, False
    if tp in (datetime, date, time):
        if isinstance(value, tp):
            return value, True
        errors.append(FieldError(here, f"expected {tp.__name__}, got {type(value).__name__}", description))
        return value, False
    if tp is Any:
        return value, True
    errors.append(FieldError(here, f"unsupported annotation {tp!r}", description))
    return value, False


def _check_constraints(
    opts: Field, value: Any, here: str, errors: list[FieldError], description: str | None = None
) -> None:
    if not isinstance(value, (bool, int, float, str, list)):
        return
    if isinstance(value, bool) and not isinstance(value, (str, list)):
        return
    if opts.ge is not None and isinstance(value, (int, float)) and not isinstance(value, bool) and value < opts.ge:
        errors.append(FieldError(here, f"value {value} is below the minimum {opts.ge}", description))
    if opts.le is not None and isinstance(value, (int, float)) and not isinstance(value, bool) and value > opts.le:
        errors.append(FieldError(here, f"value {value} exceeds the maximum {opts.le}", description))
    if opts.gt is not None and isinstance(value, (int, float)) and not isinstance(value, bool) and value <= opts.gt:
        errors.append(FieldError(here, f"value {value} must be greater than {opts.gt}", description))
    if opts.lt is not None and isinstance(value, (int, float)) and not isinstance(value, bool) and value >= opts.lt:
        errors.append(FieldError(here, f"value {value} must be less than {opts.lt}", description))
    if opts.pattern is not None and isinstance(value, str) and re.search(opts.pattern, value) is None:
        errors.append(FieldError(here, f"value does not match pattern {opts.pattern!r}", description))
    if opts.min_length is not None and isinstance(value, (str, list)) and len(value) < opts.min_length:
        errors.append(FieldError(here, f"length {len(value)} is below the minimum {opts.min_length}", description))
    if opts.max_length is not None and isinstance(value, (str, list)) and len(value) > opts.max_length:
        errors.append(FieldError(here, f"length {len(value)} exceeds the maximum {opts.max_length}", description))
# env overlay                                                            #


def _apply_env(cls: type[Config], data: dict[str, Any], prefix: str) -> None:
    import os

    head = prefix.upper() + "_"
    for env_key, raw in os.environ.items():
        if not env_key.startswith(head):
            continue
        parts = [p.lower() for p in env_key[len(head) :].split("__") if p]
        if not parts:
            continue
        target = data
        for part in parts[:-1]:
            child = target.get(part)
            if not isinstance(child, dict):
                child = {}
                target[part] = child
            target = child
        target[parts[-1]] = _coerce_env(cls, parts, raw)


def _coerce_env(cls: type[Config], parts: list[str], raw: str) -> Any:
    # best-effort coercion against the annotation at this path
    spec: _FieldSpec | None = None
    current: type[Config] = cls
    for i, part in enumerate(parts):
        spec = current.__schema_fields__.get(part)
        if spec is None:
            return raw
        if i < len(parts) - 1:
            if _is_config_type(spec.type):
                current = spec.type
                continue
            return raw
    if spec is None:
        return raw
    tp = spec.type
    if tp is int and re.fullmatch(r"[+-]?\d+", raw):
        return int(raw)
    if tp is float and re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", raw):
        return float(raw)
    if tp is bool and raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw
# load/save plumbing                                                     #


def _to_plain(table: Table) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in table:
        value = table[key]
        out[key] = _to_plain_value(value)
    return out


def _to_plain_value(value: Any) -> Any:
    if isinstance(value, Table):
        return _to_plain(value)
    if isinstance(value, ArrayOfTables):
        return [_to_plain_value(v) for v in value]
    if isinstance(value, list):
        return [_to_plain_value(v) for v in value]
    return value


def _iter_descriptions(cls: type[Config], prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    out: list[tuple[tuple[str, ...], str]] = []
    for fname, spec in cls.__schema_fields__.items():
        fpath = (*prefix, fname)
        if spec.description:
            out.append((fpath, spec.description))
        if spec.nested():
            out.extend(_iter_descriptions(spec.type, fpath))
    return out


def _validated_snapshot(cls: type[Config], data: dict[str, Any]) -> dict[str, Any]:
    """
    The comparison baseline: only keys actually present in the file.
    """
    out: dict[str, Any] = {}
    for fname, spec in cls.__schema_fields__.items():
        if fname not in data:
            continue
        value = data[fname]
        if spec.nested() and isinstance(value, dict):
            out[fname] = _validated_snapshot(spec.type, value)
        else:
            out[fname] = value
    return out


def _apply_diff(instance: Config, doc: Document, snapshot: dict[str, Any], path: list[str]) -> None:
    current = instance._current_data()

    def walk(cls: type[Config], cur: dict[str, Any], snap: dict[str, Any], prefix: list[str]) -> None:
        for fname, spec in cls.__schema_fields__.items():
            fpath = [*prefix, fname]
            now = cur.get(fname)
            was = snap.get(fname, _MISSING)
            _origin = get_origin(spec.type)
            if _origin is list:
                _args = get_args(spec.type)
                if _args and _is_config_type(_args[0]) and isinstance(now, list):
                    now = [v._current_data() if isinstance(v, Config) else v for v in now]
            if spec.nested() and isinstance(now, Config):
                sub_snap = was if isinstance(was, dict) else {}
                walk(spec.type, now._current_data(), sub_snap, fpath)
                continue
            if now is None:
                if was is not _MISSING:
                    if not spec.optional:
                        raise ConfigError(
                            f"cannot assign None to non-optional field {'.'.join(fpath)}"
                        )
                    _doc_delete(doc, fpath)
                continue
            if was is _MISSING:
                # never present in the file: defaults stay unpersisted
                if spec.has_default and now == spec.default:
                    continue
                _doc_assign(doc, fpath, now)
                continue
            if now != was:
                _doc_assign(doc, fpath, now)

    walk(type(instance), current, snapshot, path)


def _doc_assign(doc: Document, fpath: list[str], value: Any) -> None:
    doc.set_path(".".join(fpath), value)


def _doc_delete(doc: Document, fpath: list[str]) -> None:
    target: Any = doc.root
    for part in fpath[:-1]:
        target = target[part]
    if isinstance(target, Table) and fpath[-1] in target:
        del target[fpath[-1]]
