"""Constructed array-of-tables bookkeeping across edits and replacements."""

import tomlclass


def test_constructed_aot_element_edit_renders_once() -> None:
    doc = tomlclass.parse("")
    blocks = tomlclass.aot()
    blocks.append({"ak": 1})
    doc["x"] = blocks
    doc["x"][0]["f"] = 2
    assert tomlclass.parse(doc.dumps()).to_dict() == {"x": [{"ak": 1, "f": 2}]}


def test_constructed_aot_broadcast_set_path_renders_once() -> None:
    doc = tomlclass.parse("")
    blocks = tomlclass.aot()
    blocks.append({"ak": 1})
    doc["x"] = blocks
    doc.set_path("x.g", 9)
    assert tomlclass.parse(doc.dumps()).to_dict() == {"x": [{"ak": 1, "g": 9}]}


def test_root_scalar_after_aot_replacement_stays_at_root() -> None:
    doc = tomlclass.parse('[[products]]\nn = "one"\n[[products]]\nn = "two"\n')
    doc["products"] = [{"n": "new"}]
    doc["port"] = 0
    assert tomlclass.parse(doc.dumps()).to_dict() == {"products": [{"n": "new"}], "port": 0}


def test_deleted_constructed_aot_stops_rendering() -> None:
    doc = tomlclass.parse("[t]\n")
    blocks = tomlclass.aot()
    blocks.append({"k": 1})
    doc["t"]["sub"] = blocks
    del doc["t"]["sub"]
    assert tomlclass.parse(doc.dumps()).to_dict() == {"t": {}}


def test_constructed_aot_replaced_by_scalar_stops_rendering() -> None:
    doc = tomlclass.parse("")
    blocks = tomlclass.aot()
    blocks.append({"m": 1})
    doc["k"] = blocks
    doc["k"] = 2
    assert tomlclass.parse(doc.dumps()).to_dict() == {"k": 2}


def test_inline_aot_element_edit_does_not_leak_stray_line() -> None:
    doc = tomlclass.parse("a.q = 1\n\n[t]\nx = 3\n")
    port = tomlclass.aot()
    port.append({"k": 1})
    doc.root["a"]["port"] = port
    doc.root["a"]["port"][0]["z"] = 2
    assert tomlclass.parse(doc.dumps()).to_dict() == {
        "a": {"q": 1, "port": [{"k": 1, "z": 2}]},
        "t": {"x": 3},
    }


def test_appended_aot_block_renders_after_subtable_sections() -> None:
    doc = tomlclass.parse('[[products]]\nname = "nail"\n\n[products.sub]\nz = 1  # nested\n')
    doc["products"].append({"x": 9})
    out = doc.dumps()
    assert tomlclass.parse(out).to_dict() == {
        "products": [{"name": "nail", "sub": {"z": 1}}, {"x": 9}]
    }
    assert out.index("[[products]]") < out.index("[products.sub]") < out.rindex("[[products]]")


def test_aot_imul_renders_valid_output() -> None:
    doc = tomlclass.parse('[[products]]\nname = "nail"\n\n[products.sub]\nz = 1\n')
    doc["products"] *= 2
    # the appended copy renders after the parsed element's [products.sub]
    # section; its sub-table renders inline (a shallow items copy)
    assert tomlclass.parse(doc.dumps()).to_dict() == {
        "products": [{"name": "nail", "sub": {"z": 1}}, {"name": "nail", "sub": {"z": 1}}]
    }


def test_constructed_aot_over_scalar_replaces_the_line() -> None:
    doc = tomlclass.parse("[t]\nport = 1  # the port\n")
    blocks = tomlclass.aot()
    blocks.append({"rep": 9})
    doc["t"]["port"] = blocks
    assert tomlclass.parse(doc.dumps()).to_dict() == {"t": {"port": [{"rep": 9}]}}


def test_constructed_aot_over_inline_table_replaces_the_line() -> None:
    doc = tomlclass.parse("cfg = { a = 1 }\n")
    blocks = tomlclass.aot()
    blocks.append({"rep": 9})
    doc["cfg"] = blocks
    assert tomlclass.parse(doc.dumps()).to_dict() == {"cfg": [{"rep": 9}]}
