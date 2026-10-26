"""Appended [[block]] elements materialize only non-default, non-None fields."""

import pytest

from tests._compat import tomllib
from tomlclass import Config

pydantic = pytest.importorskip("pydantic", reason="pydantic interop needs pydantic v2")
from pydantic import Field  # noqa: E402

from tomlclass.pydantic import TomlModel  # noqa: E402


class StockedItem(Config):
    name: str = ""
    qty: int = 1
    note: str | None = None


class Stock(Config):
    """Stock lines."""

    items: list[StockedItem] = []  # noqa: RUF012 — the mutable default is the test subject


def test_config_appended_element_skips_defaults_and_none(tmp_path):
    src = tmp_path / "s.toml"
    src.write_text('[[items]]\nname = "a"\nqty = 2\n', encoding="utf-8")
    stock = Stock.load(src)
    stock.items.append(StockedItem(name="b"))
    stock.items.append(StockedItem(name="c", qty=9, note="third"))
    stock.save(src)
    data = tomllib.loads(src.read_text(encoding="utf-8"))
    assert data == {
        "items": [
            {"name": "a", "qty": 2},
            {"name": "b"},
            {"name": "c", "qty": 9, "note": "third"},
        ]
    }


def test_config_appended_element_none_on_non_optional_raises(tmp_path):
    class StrictItem(Config):
        name: str = ""

    class StrictStock(Config):
        items: list[StrictItem] = []  # noqa: RUF012 — the mutable default is the test subject

    src = tmp_path / "s.toml"
    src.write_text('[[items]]\nname = "a"\n', encoding="utf-8")
    stock = StrictStock.load(src)
    stock.items.append(StrictItem(name="b"))
    stock.items[-1].name = None
    from tomlclass import ConfigError

    with pytest.raises(ConfigError, match="non-optional"):
        stock.save(src)


class PCartItem(TomlModel):
    name: str
    qty: int = 1
    note: str | None = None


class PCart(TomlModel):
    items: list[PCartItem] = Field(default_factory=list)


def test_pydantic_appended_element_skips_defaults_and_none(tmp_path):
    p = tmp_path / "cart.toml"
    p.write_text('[[items]]\nname = "a"\nqty = 2\n', encoding="utf-8")
    cart = PCart.load(p)
    cart.items.append(PCartItem(name="b"))
    cart.items.append(PCartItem(name="c", qty=9, note="third"))
    cart.save(p)
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    assert data == {
        "items": [
            {"name": "a", "qty": 2},
            {"name": "b"},
            {"name": "c", "qty": 9, "note": "third"},
        ]
    }


# -- removing an element deletes its own lines, not a survivor's ------------- #


def test_config_middle_element_removal_keeps_survivor_comments(tmp_path):
    src = tmp_path / "s.toml"
    src.write_text(
        '[[items]]  # first item\nname = "first"\n\n[[items]]\nname = "nail"  # the nail\n',
        encoding="utf-8",
    )
    stock = Stock.load(src)
    del stock.items[0]
    stock.save(src)
    text = src.read_text(encoding="utf-8")
    assert "# the nail" in text
    assert "# first item" not in text
    assert tomllib.loads(text) == {"items": [{"name": "nail"}]}


def test_pydantic_middle_element_removal_keeps_survivor_comments(tmp_path):
    p = tmp_path / "cart.toml"
    p.write_text(
        '[[items]]  # first item\nname = "first"\n\n[[items]]\nname = "nail"  # the nail\n',
        encoding="utf-8",
    )
    cart = PCart.load(p)
    cart.items.pop(0)
    cart.save(p)
    text = p.read_text(encoding="utf-8")
    assert "# the nail" in text
    assert "# first item" not in text
    assert tomllib.loads(text) == {"items": [{"name": "nail"}]}


def test_config_element_edit_still_splices_in_place(tmp_path):
    src = tmp_path / "s.toml"
    src.write_text('[[items]]\nname = "a"  # keep\n', encoding="utf-8")
    stock = Stock.load(src)
    stock.items[0].qty = 5
    stock.save(src)
    text = src.read_text(encoding="utf-8")
    assert "# keep" in text
    assert tomllib.loads(text) == {"items": [{"name": "a", "qty": 5}]}


def test_config_element_reorder_replaces_wholesale(tmp_path):
    src = tmp_path / "s.toml"
    src.write_text('[[items]]\nname = "a"\n\n[[items]]\nname = "b"\n', encoding="utf-8")
    stock = Stock.load(src)
    stock.items = [StockedItem(name="b"), StockedItem(name="a")]
    stock.save(src)
    # wholesale replacement keeps memory and file consistent; default-valued
    # fields stay out of the file (invariant 3)
    assert tomllib.loads(src.read_text(encoding="utf-8")) == {
        "items": [{"name": "b"}, {"name": "a"}]
    }
