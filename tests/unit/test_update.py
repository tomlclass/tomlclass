"""
One-call updates: tomlclass.update() and Document.set_path.
"""


import pytest

import tomlclass
from tests._compat import tomllib

SOURCE = """\
# service configuration
name = "demo"

[server]
# the bind address
host = "0.0.0.0"
port = 8000  # the port
"""


def test_update_existing_value_keeps_comment(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    doc = tomlclass.update(target, {"server.port": 9090})
    assert doc["server"]["port"] == 9090
    text = target.read_text(encoding="utf-8")
    assert "port = 9090  # the port" in text
    assert "# the bind address" in text
    assert 'host = "0.0.0.0"' in text
    assert "# service configuration" in text


def test_update_untouched_regions_byte_exact(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    tomlclass.update(target, {"name": "prod"})
    assert target.read_text(encoding="utf-8") == SOURCE.replace('name = "demo"', 'name = "prod"')


def test_update_accepts_str_path(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text("a = 1\n", encoding="utf-8")
    tomlclass.update(str(target), {"a": 2})
    assert target.read_text(encoding="utf-8") == "a = 2\n"


def test_update_creates_missing_key_in_existing_table(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    tomlclass.update(target, {"server.timeout": 30})
    text = target.read_text(encoding="utf-8")
    assert "timeout = 30" in text
    assert "# the bind address" in text  # untouched lines survive


def test_update_creates_missing_intermediate_table(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    doc = tomlclass.update(target, {"cache.dir": "/tmp/cache"})
    # the new table renders as a [cache] block holding its entry — never as a
    # dotted line plus an empty [cache] header (which would define it twice) —
    # and lands at EOF, after every parsed block
    expected = SOURCE.rstrip("\n") + '\n\n[cache]\ndir = "/tmp/cache"\n'
    text = target.read_text(encoding="utf-8")
    assert text == expected
    tomllib.loads(text)  # valid TOML
    assert doc["cache"]["dir"] == "/tmp/cache"


def test_update_creates_deep_missing_tables(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text("top = 1\n", encoding="utf-8")
    tomlclass.update(target, {"x.y.z": 1})
    text = target.read_text(encoding="utf-8")
    tomllib.loads(text)
    data = tomllib.loads(text)
    assert data == {"top": 1, "x": {"y": {"z": 1}}}


def test_update_multiple_keys_at_once(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    tomlclass.update(target, {"name": "prod", "server.port": 9090, "server.timeout": 5})
    text = target.read_text(encoding="utf-8")
    assert 'name = "prod"' in text
    assert "port = 9090" in text
    assert "timeout = 5" in text
    assert "# service configuration" in text


def test_update_aot_whole_replace(tmp_path):
    target = tmp_path / "items.toml"
    target.write_text("[[items]]\nname = 'a'\nprice = 1\n", encoding="utf-8")
    tomlclass.update(target, {"items": [{"name": "b"}, {"name": "c"}]})
    text = target.read_text(encoding="utf-8")
    assert text.count("[[items]]") == 2
    assert 'name = "b"' in text and 'name = "c"' in text
    assert "name = 'a'" not in text


def test_update_none_raises_and_writes_nothing(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    with pytest.raises(tomlclass.TOMLTypeError):
        tomlclass.update(target, {"name": "prod", "server.port": None})
    assert target.read_text(encoding="utf-8") == SOURCE  # all-or-nothing


def test_update_unserializable_value_raises(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text("a = 1\n", encoding="utf-8")
    with pytest.raises(tomlclass.TOMLTypeError):
        tomlclass.update(target, {"a": object()})
    assert target.read_text(encoding="utf-8") == "a = 1\n"


def test_update_file_object_rejected(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text("a = 1\n", encoding="utf-8")
    with target.open("rb") as f, pytest.raises(TypeError):
        tomlclass.update(f, {"a": 2})


def test_update_empty_writes_byte_identical(tmp_path):
    target = tmp_path / "app.toml"
    target.write_text(SOURCE, encoding="utf-8")
    tomlclass.update(target, {})
    assert target.read_text(encoding="utf-8") == SOURCE


def test_document_set_path_matches_update(tmp_path):
    doc = tomlclass.parse(SOURCE)
    doc.set_path("server.port", 9090)
    assert doc["server"]["port"] == 9090
    assert doc.dumps() == SOURCE.replace("port = 8000", "port = 9090")
    doc.set_path("cache.dir", "/tmp")  # creates the [cache] table
    assert doc["cache"]["dir"] == "/tmp"
