"""
Regression tests for the fourth 0.2.1 batch: AoT insert position, extend/+=
rendering, element replacement, and same-object reassignment no-ops.
"""

import pytest

import tomlclass
from tests._compat import tomllib

SRC = "[[it]]\nn = 1\n\n[[it]]\nn = 2\n\n[[it]]\nn = 3\n"


def _values(doc, key="it"):
    return [element["n"] for element in doc[key]]


def _assert_roundtrip(doc, expected):
    """Memory order, dumps output and idempotency must all agree."""
    out = doc.dumps()
    assert _values(doc) == expected
    assert _values(tomlclass.parse(out)) == expected
    assert tomlclass.parse(out).to_dict() == {"it": [{"n": n} for n in expected]}
    assert doc.dumps() == out  # idempotent


@pytest.mark.parametrize(
    "idx,expected",
    [(-5, [9, 1, 2, 3]), (-3, [9, 1, 2, 3]), (-2, [1, 9, 2, 3]), (-1, [1, 2, 9, 3]),
     (0, [9, 1, 2, 3]), (1, [1, 9, 2, 3]), (2, [1, 2, 9, 3]), (3, [1, 2, 3, 9]),
     (9, [1, 2, 3, 9])],
)
def test_aot_insert_position_matrix(idx, expected):
    d = tomlclass.parse(SRC)
    d["it"].insert(idx, {"n": 9})
    _assert_roundtrip(d, expected)


def test_aot_insert_single_element():
    d = tomlclass.parse("[[it]]\nn = 1\n")
    d["it"].insert(0, {"n": 0})
    _assert_roundtrip(d, [0, 1])


def test_aot_insert_twice_same_position_matches_list_semantics():
    d = tomlclass.parse(SRC)
    d["it"].insert(0, {"n": 10})
    d["it"].insert(0, {"n": 11})  # lands before the first insert
    _assert_roundtrip(d, [11, 10, 1, 2, 3])


def test_aot_insert_two_positions():
    d = tomlclass.parse(SRC)
    d["it"].insert(1, {"n": 10})
    d["it"].insert(2, {"n": 11})
    _assert_roundtrip(d, [1, 10, 11, 2, 3])


def test_aot_insert_then_append():
    d = tomlclass.parse(SRC)
    d["it"].append({"n": 8})
    d["it"].insert(0, {"n": 7})
    _assert_roundtrip(d, [7, 1, 2, 3, 8])


def test_aot_insert_between_appended_elements():
    d = tomlclass.parse(SRC)
    d["it"].append({"n": 8})
    d["it"].append({"n": 9})
    d["it"].insert(3, {"n": 7})
    _assert_roundtrip(d, [1, 2, 3, 7, 8, 9])


def test_aot_insert_then_pop_parsed_element():
    d = tomlclass.parse(SRC)
    d["it"].insert(1, {"n": 7})
    d["it"].pop(2)  # removes the parsed n=2; the insert stays where it was
    _assert_roundtrip(d, [1, 7, 3])


def test_aot_insert_then_pop_the_inserted_element():
    d = tomlclass.parse(SRC)
    d["it"].insert(1, {"n": 7})
    d["it"].pop(1)
    _assert_roundtrip(d, [1, 2, 3])


def test_aot_iadd_routes_through_append_pipeline():
    d = tomlclass.parse(SRC)
    aot = d["it"]
    aot += [{"n": 8}]
    _assert_roundtrip(d, [1, 2, 3, 8])


def test_aot_insert_table_object():
    d = tomlclass.parse(SRC)
    element = tomlclass.Table()
    element["n"] = 42
    d["it"].insert(1, element)
    _assert_roundtrip(d, [1, 42, 2, 3])


def test_aot_extend_renders_new_elements():
    d = tomlclass.parse(SRC)
    d["it"].extend([{"n": 8}])
    _assert_roundtrip(d, [1, 2, 3, 8])


def test_aot_extend_multiple_elements():
    d = tomlclass.parse(SRC)
    d["it"].extend([{"n": 8}, {"n": 9}])
    _assert_roundtrip(d, [1, 2, 3, 8, 9])


def test_aot_extend_then_insert():
    d = tomlclass.parse(SRC)
    d["it"].extend([{"n": 8}])
    d["it"].insert(0, {"n": 7})
    _assert_roundtrip(d, [7, 1, 2, 3, 8])


def test_aot_extend_empty_keeps_document():
    d = tomlclass.parse(SRC)
    d["it"].extend([])
    _assert_roundtrip(d, [1, 2, 3])


def test_aot_insert_lands_before_anchor_header_with_comments_kept():
    src = "[[it]]\nn = 1  # one\n\n# separator comment\n\n[[it]]\nn = 2\n"
    d = tomlclass.parse(src)
    d["it"].insert(1, {"n": 15})
    out = d.dumps()
    # the new block renders immediately before its anchor [[header]]; the
    # inter-element comment stays attached to the element it precedes
    assert out == "[[it]]\nn = 1  # one\n\n# separator comment\n\n[[it]]\nn = 15\n[[it]]\nn = 2\n"
    _assert_roundtrip(d, [1, 15, 2])


def test_aot_insert_and_extend_crlf_document():
    src = "[[it]]\r\nn = 1\r\n\r\n[[it]]\r\nn = 2\r\n"
    d = tomlclass.parse(src)
    d["it"].insert(0, {"n": 0})
    d["it"].extend([{"n": 3}])
    out = d.dumps()
    assert out.count("\n") == out.count("\r\n")  # no mixed line endings
    assert _values(tomlclass.parse(out)) == [0, 1, 2, 3]
    assert d.dumps() == out


def test_aot_insert_nested_path():
    src = '[tool]\nname = "x"\n\n[[tool.items]]\nn = 1\n\n[[tool.items]]\nn = 2\n'
    d = tomlclass.parse(src)
    d["tool"]["items"].insert(0, {"n": 9})
    d["tool"]["items"].extend([{"n": 8}])
    out = d.dumps()
    assert "[[tool.items]]" in out
    back = tomlclass.parse(out)
    assert [e["n"] for e in back["tool"]["items"]] == [9, 1, 2, 8]
    assert tomllib.loads(out) == {"tool": {"name": "x", "items": [{"n": 9}, {"n": 1}, {"n": 2}, {"n": 8}]}}
    assert d.dumps() == out


def test_aot_whole_replace_after_insert_leaves_no_ghosts():
    d = tomlclass.parse(SRC)
    d["it"].insert(1, {"n": 7})
    d["it"] = [{"n": 50}]
    _assert_roundtrip(d, [50])


def test_plain_array_insert_extend_still_canonical():
    d = tomlclass.parse("arr = [1, 2]\n")
    d["arr"].insert(0, 0)
    d["arr"].extend([3])
    out = d.dumps()
    assert tomllib.loads(out) == {"arr": [0, 1, 2, 3]}
    assert d.dumps() == out


def test_document_subscript_iadd_appends_and_renders():
    d = tomlclass.parse(SRC)
    d["it"] += [{"n": 8}]
    _assert_roundtrip(d, [1, 2, 3, 8])


def test_reassign_same_table_no_duplicate_header():
    d = tomlclass.parse('[t]\nx = 1\n')
    t = d["t"]
    t["x"] = 5
    d["t"] = t
    out = d.dumps()
    assert out == "[t]\nx = 5\n"
    assert tomllib.loads(out) == {"t": {"x": 5}}  # a second [t] would be invalid TOML


def test_reassign_same_aot_is_noop():
    d = tomlclass.parse(SRC)
    d["it"] = d["it"]
    assert d.dumps() == SRC


def test_replace_aot_with_own_elements_raises():
    d = tomlclass.parse(SRC)
    with pytest.raises(tomlclass.TOMLTypeError):
        d["it"] = list(d["it"])


@pytest.mark.parametrize("idx,expected", [(0, [50, 2, 3]), (1, [1, 50, 3]), (2, [1, 2, 50]), (-1, [1, 2, 50])])
def test_aot_setitem_replaces_parsed_element(idx, expected):
    d = tomlclass.parse(SRC)
    d["it"][idx] = {"n": 50}
    _assert_roundtrip(d, expected)


def test_aot_setitem_replaces_appended_element():
    d = tomlclass.parse(SRC)
    d["it"].append({"n": 8})
    d["it"][3] = {"n": 9}
    _assert_roundtrip(d, [1, 2, 3, 9])


def test_aot_setitem_replaces_inserted_element():
    d = tomlclass.parse(SRC)
    d["it"].insert(1, {"n": 7})
    d["it"][1] = {"n": 70}
    _assert_roundtrip(d, [1, 70, 2, 3])


def test_aot_setitem_out_of_range_raises():
    d = tomlclass.parse(SRC)
    with pytest.raises(IndexError):
        d["it"][9] = {"n": 0}


def test_aot_setitem_slice_raises():
    d = tomlclass.parse(SRC)
    with pytest.raises(NotImplementedError):
        d["it"][0:1] = []


def test_aot_sort_reverse_raise():
    d = tomlclass.parse(SRC)
    with pytest.raises(NotImplementedError):
        d["it"].sort()
    with pytest.raises(NotImplementedError):
        d["it"].reverse()


def test_find_projects_across_aot_elements():
    d = tomlclass.parse(SRC)
    assert d.find("it.n") == [1, 2, 3]
    assert d.find("it") is d["it"]  # terminal segment: the array itself
    assert d.find("it.missing") == [None, None, None]  # never depends on element count


def test_find_projection_single_element_returns_list():
    d = tomlclass.parse("[[it]]\nn = 1\n")
    assert d.find("it.n") == [1]  # same type as the multi-element result


def test_find_projection_empty_aot_and_deeper_paths():
    d = tomlclass.parse('[[it]]\nn = 1\n\n[[it]]\n\n[[it]]\nn = 3\n[t]\n[t.a]\nb = 7\n')
    assert d.find("it.n") == [1, None, 3]
    assert d.find("t.a.b") == 7  # plain tables unchanged
    assert d.find("nope.nope") is None


def test_set_path_broadcasts_across_aot_elements():
    d = tomlclass.parse(SRC)
    d.set_path("it.n", 9)
    out = d.dumps()
    assert tomllib.loads(out) == {"it": [{"n": 9}, {"n": 9}, {"n": 9}]}
    assert d.dumps() == out  # idempotent


def test_set_path_broadcast_creates_key_in_every_element():
    d = tomlclass.parse(SRC)
    d.set_path("it.tag", "x")
    out = d.dumps()
    data = tomllib.loads(out)
    assert all(element["tag"] == "x" for element in data["it"])
    assert d.dumps() == out


def test_set_path_terminal_aot_whole_replace_unchanged():
    d = tomlclass.parse(SRC)
    d.set_path("it", [{"n": 5}])
    _assert_roundtrip(d, [5])


# set_path type-switch matrix: every combination of target type (scalar /
# array / table / aot) crossed with the assigned value shape, on existing and
# missing keys. This path was rewritten repeatedly during 0.2.1 — the matrix
# locks its semantics instead of relying on changelog history.
SET_PATH_CASES = [
    # ("source", "dotted", value, expected parsed dict)
    ("x = 1\n", "x", {"a": 1}, {"x": {"a": 1}}),                       # scalar -> table
    ("x = 1\n", "x", [1, 2], {"x": [1, 2]}),                           # scalar -> array
    ("x = 1\n", "x.y", 5, {"x": {"y": 5}}),                            # scalar -> table hosting new key
    ("t = [1, 2]\n", "t.x", 5, {"t": {"x": 5}}),                       # array -> table hosting new key
    ("t = [1, 2]\n", "t", {"x": 1}, {"t": {"x": 1}}),                  # array -> table wholesale
    ("t = [1, 2]\n", "t", 5, {"t": 5}),                                # array -> scalar
    ("[t]\nx = 1\n", "t.x", {"a": 1}, {"t": {"x": {"a": 1}}}),         # scalar in table -> table
    ("[t]\nx = 1\n", "t.x", [1], {"t": {"x": [1]}}),                   # scalar in table -> array
    ("[t]\n[t.a]\nx = 1\n", "t.a", 5, {"t": {"a": 5}}),                # nested table -> scalar
    ("[t]\n[t.a]\nx = 1\n", "t.a", [1], {"t": {"a": [1]}}),            # nested table -> array
    ("[a]\nx = 1\n", "a", {"b": 2}, {"a": {"b": 2}}),                  # table wholesale replace
    ("[[it]]\nn = 1\n", "it", {"n": 2}, {"it": {"n": 2}}),             # aot -> table
    ("[[it]]\nn = 1\n", "it", 5, {"it": 5}),                           # aot -> scalar
    ("[[it]]\nn = 1\n", "it", [{"n": 2}], {"it": [{"n": 2}]}),         # aot whole replace
    ("[[it]]\nn = 1\n", "it.n", 9, {"it": [{"n": 9}]}),                # broadcast into elements
    ("", "a.b", 1, {"a": {"b": 1}}),                                   # create intermediates from scratch
    ("[a]\nx = 1\n", "a.b.c", 1, {"a": {"x": 1, "b": {"c": 1}}}),      # create nested under existing
    ("", "x", [{"a": 1}], {"x": [{"a": 1}]}),                          # fresh key: array of tables stays inline
]


@pytest.mark.parametrize(
    "src,dotted,value,expected",
    SET_PATH_CASES,
    ids=[f"{c[1]!r}:{type(c[2]).__name__}" for c in SET_PATH_CASES],
)
def test_set_path_type_switch_matrix(src, dotted, value, expected):
    d = tomlclass.parse(src)
    d.set_path(dotted, value)
    out = d.dumps()
    assert tomllib.loads(out) == expected  # valid TOML, exact content
    assert tomlclass.parse(out).to_dict() == expected  # re-parseable
    assert d.dumps() == out  # idempotent
