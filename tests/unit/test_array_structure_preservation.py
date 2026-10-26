"""Alignment-preserving structural edits keep per-element array comments."""

import tomlclass
from tests._compat import tomllib

SRC = "ml = [\n  1,  # one\n  2,  # two\n  3,  # three\n]\n"


def _after(op, expected):
    doc = tomlclass.parse(SRC)
    op(doc["ml"])
    out = doc.dumps()
    reparsed = tomlclass.parse(out)
    assert reparsed.to_dict() == {"ml": expected} == doc.to_dict()
    assert doc.dumps() == out  # idempotent
    return out


def test_pop_head_keeps_survivor_comments():
    out = _after(lambda arr: arr.pop(0), [2, 3])
    assert out == "ml = [\n  2,  # two\n  3,  # three\n]\n"


def test_pop_tail_keeps_survivor_comments():
    out = _after(lambda arr: arr.pop(), [1, 2])
    assert out == "ml = [\n  1,  # one\n  2,  # two\n]\n"


def test_remove_keeps_survivor_comments():
    out = _after(lambda arr: arr.remove(2), [1, 3])
    assert "# one" in out and "# three" in out and "# two" not in out


def test_del_item_keeps_survivor_comments():
    out = _after(lambda arr: del_item(arr, 1), [1, 3])
    assert "# one" in out and "# three" in out and "# two" not in out


def del_item(arr, index):
    del arr[index]


def test_insert_keeps_all_comments():
    out = _after(lambda arr: arr.insert(1, 99), [1, 99, 2, 3])
    assert all(c in out for c in ("# one", "# two", "# three"))
    assert tomllib.loads(out) == {"ml": [1, 99, 2, 3]}


def test_extend_keeps_all_comments():
    out = _after(lambda arr: arr.extend([7, 8]), [1, 2, 3, 7, 8])
    assert all(c in out for c in ("# one", "# two", "# three"))


def test_iadd_keeps_all_comments():
    out = _after(lambda arr: arr.__iadd__([7]), [1, 2, 3, 7])
    assert all(c in out for c in ("# one", "# two", "# three"))


def test_slice_assign_keeps_survivor_comments():
    def op(arr):
        arr[0:2] = [8, 9]

    out = _after(op, [8, 9, 3])
    assert "# three" in out


def test_imul_keeps_originals_and_appends_copies():
    out = _after(lambda arr: arr.__imul__(2), [1, 2, 3, 1, 2, 3])
    assert all(c in out for c in ("# one", "# two", "# three"))
    assert tomllib.loads(out) == {"ml": [1, 2, 3, 1, 2, 3]}


def test_edit_then_structural_edit_keeps_neighbor_comments():
    def op(arr):
        arr[0] = 42
        arr.pop(2)

    # the edited element re-renders canonically; untouched survivors keep comments
    out = _after(op, [42, 2])
    assert "# two" in out and "# one" not in out


def test_structural_then_edit_keeps_own_line_comment():
    def op(arr):
        arr.pop(0)
        arr[0] = 9

    out = _after(op, [9, 3])
    assert "# two" in out and "# three" in out  # the edited line keeps its comment


def test_single_line_style_survives_structural_edit():
    doc = tomlclass.parse("a = [1, 2, 3]\n")
    doc["a"].pop(1)
    assert doc.dumps() == "a = [1, 3]\n"


def test_crlf_array_structural_edit_preserves_endings():
    doc = tomlclass.parse("a = [\r\n  1,  # one\r\n  2,  # two\r\n]\r\n")
    doc["a"].pop(0)
    out = doc.dumps()
    assert out == "a = [\r\n  2,  # two\r\n]\r\n"


def test_nested_array_structural_edit_keeps_outer_layout():
    src = "m = [\n  [1, 2],  # inner\n  3,  # three\n]\n"
    doc = tomlclass.parse(src)
    doc["m"].pop(1)
    out = doc.dumps()
    assert "# inner" in out
    assert tomlclass.parse(out).to_dict() == {"m": [[1, 2]]}


def test_sort_still_renders_canonically():
    # order-destroying mutations cannot keep per-element source positions
    doc = tomlclass.parse(SRC)
    doc["ml"].sort(reverse=True)
    out = doc.dumps()
    assert tomllib.loads(out) == {"ml": [3, 2, 1]}
    assert doc.dumps() == out
