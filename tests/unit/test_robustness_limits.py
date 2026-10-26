"""Depth limits, iterator slice assignment and datetime conversion edges."""

import datetime as dt
from typing import Any

import pytest

from tomlclass import TOMLParseError, TOMLTypeError, document, dumps, loads, parse, table

# -- header / dotted-key table depth (parse-time limit: 200) ---------------- #


def test_header_path_over_depth_limit_rejected() -> None:
    deep = ".".join(f"k{i}" for i in range(201))
    with pytest.raises(TOMLParseError, match="nesting depth"):
        parse(f"[{deep}]\nx = 1\n")


def test_header_path_at_depth_limit_round_trips() -> None:
    deep = ".".join(f"k{i}" for i in range(200))
    source = f"[{deep}]\nx = 1\n"
    doc = parse(source)
    assert doc.dumps() == source
    node: Any = doc.to_dict()
    for i in range(200):
        node = node[f"k{i}"]
    assert node == {"x": 1}


def test_dotted_key_over_depth_limit_rejected() -> None:
    deep = ".".join(f"k{i}" for i in range(202))
    with pytest.raises(TOMLParseError, match="nesting depth"):
        parse(f"{deep} = 1\n")


def test_dotted_key_at_depth_limit_round_trips() -> None:
    deep = ".".join(f"k{i}" for i in range(201))
    source = f"{deep} = 1\n"
    doc = parse(source)
    assert doc.dumps() == source
    node: Any = doc.to_dict()
    for i in range(201):
        node = node[f"k{i}"]
    assert node == 1


def test_chained_headers_over_cumulative_depth_rejected() -> None:
    headers = "\n".join(
        "[" + ".".join(f"k{j}" for j in range(i)) + "]" for i in range(1, 203)
    )
    with pytest.raises(TOMLParseError, match="nesting depth"):
        parse(headers + "\n")


# -- API-supplied value depth (assignment-time limit: 200) ------------------ #


def _deep_list(levels: int) -> list[Any]:
    root: list[Any] = []
    node = root
    for _ in range(levels):
        child: list[Any] = []
        node.append(child)
        node = child
    return root


def _deep_dict(levels: int) -> dict[str, Any]:
    root: dict[str, Any] = {}
    node = root
    for _ in range(levels):
        node["child"] = {}
        node = node["child"]
    return root


def test_deep_list_assignment_raises_toml_type_error() -> None:
    doc = parse("[t]\n")
    with pytest.raises(TOMLTypeError, match="nesting depth"):
        doc["t"]["k"] = _deep_list(300)


def test_deep_dict_assignment_raises_toml_type_error() -> None:
    doc = parse("[t]\n")
    with pytest.raises(TOMLTypeError, match="nesting depth"):
        doc["t"]["k"] = _deep_dict(300)


def test_deep_manual_table_chain_rejected_at_assignment() -> None:
    with pytest.raises(TOMLTypeError, match="nesting depth"):
        node = table()
        for _ in range(300):
            child = table()
            node["x"] = child
            node = child


def test_manual_table_chain_within_limit_assigns_and_renders() -> None:
    root = table()
    node = root
    for _ in range(50):
        child = table()
        node["x"] = child
        node = child
    node["leaf"] = 1
    doc = document()
    doc["k"] = root
    reparsed = parse(doc.dumps())
    inner: Any = reparsed["k"]
    for _ in range(50):
        inner = inner["x"]
    assert inner["leaf"] == 1


def test_dumps_deep_mapping_raises_toml_type_error() -> None:
    with pytest.raises(TOMLTypeError, match="nesting depth"):
        dumps({"k": _deep_dict(300)})


def test_dumps_deep_mapping_with_none_sentinel_raises_toml_type_error() -> None:
    deep = _deep_dict(300)
    deep["leaf"] = None
    with pytest.raises(TOMLTypeError, match="nesting depth"):
        dumps(deep, none_value="null")


# -- array slice assignment consumes iterators exactly once ----------------- #


def test_array_slice_assignment_accepts_iterator() -> None:
    doc = parse("arr = [1, 2, 3]\n")
    doc["arr"][0:2] = iter([9, 8])
    assert list(doc["arr"]) == [9, 8, 3]
    assert parse(doc.dumps()).to_dict()["arr"] == [9, 8, 3]


def test_array_slice_assignment_accepts_generator() -> None:
    doc = parse("arr = [1, 2, 3, 4]\n")
    doc["arr"][1:3] = (v * 10 for v in (7, 8))
    assert list(doc["arr"]) == [1, 70, 80, 4]


def test_array_whole_slice_assignment_from_iterator() -> None:
    doc = parse("arr = [1, 2, 3]\n")
    doc["arr"][:] = iter([5, 6, 7, 8])
    assert list(doc["arr"]) == [5, 6, 7, 8]
    assert len(doc["arr"].spans) == len(doc["arr"])


def test_array_extended_slice_assignment_validates_before_mutating() -> None:
    doc = parse("arr = [1, 2, 3, 4]\n")
    with pytest.raises(ValueError):
        doc["arr"][::2] = iter([7])
    assert list(doc["arr"]) == [1, 2, 3, 4]
    assert len(doc["arr"].spans) == len(doc["arr"])
    assert parse(doc.dumps()).to_dict()["arr"] == [1, 2, 3, 4]


def test_array_extended_slice_assignment_matching_length() -> None:
    doc = parse("arr = [1, 2, 3, 4]\n")
    doc["arr"][::2] = [9, 8]
    assert list(doc["arr"]) == [9, 2, 8, 4]
    assert parse(doc.dumps()).to_dict()["arr"] == [9, 2, 8, 4]


# -- datetime conversion never leaks private node types ---------------------- #


def test_leap_second_datetime_converts_to_stdlib_type() -> None:
    doc = parse("at = 2024-06-30T23:59:60Z\n")
    value = doc.to_dict()["at"]
    assert type(value) is dt.datetime
    assert (value.hour, value.minute, value.second) == (23, 59, 59)
    plain = loads("at = 2024-06-30T23:59:60Z\n")["at"]
    assert type(plain) is dt.datetime


def test_odd_fraction_width_time_converts_to_stdlib_type() -> None:
    value = loads("t = 07:32:00.1\n")["t"]
    assert type(value) is dt.time
    assert value.microsecond == 100000


def test_lowercase_separator_datetime_converts_to_stdlib_type() -> None:
    value = loads("a = 1979-05-27t07:32:00z\n")["a"]
    assert type(value) is dt.datetime
    assert value.tzinfo is not None


# -- deleting a table kills its nested array-of-tables blocks ---------------- #


def test_delete_table_removes_nested_aot_blocks() -> None:
    doc = parse("[a]\nx = 1  # ax\n\n[[a.items]]\nn = 1  # first\n")
    del doc["a"]
    assert doc.dumps() == ""
    assert doc.to_dict() == {}


def test_replace_table_with_scalar_removes_nested_aot_blocks() -> None:
    doc = parse("[a]\nx = 1\n\n[[a.items]]\nn = 1\n")
    doc["a"] = 5
    out = doc.dumps()
    assert parse(out).to_dict() == {"a": 5}
