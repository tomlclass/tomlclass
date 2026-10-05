"""
Regression tests for the second 0.2.1 batch (community-found issues).
"""


import tomlclass
from tests._compat import tomllib
from tomlclass import Config, Field


def test_array_append_then_modify_element():
    # after a clean-splice append, element edits must not be silently dropped
    d = tomlclass.parse('arr = [\n  "a",\n  "b",\n]\n')
    d["arr"].append("c")
    d["arr"][0] = "X"
    out = d.dumps()
    assert '"X"' in out and '"a"' not in out
    assert tomllib.loads(out) == {"arr": ["X", "b", "c"]}


def test_inline_table_whole_replacement():
    # replacing an inline table must not leave the old entries behind
    d = tomlclass.parse("x = {a = 1, b = 2}\n")
    d["x"] = {"c": 9}
    out = d.dumps()
    assert tomllib.loads(out) == {"x": {"c": 9}}
    assert tomlclass.parse(out)  # valid TOML


def test_list_of_config_elements_are_instances_and_persist_edits(tmp_path):
    class Item(Config):
        name: str = ""
        qty: int = 0

    class Shop(Config):
        items: list[Item] = []  # noqa: RUF012 — the mutable default is the test subject

    src = tmp_path / "shop.toml"
    src.write_text('items = [\n  { name = "apple", qty = 2 },\n]\n', encoding="utf-8")
    shop = Shop.load(src)
    assert isinstance(shop.items[0], Item)
    shop.items[0].qty = 999
    shop.save(src)
    assert tomllib.loads(src.read_text(encoding="utf-8")) == {
        "items": [{"name": "apple", "qty": 999}]
    }


def _i18n_lookup(key):
    return {"cfg.host": "主机地址"}.get(key)


def test_i18n_resolver_on_subclass():
    class Localized(Config):
        i18n_resolver = staticmethod(_i18n_lookup)

        host: str = Field(description={"i18n": "cfg.host", "default": "Host addr"})

    assert Localized.__schema_fields__["host"].description == "主机地址"


def test_set_path_table_replaced_by_scalar(tmp_path):
    src = tmp_path / "t.toml"
    src.write_text("[t]\nx = 1\n", encoding="utf-8")
    doc = tomlclass.update(src, {"t": 5})
    out = src.read_bytes().decode("utf-8")
    assert tomllib.loads(out) == {"t": 5}
    assert doc.dumps() == out


def test_set_path_scalar_replaced_by_table(tmp_path):
    src = tmp_path / "t.toml"
    src.write_text("t = 5\n", encoding="utf-8")
    doc = tomlclass.update(src, {"t": {"x": 1}})
    out = src.read_bytes().decode("utf-8")
    assert tomllib.loads(out) == {"t": {"x": 1}}
    assert doc.dumps() == out


def test_deleted_table_can_be_readded():
    d = tomlclass.parse("[t.x]\ny = 1\n")
    del d["t"]
    d["t"] = {"z": 2}
    out = d.dumps()
    assert tomllib.loads(out) == {"t": {"z": 2}}
    assert d.dumps() == out  # idempotent


def test_assign_crlf_string_escapes_cr():
    # assigning a value containing CR LF must escape the CR — a raw CR in a
    # multiline string is normalized away by conforming parsers on re-read
    d = tomlclass.parse("")
    d["k"] = "a\r\nb"
    out = d.dumps()
    assert "\\r" in out  # escaped form, not a raw CR byte
    assert tomlclass.parse(out)["k"] == "a\r\nb"


def test_assign_crlf_multiline_content_preserved():
    d = tomlclass.parse("")
    d["k"] = "l1\r\nl2\r\nl3"
    assert tomlclass.parse(d.dumps())["k"] == "l1\r\nl2\r\nl3"


def test_assign_cr_with_triple_quotes_uses_basic_multiline():
    d = tomlclass.parse("")
    d["k"] = 'has """quotes"""\r\nline2'
    out = d.dumps()
    assert tomllib.loads(out)["k"] == 'has """quotes"""\r\nline2'
