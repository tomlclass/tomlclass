"""
Regression tests for the 0.2.1 fixes.

- root-level pending keys no longer land inside the last table (P0)
- Field(coerce=True) conversions reach the instance
- template() emits type-correct placeholders for required non-str fields
- non-str mapping keys no longer crash format_key
"""


import tomlclass
from tests._compat import tomllib
from tomlclass import Config, Field


def test_root_key_not_swallowed_by_last_table(tmp_path):
    target = tmp_path / "pyproject.toml"
    target.write_bytes(b"[tool.black]\nline-length = 88\n")
    doc = tomlclass.update(target, {"project_name": "demo"})
    text = target.read_text(encoding="utf-8")
    assert text == 'project_name = "demo"\n[tool.black]\nline-length = 88\n'
    assert tomllib.loads(text) == {"project_name": "demo", "tool": {"black": {"line-length": 88}}}
    assert doc.dumps() == text  # dumps is idempotent


def test_root_aot_last_still_root_level(tmp_path):
    target = tmp_path / "items.toml"
    target.write_text('[[items]]\nname = "a"\n', encoding="utf-8")
    tomlclass.update(target, {"root_key": 1})
    assert target.read_text(encoding="utf-8").startswith("root_key = 1\n")


def test_root_nested_table_after_header_only_file(tmp_path):
    target = tmp_path / "app.toml"
    target.write_bytes(b"[tool.black]\nline-length = 88\n")
    tomlclass.update(target, {"cache.dir": "/tmp"})
    text = target.read_text(encoding="utf-8")
    assert tomllib.loads(text) == {"tool": {"black": {"line-length": 88}}, "cache": {"dir": "/tmp"}}


def test_root_kv_anchor_still_wins(tmp_path):
    # when root already has kv lines, new keys follow the last root kv (existing behavior)
    target = tmp_path / "app.toml"
    target.write_text('name = "x"\n\n[server]\nhost = "h"\n', encoding="utf-8")
    tomlclass.update(target, {"extra": 1})
    text = target.read_text(encoding="utf-8")
    assert tomllib.loads(text) == {"name": "x", "extra": 1, "server": {"host": "h"}}


def test_coerce_reaches_instance(tmp_path):
    class Server(Config):
        port: int = Field(coerce=True)

    src = tmp_path / "c.toml"
    src.write_text('port = "8080"\n', encoding="utf-8")
    server = Server.load(src)
    assert server.port == 8080 and isinstance(server.port, int)
    assert server.port + 1 == 8081  # arithmetic works — the type violation is gone
    # diff semantics: the coerced value equals the file value, so save is a no-op
    server.save(src)
    assert src.read_text(encoding="utf-8") == 'port = "8080"\n'


def test_template_type_correct_placeholders():
    class Server(Config):
        """Server settings."""

        host: str
        port: int
        debug: bool
        ratio: float

    template = Server.template()
    data = tomllib.loads(template)
    assert data == {"host": "", "port": 0, "debug": False, "ratio": 0.0}
    tomlclass.loads(template)  # the template itself is valid TOML


def test_format_key_accepts_non_str():
    assert tomlclass.dumps({1: "x"}) == '1 = "x"\n'
    doc = tomlclass.parse("")
    doc["t"] = {2: "y"}  # nested non-str key through the engine
    assert '"t"' in doc.dumps() or "t" in doc.dumps()
