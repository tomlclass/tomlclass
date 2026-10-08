"""
Optional pydantic interop (tomlclass.pydantic): validation stays pydantic's,
tomlclass owns lossless TOML load/save with diff-based write-back.
"""

import pytest

toml_pydantic = pytest.importorskip("pydantic")

from typing import Annotated  # noqa: E402

from pydantic import Field, field_validator  # noqa: E402

import tomlclass  # noqa: E402
from tests._compat import tomllib  # noqa: E402
from tomlclass.pydantic import TomlModel  # noqa: E402


class _Server(TomlModel):
    """HTTP server settings."""

    host: str = Field("127.0.0.1", description="the bind address")
    port: int = Field(8000, ge=1, le=65535)
    debug: bool = False


def test_template_from_field_descriptions():
    text = _Server.template()
    assert "# HTTP server settings." in text
    assert "# the bind address" in text
    assert 'host = "127.0.0.1"' in text
    assert "port = 8000" in text
    assert "debug = false" in text


def test_load_validates_through_pydantic(tmp_path):
    p = tmp_path / "s.toml"
    p.write_text('host = "0.0.0.0"\nport = 9000\n', encoding="utf-8")
    server = _Server.load(p)
    assert server.host == "0.0.0.0" and server.port == 9000

    p.write_text('host = "0.0.0.0"\nport = 70000\n', encoding="utf-8")  # le=65535
    with pytest.raises(toml_pydantic.ValidationError):
        _Server.load(p)


def test_field_validator_runs_on_load(tmp_path):
    class Cursed(TomlModel):
        port: int = 8000

        @field_validator("port")
        @classmethod
        def not_1337(cls, v: int) -> int:
            if v == 1337:
                raise ValueError("port 1337 is cursed")
            return v

    p = tmp_path / "c.toml"
    p.write_text("port = 1337\n", encoding="utf-8")
    with pytest.raises(toml_pydantic.ValidationError):
        Cursed.load(p)


def test_save_preserves_comments_and_untouched_lines(tmp_path):
    p = tmp_path / "s.toml"
    p.write_text(
        '# production server\nhost = "0.0.0.0"  # exposed\nport = 9000\ndebug = true\n',
        encoding="utf-8",
    )
    server = _Server.load(p)
    server.host = "10.0.0.1"
    server.save(p)
    text = p.read_text(encoding="utf-8")
    assert text == (
        '# production server\nhost = "10.0.0.1"  # exposed\nport = 9000\ndebug = true\n'
    )


def test_save_persists_new_values_and_reloads(tmp_path):
    p = tmp_path / "s.toml"
    p.write_text('host = "0.0.0.0"\n', encoding="utf-8")
    server = _Server.load(p)
    server.port = 9000
    server.save(p)
    back = _Server.load(p)
    assert back.host == "0.0.0.0" and back.port == 9000
    assert tomlclass.Document is not None  # engine import sanity


def test_save_unbound_raises():
    from tomlclass import ConfigError

    with pytest.raises(ConfigError):
        _Server(port=1).save("nowhere.toml")


def test_nested_models_become_tables(tmp_path):
    class Pool(TomlModel):
        size: int = 5

    class DB(TomlModel):
        """database."""

        pool: Pool = Field(default_factory=Pool)

    p = tmp_path / "db.toml"
    p.write_text("[pool]\nsize = 8\n", encoding="utf-8")
    db = DB.load(p)
    assert db.pool.size == 8
    db.pool.size = 12
    db.save(p)
    out = p.read_text(encoding="utf-8")
    assert tomllib.loads(out) == {"pool": {"size": 12}}  # diff save: untouched lines byte-identical
    assert DB.load(p).pool.size == 12
    template = DB.template()
    assert "# database." in template  # docstring summary lands above the table
    assert tomllib.loads(template) == {"pool": {"size": 5}}


def test_list_of_models_become_aot(tmp_path):
    class Item(TomlModel):
        name: str = "x"
        qty: int = 1

    class Cart(TomlModel):
        items: list[Item] = Field(default_factory=list)

    p = tmp_path / "cart.toml"
    p.write_text("[[items]]\nname = \"a\"\nqty = 1\n\n[[items]]\nname = \"b\"\nqty = 2\n", encoding="utf-8")
    cart = Cart.load(p)
    assert [i.name for i in cart.items] == ["a", "b"]
    cart.items.append(Item(name="c", qty=3))
    cart.save(p)
    out = p.read_text(encoding="utf-8")
    assert tomllib.loads(out) == {"items": [{"name": "a", "qty": 1}, {"name": "b", "qty": 2}, {"name": "c", "qty": 3}]}
    assert Cart.load(p).items[2].name == "c"


def test_none_on_loaded_field_deletes_key(tmp_path):
    class C(TomlModel):
        nickname: str | None = None
        name: str = "x"

    p = tmp_path / "c.toml"
    p.write_text('nickname = "old"\nname = "y"\n', encoding="utf-8")
    c = C.load(p)
    c.nickname = None
    c.save(p)
    text = p.read_text(encoding="utf-8")
    assert tomllib.loads(text) == {"name": "y"}  # None deletes the key
    assert "nickname" not in text


def test_enum_field_serializes_value(tmp_path):
    from enum import Enum

    class Mode(Enum):
        FAST = "fast"
        SLOW = "slow"

    class C(TomlModel):
        mode: Mode = Mode.FAST

    p = tmp_path / "c.toml"
    p.write_text('mode = "fast"\n', encoding="utf-8")
    c = C.load(p)
    assert c.mode is Mode.FAST
    c.mode = Mode.SLOW
    c.save(p)
    assert tomllib.loads(p.read_text(encoding="utf-8")) == {"mode": "slow"}


def test_aot_element_edit_preserves_element_comments(tmp_path):
    class Item(TomlModel):
        name: str = "x"
        qty: int = 1

    class Cart(TomlModel):
        items: list[Item] = Field(default_factory=list)

    p = tmp_path / "cart.toml"
    p.write_text(
        '[[items]]\nname = "a"  # keep-a\nqty = 1\n\n[[items]]\nname = "b"  # keep-b\nqty = 2\n',
        encoding="utf-8",
    )
    cart = Cart.load(p)
    cart.items[1].qty = 20  # element-field edit must splice in place
    cart.save(p)
    text = p.read_text(encoding="utf-8")
    assert "# keep-a" in text and "# keep-b" in text
    assert "qty = 20" in text and 'name = "b"' in text
    assert tomllib.loads(text) == {"items": [{"name": "a", "qty": 1}, {"name": "b", "qty": 20}]}


def test_aot_append_and_pop_through_diff(tmp_path):
    class Item(TomlModel):
        name: str = "x"

    class Cart(TomlModel):
        items: list[Item] = Field(default_factory=list)

    p = tmp_path / "cart.toml"
    p.write_text('[[items]]\nname = "a"\n', encoding="utf-8")
    cart = Cart.load(p)
    cart.items.append(Item(name="b"))
    cart.save(p)
    assert tomllib.loads(p.read_text(encoding="utf-8")) == {"items": [{"name": "a"}, {"name": "b"}]}
    cart.items.pop()
    cart.save(p)
    assert tomllib.loads(p.read_text(encoding="utf-8")) == {"items": [{"name": "a"}]}


def test_save_to_new_path_updates_state(tmp_path):
    p1 = tmp_path / "a.toml"
    p1.write_text('host = "a"\n', encoding="utf-8")
    p2 = tmp_path / "b.toml"
    server = _Server.load(p1)
    server.save(p2)  # switch files mid-session
    server.port = 9000
    server.save(p2)  # must diff against b.toml, not the original a.toml
    data = tomllib.loads(p2.read_text(encoding="utf-8"))
    assert data == {"host": "a", "port": 9000}  # loaded values survive; never-written defaults stay out


def test_nan_field_save_is_idempotent(tmp_path):
    import math

    class C(TomlModel):
        v: float = 0.0

    p = tmp_path / "c.toml"
    p.write_text("v = 1.0\n", encoding="utf-8")
    c = C.load(p)
    c.v = math.nan
    c.save(p)
    first = p.read_text(encoding="utf-8")
    c.save(p)
    assert p.read_text(encoding="utf-8") == first  # NaN no longer rewrites every save


def test_optional_model_and_annotated_list_in_template():

    class Pool(TomlModel):
        size: int = 5

    class DB(TomlModel):
        pool: Pool | None = None
        apool: "Annotated[list[Pool], Field(default_factory=list)]" = Field(default_factory=list)

    template = DB.template()
    assert "[pool]" in template
    assert "[[apool]]" in template
    # the template shows one sample [[apool]] block with the item defaults
    assert tomllib.loads(template) == {"pool": {"size": 5}, "apool": [{"size": 5}]}
