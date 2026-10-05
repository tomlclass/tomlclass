"""
toml-test conformance suite (TOML 1.0 manifest).

- valid cases: parse must succeed, semantics must match the expected JSON,
  and dumps() must round-trip byte-exactly
- invalid cases: parse must raise TOMLParseError

Both sides are canonicalized to ``(tag, plain_value)`` trees before compare,
so formatting differences (float repr, ``z`` vs ``Z``, ``+00:00`` vs ``Z``)
never mask real mismatches.
"""

import datetime as dt
import json
import math
import re
from pathlib import Path

import pytest

import tomlclass

CORPUS = Path(__file__).parent.parent / "corpus" / "toml-test"


def _manifest_files() -> list[str]:
    manifest = CORPUS / "files-toml-1.0.0"
    entries = []
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and line.endswith(".toml"):
            if not (CORPUS / line).exists():
                pytest.fail(f"toml-test corpus file missing: {line}")
            entries.append(line)
    n_valid = sum(1 for e in entries if e.startswith("valid/"))
    n_invalid = sum(1 for e in entries if e.startswith("invalid/"))
    assert (n_valid, n_invalid) == (208, 501), (
        f"toml-test 1.0 corpus drifted: {n_valid} valid / {n_invalid} invalid"
    )
    return entries


MANIFEST = _manifest_files()
VALID = [e for e in MANIFEST if e.startswith("valid/")]
INVALID = [e for e in MANIFEST if e.startswith("invalid/")]

# Files the 1.0 manifest lists as invalid but TOML 1.1 makes valid —
# tomlclass implements 1.1, so these must parse (and round-trip byte-exactly)
# instead of raising.
TOML_11_UPGRADES = {
    "datetime/no-secs.toml",
    "local-datetime/no-secs.toml",
    "local-time/no-secs.toml",
    "string/basic-byte-escapes.toml",
    "inline-table/linebreak-01.toml",
    "inline-table/linebreak-02.toml",
    "inline-table/linebreak-03.toml",
    "inline-table/linebreak-04.toml",
    "inline-table/trailing-comma.toml",
    "key/special-character.toml",
    "encoding/ideographic-space.toml",
}


def _canon_float(x: float | str) -> str:
    f = float(x)
    if math.isnan(f):
        return "nan"
    if math.isinf(f):
        return "inf" if f > 0 else "-inf"
    return repr(f)


def _norm_datetime_text(s: str) -> str:
    if len(s) > 10 and s[10] in (" ", "t"):
        s = s[:10] + "T" + s[11:]
    if s.endswith("z"):
        s = s[:-1] + "Z"
    if s.endswith(("+00:00", "-00:00")):
        s = s[:-6] + "Z"
    # normalize fractional seconds to microsecond precision (6 digits)
    return re.sub(r"\.(\d+)", lambda m: "." + (m[1] + "000000")[:6], s)


def _plain_expected(node: object) -> object:
    """
    Expected-side: toml-test JSON → (tag, value) canonical tree.
    """
    if isinstance(node, dict):
        if set(node.keys()) == {"type", "value"} and isinstance(node["value"], str):
            t, s = node["type"], node["value"]
            if t == "integer":
                return ("integer", int(s))
            if t == "float":
                return ("float", _canon_float(s))
            if t == "bool":
                return ("bool", s)
            if t == "string":
                return ("string", s)
            if t in ("datetime", "datetime-local", "datetime_local"):
                return ("datetime", _norm_datetime_text(s))
            if t in ("date", "date-local"):
                return ("date", _norm_datetime_text(s))
            if t in ("time", "time-local"):
                return ("time", _norm_datetime_text(s))
            raise AssertionError(f"unknown tag {t}")
        return {k: _plain_expected(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_plain_expected(v) for v in node]
    return node


def _plain_mine(value: object) -> object:
    """
    Mine-side: CST tree → (tag, value) canonical tree.
    """
    if isinstance(value, tomlclass.Table):
        return {k: _plain_mine(v) for k, v in value.items()}
    if isinstance(value, (list, tomlclass.Array)):
        return [_plain_mine(v) for v in value]
    if isinstance(value, bool):
        return ("bool", "true" if value else "false")
    if isinstance(value, int):
        return ("integer", value)
    if isinstance(value, float):
        return ("float", _canon_float(value))
    if isinstance(value, str):
        return ("string", value)
    raw = getattr(value, "toml_raw", None)
    if raw is not None:
        raw = _norm_datetime_text(str(raw))
        if isinstance(value, dt.datetime):
            # toml-test tags local datetimes as plain "datetime" too
            return ("datetime", raw)
        if isinstance(value, dt.date):
            return ("date", raw)
        if isinstance(value, dt.time):
            return ("time", raw)
    if isinstance(value, dt.datetime):
        return ("datetime", value.isoformat())
    raise AssertionError(f"unhandled value type {type(value)!r}")


def _diff(path: str, mine: object, theirs: object, out: list[str]) -> None:
    if isinstance(mine, dict) and isinstance(theirs, dict):
        if set(mine) != set(theirs):
            only_m = sorted(set(mine) - set(theirs))
            only_t = sorted(set(theirs) - set(mine))
            out.append(f"{path}: extra(mine)={only_m} missing(mine)={only_t}")
            return
        for k in theirs:
            _diff(f"{path}.{k}", mine[k], theirs[k], out)
        return
    if isinstance(mine, list) and isinstance(theirs, list):
        if len(mine) != len(theirs):
            out.append(f"{path}: length {len(mine)} != {len(theirs)}")
            return
        for i, (m_item, t_item) in enumerate(zip(mine, theirs, strict=False)):
            _diff(f"{path}[{i}]", m_item, t_item, out)
        return
    if mine != theirs:
        out.append(f"{path}: {mine!r} != {theirs!r}")


def _iter_manifest(kind: str):
    for entry in {"valid": VALID, "invalid": INVALID}[kind]:
        src = CORPUS / entry
        if src.exists():
            yield entry, src


@pytest.mark.parametrize(
    "entry",
    [e for e, _ in _iter_manifest("valid")],
    ids=lambda e: e.removeprefix("valid/"),
)
def test_toml_test_valid(entry: str):
    src = CORPUS / entry
    text = src.read_bytes().decode("utf-8")
    doc = tomlclass.parse(text)
    # byte-exact round-trip axiom on every valid corpus file
    assert doc.dumps() == text
    json_file = src.with_suffix(".json")
    if json_file.exists():
        expected = _plain_expected(json.loads(json_file.read_text(encoding="utf-8")))
        mine = _plain_mine(doc.root)
        out: list[str] = []
        _diff("$", mine, expected, out)
        assert not out, "\n".join(out)


@pytest.mark.parametrize(
    "entry",
    [e for e, _ in _iter_manifest("invalid")],
    ids=lambda e: e.removeprefix("invalid/"),
)
def test_toml_test_invalid(entry: str):
    raw = (CORPUS / entry).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return  # invalid encoding is itself a correct rejection
    if entry.removeprefix("invalid/") in TOML_11_UPGRADES:
        doc = tomlclass.parse(text)  # valid under TOML 1.1
        assert doc.dumps() == text
        return
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.parse(text)


@pytest.mark.parametrize(
    "entry",
    [
        "invalid/encoding/bom-not-at-start-01.toml",
        "invalid/encoding/bom-not-at-start-02.toml",
        "invalid/encoding/bom-not-at-start-03.toml",
        "invalid/control/comment-cr.toml",
    ],
)
def test_toml_test_invalid_explicit(entry: str):
    # explicit assertions (not relying on the generic path): misplaced BOM and bare CR in comments must be rejected
    text = (CORPUS / entry).read_bytes().decode("utf-8")
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.parse(text)
