"""
Annotation layer tests: template, validation, load/save diff semantics.
"""

from datetime import datetime

import pytest

import tomlclass
from tomlclass import Config, ConfigError, Field, ValidationError


class Server(Config):
    """
    HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    ssl_cert:
        Optional PEM certificate path.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    ssl_cert: str | None = None


class App(Config):
    """
    Application configuration.
    """

    name: str = Field("demo", description="Visible app name")
    debug: bool = False
    server: Server
    tags: list[str] = []  # noqa: RUF012 — exercising mutable schema defaults is the point


def test_template_generation():
    text = App.template()
    assert '# Application configuration.' in text
    assert "# Visible app name" in text
    assert "# Address to bind." in text
    assert '[server]' in text or '[Server]' in text.lower() or '[server]' in text
    assert 'name = "demo"' in text
    assert 'port = 8000' in text
    # byte-stable for the same schema
    assert App.template() == text


def test_defaults_instantiation():
    app = App()
    assert app.name == "demo"
    assert app.debug is False
    assert app.server.port == 8000
    assert app.server.ssl_cert is None


def test_validate_dict_aggregates():
    errors = App.validate_dict({"name": 42, "debug": "oops", "server": {"port": "x"}, "unknown": 1})
    assert len(errors) == 3
    paths = {e.path for e in errors}
    assert "name" in paths and "debug" in paths and "server.port" in paths


def test_validation_errors_carry_description():
    errors = App.validate_dict({"server": {"port": "x"}})
    assert len(errors) == 1
    e = errors[0]
    assert e.path == "server.port"
    assert e.description == "Port to listen on."
    assert "(Port to listen on.)" in str(e)


def test_constraint_message_readable():
    class Range(Config):
        """Tuning."""

        level: int = Field(1, ge=1, le=10)

    errors = Range.validate_dict({"level": 99})
    assert str(errors[0]) == "level: value 99 exceeds the maximum 10"
    errors = Range.validate_dict({"level": 0})
    assert str(errors[0]) == "level: value 0 is below the minimum 1"


def test_validate_dict_optional_null():
    errors = Server.validate_dict({"ssl_cert": None})
    assert errors == []  # Optional accepts None
    errors = Server.validate_dict({"port": None})
    assert len(errors) == 1  # non-optional rejects null


def test_load_and_diff_save(tmp_path):
    src = tmp_path / "app.toml"
    src.write_text(
        '# my app\nname = "prod"\n\n[server]\n# the address\nhost = "0.0.0.0"\nport = 80\n',
        encoding="utf-8",
    )
    app = App.load(src)

    # unchanged save → byte-identical
    app.save(src)
    assert src.read_text(encoding="utf-8") == '# my app\nname = "prod"\n\n[server]\n# the address\nhost = "0.0.0.0"\nport = 80\n'  # noqa: E501

    # change one value → only that value changes, comments survive
    app.server.port = 8080
    app.save(src)
    text = src.read_text(encoding="utf-8")
    assert 'port = 8080' in text
    assert '# the address' in text
    assert 'name = "prod"' in text
    assert 'host = "0.0.0.0"' in text


def test_defaults_never_persisted(tmp_path):
    src = tmp_path / "app.toml"
    src.write_text('name = "prod"\n', encoding="utf-8")
    app = App.load(src)
    app.save(src)
    assert src.read_text(encoding="utf-8") == 'name = "prod"\n'  # defaults untouched


def test_unknown_keys_preserved(tmp_path):
    src = tmp_path / "app.toml"
    src.write_text('name = "prod"\nuser_extra = "mine"\n', encoding="utf-8")
    app = App.load(src)
    app.debug = True
    app.save(src)
    text = src.read_text(encoding="utf-8")
    assert 'user_extra = "mine"' in text
    assert 'debug = true' in text


def test_save_creates_missing_nested_table(tmp_path):
    # regression: a nested table absent from the file must be written as a
    # [table] block holding its entries, not as a dotted line plus an empty
    # header (which would define the table twice — invalid TOML)
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    src = tmp_path / "app.toml"
    src.write_text('name = "prod"\n', encoding="utf-8")
    app = App.load(src)
    app.server.host = "0.0.0.0"
    app.save(src)
    text = src.read_text(encoding="utf-8")
    assert tomllib.loads(text) == {"name": "prod", "server": {"host": "0.0.0.0"}}
    assert '[server]\nhost = "0.0.0.0"\n' in text


def test_strict_unknown_rejected(tmp_path):
    src = tmp_path / "app.toml"
    src.write_text('name = "prod"\nuser_extra = "mine"\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        App.load(src, strict=True)


def test_none_deletes_key_on_save(tmp_path):
    src = tmp_path / "s.toml"
    src.write_text('ssl_cert = "a.pem"\n', encoding="utf-8")
    server = Server.load(src)
    server.ssl_cert = None
    server.save(src)
    assert src.read_text(encoding="utf-8") == ""


def test_env_override(tmp_path, monkeypatch):
    src = tmp_path / "app.toml"
    src.write_text('[server]\nport = 80\n', encoding="utf-8")
    monkeypatch.setenv("MYAPP_SERVER__PORT", "9000")
    monkeypatch.setenv("MYAPP_DEBUG", "true")
    monkeypatch.setenv("MYAPP_SERVER__HOST", "0.0.0.0")
    app = App.load(src, env_prefix="MYAPP")
    assert app.server.port == 9000
    assert app.debug is True              # bool coercion
    assert app.server.host == "0.0.0.0"   # nested path


def test_watch_requires_watchfiles():
    try:
        import watchfiles  # noqa: F401
        pytest.skip("watchfiles installed")
    except ImportError:
        pass
    with pytest.raises(RuntimeError):
        Server.watch("x.toml", lambda i: None)


def test_datetime_field_roundtrip(tmp_path):
    class Scheduled(Config):
        """
        Scheduled item.

        at:
            When it runs.
        """

        at: datetime = datetime(2026, 1, 1, 0, 0, 0)

    src = tmp_path / "s.toml"
    src.write_text('at = 2026-06-01T12:00:00Z\n', encoding="utf-8")
    s = Scheduled.load(src)
    assert s.at.year == 2026 and s.at.utcoffset() is not None
    s.save(src)
    assert src.read_text(encoding="utf-8") == 'at = 2026-06-01T12:00:00Z\n'  # unchanged → untouched


def test_tomltypeerror_on_none():
    doc = tomlclass.parse("a = 1\n")
    with pytest.raises(tomlclass.TOMLTypeError):
        doc["a"] = None
    with pytest.raises(TypeError):  # integrates with stdlib hierarchy
        doc["a"] = None


def test_comment_injection_on_load(tmp_path):
    src = tmp_path / "app.toml"
    src.write_text('name = "prod"\n\n[server]\nport = 80\n', encoding="utf-8")

    # default "none": file kept as written, no injection
    app = App.load(src)
    app.save(src)
    assert src.read_text(encoding="utf-8") == 'name = "prod"\n\n[server]\nport = 80\n'

    # "missing": inject a description only for keys without a comment
    app = App.load(src, comments="missing")
    app.save(src)
    text = src.read_text(encoding="utf-8")
    assert 'name = "prod"  # Visible app name' in text  # comment anchors to the key; original whitespace kept
    assert "port = 80  # Port to listen on." in text
    assert "# Address to bind." not in text  # host not persisted: defaults never materialize, injection included
    assert 'name = "prod"' in text and "port = 80" in text

    # "all": same effect here (every description comes from the docstring); idempotent
    app = App.load(src, comments="all")
    app.save(src)
    assert src.read_text(encoding="utf-8") == text


class Product(Config):
    name: str = ""


class Shop(Config):
    products: list[Product] = []  # noqa: RUF012 — the mutable default is the test subject


def test_aot_whole_replace(tmp_path):
    # whole replacement must drop the old elements and render the new ones
    src = tmp_path / "s.toml"
    src.write_text("[[products]]\nname = 'a'\n", encoding="utf-8")
    shop = Shop.load(src)
    shop.products = [Product(name="b"), Product(name="c")]
    shop.save(src)
    text = src.read_text(encoding="utf-8")
    assert 'name = "b"' in text and 'name = "c"' in text
    assert "name = 'a'" not in text and "name = 'a'" not in text.replace('"', "'")
    assert text.count("[[products]]") == 2


def test_aot_whole_replace_empty_clears(tmp_path):
    src = tmp_path / "s.toml"
    src.write_text("[[products]]\nname = 'a'\n", encoding="utf-8")
    shop = Shop.load(src)
    shop.products = []
    shop.save(src)
    assert src.read_text(encoding="utf-8") == ""


def test_pure_default_save_atomic(tmp_path):
    # saving a pure-default instance is also an atomic write (no temp leftovers)
    target = tmp_path / "new.toml"
    app = Shop()
    app.save(target)
    assert target.read_text(encoding="utf-8") == "products = []\n"  # an empty AoT renders as an inline empty array
    assert list(tmp_path.iterdir()) == [target]


def test_strict_nested_unknown(tmp_path):
    # strict must propagate into nested tables
    src = tmp_path / "s.toml"
    src.write_text('[server]\nport = 80\nwho_knows = 1\n', encoding="utf-8")
    errors = App.validate_dict({"server": {"port": 80, "who_knows": 1}}, strict=True)
    assert any(e.path == "server.who_knows" for e in errors)
    with pytest.raises(ValidationError):
        App.load(src, strict=True)


def test_none_on_non_optional_raises(tmp_path):
    # assigning None to a non-optional field must raise on save, not silently delete the key
    src = tmp_path / "s.toml"
    src.write_text("port = 80\n", encoding="utf-8")
    server = Server.load(src)
    server.port = None
    with pytest.raises(ConfigError):
        server.save(src)
    assert src.read_text(encoding="utf-8") == "port = 80\n"
