"""
Regression tests for the third 0.2.1 batch (community-found issues 11-14).
"""

import pytest

import tomlclass
from tests._compat import tomllib
from tomlclass import Config

CASES = [
    ("[t]\nx = 1\n", {"t": 5}, lambda d: d.__setitem__("t", 5)),
    ("[t]\nx = 1\n[other]\ny = 2\n", {"t": 5, "other": {"y": 2}}, lambda d: d.__setitem__("t", 5)),
    ("[a.t]\nx = 1\n", {"a": {"t": 5}}, lambda d: d["a"].__setitem__("t", 5)),
    ("[t]\nx = 1\n", {"t": "s"}, lambda d: d.__setitem__("t", "s")),
    ("[t]\nx = 1\n", {"t": [1, 2]}, lambda d: d.__setitem__("t", [1, 2])),
    ("[[it]]\nx = 1\n", {"it": 5}, lambda d: d.__setitem__("it", 5)),
    ('t = "s"\n', {"t": [1, 2]}, lambda d: d.__setitem__("t", [1, 2])),
]


@pytest.mark.parametrize("src,expect,act", CASES, ids=[c[0].replace("\n", "\\n") for c in CASES])
def test_setitem_table_replaced(tmp_path, src, expect, act):
    target = tmp_path / "x.toml"
    target.write_text(src, encoding="utf-8")
    doc = tomlclass.parse(src)
    act(doc)
    out = doc.dumps()
    assert tomllib.loads(out) == expect
    assert tomlclass.parse(out).to_dict() == expect  # re-parseable, no duplicate definitions
    assert doc.dumps() == out  # idempotent


def test_literal_validation():
    from typing import Literal

    class C(Config):
        mode: Literal["a", "b"] = "a"

    assert C.validate_dict({"mode": "a"}) == []
    errors = C.validate_dict({"mode": "z"})
    assert errors and "value must be one of" in str(errors[0])
    # bool does not match Literal[1]
    class Nums(Config):
        n: Literal[1, 2] = 1

    assert Nums.validate_dict({"n": 2}) == []
    assert Nums.validate_dict({"n": True})  # True == 1 but type differs → rejected


def test_multiline_array_element_edit_preserves_layout_and_comments():
    src = 'arr = [\n  "a",  # first\n  "b",  # second\n]\n'
    d = tomlclass.parse(src)
    d["arr"][0] = "X"
    out = d.dumps()
    assert out == 'arr = [\n  "X",  # first\n  "b",  # second\n]\n'
    assert tomllib.loads(out) == {"arr": ["X", "b"]}


def test_comments_all_injected_into_aot_elements(tmp_path):
    class Item(Config):
        """
        item

        name:
            Item name here.
        qty:
            Quantity here.
        """
        name: str = "x"
        qty: int = 0

    class Shop(Config):
        """shop"""
        items: list[Item]

    src = tmp_path / "shop.toml"
    src.write_bytes(b"[[items]]\nname = \"a\"\nqty = 2\n")
    shop = Shop.load(src, comments="all")
    shop.save(src)
    text = src.read_text(encoding="utf-8")
    assert 'name = "a"  # Item name here.' in text
    assert "qty = 2  # Quantity here." in text


def test_edit_then_append_values_preserved():
    # mixed edit + append falls back to canonical rendering; values must survive
    d = tomlclass.parse('arr = [\n  "a",  # first\n  "b",  # second\n]\n')
    d["arr"][0] = "X"
    d["arr"].append("c")
    assert tomllib.loads(d.dumps())["arr"] == ["X", "b", "c"]


def test_nested_array_inner_edits_are_scoped():
    d = tomlclass.parse("arr = [[1, 2], [3]]\n")
    d["arr"][0][0] = 9
    assert tomllib.loads(d.dumps())["arr"] == [[9, 2], [3]]
    d["arr"][1][0] = 8
    assert tomllib.loads(d.dumps())["arr"] == [[9, 2], [8]]
    d["arr"][0].append(7)
    assert tomllib.loads(d.dumps())["arr"] == [[9, 2, 7], [8]]


def test_chained_scalar_table_scalar_replacement(tmp_path):
    target = tmp_path / "t.toml"
    target.write_text("t = 5\n", encoding="utf-8")
    doc = tomlclass.parse("t = 5\n")
    doc["t"] = {"x": 1}
    out1 = doc.dumps()
    assert not out1.startswith("\n")  # no stray leading blank line
    assert tomllib.loads(out1) == {"t": {"x": 1}}
    doc["t"] = 5
    out2 = doc.dumps()
    assert tomllib.loads(out2) == {"t": 5}
    assert doc.dumps() == out2  # idempotent
    doc.save(target)
    assert tomllib.loads(target.read_text(encoding="utf-8")) == {"t": 5}


def test_config_list_in_place_mutations_persist(tmp_path):
    # I22: the diff snapshot must not share list objects with the instance,
    # or append/pop/extend/insert/clear changes are silently dropped on save
    class Item(Config):
        name: str = ""
        qty: int = 0

    class Shop(Config):
        items: list[Item] = []  # noqa: RUF012 — the mutable default is the test subject

    src = tmp_path / "shop.toml"
    src.write_bytes(b'items = [\n  { name = "apple", qty = 2 },\n]\n')

    shop = Shop.load(src)
    shop.items.append(Item(name="pear", qty=1))
    shop.save(src)
    assert tomllib.loads(src.read_text(encoding="utf-8"))["items"][-1] == {"name": "pear", "qty": 1}

    shop = Shop.load(src)
    shop.items[0].qty = 42
    shop.save(src)
    assert tomllib.loads(src.read_text(encoding="utf-8"))["items"][0]["qty"] == 42

    shop = Shop.load(src)
    shop.items.pop()
    shop.save(src)
    assert len(tomllib.loads(src.read_text(encoding="utf-8"))["items"]) == 1

    shop = Shop.load(src)
    shop.items.clear()
    shop.save(src)
    assert tomllib.loads(src.read_text(encoding="utf-8")) == {"items": []}


def test_nested_array_structural_mutations_keep_siblings():
    # structural changes on an inner array must not drop siblings
    d = tomlclass.parse("arr = [[1,2],[3]]\n")
    d["arr"][0].pop()
    assert tomllib.loads(d.dumps())["arr"] == [[1], [3]]
    d["arr"][0].clear()
    assert tomllib.loads(d.dumps())["arr"] == [[], [3]]
    d["arr"][0].insert(0, 0)
    assert tomllib.loads(d.dumps())["arr"] == [[0], [3]]
    d["arr"][0].extend([9])
    assert tomllib.loads(d.dumps())["arr"] == [[0, 9], [3]]


def test_inner_edit_combined_with_outer_append():
    # mixing inner edits and outer appends keeps every value
    d = tomlclass.parse("arr = [[1,2],[3]]\n")
    d["arr"][0][0] = 9
    d["arr"].append([4])
    assert tomllib.loads(d.dumps())["arr"] == [[9, 2], [3], [4]]


def test_chained_same_type_replacements(tmp_path):
    # chained same-type replacements leave exactly
    # one definition behind
    d = tomlclass.parse("[t]\nx = 1\n")
    d["t"] = 5
    d["t"] = 7
    out = d.dumps()
    assert tomllib.loads(out) == {"t": 7} and d.dumps() == out

    d = tomlclass.parse("t = 5\n")
    d["t"] = {"x": 1}
    d["t"] = {"y": 2}
    out = d.dumps()
    assert tomllib.loads(out) == {"t": {"y": 2}} and d.dumps() == out

    d = tomlclass.parse("t = 5\n")
    d["t"] = {"x": 1}
    d["t"] = 6
    out = d.dumps()
    assert tomllib.loads(out) == {"t": 6} and d.dumps() == out


def test_nested_append_then_outer_append():
    # inner append + outer append: both must survive
    d = tomlclass.parse("arr = [[1, 2], [3]]\n")
    d["arr"][0].append(5)
    d["arr"].append([4])
    assert tomllib.loads(d.dumps())["arr"] == [[1, 2, 5], [3], [4]]


def test_outer_append_then_nested_append():
    # same combination, opposite order
    d = tomlclass.parse("arr = [[1, 2], [3]]\n")
    d["arr"].append([4])
    d["arr"][0].append(5)
    assert tomllib.loads(d.dumps())["arr"] == [[1, 2, 5], [3], [4]]


def test_three_level_appends_all_survive():
    d = tomlclass.parse("arr = [[[1]],[[2]]]\n")
    d["arr"][0][0].append(9)
    d["arr"][0].append([5])
    d["arr"].append([[3]])
    assert tomllib.loads(d.dumps())["arr"] == [[[1, 9], [5]], [[2]], [[3]]]


def test_array_appends_invalidated_by_replacement():
    # a clean-append record must not resurrect the old array text after the
    # key is replaced by a scalar
    d = tomlclass.parse("arr = [[1, 2], [3]]\n")
    d["arr"].append([4])
    d["arr"] = 5
    assert tomllib.loads(d.dumps()) == {"arr": 5}


def test_aot_clear_multi_element(tmp_path):
    # clearing a multi-element AoT must not raise IndexError
    src = tmp_path / "arr.toml"
    src.write_text("arr = [[1,2],[3],[4],[5]]\n", encoding="utf-8")
    d = tomlclass.parse(src.read_text(encoding="utf-8"))
    d["arr"].clear()
    out = d.dumps()
    assert tomllib.loads(out) == {"arr": []}
    assert d.dumps() == out


def test_aot_element_with_list_config_field(tmp_path):
    # list[Config] inside an AoT element must survive load/save
    # (both `subs = [{...}]` inline and `[[hosts.subs]]` child-aot forms)
    from tomlclass import Config as _Config

    class Sub(_Config):
        k: int = 0

    class Host(_Config):
        n: int = 0
        subs: list[Sub] = []  # noqa: RUF012 — the mutable default is the test subject

    class Cont(_Config):
        hosts: list[Host] = []  # noqa: RUF012 — the mutable default is the test subject

    for content in (
        b"[[hosts]]\nn = 1\nsubs = [{k = 1}]\n",
        b"[[hosts]]\nn = 1\n[[hosts.subs]]\nk = 1\n",
    ):
        src = tmp_path / "c.toml"
        src.write_bytes(content)
        cont = Cont.load(src)
        cont.save(src)  # no-modify save: must not raise
        out = src.read_bytes().decode("utf-8")
        assert tomllib.loads(out)["hosts"][0]["subs"][0]["k"] == 1

    # nested edit persists
    cont = Cont.load(src)
    cont.hosts[0].subs[0].k = 99
    cont.save(src)
    assert tomllib.loads(src.read_bytes().decode("utf-8"))["hosts"][0]["subs"][0]["k"] == 99
