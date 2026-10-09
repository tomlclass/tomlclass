"""
Regression tests for the review batch: editing appended array elements,
multiplicative and aliasing AoT mutators, and dict-semantic popitem.
"""

import pytest

import tomlclass
from tests._compat import tomllib
from tomlclass import TOMLTypeError


def test_edit_appended_single_line_array_element():
    # an appended element edited afterwards must render its new value, not
    # raise IndexError (the append path records no span for the new element)
    d = tomlclass.parse("items = [1, 2, 3]\n")
    d["items"].append(4)
    d["items"][3] = 44
    out = d.dumps()
    assert tomllib.loads(out) == {"items": [1, 2, 3, 44]}
    assert tomlclass.parse(out).dumps() == out


def test_edit_appended_multiline_array_element_keeps_comments():
    # editing an appended element rebuilds the region from the parsed
    # siblings — their per-element comments must survive
    src = "items = [\n  1,  # one\n  2,  # two\n]\n"
    d = tomlclass.parse(src)
    d["items"].append(3)
    d["items"][2] = 33
    out = d.dumps()
    assert "# one" in out and "# two" in out
    assert tomllib.loads(out) == {"items": [1, 2, 33]}
    assert tomlclass.parse(out).dumps() == out


def test_edit_appended_element_then_append_again():
    # the whole pipeline must stay idempotent across a mixed append/edit/
    # append sequence
    d = tomlclass.parse("items = [1, 2]\n")
    d["items"].append(3)
    d["items"][2] = 33
    d["items"].append(4)
    out = d.dumps()
    assert tomllib.loads(out) == {"items": [1, 2, 33, 4]}
    d2 = tomlclass.parse(out)
    d2["items"].append(5)
    out2 = d2.dumps()
    assert tomllib.loads(out2) == {"items": [1, 2, 33, 4, 5]}
    assert tomlclass.parse(out2).dumps() == out2


def test_aot_imul_renders_every_copy():
    # list *= used to bypass the edit bookkeeping: memory doubled while the
    # output silently kept the old blocks
    d = tomlclass.parse("[[it]]\nn = 1\n[[it]]\nn = 2\n")
    d["it"] *= 2
    out = d.dumps()
    assert out.count("[[it]]") == 4
    assert tomllib.loads(out) == {"it": [{"n": 1}, {"n": 2}] * 2}
    assert tomlclass.parse(out).dumps() == out


def test_array_imul_renders_every_copy():
    d = tomlclass.parse("xs = [1, 2]\n")
    d["xs"] *= 2
    out = d.dumps()
    assert tomllib.loads(out) == {"xs": [1, 2, 1, 2]}
    assert tomlclass.parse(out).dumps() == out


def test_aot_append_rejects_aliased_parsed_element():
    # appending an element that already lives in the array would render it
    # twice (its parsed position plus a fresh block)
    d = tomlclass.parse("[[it]]\nn = 1\n[[it]]\nn = 2\n")
    with pytest.raises(TOMLTypeError):
        d["it"].append(d["it"][0])
    assert len(d["it"]) == 2  # memory unchanged after the rejection
    out = d.dumps()
    assert tomllib.loads(out) == {"it": [{"n": 1}, {"n": 2}]}


def test_aot_insert_rejects_aliased_parsed_element():
    d = tomlclass.parse("[[it]]\nn = 1\n[[it]]\nn = 2\n")
    with pytest.raises(TOMLTypeError):
        d["it"].insert(1, d["it"][1])
    assert len(d["it"]) == 2


def test_aot_append_rejects_aliased_appended_element():
    # a runtime-appended element is equally forbidden from re-appending
    d = tomlclass.parse("[[it]]\nn = 1\n")
    d["it"].append({"n": 2})
    appended = d["it"][1]
    with pytest.raises(TOMLTypeError):
        d["it"].append(appended)
    assert len(d["it"]) == 2


def test_table_popitem_follows_dict_lifo_semantics():
    # popitem used to walk insertion order (FIFO) and bypassed the edit
    # hooks, leaving the popped line rendered on save
    d = tomlclass.parse("a = 1\nb = 2\n")
    key, value = d.popitem()
    assert (key, value) == ("b", 2)
    out = d.dumps()
    assert tomllib.loads(out) == {"a": 1}


def test_table_popitem_on_header_table_deletes_line():
    d = tomlclass.parse("root = 0\n[t]\nx = 1\ny = 2\n")
    key, _ = d["t"].popitem()
    assert key == "y"
    out = d.dumps()
    assert tomllib.loads(out) == {"root": 0, "t": {"x": 1}}
    assert tomlclass.parse(out).dumps() == out


def test_aot_imul_zero_and_negative_clear():
    # list semantics: *= 0 (or negative) empties the array
    for factor in (0, -1):
        d = tomlclass.parse("[[it]]\nn = 1\n[[it]]\nn = 2\n")
        d["it"] *= factor
        out = d.dumps()
        assert tomllib.loads(out) == {}
        assert tomlclass.parse(out).dumps() == out


def test_edit_appended_aot_element_renders_once():
    # editing (or adding keys on) a runtime-appended element used to emit the
    # element's lines twice: the fresh [[block]] and again the pending flush
    d = tomlclass.parse("[[it]]\nn = 0\n")
    d["it"].append({"n": 5})
    d["it"][1]["n"] = 10
    d["it"][1]["m"] = 20
    out = d.dumps()
    assert out.count("[[it]]") == 2
    assert out.count("n = 10") == 1
    assert out.count("m = 20") == 1
    assert tomllib.loads(out) == {"it": [{"n": 0}, {"n": 10, "m": 20}]}
    assert tomlclass.parse(out).dumps() == out


def test_edit_parsed_aot_element_still_splices():
    # neighbor check: parsed elements keep splicing in place
    d = tomlclass.parse("[[it]]\nn = 0\n[[it]]\nn = 1\n")
    d["it"][0]["n"] = 99
    out = d.dumps()
    assert out.count("[[it]]") == 2 and out.count("n = 99") == 1
    assert tomllib.loads(out) == {"it": [{"n": 99}, {"n": 1}]}
    assert tomlclass.parse(out).dumps() == out
