"""
Robustness properties: hostile input and wide value spaces.

- malformed input raises only :class:`TOMLParseError` — never an internal error
- valid documents round-trip byte-exactly across the full TOML value space
  (unicode keys/values, dotted/quoted keys, arrays of tables, inline tables,
  datetimes, nan/inf, int64 limits), agreeing with :mod:`tomllib` on semantics
- mixed line endings survive untouched; assigned CR never leaks as a raw byte
- truncated documents fail with :class:`TOMLParseError` at every cut point
- large documents stay byte-exact; nesting behaves at its documented boundary
- arbitrary edit sequences keep memory and rendered output semantically equal
"""

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tomlclass
from tests._compat import tomllib
from tomlclass import Document
from tomlclass.errors import TOMLParseError

# -- helpers ------------------------------------------------------------------- #

_CTRL = "".join(chr(c) for c in (0, 1, 0x08, 0x0B, 0x0C, 0x1F, 0x7F))
_NAN = ("__nan__",)


def _norm(value):
    """NaN-insensitive deep equality wrapper (nan != nan would break dict ==)."""
    if isinstance(value, float) and math.isnan(value):
        return _NAN
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


def _assert_only_parse_error(text, version="1.1"):
    try:
        doc = tomlclass.parse(text, toml_version=version)
    except TOMLParseError:
        return
    assert isinstance(doc, Document)


# -- 1. malformed input only ever raises TOMLParseError ------------------------ #

_TOML_METACHARS = "=[]{}\"'\\\n\r\t #.,:+-0123456789abcdefntxzuiUT"
_UNI_POOL = "αβγ漢字\U0001f389é́" + _CTRL

_GKEY = st.sampled_from(["a", "b.c", '"q k"', "'l'", "a.b-c", '"a.b"', "0", "-", "a."])
_GVAL = st.sampled_from(
    [
        "1",
        "0x1F",
        "1.5e10",
        "nan",
        "+inf",
        "-inf",
        "true",
        "false",
        '"s"',
        "'l'",
        '"""ml"""',
        "'''ml'''",
        '""',
        "''",
        '"\\u00e9"',
        '"\\U0001F600"',
        '"\\x41"',
        '"\\e"',
        '"\\',
        "[]",
        "[1,2]",
        "[1,]",
        "[[1],[2]]",
        "{}",
        "{a=1}",
        "{ a = 1, }",
        "[{a=1},{b=2}]",
        "1979-05-27T07:32:00Z",
        "1979-05-27T07:32:00",
        "1979-05-27",
        "07:32:00",
        "07:32",
        "00:00:60",
        "9223372036854775807",
        "99999999999999999999999",
        "0x",
        "0b2",
        "1.",
        ".1",
        "1e",
        "1e+308",
        "1e309",
        "tru",
        "[1 2]",
        "{a=1,}",
        ",",
        "=",
        "1979-13-45",
        "99:99:99",
        "[[[",
        "}}",
        "1 2",
    ]
)
_GLINE = st.one_of(
    st.builds(lambda k, v: f"{k} = {v}", _GKEY, _GVAL),
    st.builds(lambda k, v: f"[{k}]\n{k} = {v}", _GKEY, _GVAL),
    st.builds(lambda k: f"[[{k}]]", _GKEY),
    st.builds(lambda k: f"[{k}]", _GKEY),
    st.just("# comment"),
    st.just(""),
    st.builds(lambda v: f"k = {v} # c", _GVAL),
)
_GRAMMAR_DOC = st.lists(_GLINE, max_size=10).map("\n".join)


def test_ascii_soup_parses_or_raises_parse_error():
    @settings(max_examples=200, deadline=None)
    @given(st.text(alphabet=_TOML_METACHARS, max_size=120))
    def run(text):
        _assert_only_parse_error(text)

    run()


def test_unicode_soup_parses_or_raises_parse_error():
    @settings(max_examples=200, deadline=None)
    @given(st.text(alphabet=_TOML_METACHARS + _UNI_POOL, max_size=120))
    def run(text):
        _assert_only_parse_error(text)

    run()


@settings(max_examples=200, deadline=None)
@given(st.text(max_size=150))
def test_arbitrary_text_parses_or_raises_parse_error(text):
    _assert_only_parse_error(text)


def test_grammar_fragments_parses_or_raises_parse_error_in_both_versions():
    @settings(max_examples=200, deadline=None)
    @given(_GRAMMAR_DOC)
    def run(text):
        _assert_only_parse_error(text)
        _assert_only_parse_error(text, version="1.0")

    run()


@settings(max_examples=150, deadline=None)
@given(st.text(alphabet="\r\n", max_size=60))
def test_newline_soup_between_statements(gaps):
    _assert_only_parse_error("k = 1" + gaps + "[a]" + gaps + "x = 'y'" + gaps)


# -- 2. wide value space round-trips byte-exactly ------------------------------- #

_BARE_KEY = st.from_regex(r"[A-Za-z0-9_-]+", fullmatch=True)
_UNI_KEY = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, exclude_categories=("Cs", "Cc", "Cf")),
    min_size=1,
    max_size=6,
)


def _quoted_key(s):
    out = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ord(ch) < 0x20 or ord(ch) == "\x7f":
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


# (rendered text, semantic key value) — dedup must use the semantic value
_KEY = st.one_of(
    st.builds(lambda k: (k, k), _BARE_KEY),
    _UNI_KEY.map(lambda s: (_quoted_key(s), s)),
    st.builds(lambda a, b: (_quoted_key(a + "." + b), a + "." + b), _UNI_KEY, _UNI_KEY),
)

_INT_TEXT = st.one_of(
    st.integers(min_value=-(2**63), max_value=2**63 - 1).map(str),
    st.integers(min_value=0, max_value=2**63 - 1).map(lambda v: f"0x{v:X}"),
    st.integers(min_value=0, max_value=2**63 - 1).map(lambda v: f"0o{v:o}"),
    st.integers(min_value=0, max_value=2**63 - 1).map(lambda v: f"0b{v:b}"),
)
_FLOAT_TEXT = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, allow_subnormal=False).map(repr),
    st.sampled_from(["nan", "+nan", "-nan", "inf", "+inf", "-inf"]),
    st.from_regex(r"[+-]?(0|[1-9](_?[0-9])*)\.[0-9](_?[0-9])*(e[+-]?[0-9](_?[0-9])*)?", fullmatch=True),
)
_DATE_TEXT = st.builds(
    lambda y, m, d: f"{y}-{m}-{d}",
    st.integers(min_value=1, max_value=9999).map(lambda v: f"{v:04d}"),
    st.sampled_from(["01", "02", "04", "06", "07", "12"]),
    st.sampled_from(["01", "10", "28"]),
)
_TIME_TEXT = st.builds(
    lambda h, m, s, f: f"{h}:{m}:{s}{f}",
    st.sampled_from(["00", "07", "23"]),
    st.sampled_from(["00", "32", "59"]),
    st.sampled_from(["00", "45", "59"]),
    st.sampled_from(["", ".5", ".123456789012"]),
)
_DT_TEXT = st.one_of(
    _DATE_TEXT,
    _TIME_TEXT,
    st.builds(
        lambda d, sep, t, tz: d + sep + t + tz,
        _DATE_TEXT,
        st.sampled_from(["T", "t", " "]),
        _TIME_TEXT,
        st.sampled_from(["", "Z", "z", "+00:00", "-07:30", "+23:59"]),
    ),
)
_STR_TEXT = st.one_of(
    st.text(st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, exclude_categories=("Cs", "Cc")), max_size=8).map(
        lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    ),
    st.text(alphabet="ab\t", max_size=6).map(lambda s: "'" + s + "'"),
    st.sampled_from(['""', "''", '"\\t\\n\\r\\\\\\""', '"\\u00e9"', '"\\U0001F600"', '"\\uD7FF"', '"\\uE000"']),
)
_ML_STR_TEXT = st.sampled_from(
    [
        '"""\nline1\nline2\n"""',
        "'''\nraw\\n\n'''",
        '"""\ncont\\\ninue\n"""',
        '"""a"""',
        "'''b'''",
        '"""\n"""',
        "'''\n'''",
    ]
)
_V11_STR_TEXT = st.sampled_from(['"\\x41"', '"\\x7f"', '"\\e[0m"'])


def _value_text(depth, *, multiline_ok, v11):
    scalars = [_INT_TEXT, _FLOAT_TEXT, st.sampled_from(["true", "false"]), _DT_TEXT, _STR_TEXT]
    if v11:
        scalars.append(_V11_STR_TEXT)
    scalar = st.one_of(*scalars)
    if multiline_ok:
        scalar = st.one_of(scalar, _ML_STR_TEXT)

    def array_of(inner):
        return st.lists(inner, max_size=3).map(
            lambda v: ("[\n  " + ",\n  ".join(v) + ",\n]") if len(v) > 2 else "[" + ", ".join(v) + "]"
        )

    if depth <= 0:
        return st.one_of(scalar, array_of(scalar))
    nested = _value_text(depth - 1, multiline_ok=multiline_ok, v11=v11)
    inline = st.lists(
        st.tuples(_KEY, _value_text(depth - 1, multiline_ok=False, v11=v11)),
        max_size=3,
        unique_by=lambda kv: kv[0][1],
    ).map(lambda kvs: "{ " + ", ".join(f"{k[0]} = {v}" for k, v in kvs) + " }")
    return st.one_of(scalar, array_of(nested), inline)


@st.composite
def _document(draw, v11=False):
    value = _value_text(3, multiline_ok=True, v11=v11)
    lines = []

    def unique_keys(count):
        seen, texts = set(), []
        while len(texts) < count:
            text, semantic = draw(_KEY)
            if semantic not in seen:
                seen.add(semantic)
                texts.append(text)
        return texts

    def emit_aot(path):
        for _ in range(draw(st.integers(min_value=1, max_value=3))):
            lines.append("[[" + ".".join(path) + "]]")
            lines.extend(f"{k} = {draw(value)}" for k in unique_keys(draw(st.integers(min_value=0, max_value=3))))

    def emit_tree(path, depth):
        n_scalars = draw(st.integers(min_value=0, max_value=4))
        n_dotted = draw(st.integers(min_value=0, max_value=2 if depth < 2 else 0))
        n_subs = draw(st.integers(min_value=0, max_value=2 if depth < 2 else 0))
        n_aots = draw(st.integers(min_value=0, max_value=2 if depth < 2 else 0))
        keys = unique_keys(n_scalars + n_subs + n_aots + 3 * n_dotted)
        idx = 0
        body_start = len(lines)
        for _ in range(n_dotted):
            p1, p2, leaf = keys[idx], keys[idx + 1], keys[idx + 2]
            idx += 3
            lines.append(f"{p1}.{p2}.{leaf} = {draw(value)}")
        for _ in range(n_scalars):
            lines.append(f"{keys[idx]} = {draw(value)}")
            idx += 1
        if path:
            lines.insert(body_start, "[" + ".".join(path) + "]")
        for _ in range(n_subs):
            emit_tree([*path, keys[idx]], depth + 1)
            idx += 1
        for _ in range(n_aots):
            emit_aot([*path, keys[idx]])
            idx += 1

    n_scalars = draw(st.integers(min_value=0, max_value=4))
    n_dotted = draw(st.integers(min_value=0, max_value=2))
    n_subs = draw(st.integers(min_value=0, max_value=3))
    n_aots = draw(st.integers(min_value=0, max_value=2))
    keys = unique_keys(n_scalars + n_subs + n_aots + 3 * n_dotted)
    idx = 0
    for _ in range(n_dotted):
        p1, p2, leaf = keys[idx], keys[idx + 1], keys[idx + 2]
        idx += 3
        lines.append(f"{p1}.{p2}.{leaf} = {draw(value)}")
    for _ in range(n_scalars):
        lines.append(f"{keys[idx]} = {draw(value)}")
        idx += 1
    for _ in range(n_subs):
        emit_tree([keys[idx]], 1)
        idx += 1
    for _ in range(n_aots):
        emit_aot([keys[idx]])
        idx += 1

    rendered = []
    for line in lines:
        rendered.append(line)
        if draw(st.sampled_from([0, 0, 0, 1, 2])) == 1:
            rendered.append("# c")
        elif draw(st.sampled_from([0, 0, 1])) == 1:
            rendered.append("")
    return "\n".join(rendered) + "\n"


def _check_roundtrip(text, oracle):
    if oracle:
        expected = tomllib.loads(text)  # the generator must produce valid TOML 1.0
        assert _norm(tomlclass.loads(text)) == _norm(expected), text
    doc = tomlclass.parse(text)
    first = doc.dumps()
    assert first == text, f"round-trip not byte-exact: {text!r} -> {first!r}"
    reparsed = tomlclass.parse(first)
    assert reparsed.dumps() == first  # rendering is idempotent
    assert _norm(reparsed.to_dict()) == _norm(doc.to_dict())


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.data_too_large])
@given(_document(v11=False))
def test_core_documents_match_tomllib_and_round_trip(text):
    _check_roundtrip(text, oracle=True)


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.data_too_large])
@given(_document(v11=True))
def test_version_11_documents_round_trip(text):
    _check_roundtrip(text, oracle=False)


# -- 3. mixed line endings ------------------------------------------------------ #

_EOL_LINES = [
    "a = 1",
    'b = "two"',
    "[t]",
    "x = [1, 2, 3]  # keep",
    "y = { z = 4 }",
    "[[items]]",
    "n = 1",
    "s = '''",
    "raw text",
    "'''",
    'e = "esc\\t"',
]


@st.composite
def _mixed_ending_doc(draw):
    lines = draw(st.lists(st.sampled_from(_EOL_LINES), min_size=2, max_size=8))
    endings = draw(
        st.lists(st.sampled_from(["\n", "\r\n"]), min_size=len(lines), max_size=len(lines)).filter(
            lambda es: "\n" in es and "\r\n" in es
        )
    )
    return "".join(line + e for line, e in zip(lines, endings, strict=True))


@settings(max_examples=100, deadline=None)
@given(_mixed_ending_doc())
def test_mixed_ending_document_round_trips_byte_exactly(text):
    assert "\n" in text and "\r\n" in text  # genuinely mixed line endings
    try:
        doc = tomlclass.parse(text)  # the line salad can be structurally invalid
    except TOMLParseError:
        return
    assert doc.dumps() == text


@settings(max_examples=100, deadline=None)
@given(_mixed_ending_doc(), st.sampled_from(["a\rb", "x\r\ny", "\r", "line1\r\nline2"]))
def test_edited_document_never_contains_bare_carriage_return(text, cr_value):
    try:
        doc = tomlclass.parse(text)
    except TOMLParseError:
        return
    doc["assigned"] = cr_value
    out = doc.dumps()
    assert "\r" not in out.replace("\r\n", ""), f"raw CR leaked: {out!r}"
    back = tomlclass.parse(out)
    assert back["assigned"] == cr_value  # CR survives as an escape
    assert back.dumps() == out


# -- 4. truncation and mutation ---------------------------------------------------- #

_SEED_DOCS = [
    'a = 1\nb = "two"\n\n[t]\nx = [1, 2, 3]  # c\ny = { z = 4, w = [5, { q = 6 }] }\n',
    '[[items]]\nname = "x"\ntags = ["a", "b"]\n\n[[items]]\nname = "y"\n',
    "s = '''\nml\r\nlines\n'''\nd = 1979-05-27T07:32:00Z\nf = nan\n",
    'a.b.c = 1\n"k.q" = { inner = { deep = [1, [2, [3]]] } }\n',
    "bin = 0b1010\nhex = 0xFF\nbig = 9223372036854775807\nt = 07:32:00.999\n",
    'esc = "a\\tb\\u00e9c\\U0001F600"\n',
]
_MUTATION_CHARS = "abz\"'\\#=[]{},.0123456789 \t\n\r+-.e"


def test_every_prefix_of_every_seed_document():
    for seed in _SEED_DOCS:
        for cut in range(len(seed) + 1):
            _assert_only_parse_error(seed[:cut])


@settings(max_examples=150, deadline=None)
@given(st.sampled_from(_SEED_DOCS), st.integers(min_value=0, max_value=250), st.integers(min_value=0, max_value=2))
def test_truncated_document_tail_variants(seed, cut, tail_mode):
    truncated = seed[:cut]
    mutated = {0: truncated, 1: truncated + truncated[-1:], 2: truncated + "="}[tail_mode]
    _assert_only_parse_error(mutated)


@settings(max_examples=150, deadline=None)
@given(
    st.sampled_from(_SEED_DOCS),
    st.integers(min_value=0, max_value=180),
    st.sampled_from(_MUTATION_CHARS),
    st.integers(min_value=0, max_value=2),
)
def test_single_byte_mutation(seed, pos, ch, mode):
    if mode == 0:  # replace
        mutated = seed[:pos] + ch + seed[pos + 1 :]
    elif mode == 1:  # insert
        mutated = seed[:pos] + ch + seed[pos:]
    else:  # delete
        mutated = seed[:pos] + seed[pos + 1 :]
    _assert_only_parse_error(mutated)


# -- 5. large documents ------------------------------------------------------------ #


def test_many_tables_round_trip_and_edit():
    parts = []
    for table in range(500):
        parts.append(f"[table_{table}]")
        parts.extend(f"key_{k} = {table * 10 + k}  # comment {k}" for k in range(10))
    text = "\n".join(parts) + "\n"
    doc = tomlclass.parse(text)
    assert doc.dumps() == text
    doc["table_250"]["key_5"] = 999
    back = tomlclass.parse(doc.dumps())
    assert back["table_250"]["key_5"] == 999
    assert back["table_0"]["key_0"] == 0


def test_many_root_keys_round_trip():
    text = "\n".join(f"k{i} = {i}" for i in range(2000)) + "\n"
    doc = tomlclass.parse(text)
    assert doc.dumps() == text


def test_large_array_round_trip_and_append():
    text = "big = [\n" + "\n".join(f"  {i},  # elem {i}" for i in range(5000)) + "\n]\n"
    doc = tomlclass.parse(text)
    assert doc.dumps() == text
    doc["big"].append(99999)
    back = tomlclass.parse(doc.dumps())
    assert len(back["big"]) == 5001 and back["big"][-1] == 99999


def test_many_array_of_tables_blocks_round_trip():
    text = "".join(f"[[e]]\nn = {i}\nx = 'v{i}'\n" for i in range(1000))
    doc = tomlclass.parse(text)
    assert doc.dumps() == text


# -- 6. nesting boundary ------------------------------------------------------------ #


def test_value_nesting_just_under_cap_round_trips():
    for depth in (1, 50, 150, 199):
        text = "a = " + "[" * depth + "1" + "]" * depth + "\n"
        doc = tomlclass.parse(text)
        assert doc.dumps() == text
        value = doc["a"]
        for _ in range(depth):
            value = value[0]
        assert value == 1


@pytest.mark.parametrize("depth", [200, 201, 400])
def test_value_nesting_at_and_over_cap_is_a_parse_error(depth):
    text = "a = " + "[" * depth + "1" + "]" * depth + "\n"
    with pytest.raises(TOMLParseError):
        tomlclass.parse(text)


def test_deep_header_path_over_cap_is_a_parse_error():
    header = ".".join(f"k{i}" for i in range(300))
    with pytest.raises(TOMLParseError, match="nesting depth"):
        tomlclass.parse(f"[{header}]\nx = 1\n")


def test_deep_dotted_key_over_cap_is_a_parse_error():
    dotted = ".".join(f"k{i}" for i in range(300))
    with pytest.raises(TOMLParseError, match="nesting depth"):
        tomlclass.parse(f"{dotted} = 1\n")


def test_deep_python_value_assignment_renders():
    value = 1
    for _ in range(150):
        value = [value]
    doc = tomlclass.document()
    doc["k"] = value
    back = tomlclass.parse(doc.dumps())
    assert back.to_dict() == {"k": value}


def test_moderately_nested_inline_tables_parse():
    text = "a = " + "{ x = " * 50 + "1" + " }" * 50 + "\n"
    doc = tomlclass.parse(text)
    assert doc.dumps() == text


# -- 7. array slice operations with re-iterable values ------------------------------ #


def test_slice_assignment_with_list_round_trips():
    doc = tomlclass.parse("a = [1, 2, 3]\n")
    doc["a"][0:2] = [10, 20, 30]
    assert tomlclass.parse(doc.dumps()).to_dict() == {"a": [10, 20, 30, 3]}


def test_extended_slice_assignment_round_trips():
    doc = tomlclass.parse("a = [1, 2, 3]\n")
    doc["a"][::2] = [9, 9]
    assert tomlclass.parse(doc.dumps()).to_dict() == {"a": [9, 2, 9]}


def test_slice_deletion_round_trips():
    doc = tomlclass.parse("a = [1, 2, 3]\n")
    del doc["a"][0:2]
    assert tomlclass.parse(doc.dumps()).to_dict() == {"a": [3]}


def test_slice_growth_beyond_current_length():
    doc = tomlclass.parse("a = [1, 2, 3]\n")
    doc["a"][5:8] = [1, 2]
    assert tomlclass.parse(doc.dumps()).to_dict() == {"a": [1, 2, 3, 1, 2]}


def test_appended_element_can_be_edited_afterwards():
    doc = tomlclass.parse("a = [1, 2]  # c\n")
    arr = doc["a"]
    arr.append(9)
    arr[-1] = 99
    arr[0] = 100
    assert tomlclass.parse(doc.dumps()).to_dict()["a"] == [100, 2, 99]


# -- 8. arbitrary edit sequences keep memory and output equal ----------------------- #

_OP_KEYS = st.sampled_from(["alpha", "beta", "gamma", "delta", "eps"])
_OP_SCALARS = st.one_of(
    st.integers(min_value=-(2**63), max_value=2**63 - 1),
    st.floats(allow_nan=True, allow_infinity=True, allow_subnormal=False),
    st.booleans(),
    st.text(st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, exclude_categories=("Cs", "Cc")), max_size=10),
    st.sampled_from([float("nan"), float("inf"), -float("inf")]),
)
_OP_LISTS = st.lists(st.one_of(st.integers(-1000, 1000), st.text(max_size=5)), max_size=5)
_BASE_DOCS = st.sampled_from(
    [
        'a = 1\nb = "two"\n\n[t]\nx = [1, 2, 3]  # comment\ny = { z = 4 }\n',
        "[[items]]\nn = 1\n[[items]]\nn = 2\n\ntail = true\n",
        'k = [10, 20]\n\n# lead\n[deep.sub]\nv = "s"\narr = [[1, 2], [3, 4]]\n',
        "a.b.c = 1\na.b.d = 2\nplain = 0\n",
        "",
    ]
)
_OPS = st.lists(st.tuples(st.integers(0, 13), _OP_KEYS, _OP_SCALARS, _OP_LISTS), min_size=1, max_size=12)


def _apply_op(doc, choice, key, value, list_value):
    if choice == 0:
        doc[key] = value
    elif choice == 1:
        doc.setdefault(key, value)
    elif choice == 2:
        if key in doc:
            del doc[key]
    elif choice == 3:
        doc.pop(key, None)
    elif choice in (4, 5, 6, 7):
        arr = doc.get("k")
        if isinstance(arr, tomlclass.Array) and not isinstance(arr, tomlclass.ArrayOfTables):
            if choice == 4:
                arr.append(value)
            elif choice == 5:
                arr.extend(list_value)
            elif choice == 6 and arr:
                arr.pop()
            elif choice == 7 and arr:
                arr[abs(hash(key)) % len(arr)] = value
    elif choice == 8:
        if "t" in doc and isinstance(doc["t"], tomlclass.Table):
            doc["t"][key] = value
        else:
            doc[key] = value
    elif choice == 9:
        doc.set_path("deep.made.up", value)
    elif choice == 10:
        doc.add(tomlclass.comment("note " + str(key)))
    elif choice == 11:
        items = doc.get("items")
        if isinstance(items, tomlclass.ArrayOfTables):
            items.append({"n": abs(hash(key)) % 100})
    elif choice == 12:
        if "k" in doc and isinstance(doc["k"], tomlclass.Array):
            doc["k"] = list_value
    elif choice == 13 and key in doc and isinstance(doc[key], tomlclass.Array) and doc[key]:
        del doc[key][0]


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.data_too_large])
@given(_BASE_DOCS, _OPS)
def test_after_every_edit_output_reparses_to_the_same_values(base, ops):
    doc = tomlclass.parse(base)
    for choice, key, value, list_value in ops:
        _apply_op(doc, choice, key, value, list_value)
        out = doc.dumps()
        reparsed = tomlclass.parse(out)
        assert _norm(reparsed.to_dict()) == _norm(doc.to_dict()), (
            f"memory/output divergence after op {choice}:\nbase={base!r}\nout={out!r}"
        )
        assert tomlclass.parse(reparsed.dumps()).dumps() == out  # idempotent render
