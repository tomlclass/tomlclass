"""
Round-trip axiom tests: parse -> dumps must be byte-identical.
"""

import pytest

import tomlclass

STYLE_MATRIX = {
    "hex_int": "a = 0xDEAD_beef\n",
    "oct_int": "a = 0o755\n",
    "bin_int": "a = 0b1010_1010\n",
    "underscore_int": "a = 1_000_000\n",
    "negative": "a = -17\n",
    "float_styles": "a = 1.0e6\nb = -0.5\n",
    "float_inf_nan": "a = inf\nb = -inf\nc = nan\n",
    "literal_string": "a = 'C:\\path\\no\\escapes'\n",
    "multiline_basic": 'a = """\nline1\nline2"""\n',
    "multiline_literal": "a = '''\nraw \nlines'''\n",
    "multiline_escapes": 'a = """\nno break \\\n    here"""\n',
    "inline_table": "a = { x = 1, y = 'z' }\n",
    "array_styles": "a = [\n    1,   # first\n    2,   # second\n]\n",
    "aot": "[[products]]\nname = 'a'\n\n[[products]]\nname = 'b'\n",
    "dotted_keys": "a.b.c = 1\na.b.d = 'x'\n",
    "quoted_keys": '"quoted key" = 1\n\'literal key\' = 2\n',
    "table_comments": "# header comment\n[t]  # trailing\nk = 1  # value comment\n",
    "crlf": "a = 1\r\nb = 2\r\n",
    "datetimes": "odt = 1979-05-27T07:32:00Z\nldt = 1979-05-27 07:32:00\nd = 1979-05-27\nt = 07:32:00.999\n",
    "leap_second": "a = 1990-12-31T23:59:60Z\n",
    "deep_nesting": "[a.b.c]\nd.e.f = true\n",
}


def test_style_matrix_roundtrip():
    for name, source in STYLE_MATRIX.items():
        doc = tomlclass.parse(source)
        assert doc.dumps() == source, f"round-trip failed for {name}"


def test_empty_document():
    assert tomlclass.parse("").dumps() == ""


def test_whitespace_only():
    source = "\n\n  \n# only a comment\n"
    assert tomlclass.parse(source).dumps() == source


def test_semantic_access():
    doc = tomlclass.parse(STYLE_MATRIX["hex_int"])
    assert doc["a"] == 0xDEADbeef
    doc2 = tomlclass.parse(STYLE_MATRIX["multiline_basic"])
    assert doc2["a"] == "line1\nline2"
    doc3 = tomlclass.parse(STYLE_MATRIX["leap_second"])
    assert doc3["a"].year == 1990


def test_multiline_quote_boundaries():
    # AI 评审 P0-3：""""""（6）与更多引号的经典边界——语义值 + 往返双断言
    quote = '"'
    newline = "\n"
    cases = {
        6: "",        # """ + 空 + """
        7: '"',       # """ + " + """
        8: '""',      # """ + "" + """
    }
    for k, expected in cases.items():
        source = "a = " + quote * k + newline
        doc = tomlclass.parse(source)
        assert doc["a"] == expected, f"quotes={k}: {doc['a']!r} != {expected!r}"
        assert doc.dumps() == source, f"quotes={k}: round-trip broken"
    # k=9：body 连续 3 个引号超出 ABNF（mlb-quotes 最多 2 个）→ 正确拒绝
    with pytest.raises(tomlclass.TOMLParseError):
        tomlclass.parse("a = " + quote * 9 + newline)


def test_delete_with_leading_comment_line():
    # AI 评审 P1：删键时整行注释留在原位（含其后空行的实测语义）
    source = "# comment for a\na = 1\nb = 2\n"
    doc = tomlclass.parse(source)
    del doc["a"]
    assert doc.dumps() == "# comment for a\nb = 2\n"
