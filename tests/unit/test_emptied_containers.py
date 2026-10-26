"""Emptied containers agree between to_dict() and the rendered file."""

import tomlclass


def _assert_coherence(doc):
    out = doc.dumps()
    reparsed = tomlclass.parse(out)
    assert doc.to_dict() == reparsed.to_dict(), (doc.to_dict(), reparsed.to_dict())
    assert tomlclass.loads(out) == doc.to_dict()


def test_cleared_aot_agrees_between_memory_and_file():
    doc = tomlclass.parse("[[items]]\nn = 1  # first\n")
    doc["items"].clear()
    assert doc.dumps() == ""
    _assert_coherence(doc)


def test_aot_pop_to_empty_agrees():
    doc = tomlclass.parse("[[items]]\nn = 1\n")
    doc["items"].pop(0)
    assert doc.dumps() == ""
    _assert_coherence(doc)


def test_aot_imul_zero_agrees():
    doc = tomlclass.parse("[[items]]\nn = 1\n")
    doc["items"] *= 0
    assert doc.dumps() == ""
    _assert_coherence(doc)


def test_aot_whole_replace_with_empty_list_agrees():
    doc = tomlclass.parse("[[items]]\nn = 1\n")
    doc["items"] = []
    assert doc.dumps() == ""
    _assert_coherence(doc)


def test_emptied_aot_recovers_when_refilled():
    doc = tomlclass.parse("[[items]]\nn = 1\n")
    doc["items"].clear()
    assert doc.to_dict() == {}
    doc["items"].append({"n": 2})
    _assert_coherence(doc)
    assert tomlclass.parse(doc.dumps()).to_dict() == {"items": [{"n": 2}]}


def test_emptied_dotted_table_agrees():
    doc = tomlclass.parse("a.b = 1\n\n[t]\nx = 3\n")
    del doc.root["a"]["b"]
    assert tomlclass.parse(doc.dumps()).to_dict() == {"t": {"x": 3}}
    _assert_coherence(doc)


def test_emptied_nested_dotted_tables_cascade():
    doc = tomlclass.parse("a.b.c = 1\n")
    del doc.root["a"]["b"]["c"]
    assert doc.to_dict() == {}
    _assert_coherence(doc)


def test_emptied_dotted_table_recovers_when_refilled():
    doc = tomlclass.parse("a.b = 1\n")
    del doc.root["a"]["b"]
    assert doc.to_dict() == {}
    doc.root["a"]["b"] = 2
    _assert_coherence(doc)
    assert tomlclass.parse(doc.dumps()).to_dict() == {"a": {"b": 2}}


def test_declared_table_emptied_by_deletes_stays_in_memory():
    # a [table] header remains in the file once every entry is deleted —
    # memory keeps it too (only dotted-key tables vanish with their lines)
    doc = tomlclass.parse("[t]\nx = 1\n")
    del doc["t"]["x"]
    assert doc.to_dict() == {"t": {}}
    _assert_coherence(doc)
