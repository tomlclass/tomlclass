"""
Everyday user scenarios across the public API — the calls a downstream user
actually makes, with both semantic (tomllib) and byte-level assertions.
"""

import datetime as dt
from typing import ClassVar, Literal

import pytest

import tomlclass
from tests._compat import tomllib
from tomlclass import Config, InlineTable

# -- update() on real-world file shapes --------------------------------------


def test_update_creates_aot_from_list_of_dicts(tmp_path):
    target = tmp_path / "pyproject.toml"
    target.write_text('[project]\nname = "demo"\n', encoding="utf-8")
    tomlclass.update(target, {"project.version": "1.0.0", "authors": [{"name": "A"}, {"name": "B"}]})
    text = target.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["project"]["version"] == "1.0.0"
    assert data["authors"] == [{"name": "A"}, {"name": "B"}]


def test_update_on_dotted_key_file(tmp_path):
    # a file written with dotted keys: root key + extending the sealed table
    target = tmp_path / "d.toml"
    target.write_text('a.b = 1\na.c = 2\n', encoding="utf-8")
    doc = tomlclass.update(target, {"a.d": 3, "top": True})
    assert doc["a"]["d"] == 3 and doc["top"] is True
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert data == {"a": {"b": 1, "c": 2, "d": 3}, "top": True}


def test_update_unicode_keys_and_values(tmp_path):
    target = tmp_path / "u.toml"
    target.write_text('existing = 1\n', encoding="utf-8")
    tomlclass.update(target, {"键": "值", "section": {"名字": True}})
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert data == {"existing": 1, "键": "值", "section": {"名字": True}}


def test_update_datetime_value(tmp_path):
    target = tmp_path / "t.toml"
    target.write_text('name = "x"\n', encoding="utf-8")
    tomlclass.update(target, {"released_at": dt.datetime(2026, 10, 6, 12, 30, 0)})
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert data["released_at"] == dt.datetime(2026, 10, 6, 12, 30, 0)
    # and it reads back as a datetime
    assert tomlclass.load(target)["released_at"].year == 2026


def test_update_all_or_nothing_across_keys(tmp_path):
    target = tmp_path / "a.toml"
    target.write_text("ok = 1\n", encoding="utf-8")
    with pytest.raises(tomlclass.TOMLTypeError):
        tomlclass.update(target, {"good": 2, "bad": None})
    assert target.read_text(encoding="utf-8") == "ok = 1\n"  # nothing written


def test_update_multiline_string_value(tmp_path):
    target = tmp_path / "m.toml"
    target.write_text('title = "x"\n', encoding="utf-8")
    tomlclass.update(target, {"body": "line1\nline2\n"})
    text = target.read_text(encoding="utf-8")
    assert tomllib.loads(text)["body"] == "line1\nline2\n"
    # and a second identical update is idempotent
    tomlclass.update(target, {"body": "line1\nline2\n"})
    assert tomllib.loads(target.read_text(encoding="utf-8"))["body"] == "line1\nline2\n"


def test_crlf_file_edits_keep_line_endings(tmp_path):
    # editing an existing value on a CRLF file keeps that line's CRLF;
    # newly appended lines use \n (documented mixed-line-ending behavior)
    target = tmp_path / "w.toml"
    target.write_bytes(b'name = "x"\r\n[tool]\r\nmode = "fast"\r\n')
    tomlclass.update(target, {"name": "y"})
    raw = target.read_bytes()
    assert raw.startswith(b'name = "y"\r\n')
    assert tomllib.loads(raw.decode("utf-8")) == {"name": "y", "tool": {"mode": "fast"}}


# -- Document mapping / navigation -------------------------------------------


def test_document_mapping_protocol():
    doc = tomlclass.parse('[server]\nhost = "h"\nport = 8000\n')
    assert "server" in doc
    assert "missing" not in doc
    assert len(doc) == 1
    assert list(doc) == ["server"]
    assert doc["server"].get("port") == 8000
    assert doc["server"].get("nope") is None
    with pytest.raises(KeyError):
        doc["nope"]


def test_find_and_set_path_on_aot_elements(tmp_path):
    # find() projects across aot elements; set_path() broadcasts into every one
    doc = tomlclass.parse('[[servers]]\nhost = "a"\n[[servers]]\nhost = "b"\n')
    assert doc.find("servers.host") == ["a", "b"]
    doc.set_path("servers.port", 8000)
    out = doc.dumps()
    data = tomllib.loads(out)
    assert data["servers"][0]["port"] == 8000
    assert data["servers"][1]["port"] == 8000  # every element updated


def test_reload_then_edit_again(tmp_path):
    # the save → reload → edit cycle stays consistent
    target = tmp_path / "app.toml"
    target.write_text('name = "demo"\n\n[server]\nhost = "h"\nport = 8000\n', encoding="utf-8")
    doc = tomlclass.load(target)
    doc["server"]["port"] = 9000
    doc.save(target)
    doc2 = tomlclass.load(target)
    assert doc2["server"]["port"] == 9000
    doc2["debug"] = True
    doc2.save(target)
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert data == {"name": "demo", "debug": True, "server": {"host": "h", "port": 9000}}


# -- InlineTable and arrays ---------------------------------------------------


def test_explicit_inline_table_creation_and_closedness():
    doc = tomlclass.parse("")
    doc["point"] = InlineTable({"x": 1, "y": 2})
    out = doc.dumps()
    assert tomllib.loads(out) == {"point": {"x": 1, "y": 2}}
    # inline tables are closed: keys cannot be added later
    with pytest.raises(tomlclass.TOMLTypeError):
        doc["point"]["z"] = 3


def test_array_sort_and_reverse_persist():
    doc = tomlclass.parse("nums = [3, 1, 2]\n")
    doc["nums"].sort()
    assert tomllib.loads(doc.dumps())["nums"] == [1, 2, 3]
    doc["nums"].reverse()
    assert tomllib.loads(dumps2 := doc.dumps())["nums"] == [3, 2, 1]
    assert doc.dumps() == dumps2


def test_aot_append_dict_then_edit_element(tmp_path):
    target = tmp_path / "items.toml"
    target.write_text('[[items]]\nname = "a"\n', encoding="utf-8")
    doc = tomlclass.load(target)
    doc["items"].append({"name": "b"})
    doc.save(target)
    doc2 = tomlclass.load(target)
    assert doc2["items"][-1]["name"] == "b"
    doc2["items"][-1]["name"] = "B"
    doc2.save(target)
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert data["items"] == [{"name": "a"}, {"name": "B"}]


# -- Config layer extras ------------------------------------------------------


def test_config_classvar_and_underscore_excluded():
    class App(Config):
        """App."""

        visible: str = "v"
        _hidden: str = "h"  # underscore-prefixed: excluded from the schema
        kind: ClassVar[str] = "k"  # ClassVar: excluded

    text = App.template()
    assert "visible" in text
    assert "_hidden" not in text and "hidden =" not in text
    assert "kind" not in text
    app = App()
    assert app.visible == "v" and app._hidden == "h"


def test_config_subclass_inherits_fields(tmp_path):
    class Base(Config):
        """Base."""

        shared: str = "s"

    class Child(Base):
        own: int = 1

    text = Child.template()
    assert "shared" in text and "own" in text
    src = tmp_path / "c.toml"
    src.write_text('shared = "x"\nown = 2\n', encoding="utf-8")
    child = Child.load(src)
    assert child.shared == "x" and child.own == 2


def test_config_load_toml_version_passthrough(tmp_path):
    from tomlclass import TOMLParseError

    src = tmp_path / "t.toml"
    src.write_text("t = 13:37\n", encoding="utf-8")

    class T(Config):
        t: dt.time = None  # type: ignore[assignment]

    assert T.load(src).t == dt.time(13, 37)  # default 1.1 accepts it
    with pytest.raises(TOMLParseError):
        T.load(src, toml_version="1.0")  # 1.0 rejects the seconds-omitted time


def test_validate_bool_not_matching_int_literal():

    class Nums(Config):
        n: Literal[1, 2] = 1

    assert Nums.validate_dict({"n": 2}) == []
    assert Nums.validate_dict({"n": True})  # True == 1 but type differs → rejected


def test_env_override_accepts_single_and_double_underscore(tmp_path, monkeypatch):
    # both PREFIX_FIELD and PREFIX__FIELD address a top-level field
    class App(Config):
        port: int = 8000

    src = tmp_path / "a.toml"
    src.write_text("port = 8000\n", encoding="utf-8")
    monkeypatch.setenv("APP_PORT", "1234")
    assert App.load(src, env_prefix="APP").port == 1234
    monkeypatch.setenv("APP__PORT", "1234")
    assert App.load(src, env_prefix="APP").port == 1234
    # prefix must be followed by an underscore: unrelated vars never match
    monkeypatch.delenv("APP__PORT")
    monkeypatch.delenv("APP_PORT")
    monkeypatch.setenv("APPX_PORT", "1234")
    assert App.load(src, env_prefix="APP").port == 8000


def test_crlf_array_append_uses_crlf(tmp_path):
    # appended lines match the file's line endings — no mixed endings
    target = tmp_path / "arr.toml"
    target.write_bytes(b'arr = [\r\n  "a",\r\n  "b",\r\n]\r\n')
    doc = tomlclass.load(target)
    doc["arr"].append("c")
    doc.save(target)
    raw = target.read_bytes()
    assert b"\r\n" in raw and raw.replace(b"\r\n", b"").count(b"\n") == 0
    assert tomllib.loads(raw.decode("utf-8"))["arr"] == ["a", "b", "c"]


def test_aot_element_edit_preserves_crlf_and_comments(tmp_path):
    # editing one AoT element field must not rewrite the whole file
    class Item(Config):
        """Item."""

        n: int = 0
        tags: list[int] = []  # noqa: RUF012 — the mutable default is the test subject

    class Box(Config):
        """Box."""

        its: list[Item] = []  # noqa: RUF012 — the mutable default is the test subject

    src = tmp_path / "b.toml"
    src.write_bytes(b'[[its]]\nn = 0  # count\ntags = [1, 2]\r\n')
    box = Box.load(src, comments="all")
    box.its[0].n = 99
    box.save(src)
    raw = src.read_bytes()
    assert b"\r\n" in raw  # line endings survive
    assert b"# count" in raw  # injected comment survives
    assert tomllib.loads(raw.decode("utf-8"))["its"][0]["n"] == 99


def test_pending_lines_match_crlf_endings(tmp_path):
    # new keys/tables in a CRLF file use CRLF, not LF
    src = tmp_path / "c.toml"
    src.write_bytes(b"a = 1\r\n[t]\r\nx = 1\r\n")
    doc = tomlclass.load(src)
    doc["newk"] = 1
    doc["newt"] = {"z": 1}
    out = doc.dumps()
    assert out.replace("\r\n", "").count("\n") == 0
    assert tomllib.loads(out) == {"a": 1, "newk": 1, "t": {"x": 1}, "newt": {"z": 1}}


def test_optional_set_then_none_deletes(tmp_path):
    # a value added in one save cycle is deletable in the next
    class Opt(Config):
        a: int | None = None
        b: int = 5

    src = tmp_path / "o.toml"
    src.write_text("b = 5\n", encoding="utf-8")
    c = Opt.load(src)
    c.a = 7
    c.save(src)
    assert tomllib.loads(src.read_text(encoding="utf-8")) == {"a": 7, "b": 5}
    c.a = None
    c.save(src)
    assert tomllib.loads(src.read_text(encoding="utf-8")) == {"b": 5}
    c.save(src)  # double save is a no-op
    assert tomllib.loads(src.read_text(encoding="utf-8")) == {"b": 5}
