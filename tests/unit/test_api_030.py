"""
0.3.0 public-surface tests: unified path grammar, Document mapping protocol,
construction API, comment addressability and the extended Config layer.
"""

import datetime as dt
from collections.abc import Mapping
from enum import Enum, IntEnum
from typing import Annotated, ClassVar

import pytest

import tomlclass
from tests._compat import tomllib
from tomlclass import Config, ConfigError, Field, ValidationError

# -- path grammar -------------------------------------------------------------


def test_path_quoted_keys_with_dots():
    doc = tomlclass.parse('"a.b" = 2\n[t]\n"x.y" = 3\n')
    assert doc.find('"a.b"') == 2
    assert doc.find('t."x.y"') == 3
    doc.set_path("'a.b'", 99)
    assert tomllib.loads(doc.dumps()) == {"a.b": 99, "t": {"x.y": 3}}


def test_path_index_addresses_aot_elements():
    doc = tomlclass.parse("[[it]]\nn = 1\n\n[[it]]\nn = 2\n\n[[it]]\nn = 3\n")
    assert doc.find("it[0].n") == 1
    assert doc.find("it[2].n") == 3
    assert doc.find("it[9]") is None
    doc.set_path("it[1].n", 20)
    assert [e["n"] for e in tomlclass.parse(doc.dumps())["it"]] == [1, 20, 3]
    assert doc.dumps() == doc.dumps()


def test_path_index_out_of_range_and_missing_raise_on_write():
    doc = tomlclass.parse("[[it]]\nn = 1\n")
    with pytest.raises(IndexError):
        doc.set_path("it[5].n", 0)
    with pytest.raises(KeyError):
        doc.set_path("missing[0].n", 0)


def test_path_syntax_errors_raise_value_error():
    doc = tomlclass.parse("[[it]]\nn = 1\n")
    for bad in ["", "a..b", "a.", ".a", "a[", "a[01]", "a[-1]", 'a["b', "a[*]"]:
        with pytest.raises(ValueError):
            doc.find(bad)
        with pytest.raises(ValueError):
            doc.set_path(bad, 1)


def test_find_projection_unchanged():
    d = tomlclass.parse("[[it]]\nn = 1\n\n[[it]]\nn = 2\n")
    assert d.find("it.n") == [1, 2]
    assert d.find("it") is d["it"]


# -- Document protocol ---------------------------------------------------------


def test_document_is_mapping_with_value_equality():
    doc = tomlclass.parse('a = 1\n[t]\nb = "x"\n')
    assert isinstance(doc, Mapping)
    assert doc == {"a": 1, "t": {"b": "x"}}
    assert doc == tomlclass.parse('a = 1\n[t]\nb = "x"\n')
    assert doc != {"a": 1}
    assert doc != 42
    with pytest.raises(TypeError):
        hash(doc)


def test_document_full_mapping_surface():
    doc = tomlclass.parse("a = 1\nb = 2\n")
    assert list(doc.keys()) == ["a", "b"]
    assert list(doc.values()) == [1, 2]
    assert list(doc.items()) == [("a", 1), ("b", 2)]
    assert list(reversed(doc)) == ["b", "a"]
    assert doc.pop("a") == 1
    assert "a" not in doc and doc.dumps() == "b = 2\n"  # the line is gone from output
    doc.setdefault("c", 3)
    assert doc["c"] == 3 and "c = 3" in doc.dumps()
    doc.update({"b": 20})
    assert doc["b"] == 20 and "b = 20" in doc.dumps()
    assert doc.copy() == {"b": 20, "c": 3}
    merged = doc | {"d": 4}
    assert merged == {"b": 20, "c": 3, "d": 4}
    doc |= {"e": 5}
    assert doc["e"] == 5


def test_document_pop_and_clear_remove_lines():
    doc = tomlclass.parse("a = 1\n\n[t]\nx = 1\n")
    doc.pop("a")
    assert "a = 1" not in doc.dumps()
    doc["t"].clear()
    assert doc.dumps() == "[t]\n"
    assert tomlclass.parse(doc.dumps()).to_dict() == {"t": {}}


def test_table_dict_mutators_route_through_hooks():
    doc = tomlclass.parse("[t]\nx = 1\ny = 2\nz = 3\n")
    t = doc["t"]
    t.update({"x": 10})
    assert "x = 10" in doc.dumps()
    assert t.setdefault("w", 4) == 4
    assert "w = 4" in doc.dumps()
    assert t.pop("y") == 2
    assert "y = 2" not in doc.dumps()


def test_to_dict_returns_standard_datetimes():
    doc = tomlclass.parse("d = 1979-05-27T07:32:00Z\nt = 07:32:00\n")
    plain = doc.to_dict()
    assert type(plain["d"]) is dt.datetime
    assert type(plain["t"]) is dt.time
    assert plain["d"].tzinfo is not None


def test_table_to_dict():
    doc = tomlclass.parse("[s]\nx = 1\n")
    assert doc["s"].to_dict() == {"x": 1}


# -- comments -------------------------------------------------------------------


def test_comment_on_table_header_line():
    doc = tomlclass.parse("[db] # primary\nx = 1\n")
    assert doc.comment("db") == "primary"
    doc.set_comment("db", "changed")
    assert doc.dumps() == "[db]  # changed\nx = 1\n"
    doc.set_comment("db", None)
    assert doc.dumps() == "[db]\nx = 1\n"
    assert doc.comment("db") is None


def test_comment_on_dotted_key_leaf():
    doc = tomlclass.parse("a.b = 1  # leaf\n")
    assert doc.comment("a.b") == "leaf"
    doc.set_comment("a.b", "new")
    assert doc.dumps() == "a.b = 1  # new\n"


def test_comment_on_api_created_key():
    doc = tomlclass.parse("[t]\nx = 1\n")
    doc["t"]["fresh"] = 7
    doc.set_comment("t.fresh", "created")
    assert doc.comment("t.fresh") == "created"
    assert "fresh = 7  # created" in doc.dumps()
    assert tomlclass.dumps(tomlclass.parse(doc.dumps())) == doc.dumps()


def test_comment_on_aot_element_field():
    doc = tomlclass.parse("[[it]]\nn = 1  # one\n\n[[it]]\nn = 2\n")
    assert doc.comment("it[0].n") == "one"
    doc.set_comment("it[1].n", "two")
    assert "n = 2  # two" in doc.dumps()
    with pytest.raises(KeyError):
        doc.set_comment("it.n", "ambiguous")


def test_comment_missing_key_behaviour():
    doc = tomlclass.parse("a = 1\n")
    assert doc.comment("nope") is None
    with pytest.raises(KeyError):
        doc.set_comment("nope", "x")


# -- construction API -------------------------------------------------------------


def test_document_builder_from_scratch():
    doc = tomlclass.document()
    doc["name"] = "app"
    t = tomlclass.table()
    t["port"] = 8000
    doc["server"] = t
    out = doc.dumps()
    assert out == 'name = "app"\n\n[server]\nport = 8000\n'
    assert tomlclass.parse(out) == {"name": "app", "server": {"port": 8000}}


def test_aot_builder_grows_blocks():
    doc = tomlclass.document()
    items = tomlclass.aot()
    doc["items"] = items
    items.append({"n": 1})
    items.append({"n": 2})
    out = doc.dumps()
    assert out == "[[items]]\nn = 1\n\n[[items]]\nn = 2\n"
    items.append({"n": 3})
    assert doc.dumps().count("[[items]]") == 3  # appends after the first dump render too


def test_trivia_lines_attach_via_add():
    doc = tomlclass.document()
    doc["a"] = 1
    doc.add(tomlclass.comment("edited below"))
    doc.add(tomlclass.nl())
    out = doc.dumps()
    assert "# edited below" in out
    assert tomlclass.parse(out) == {"a": 1}


def test_add_existing_key_raises():
    doc = tomlclass.parse("a = 1\n")
    with pytest.raises(KeyError):
        doc.add("a", 2)


def test_dump_and_load_path(tmp_path):
    target = tmp_path / "x.toml"
    with target.open("w", encoding="utf-8", newline="") as fp:
        tomlclass.dump({"a": 1, "t": {"b": 2}}, fp)
    assert tomllib.loads(target.read_text(encoding="utf-8")) == {"a": 1, "t": {"b": 2}}
    doc = tomlclass.load_path(target)
    assert isinstance(doc, tomlclass.Document)
    assert doc["a"] == 1
    with (target.open("rb")) as binary, pytest.raises(TypeError):
        tomlclass.load_path(binary)


# -- Config layer -------------------------------------------------------------------


def test_config_dict_annotation_roundtrip(tmp_path):
    class C(Config):
        limits: dict[str, int] = {}  # noqa: RUF012 - the mutable default is the test subject

    p = tmp_path / "c.toml"
    p.write_text("limits = { soft = 10, hard = 20 }\n", encoding="utf-8")
    c = C.load(p)
    assert c.limits == {"soft": 10, "hard": 20}
    c.limits["hard"] = 30
    c.save(p)
    back = C.load(p)
    assert back.limits == {"soft": 10, "hard": 30}


def test_config_enum_annotation(tmp_path):
    class Mode(Enum):
        FAST = "fast"
        SLOW = "slow"

    class C(Config):
        mode: Mode = Mode.FAST

    p = tmp_path / "c.toml"
    p.write_text('mode = "slow"\n', encoding="utf-8")
    c = C.load(p)
    assert c.mode is Mode.SLOW
    c.mode = Mode.FAST
    c.save(p)
    assert tomllib.loads(p.read_text(encoding="utf-8")) == {"mode": "fast"}
    assert C.validate_dict({"mode": "turbo"})


def test_config_enum_template_plain_str_and_int():
    # template() renders raw member values for every enum flavor — plain,
    # str-mixin and int-mixin alike (the save path already did; this path
    # used to crash on plain Enums and emit invalid TOML for IntEnums)
    class Mode(Enum):
        FAST = "fast"

    class Speed(IntEnum):
        LOW = 1

    class C(Config):
        mode: Mode = Mode.FAST
        speed: Speed = Speed.LOW

    text = C.template()
    assert tomllib.loads(text) == {"mode": "fast", "speed": 1}


def test_config_annotated_field():
    class C(Config):
        port: Annotated[int, Field(ge=1, le=65535, description="listen port")] = 8000

    assert "listen port" in C.template()
    assert C.validate_dict({"port": 0})  # ge=1 rejects
    assert not C.validate_dict({"port": 8080})


def test_config_default_factory_isolated_instances():
    class C(Config):
        tags: list[str] = Field(default_factory=list)

    a, b = C(), C()
    a.tags.append("x")
    assert b.tags == []


def test_config_to_dict_and_reload(tmp_path):
    class Nested(Config):
        depth: int = 1

    class C(Config):
        name: str = "x"
        nested: Nested = Field(default_factory=Nested)

    p = tmp_path / "c.toml"
    p.write_text('name = "app"\n\n[nested]\ndepth = 3\n', encoding="utf-8")
    c = C.load(p)
    assert c.to_dict() == {"name": "app", "nested": {"depth": 3}}
    assert type(c.to_dict()["nested"]) is dict
    p.write_text('name = "app2"\n\n[nested]\ndepth = 5\n', encoding="utf-8")
    c.reload()
    assert c.name == "app2" and c.nested.depth == 5
    with pytest.raises(ConfigError):
        C().reload()


def test_config_validate_assignment():
    class C(Config):
        port: int = 8000
        validate_assignment: ClassVar[bool] = True

    c = C()
    c.port = 9000
    assert c.port == 9000
    with pytest.raises(ValidationError):
        c.port = "not a number"


def test_config_extra_forbid():
    class C(Config):
        x: int = 0
        extra: ClassVar[str] = "forbid"

    assert C.validate_dict({"x": 1, "nope": 2})
    assert not C.validate_dict({"x": 1})


def test_config_docstring_same_line_format():
    class C(Config):
        """
        Service.

        host: the bind address
        port:
            the listen port
        """

        host: str = "0.0.0.0"
        port: int = 80

    text = C.template()
    assert "# the bind address" in text
    assert "# the listen port" in text


def test_template_wraps_long_comments():
    long_text = " ".join(["word"] * 40)

    class C(Config):
        key: str = Field(default="v", description=long_text)

    lines = [ln for ln in C.template().splitlines() if ln.startswith("#")]
    assert len(lines) > 1
    assert all(len(ln) <= 100 for ln in lines)
