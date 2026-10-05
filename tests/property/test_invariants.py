"""
Property tests for the four invariants (AGENTS.md 6-9), exercised over
randomly generated documents and random API mutations:

6. round-trip axiom      — an unmodified document's dumps() is byte-identical
7. comment preservation  — comments, ordering and formatting survive edits
8. defaults never persist— schema defaults merged in memory stay out of the file
9. CRLF fidelity         — generated lines follow the file's line endings
"""

import string
import tempfile
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given, settings

import tomlclass
from tests._compat import tomllib
from tomlclass import Config, Field

# -- generators --------------------------------------------------------------- #

KEYS = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True)
_SAFE_TEXT = string.printable.replace("#", "").replace('"', "").replace("\\", "").replace("\n", "")
SCALARS = st.one_of(
    st.integers(min_value=-(2**31), max_value=2**31),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.text(alphabet=_SAFE_TEXT, max_size=12),
)
KEYVALUES = st.dictionaries(KEYS, SCALARS, max_size=5)
DOCUMENTS = st.dictionaries(KEYS, st.one_of(SCALARS, KEYVALUES, st.lists(SCALARS, max_size=4)), max_size=6)


def _build(doc_dict):
    """Build a Document from a plain dict through the public API."""
    return tomlclass.parse(tomlclass.dumps(doc_dict))


# -- 6. round-trip axiom -------------------------------------------------------


@given(DOCUMENTS)
@settings(max_examples=200, deadline=None)
def test_roundtrip_and_idempotent_dump(doc_dict):
    text = tomlclass.dumps(doc_dict)
    doc = tomlclass.parse(text)
    assert doc.dumps() == text  # unmodified: byte-identical
    again = tomlclass.parse(doc.dumps())
    assert again.dumps() == doc.dumps()  # idempotent
    assert again.to_dict() == doc.to_dict()


@given(DOCUMENTS, st.data())
@settings(max_examples=200, deadline=None)
def test_edits_then_reparse_preserve_values(doc_dict, data):
    doc = _build(doc_dict)
    extra_keys = data.draw(st.lists(KEYS, max_size=3, unique=True))
    for key in extra_keys:
        doc[key] = data.draw(SCALARS)
    out = doc.dumps()
    back = tomlclass.parse(out)
    assert back.to_dict() == doc.to_dict()
    assert tomlclass.dumps(tomlclass.parse(out)) == out


# -- 7. comment preservation ----------------------------------------------------


@given(KEYS, SCALARS, SCALARS)
@settings(max_examples=150, deadline=None)
def test_value_edits_keep_trailing_comment(key, original, replacement):
    key = key.replace("\\", "")
    value_text = tomlclass.dumps({"v": original}).removeprefix("v = ").strip()
    doc = tomlclass.parse(f"{key} = {value_text}  # keep me\n")
    doc[key] = replacement
    out = doc.dumps()
    assert "# keep me" in out
    assert tomlclass.parse(out)[key] == replacement


@given(DOCUMENTS, st.data())
@settings(max_examples=150, deadline=None)
def test_set_comment_survives_further_edits(doc_dict, data):
    doc = _build(doc_dict)
    doc.add(tomlclass.comment("anchor"))
    key = data.draw(KEYS)
    doc[key] = data.draw(SCALARS)
    doc.set_comment(key, "pinned") if key in doc else None
    out = doc.dumps()
    assert "# anchor" in out
    if key in doc:
        assert "# pinned" in out


# -- 8. defaults never persist ---------------------------------------------------


class _Schema(Config):
    name: str = "default-name"
    retries: int = Field(default=3)
    tags: "list[str]" = Field(default_factory=list)


@given(st.text(alphabet=string.ascii_letters + "_", min_size=1, max_size=12))
@settings(max_examples=100, deadline=None)
def test_defaults_never_persist(name_value):
    # pytest fixtures are not mixed into @given tests (pytest 9 interop);
    # invariant 8 applies to the diff-based save of a loaded instance
    seed = Path(tempfile.mkdtemp()) / "c.toml"
    seed.write_text('name = "seed"\n', encoding="utf-8")
    cfg = _Schema.load(seed)
    cfg.name = name_value
    cfg.save(seed)
    data = tomllib.loads(seed.read_text(encoding="utf-8"))
    assert "retries" not in data  # untouched default stays out of the file
    assert "tags" not in data
    assert data["name"] == name_value  # the changed value persists


# -- 9. CRLF fidelity --------------------------------------------------------------


@given(DOCUMENTS, st.data())
@settings(max_examples=150, deadline=None)
def test_crlf_survives_any_edit(doc_dict, data):
    doc_dict = {"seed": 0, **doc_dict}  # non-empty base: there must be CRLF to preserve
    base = tomlclass.dumps(doc_dict).replace("\n", "\r\n")
    doc = tomlclass.parse(base)
    key = data.draw(KEYS)
    doc[key] = data.draw(SCALARS)
    doc.setdefault("appended", 1)
    out = doc.dumps()
    assert "\r\n" in out
    assert out.count("\n") == out.count("\r\n")  # no mixed line endings
    assert tomlclass.parse(out).to_dict() == doc.to_dict()
