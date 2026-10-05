# Примеры

Сквозные сценарии; каждый фрагмент кода работает как есть.

## Безопасное обновление стороннего TOML (в духе pyproject)

Нужно лишь поднять версию или переключить флаг в файле, принадлежащем другому инструменту, — не разрушая его комментарии:

```python
import tomlclass

tomlclass.update("pyproject.toml", {
    "project.version": "1.0.0",
    "tool.mytool.cache": True,       # creates [tool.mytool] if absent
})
```

Каждая нетронутая строка — комментарии других инструментов, необычные отступы, порядок ключей — после записи байт-в-байт идентична прежней.

Для более точечных вмешательств используйте движок напрямую:

```python
doc = tomlclass.load("pyproject.toml")

doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, the
                                                     # "click" comment survives
doc["tool"]["mytool"] = {"cache": True}              # rendered as a [tool.mytool] block
doc.save("pyproject.toml")
```

## Конфигурация приложения: от первого запуска до устоявшегося состояния

Типичный жизненный цикл приложения: при первом запуске создаётся шаблон с комментариями, при последующих запусках выполняются валидация и слияние, а записывается обратно только изменившееся.

```python
from pathlib import Path

from tomlclass import Config, Field

class Server(Config):
    """HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)


class App(Config):
    """Application configuration."""

    name: str = "demo"
    debug: bool = False
    server: Server


CONFIG = Path("app.toml")


def load_config() -> App:
    if not CONFIG.exists():
        CONFIG.write_text(App.template(), encoding="utf-8")  # first run: commented template
    return App.load(CONFIG, env_prefix="APP")                # validate + defaults + env overrides


app = load_config()
app.debug = True
app.save(CONFIG)  # diff write-back: only debug changed; user comments survive
```

Что видит пользователь, когда значение невалидно:

```
ValidationError: 1 validation error(s): server.port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

Описание берётся напрямую из docstring схемы — ошибка указывает на задокументированное ограничение, а не просто на число.

## Пакетные правки с полным контролем

```python
import tomlclass

doc = tomlclass.load("app.toml")

doc.set_path("server.port", 9090)          # change; comment on that line survives
doc.set_path("logging.level", "debug")     # creates the [logging] table
doc.set_comment("server.port", "exposed")  # replace the comment too
doc.save("app.toml")                       # one atomic write
```

## Массивы таблиц (AoT)

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})  # append: rendered as a new block
doc["products"] = [{"name": "sofa"}]      # whole replace: old elements removed
```

## Миграция с tomllib

```python
data = tomlclass.loads(text)   # plain dict (same convention as tomllib.loads)
data = tomlclass.load(fp)      # binary file object (same convention as tomllib.load)

# Upgrade to lossless editing when needed:
doc = tomlclass.load("pyproject.toml")  # path argument -> Document
```

## Env-переопределения и горячая перезагрузка

```python
# APP_SERVER__PORT=9000 overrides server.port (__ separates path segments)
server = Server.load("server.toml", env_prefix="APP")

# Hot reload (optional dependency watchfiles); stop_event stops from another thread.
# Validation failures keep the previous good instance and watching continues.
Server.watch("server.toml", callback, stop_event=event)
```

## Миграция схемы

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
