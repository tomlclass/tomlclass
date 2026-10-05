"""
TOML 1.1 additions: \\e and \\x escapes, seconds omitted from times,
newlines and trailing commas inside inline tables, non-ASCII bare keys.

The five valid files are vendored from toml-test 1.5.0 (MIT, the files the
1.1 manifest adds on top of 1.0); each must parse and round-trip byte-exactly.
"""

import datetime as dt
from pathlib import Path

import pytest

import tomlclass

CORPUS_11 = Path(__file__).parent.parent / "corpus" / "toml-test-1.1" / "valid"


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in CORPUS_11.glob("*.toml")),
    ids=lambda n: n.removesuffix(".toml"),
)
def test_toml_11_corpus_roundtrip(name):
    text = (CORPUS_11 / name).read_text(encoding="utf-8")
    doc = tomlclass.parse(text)
    assert doc.dumps() == text


def test_escape_e():
    assert tomlclass.loads('a = "\\e"')["a"] == "\x1b"
    # multiline basic strings too
    assert tomlclass.loads('a = """\\e"""')["a"] == "\x1b"
    # literal strings keep the backslash
    assert tomlclass.loads(r"a = '\e'")["a"] == "\\e"


def test_escape_x():
    assert tomlclass.loads('a = "\\x41"')["a"] == "A"
    assert tomlclass.loads('a = "\\x00\\x7f\\xf8"')["a"] == "\x00\x7f\xf8"
    assert tomlclass.loads('a = """\\x68\\x69"""')["a"] == "hi"
    assert tomlclass.loads(r"a = '\x41'")["a"] == "\\x41"


@pytest.mark.parametrize("bad", ['"\\xAg"', '"\\x3"', '"\\x"'])
def test_escape_x_invalid(bad):
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.loads(f"a = {bad}\n")


def test_multiline_escape_crlf_preserved():
    # escape-produced CR LF must survive: only raw source newlines are
    # normalized in multiline strings
    assert tomlclass.loads('a = """\\x0d\\x0a"""')["a"] == "\r\n"
    assert tomlclass.loads('a = """\\u000d\\u000a"""')["a"] == "\r\n"


def test_time_without_seconds():
    d = tomlclass.loads(
        "t = 13:37\n"
        "odt = 1979-05-27T07:32Z\n"
        "odt2 = 1979-05-27 07:32-07:00\n"
        "ldt = 1979-05-27T07:32\n"
        "full = 07:32:00.999\n"
    )
    assert d["t"] == dt.time(13, 37)
    assert d["odt"] == dt.datetime(1979, 5, 27, 7, 32, tzinfo=dt.timezone.utc)
    assert d["odt2"].utcoffset() == dt.timedelta(hours=-7)
    assert d["ldt"] == dt.datetime(1979, 5, 27, 7, 32)
    assert d["full"] == dt.time(7, 32, 0, 999000)
    # raw spelling preserved for lossless rendering
    doc = tomlclass.parse("t = 13:37\n")
    assert doc.dumps() == "t = 13:37\n"


def test_fractional_still_requires_seconds():
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.loads("bad = 07:32.999\n")


def test_inline_table_newlines_and_trailing_comma():
    src = 't = {\n  a = 1,\n  b = "x",\n  arr = [1,\n         2],\n}\n'
    doc = tomlclass.parse(src)
    assert doc["t"] == {"a": 1, "b": "x", "arr": [1, 2]}
    assert doc.dumps() == src  # untouched: byte-exact
    assert tomlclass.loads("t = { a = 1, }\n")["t"] == {"a": 1}
    assert tomlclass.loads("t = {\n}\n")["t"] == {}
    # comments are allowed inside inline tables (TOML 1.1)
    assert tomlclass.loads("t = {\n  a = 1, # one\n}\n")["t"] == {"a": 1}


def test_unicode_bare_keys():
    d = tomlclass.loads("€ = 1\n[中文]\n中文 = 2\n")
    assert d == {"€": 1, "中文": {"中文": 2}}
    assert tomlclass.loads("a‍b = 'zwj'\n")["a‍b"] == "zwj"
    doc = tomlclass.parse("€ = 1\n")
    assert doc.find("€") == 1
    assert doc.dumps() == "€ = 1\n"
    # keys created through the API render canonically (quoted when needed)
    doc = tomlclass.parse("")
    doc["€"] = 1
    assert doc.dumps() == '"€" = 1\n'
    # ASCII structural characters still cannot appear in bare keys
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.loads("a b = 1\n")


def test_dumps_accepts_plain_mapping():
    assert tomlclass.dumps({"a": 1, "t": {"b": "x"}}) == 'a = 1\n\n[t]\nb = "x"\n'
    assert tomlclass.dumps({}) == ""
    data = {"v": [1, 1.2, True, "string"]}
    assert tomlclass.loads(tomlclass.dumps(data)) == data
    doc = tomlclass.parse("a = 1\n")
    assert tomlclass.dumps(doc) == "a = 1\n"  # Document path unchanged


def test_dumps_rejects_none():
    with pytest.raises(tomlclass.TOMLTypeError, match="None cannot be represented"):
        tomlclass.dumps(None)
    with pytest.raises(tomlclass.TOMLTypeError):
        tomlclass.dumps({"k": None})
