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

import enum
import re
import types
from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, ClassVar, Literal, Union, get_args, get_origin, get_type_hints

from ._document import Document, _std_datetime, atomic_write_text
from .errors import ConfigError, FieldError, ValidationError
from .nodes import ArrayOfTables, Table, format_value
from .parser import parse_source

__all__ = ["Config", "Field"]

_MISSING = object()


class Field:
    """
    Per-field options.

    :param default: explicit default value (alternative to a class-level default)
    :param default_factory: zero-arg callable producing a fresh default
        (``list``/``dict`` for mutable defaults — each instance gets its own)
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
        "default_factory",
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
        default_factory: Callable[[], Any] | None = None,
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
        self.default_factory = default_factory
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

    A field section starts at a ``field:`` line — either alone on its line or
    followed by inline text (``host: the bind address``). Before the first
    blank line everything is the summary; a bare ``word: text`` line inside
    the summary stays summary text.
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
        header = re.match(r"([A-Za-z_][A-Za-z0-9_]*):(?:\s+(.*))?$", stripped)
        if header and (not in_summary or header[2] is None):
            in_summary = False
            current = sections.setdefault(header[1], [])
            if header[2]:
                current.append(header[2])
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
    if origin in (types.UnionType, Union):
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
        return tp, False
    return tp, False


class _FieldSpec:
    """
    Resolved schema information for one field.
    """

    __slots__ = (
        "default",
        "default_factory",
        "description",
        "field",
        "has_default",
        "name",
        "optional",
        "type",
    )

    def __init__(self, name: str, tp: Any, field: Field | None, default: Any, description: str) -> None:
        self.name = name
        tp, optional = _unwrap_optional(tp)
        self.type = tp
        self.optional = optional
        self.field = field
        self.default_factory = field.default_factory if field is not None else None
        self.has_default = (
            (field is not None and (field.default is not _MISSING or field.default_factory is not None))
            or default is not _MISSING
        )
        if field is not None and field.default is not _MISSING:
            self.default = field.default
        else:
            self.default = default
        self.description = description

    def effective_default(self) -> Any:
        """Fresh default for one instance (factories return a new container)."""
        if self.default_factory is not None:
            return self.default_factory()
        return self.default

    def nested(self) -> bool:
        return _is_config_type(self.type)


class _ConfigMeta(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        cls = super().__new__(mcs, name, bases, namespace)
        hints = get_type_hints(cls, include_extras=True, localns={name: cls})
        doc_summary, doc_sections = _parse_docstring(namespace.get("__doc__"))
        fields: dict[str, _FieldSpec] = {}
        # inherit fields from Config bases
        for base in reversed(cls.__mro__[1:]):
            fields.update(getattr(base, "__schema_fields__", {}))
        for fname, hint_tp in hints.items():
            if fname.startswith("_"):
                continue
            if get_origin(hint_tp) is ClassVar:
                continue
            tp = hint_tp
            raw_default = namespace.get(fname, _MISSING)
            opts = raw_default if isinstance(raw_default, Field) else None
            # Annotated[X, Field(...)] — metadata Field applies unless the
            # class attribute itself carries one
            meta = getattr(tp, "__metadata__", None)
            if meta:
                for item in meta:
                    if isinstance(item, Field):
                        opts = opts if opts is not None else item
                tp = tp.__origin__
            default = _MISSING
            if isinstance(raw_default, Field):
                assert opts is not None  # narrows with isinstance above
                if opts.default is not _MISSING:
                    default = opts.default
            else:
                default = raw_default
            if opts is not None and opts.description is not None:
                raw_description: str | dict[str, str] | None = opts.description
            else:
                raw_description = doc_sections.get(fname, "")
            resolved_desc: str = ""
            if isinstance(raw_description, str):
                resolved_desc = raw_description
            elif raw_description is not None:
                # i18n dict: resolve through the class resolver (fall back to
                # the declared default when no resolver is installed)
                resolver = getattr(cls, "resolve_i18n", None)
                result = resolver(raw_description) if resolver is not None else raw_description.get("default", "")
                resolved_desc = result if isinstance(result, str) else raw_description.get("default", "")
            fields[fname] = _FieldSpec(fname, tp, opts, default, resolved_desc)
        extra_mode = namespace.get("extra", getattr(cls, "extra", "allow"))
        if extra_mode not in ("allow", "ignore", "forbid"):
            raise ConfigError(
                f"invalid extra mode {extra_mode!r} in {name} (use 'allow', 'ignore' or 'forbid')"
            )
        cls.__schema_fields__ = fields  # type: ignore[attr-defined]
        cls.__schema_summary__ = doc_summary  # type: ignore[attr-defined]
        return cls


class Config(metaclass=_ConfigMeta):
    """
    Base class for declarative TOML configuration.

    Subclass it, annotate fields, document them in the class docstring using
    ``field:`` sections (same-line or multi-line) — those comments become the
    generated template's comments. Nested ``Config`` subclasses become nested
    tables.

    Class options (annotate as ``ClassVar`` or they become fields):

    - ``extra: ClassVar[str]`` — ``"allow"`` (default; unknown keys survive in
      the file), ``"ignore"`` (same, unknown keys never reach the instance),
      ``"forbid"`` (unknown keys are validation errors)
    - ``validate_assignment: ClassVar[bool]`` — validate (and coerce) values
      on attribute assignment; off by default
    """

    i18n_resolver: ClassVar[Callable[[str], str | None] | None] = None
    extra: ClassVar[str] = "allow"
    validate_assignment: ClassVar[bool] = False

    __schema_fields__: ClassVar[dict[str, _FieldSpec]]
    __schema_summary__: ClassVar[str]

    def __init__(self, **kwargs: Any) -> None:
        for fname, spec in self.__schema_fields__.items():
            if fname in kwargs:
                value = kwargs.pop(fname)
            elif spec.nested():
                value = spec.type()
            elif spec.has_default:
                value = spec.effective_default()
            else:
                value = None
            setattr(self, fname, value)
        for key in kwargs:
            raise AttributeError(f"unknown field {key!r} for {type(self).__name__}")
        self._doc: Document | None = None
        self._snapshot: dict[str, Any] | None = None
        self._path: Path | None = None
        self._load_kwargs: dict[str, Any] = {}

    def __setattr__(self, name: str, value: Any) -> None:
        if not name.startswith("_") and getattr(type(self), "validate_assignment", False):
            spec = type(self).__schema_fields__.get(name)
            if spec is not None and not (spec.nested() and isinstance(value, Config)):
                errors: list[FieldError] = []
                probe: dict[str, Any] = {}
                _validate_value(spec, value, [name], errors, parent=probe, key=name)
                if errors:
                    raise ValidationError(errors)
                if name in probe:
                    value = probe[name]
        object.__setattr__(self, name, value)

    # -- data export ------------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        """
        Plain nested dict of the instance: nested ``Config`` instances become
        dicts, ``Enum`` members their values, datetimes standard-library.
        Unknown keys are included when ``extra="allow"``.
        """
        out = {fname: _plain_instance(getattr(self, fname, None)) for fname in self.__schema_fields__}
        for key, value in self.__dict__.items():
            if not key.startswith("_") and key not in self.__schema_fields__:
                out[key] = _plain_instance(value)
        return out

    def reload(self) -> None:
        """
        Re-read the file this instance was loaded from and replace the parsed
        document, snapshot and field values. Instances built in memory raise
        :class:`ConfigError`.
        """
        if self._path is None:
            raise ConfigError("reload() requires an instance loaded from a file")
        fresh = type(self).load(self._path, **self._load_kwargs)
        self._doc = fresh._doc
        self._snapshot = fresh._snapshot
        for fname in self.__schema_fields__:
            object.__setattr__(self, fname, getattr(fresh, fname))

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

        *data* is not modified; use :meth:`_validate` when the coerced values
        are needed.
        """
        errors, _ = cls._validate(data, strict)
        return errors

    @classmethod
    def _validate(cls, data: dict[str, Any], strict: bool = False) -> tuple[list[FieldError], dict[str, Any]]:
        """
        Validate *data* and return ``(errors, coerced)`` — *coerced* is a
        container copy (fresh dicts/lists, shared immutable leaves) with
        ``coerce=True`` conversions applied, ready for instance construction.
        """
        coerced = _container_copy(data)
        errors: list[FieldError] = []
        _validate_table(cls, coerced, [], errors, strict)
        return errors, coerced
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
        with Path(path).open(encoding="utf-8", newline="") as f:
            text = f.read()  # newline="": no universal-newline translation (CRLF stays intact)
        root, parts = parse_source(text, toml_version)
        doc = Document(text, root, parts)
        if comments != "none":
            mode_all = comments == "all"
            for fpath, description, under_aot in _iter_descriptions(cls):
                if not description:
                    continue
                if under_aot:
                    # AoT element fields: inject into every element's matching
                    # line (element tables are not reachable by dotted path)
                    aot = doc.find(".".join(fpath[:-1]))
                    if not isinstance(aot, ArrayOfTables):
                        continue
                    key = (fpath[-1],)
                    for element in aot:
                        if not isinstance(element, Table):
                            continue
                        if key in element._comments:
                            if mode_all:
                                element._comments[key] = f"# {description}"
                            continue
                        sp = element.entry_spans.get(key)
                        if sp is None:
                            continue
                        if mode_all or not _has_trailing_comment(doc._source, sp[1]):
                            element._comments[key] = f"# {description}"
                    continue
                dotted = ".".join(fpath)
                if doc.find(dotted) is None:
                    continue  # key not in file: nothing to inject
                if mode_all or doc.comment(dotted) is None:
                    doc.set_comment(dotted, description)
        data = _to_plain(doc.root)
        if env_prefix:
            _apply_env(cls, data, env_prefix)
        errors, coerced = cls._validate(data, strict=strict)
        if errors:
            raise ValidationError(errors)
        instance = cls._from_data(coerced)
        instance._path = Path(path)
        instance._load_kwargs = {
            "env_prefix": env_prefix,
            "strict": strict,
            "comments": comments,
            "toml_version": toml_version,
        }
        instance._doc = doc
        # the snapshot must not share list objects with the instance fields —
        # in-place mutations (append/pop/…) would change both sides of the
        # diff at once and never persist
        instance._snapshot = _container_copy(_validated_snapshot(cls, coerced))
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
        # the file is the new baseline: values written by this save (and only
        # those) must compare equal on the next save — otherwise a value
        # added and then set to None would never be deleted
        self._snapshot = _validated_snapshot(type(self), _to_plain(self._doc.root))

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
        errors, coerced = cls._validate(data)
        if errors:
            raise ValidationError(errors)
        return cls._from_data(coerced)

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
                elif get_origin(spec.type) is list:
                    args = get_args(spec.type)
                    if args and _is_config_type(args[0]) and isinstance(value, list):
                        # list[Config]: elements must be instances, or edits
                        # made through them would be silently dropped on save
                        value = [args[0]._from_data(v) if isinstance(v, dict) else v for v in value]
                elif get_origin(spec.type) is dict:
                    value = _de_table(value)
                setattr(instance, fname, value)
        if getattr(cls, "extra", "allow") == "allow":
            # unknown keys ride on the instance (and surface in to_dict);
            # they always survive in the file, and edits to them are not
            # diff-tracked
            for key, value in data.items():
                if key not in cls.__schema_fields__:
                    setattr(instance, key, value)
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
        default = _zero_value(spec.type) if not spec.has_default else spec.effective_default()
        if isinstance(default, enum.Enum):
            default = default.value  # templates render the raw member value, like the save path
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
    if origin is dict:
        return {}
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return next(iter(tp)).value
    if origin is not None:
        return ""  # union: empty string is the parseable placeholder
    if tp is bool:
        return False
    if tp is int:
        return 0
    if tp is float:
        return 0.0
    if tp is datetime:
        return datetime(1970, 1, 1)
    if tp is date:
        return date(1970, 1, 1)
    if tp is time:
        return time(0, 0)
    return ""


def _key_render(name: str) -> str:
    from .nodes import format_key

    return format_key(name)


def _wrap_comment(text: str, prefix: str = "# ", width: int = 98) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(prefix) + len(candidate) > width and current:
            lines.append(prefix + current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(prefix + current)
    return lines
# validation                                                             #


def _has_trailing_comment(text: str, value_end: int) -> bool:
    """True when a '#' comment follows *value_end* on the same line."""
    j = value_end
    while j < len(text) and text[j] in " \t":
        j += 1
    return j < len(text) and text[j] == "#"


def _container_copy(value: Any) -> Any:
    """
    Copy dict/list containers so coercion can overwrite slots in the copy;
    immutable leaves (str/int/float/bool/datetime…) are shared as-is —
    deepcopy would break the engine's raw-preserving datetime subclasses.
    """
    if isinstance(value, dict):
        return {k: _container_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_container_copy(v) for v in value]
    return value


def _validate_table(
    cls: type[Config],
    data: dict[str, Any],
    path: list[str],
    errors: list[FieldError],
    strict: bool,
) -> None:
    known = set(cls.__schema_fields__)
    extra_mode = getattr(cls, "extra", "allow")
    if strict or extra_mode == "forbid":
        errors.extend(FieldError(".".join([*path, key]), "unknown key", None) for key in data if key not in known)
    for fname, spec in cls.__schema_fields__.items():
        fpath = [*path, fname]
        if fname not in data:
            if not spec.has_default and not spec.nested() and not spec.optional:
                errors.append(FieldError(".".join(fpath), "required field missing", spec.description or None))
            continue
        value = data[fname]
        _validate_value(spec, value, fpath, errors, strict=strict, parent=data, key=fname)


def _validate_value(
    spec: _FieldSpec,
    value: Any,
    fpath: list[str],
    errors: list[FieldError],
    strict: bool = False,
    parent: Any = None,
    key: Any = None,
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

    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        if isinstance(value, tp):
            return
        for member in tp:
            if member.value == value:
                if parent is not None:
                    parent[key] = member  # normalize to the member itself
                return
        allowed = ", ".join(repr(m.value) for m in tp)
        errors.append(FieldError(here, f"value must be one of {allowed}", description))
        return

    origin = get_origin(tp)
    if origin is dict:
        args = get_args(tp)
        item_tp = args[1] if len(args) > 1 else Any
        if not isinstance(value, dict):
            errors.append(FieldError(here, f"expected an inline table, got {type(value).__name__}", description))
            return
        for k, v in value.items():
            if not isinstance(k, str):
                msg = f"inline table keys must be strings, got {type(k).__name__}"
                errors.append(FieldError(here, msg, description))
                continue
            item_spec = _FieldSpec(spec.name, item_tp, None, _MISSING, "")
            _validate_value(item_spec, v, [*fpath, str(k)], errors, strict=strict, parent=value, key=k)
        return

    if origin is list:
        (item_tp,) = get_args(tp) or (Any,)
        if not isinstance(value, list):
            errors.append(FieldError(here, f"expected an array, got {type(value).__name__}", description))
            return
        for i, item in enumerate(value):
            item_spec = _FieldSpec(spec.name, item_tp, None, _MISSING, "")
            _validate_value(item_spec, item, [*fpath, str(i)], errors, strict=strict, parent=value, key=i)
    elif origin is not None and origin in (types.UnionType, Union):
        sub_errors: list[str] = []
        for arg in get_args(tp):
            if arg is type(None):
                continue
            probe = _FieldSpec(spec.name, arg, None, _MISSING, "")
            probe_errors: list[FieldError] = []
            _validate_value(probe, value, fpath, probe_errors, strict=strict, parent=parent, key=key)
            if not probe_errors:
                return
            sub_errors.extend(e.message for e in probe_errors)
        errors.append(FieldError(here, "no union member matched: " + " | ".join(sub_errors), description))
        return
    else:
        value, ok = _check_type(spec, value, fpath, errors)
        if not ok:
            return
        if parent is not None:
            parent[key] = value  # write coerce=True conversions back into the data tree

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
    if get_origin(tp) is Literal:
        allowed = get_args(tp)
        # type() check keeps bool from matching Literal[1] (True == 1 in Python)
        if any(type(value) is type(a) and value == a for a in allowed):
            return value, True
        errors.append(
            FieldError(
                here,
                "value must be one of " + ", ".join(repr(a) for a in allowed),
                description,
            )
        )
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
    if isinstance(value, bool):
        return  # bool is constraint-free (and an int subclass — exclude it below)
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

    head = prefix.upper().rstrip("_") + "_"  # "APP_" and "APP" behave identically
    for env_key, raw in os.environ.items():
        if not env_key.startswith(head):
            continue
        # both PREFIX_FIELD and PREFIX__FIELD address a top-level field;
        # further "__" pairs separate table segments
        parts = [p.lower() for p in env_key[len(head) :].lstrip("_").split("__") if p]
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
    from ._document import _to_plain as _document_to_plain

    return _document_to_plain(table)


def _de_table(value: Any) -> Any:
    """
    Engine subtree -> plain dicts/lists with standard-library datetimes.
    """
    if isinstance(value, Table):
        return {k: _de_table(v) for k, v in value.items()}
    if isinstance(value, ArrayOfTables):
        return [_de_table(v) for v in value]
    if isinstance(value, list):
        return [_de_table(v) for v in value]
    return _std_datetime(value)


def _plain_instance(value: Any) -> Any:
    """
    Public-shape conversion for instance field values: nested ``Config``
    instances become dicts, ``Enum`` members their raw values, tables and
    datetimes their plain equivalents.
    """
    if isinstance(value, Config):
        return value.to_dict()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Table):
        return _to_plain(value)
    if isinstance(value, ArrayOfTables):
        return [_plain_instance(v) for v in value]
    if isinstance(value, list):
        return [_plain_instance(v) for v in value]
    return _std_datetime(value)


def _iter_descriptions(
    cls: type[Config], prefix: tuple[str, ...] = (), in_aot: bool = False
) -> list[tuple[tuple[str, ...], str, bool]]:
    """
    Yield ``(field_path, description, under_aot)`` — *under_aot* marks fields
    that live inside a ``list[Config]`` (an ``[[aot]]`` element), whose lines
    are only addressable through their element table.
    """
    out: list[tuple[tuple[str, ...], str, bool]] = []
    for fname, spec in cls.__schema_fields__.items():
        fpath = (*prefix, fname)
        if spec.description:
            out.append((fpath, spec.description, in_aot))
        if spec.nested():
            out.extend(_iter_descriptions(spec.type, fpath, in_aot))
        elif get_origin(spec.type) is list:
            args = get_args(spec.type)
            if args and _is_config_type(args[0]):
                out.extend(_iter_descriptions(args[0], fpath, True))
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
            if isinstance(now, enum.Enum):
                now = now.value  # TOML carries the raw member value
            _origin = get_origin(spec.type)
            _aot_elem_cls = None
            if _origin is list:
                _args = get_args(spec.type)
                if _args and _is_config_type(_args[0]):
                    _aot_elem_cls = _args[0]
                    if isinstance(now, list):
                        # de-Config-ify recursively: nested list[Config] inside
                        # the element must become plain data or it cannot be
                        # serialized
                        now = _plain_data(now)
            if _aot_elem_cls is not None and isinstance(now, list):
                # list[Config]: diff per element field so untouched AoT element
                # lines (and their comments / line endings) survive
                _diff_config_aot(doc, fpath, _aot_elem_cls, now, was)
                continue
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
                if spec.has_default and now == spec.effective_default():
                    continue
                _doc_assign(doc, fpath, now)
                continue
            if now != was:
                _doc_assign(doc, fpath, now)

    walk(type(instance), current, snapshot, path)


def _plain_data(value: Any) -> Any:
    """Recursively convert Config instances to plain dicts/lists."""
    if isinstance(value, Config):
        return {k: _plain_data(getattr(value, k)) for k in value.__schema_fields__}
    if isinstance(value, list):
        return [_plain_data(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain_data(v) for k, v in value.items()}
    return value


def _diff_config_aot(
    doc: Document,
    fpath: list[str],
    elem_cls: type[Config],
    now_list: list[dict[str, Any]],
    was: Any,
) -> None:
    """
    Apply per-element, per-field diffs for a ``list[Config]`` field.

    Unchanged element lines are never touched; appended elements go through
    ``aot.append`` (rendered as fresh ``[[block]]``s); removed elements are
    dropped via ``ArrayOfTables.pop`` (marks parsed elements dead and keeps
    the appended/inserted bookkeeping in sync). Falls back to a wholesale
    assignment when the AoT is absent from the file or the shape is not
    diffable.
    """
    aot = doc.find(".".join(fpath))
    if not isinstance(aot, ArrayOfTables):
        _doc_assign(doc, fpath, now_list)  # absent from file: create wholesale
        return
    was_list = was if isinstance(was, list) else []

    shared = min(len(now_list), len(was_list))
    for i in range(shared):
        element = aot[i]
        if not isinstance(element, Table):
            continue
        now_elem, was_elem = now_list[i], was_list[i]
        if not isinstance(was_elem, dict):
            continue
        for fname, fspec in elem_cls.__schema_fields__.items():
            nv = now_elem.get(fname, _MISSING)
            wv = was_elem.get(fname, _MISSING)
            if isinstance(nv, enum.Enum):
                nv = nv.value
            if nv == wv:
                continue  # unchanged: line untouched
            if wv is _MISSING and fspec.has_default and nv == fspec.effective_default():
                continue  # field absent from the file: defaults never persist
            if nv is None:
                if wv is _MISSING:
                    continue
                if not fspec.optional:
                    raise ConfigError(
                        f"cannot assign None to non-optional field {'.'.join([*fpath, str(i), fname])}"
                    )
                if fname in element:
                    del element[fname]  # hooked: the line is removed
                continue
            element[fname] = _plain_data(nv)  # hooked: only this line re-renders
    # removals first (from the END — popping ascending would shift the
    # remaining elements and run past the end), then appends. ArrayOfTables.pop
    # keeps its appended/inserted bookkeeping in sync — never list.pop here.
    for i in range(len(was_list) - 1, len(now_list) - 1, -1):
        aot.pop(i)
    for i in range(len(was_list), len(now_list)):
        aot.append(now_list[i])


def _doc_assign(doc: Document, fpath: list[str], value: Any) -> None:
    doc.set_path(".".join(fpath), value)


def _doc_delete(doc: Document, fpath: list[str]) -> None:
    target: Any = doc.root
    for part in fpath[:-1]:
        target = target[part]
    if isinstance(target, Table) and fpath[-1] in target:
        del target[fpath[-1]]
