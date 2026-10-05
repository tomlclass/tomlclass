"""
toml_version and none_value API modes.
"""

import datetime as dt

import pytest

import tomlclass

ONE_ZERO_CASES = [
    'a = "\\x41"',      # \x escape
    'a = "\\e"',        # \e escape
    "t = 13:37",        # seconds omitted
    "t = { a = 1,\n}",  # inline newline + trailing comma
    "€ = 1",            # non-ASCII bare key
]


@pytest.mark.parametrize("src", ONE_ZERO_CASES)
def test_version_11_accepts(src):
    tomlclass.loads(src)  # default 1.1


@pytest.mark.parametrize("src", ONE_ZERO_CASES)
def test_version_10_rejects(src):
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.loads(src, toml_version="1.0")


def test_version_10_still_parses_10():
    d = tomlclass.loads('a = "\\u0041"\nt = 13:37:00\n', toml_version="1.0")
    assert d == {"a": "A", "t": dt.time(13, 37)}


def test_version_validation():
    with pytest.raises(tomlclass.TOMLParseError, match="unsupported TOML version"):
        tomlclass.loads("a = 1", toml_version="2.0")


def test_version_in_update(tmp_path):
    target = tmp_path / "x.toml"
    target.write_text("t = 13:37:00\n", encoding="utf-8")
    tomlclass.update(target, {"s": 1}, toml_version="1.0")  # 1.0 content parses in 1.0 mode
    assert "s = 1" in target.read_text(encoding="utf-8")
    target.write_text("t = 13:37\n", encoding="utf-8")
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.update(target, {"t": 1}, toml_version="1.0")  # 1.1 value rejected in 1.0 mode
    tomlclass.update(target, {"t": 1})  # default 1.1 accepts it


def test_none_value_roundtrip():
    data = {"k": None, "list": [1, None, 3], "t": {"inner": None}}
    text = tomlclass.dumps(data, none_value="@None")
    assert text == 'k = "@None"\nlist = [1, "@None", 3]\n\n[t]\ninner = "@None"\n'
    back = tomlclass.loads(text, none_value="@None")
    assert back == data
    assert back["k"] is None and back["list"][1] is None


def test_none_value_default_rejects():
    with pytest.raises(tomlclass.TOMLTypeError):
        tomlclass.dumps({"k": None})


def test_none_value_type_and_document_path():
    with pytest.raises(ValueError, match="none_value must be a string"):
        tomlclass.dumps({}, none_value=123)
    with pytest.raises(ValueError, match="none_value applies to Mapping"):
        tomlclass.dumps(tomlclass.parse("a = 1\n"), none_value="@None")
    # raised before any file I/O
    with pytest.raises(ValueError, match="none_value applies to dict output"):
        tomlclass.load("no-such-file.toml", none_value="@None")
