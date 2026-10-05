"""
Edit semantics: dirty splicing, pending entries, deletion, AoT.
"""

import tomlclass


def test_edit_existing_value_keeps_comment():
    source = 'port = 8000  # the port\n'
    doc = tomlclass.parse(source)
    doc["port"] = 9000
    assert doc.dumps() == 'port = 9000  # the port\n'


def test_edit_keeps_key_formatting():
    source = '"quoted key"   =    1\n'
    doc = tomlclass.parse(source)
    doc["quoted key"] = 2
    assert doc.dumps() == '"quoted key"   =    2\n'


def test_new_key_appended_after_last_entry():
    source = "a = 1\nb = 2\n"
    doc = tomlclass.parse(source)
    doc["c"] = 3
    assert doc.dumps() == "a = 1\nb = 2\nc = 3\n"


def test_new_nested_table_block():
    source = "top = 1\n"
    doc = tomlclass.parse(source)
    doc["server"] = {"host": "h", "port": 9}
    assert doc.dumps() == "top = 1\n\n[server]\nhost = \"h\"\nport = 9\n"


def test_assign_into_existing_header_table():
    source = "[server]\nhost = 'h'\n"
    doc = tomlclass.parse(source)
    doc["server"]["port"] = 9
    assert doc.dumps() == "[server]\nhost = 'h'\nport = 9\n"


def test_dotted_key_edit_splices_line():
    source = "a.b = 1\n"
    doc = tomlclass.parse(source)
    doc["a"]["b"] = 2
    assert doc.dumps() == "a.b = 2\n"


def test_dotted_table_new_key_renders_dotted():
    source = "a.b = 1\nz = 9\n"
    doc = tomlclass.parse(source)
    doc["a"]["c"] = 2
    assert doc.dumps() == "a.b = 1\na.c = 2\nz = 9\n"


def test_delete_entry():
    source = "a = 1\nb = 2\nc = 3\n"
    doc = tomlclass.parse(source)
    del doc["b"]
    assert doc.dumps() == "a = 1\nc = 3\n"


def test_delete_whole_table():
    source = "keep = 1\n\n[t]\nx = 1\ny = 2\n"
    doc = tomlclass.parse(source)
    del doc["t"]
    assert doc.dumps() == "keep = 1\n\n"


def test_array_append_splices_in_place():
    # 干净数组的 append 走源切片拼接：既有元素的多余空格逐字节保留
    source = "arr = [ 1,   2,  3 ]\n"
    doc = tomlclass.parse(source)
    doc["arr"].append(4)
    assert doc.dumps() == "arr = [ 1,   2,  3, 4 ]\n"


def test_array_assignment_renders_canonically():
    # 整体赋值走规范渲染
    source = "arr = [ 1,   2,  3 ]\n"
    doc = tomlclass.parse(source)
    doc["arr"] = [1, 2, 3, 4]
    assert doc.dumps() == "arr = [1, 2, 3, 4]\n"


def test_aot_whole_replace_engine(tmp_path):
    # 引擎层整体替换：旧元素不再渲染，新元素以块渲染且可读
    source = "[[items]]\nname = 'a'\nprice = 1\n"
    doc = tomlclass.parse(source)
    doc["items"] = [{"name": "b"}, {"name": "c"}]
    rendered = doc.dumps()
    assert rendered.count("[[items]]") == 2
    assert 'name = "b"' in rendered and 'name = "c"' in rendered
    assert "name = 'a'" not in rendered
    assert doc["items"][0]["name"] == "b"  # 读取同步


def test_aot_append_renders_new_block():
    source = "[[items]]\nname = 'a'\n"
    doc = tomlclass.parse(source)
    doc["items"].append({"name": "b"})
    assert doc.dumps() == "[[items]]\nname = 'a'\n[[items]]\nname = \"b\"\n"


def test_inline_table_closed():
    source = "t = { x = 1 }\n"
    doc = tomlclass.parse(source)
    try:
        doc["t"]["y"] = 2
        raise AssertionError("expected TOMLTypeError")
    except tomlclass.TOMLTypeError:
        pass
    assert doc.dumps() == "t = { x = 1 }\n"


def test_none_assignment_raises():
    doc = tomlclass.parse("a = 1\n")
    try:
        doc["a"] = None
        raise AssertionError("expected TOMLTypeError")
    except tomlclass.TOMLTypeError:
        pass


def test_atomic_save(tmp_path):
    target = tmp_path / "out.toml"
    doc = tomlclass.parse("a = 1\n")
    doc.save(target)
    assert target.read_text(encoding="utf-8") == "a = 1\n"
    doc["a"] = 2
    doc.save(str(target))
    assert target.read_text(encoding="utf-8") == "a = 2\n"
    assert list(tmp_path.iterdir()) == [target]  # no temp leftovers


def test_parse_error_positions():
    try:
        tomlclass.parse("a = 1\nb =\n")
        raise AssertionError("expected TOMLParseError")
    except tomlclass.TOMLParseError as e:
        assert e.line == 2
        assert e.col == 4
        assert isinstance(e, ValueError)
