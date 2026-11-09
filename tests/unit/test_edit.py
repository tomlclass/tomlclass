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


def test_delete_keeps_next_entry_comment():
    # the standalone comment between two entries documents the FOLLOWING
    # entry; deleting the earlier entry must not eat it (only the blank-line
    # run around the deleted line goes)
    source = '[t]\n# above a\na = 1\n\n# above b\nb = 2\n'
    doc = tomlclass.parse(source)
    del doc["t"]["a"]
    assert doc.dumps() == '[t]\n# above a\n# above b\nb = 2\n'


def test_delete_last_entry_blank_run_goes():
    source = "a = 1\n\n# note\nb = 2\n\n"
    doc = tomlclass.parse(source)
    del doc["b"]
    assert doc.dumps() == "a = 1\n\n# note\n"


def test_delete_table_keeps_next_table_header_comment():
    source = "[a]\nx = 1\n\n# about b\n[b]\ny = 2\n"
    doc = tomlclass.parse(source)
    del doc["a"]
    assert doc.dumps() == "# about b\n[b]\ny = 2\n"


def test_delete_whole_table():
    source = "keep = 1\n\n[t]\nx = 1\ny = 2\n"
    doc = tomlclass.parse(source)
    del doc["t"]
    assert doc.dumps() == "keep = 1\n\n"


def test_array_append_splices_in_place():
    # clean-array append splices into the source: existing element spacing stays byte-exact
    source = "arr = [ 1,   2,  3 ]\n"
    doc = tomlclass.parse(source)
    doc["arr"].append(4)
    assert doc.dumps() == "arr = [ 1,   2,  3, 4 ]\n"


def test_array_assignment_renders_canonically():
    # whole assignment re-renders canonically
    source = "arr = [ 1,   2,  3 ]\n"
    doc = tomlclass.parse(source)
    doc["arr"] = [1, 2, 3, 4]
    assert doc.dumps() == "arr = [1, 2, 3, 4]\n"


def test_aot_whole_replace_engine(tmp_path):
    # engine-level whole replacement: old elements stop rendering, new ones render as blocks and stay readable
    source = "[[items]]\nname = 'a'\nprice = 1\n"
    doc = tomlclass.parse(source)
    doc["items"] = [{"name": "b"}, {"name": "c"}]
    rendered = doc.dumps()
    assert rendered.count("[[items]]") == 2
    assert 'name = "b"' in rendered and 'name = "c"' in rendered
    assert "name = 'a'" not in rendered
    assert doc["items"][0]["name"] == "b"  # reads are in sync


def test_aot_whole_replace_single_element_renders_exactly():
    # replacing the only element must render the replacement at the dead
    # element's position — no stray leading blank line, no lost content
    doc = tomlclass.parse('[[items]]\nname = "a"\n')
    doc["items"] = [{"name": "b"}]
    first = doc.dumps()
    assert first == '[[items]]\nname = "b"\n'
    assert doc.dumps() == first  # repeated dumps are idempotent


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


def test_atomic_write_durability(tmp_path, monkeypatch):
    """atomic_write_text fsyncs the file data (and the directory on POSIX) before replace"""
    import os

    from tomlclass._document import atomic_write_text

    target = tmp_path / "cfg.toml"
    fsynced_fds: list[int] = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (fsynced_fds.append(fd), real_fsync(fd))[1])

    atomic_write_text(target, "a = 1\n")

    assert target.read_text(encoding="utf-8") == "a = 1\n"
    assert list(tmp_path.iterdir()) == [target]  # no temp leftovers
    assert len(fsynced_fds) >= 1  # file data hit disk before replace
    if os.name == "posix":
        assert len(fsynced_fds) == 2  # directory fsync closes the power-loss gap


def test_atomic_write_cleanup_on_failure(tmp_path, monkeypatch):
    """a write failure removes the temp file and re-raises instead of clobbering the target"""
    import os

    from tomlclass._document import atomic_write_text

    target = tmp_path / "cfg.toml"
    target.write_text("keep = 1\n", encoding="utf-8")

    def broken_fdopen(fd, *args, **kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(os, "fdopen", broken_fdopen)
    try:
        atomic_write_text(target, "a = 1\n")
        raise AssertionError("expected OSError")
    except OSError:
        pass
    assert target.read_text(encoding="utf-8") == "keep = 1\n"  # target untouched
    assert list(tmp_path.iterdir()) == [target]  # temp cleaned up


def test_parse_error_positions():
    try:
        tomlclass.parse("a = 1\nb =\n")
        raise AssertionError("expected TOMLParseError")
    except tomlclass.TOMLParseError as e:
        assert e.line == 2
        assert e.col == 4
        assert isinstance(e, ValueError)
