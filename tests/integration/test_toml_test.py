"""
toml-test conformance suite against a live toml-test checkout.

Two official manifests are exercised:

- ``files-toml-1.0.0``: every file parsed with ``toml_version="1.0"``
  (strict legacy semantics)
- ``files-toml-1.1.0``: every file parsed with the default 1.1 mode

- valid cases: parse must succeed, semantics must match the expected JSON,
  and dumps() must round-trip byte-exactly
- invalid cases: parse must raise TOMLParseError

The suite needs a toml-test checkout (CI fetches the pinned ref into
``.toml-test/``); point ``TOML_TEST_DIR`` at its ``tests/`` directory or
clone the repo to ``.toml-test/``. Without it the whole module skips, so
offline runs stay green.
"""

import datetime as dt
import json
import math
import os
import re
from pathlib import Path

import pytest

import tomlclass

TOML_TEST_REF = "v2.2.0"  # keep in sync with .github/workflows/code-quality-check.yml

# (manifest, toml_version-or-None-for-default, n_valid, n_invalid) — counts
# are pinned to TOML_TEST_REF; drift means the checkout changed under us
MANIFESTS = [
    ("files-toml-1.0.0", "1.0", 205, 474),
    ("files-toml-1.1.0", None, 214, 467),
]


def _tests_dir() -> Path | None:
    env = os.environ.get("TOML_TEST_DIR")
    default = Path(__file__).parent.parent.parent / ".toml-test" / "tests"
    for candidate in ([Path(env)] if env else [default]):
        if (candidate / "files-toml-1.1.0").exists():
            return candidate
    return None


TESTS_DIR = _tests_dir()

pytestmark = pytest.mark.skipif(
    TESTS_DIR is None,
    reason=f"no toml-test checkout (ref {TOML_TEST_REF}); clone it to .toml-test/ or set TOML_TEST_DIR",
)


def _manifest_entries(tests: Path, manifest: str) -> list[str]:
    entries = []
    for raw_line in (tests / manifest).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and line.endswith(".toml"):
            if not (tests / line).exists():
                pytest.fail(f"toml-test corpus file missing: {line}")
            entries.append(line)
    return entries


CASES: list[tuple[str, str | None, str]] = []
if TESTS_DIR is not None:
    _seen: set[str] = set()
    for _manifest, _version, _n_valid, _n_invalid in MANIFESTS:
        _entries = _manifest_entries(TESTS_DIR, _manifest)
        _nv = sum(1 for e in _entries if e.startswith("valid/"))
        _ni = sum(1 for e in _entries if e.startswith("invalid/"))
        assert (_nv, _ni) == (_n_valid, _n_invalid), f"{_manifest} drifted: {_nv} valid / {_ni} invalid"
        _seen.update(_entries)
        CASES.extend((_manifest, _version, e) for e in _entries)
    # every corpus file on disk must be covered by at least one manifest —
    # a partial checkout must fail loudly, not silently shrink coverage
    _on_disk = {
        p.relative_to(TESTS_DIR).as_posix()
        for side in ("valid", "invalid")
        for p in (TESTS_DIR / side).rglob("*.toml")
    }
    _uncovered = sorted(_on_disk - _seen)
    assert not _uncovered, f"toml-test files not covered by any manifest: {_uncovered[:5]}"

VALID_CASES = [c for c in CASES if c[2].startswith("valid/")]
INVALID_CASES = [c for c in CASES if c[2].startswith("invalid/")]


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
    # TOML 1.1 allows omitting seconds; the canonical expected forms carry them
    def _fill_seconds(t: str) -> str:
        if re.match(r"^\d{2}:\d{2}(?![:\d])", t):
            return t[:5] + ":00" + t[5:]
        return t

    head, sep, tail = s.partition("T")
    s = head + "T" + _fill_seconds(tail) if sep else _fill_seconds(s)  # bare local time
    # fractional seconds compare digit-count-insensitively: pad to microseconds
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


def _case_id(case: tuple[str, str | None, str]) -> str:
    manifest, _version, entry = case
    return manifest.removeprefix("files-toml-") + ":" + entry


@pytest.mark.parametrize("case", VALID_CASES, ids=[_case_id(c) for c in VALID_CASES])
def test_toml_test_valid(case: tuple[str, str | None, str]):
    _manifest, version, entry = case
    src = TESTS_DIR / entry
    text = src.read_bytes().decode("utf-8")
    doc = tomlclass.parse(text) if version is None else tomlclass.parse(text, toml_version=version)
    # byte-exact round-trip axiom on every valid corpus file
    assert doc.dumps() == text
    json_file = src.with_suffix(".json")
    if json_file.exists():
        expected = _plain_expected(json.loads(json_file.read_text(encoding="utf-8")))
        mine = _plain_mine(doc.root)
        out: list[str] = []
        _diff("$", mine, expected, out)
        assert not out, "\n".join(out)


@pytest.mark.parametrize("case", INVALID_CASES, ids=[_case_id(c) for c in INVALID_CASES])
def test_toml_test_invalid(case: tuple[str, str | None, str]):
    _manifest, version, entry = case
    raw = (TESTS_DIR / entry).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return  # invalid encoding is itself a correct rejection
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.parse(text) if version is None else tomlclass.parse(text, toml_version=version)


@pytest.mark.parametrize(
    "entry",
    [
        "invalid/encoding/bom-not-at-start-01.toml",
        "invalid/encoding/bom-not-at-start-02.toml",
        "invalid/control/comment-cr.toml",
    ],
)
def test_toml_test_invalid_explicit(entry: str):
    # explicit assertions (not relying on the generic path): misplaced BOM and bare CR in comments must be rejected
    try:
        text = (TESTS_DIR / entry).read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return  # invalid encoding is itself a correct rejection
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.parse(text)
