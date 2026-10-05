"""
tomllib 标准调用兼容 + 注释参数化 API。
"""

import io

import pytest

import tomlclass


class TestTomllibCompat:
    def test_loads_returns_plain_dict(self):
        data = tomlclass.loads('a = 1\n[t]\nb = "x"\n')
        assert data == {"a": 1, "t": {"b": "x"}}
        assert type(data) is dict

    def test_load_binary_file_object(self):
        bio = io.BytesIO(b"a = 2\n")
        data = tomlclass.load(bio)
        assert data == {"a": 2}
        assert type(data) is dict

    def test_load_path_returns_document(self, tmp_path):
        src = tmp_path / "x.toml"
        src.write_text("a = 1\n", encoding="utf-8")
        doc = tomlclass.load(src)
        assert isinstance(doc, tomlclass.Document)
        assert doc.dumps() == "a = 1\n"


class TestCommentApi:
    def test_comment_roundtrip(self):
        doc = tomlclass.parse("a = 1  # hi\n")
        assert doc.comment("a") == "hi"
        doc.set_comment("a", "changed")
        assert doc.comment("a") == "changed"
        assert doc.dumps() == "a = 1  # changed\n"  # 替换沿用原有前导空白

    def test_comment_injection_without_original(self):
        doc = tomlclass.parse("a = 1\n")
        doc.set_comment("a", "note")
        assert doc.comment("a") == "note"
        assert doc.dumps() == "a = 1  # note\n"

    def test_comment_removal(self):
        doc = tomlclass.parse("a = 1  # hi\n")
        doc.set_comment("a", None)
        assert doc.comment("a") is None
        assert doc.dumps() == "a = 1\n"  # 删除注释时连同其前导空白一并清除，无孤儿尾随空格

    def test_set_comment_on_missing_key(self):
        doc = tomlclass.parse("a = 1\n")
        with pytest.raises(KeyError):
            doc.set_comment("nope", "x")

    def test_find_and_to_dict(self):
        doc = tomlclass.parse("[a.b]\nc = 1\nz = 's'\n")
        assert doc.find("a.b.c") == 1
        assert doc.find("a.b.nope") is None
        assert doc.to_dict() == {"a": {"b": {"c": 1, "z": "s"}}}
