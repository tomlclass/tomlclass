# Конфигурация

Объявляйте структуру конфигурации классами: docstring превращается в комментарии шаблона, чтение валидируется, а запись обратно затрагивает только изменённые ключи.

## Объявление

```python
from tomlclass import Config, Field

class Server(Config):
    """
    HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = 8000


class App(Config):
    name: str = Field("demo", ge=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- Первый абзац docstring становится комментарием таблицы; секции `field:` становятся комментариями над ключами (в шаблоне рендерятся как строки `#`)
- Вложенный класс = вложенная таблица; `list[T]` поддерживает валидацию элементов; поля с префиксом-подчёркиванием исключаются
- Ограничения `Field`: `ge / le / gt / lt / pattern / min_length / max_length / coerce`
- Описания полей поддерживают i18n-словари: `Field(description={"i18n": key, "default": text})`

## Точки входа

```python
app = App()                        # pure defaults (in memory)
app = App.load("app.toml")         # parse + validate + merge defaults
text = App.template()              # commented template (byte-stable per schema)
errors = App.validate_dict(raw)    # offline validation, aggregates all errors
app.save("app.toml")               # diff write-back (atomic)
```

## Ошибки валидации

`validate_dict` и `load` агрегируют **все** нарушения в одну `ValidationError` вместо падения на первой. Каждый `FieldError` указывает точечный путь, что именно не так и — если у поля есть описание — задокументированный смысл поля:

```python
class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = Field(8000, ge=1, le=65535)


Server.validate_dict({"port": 70000})
# ValidationError: 1 validation error(s): port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

Сообщение называет нарушенную границу простым языком и указывает на описание из схемы, так что исправление обычно очевидно без открытия исходника схемы.

## Семантика представления

1. Значения по умолчанию никогда не сохраняются в файл — файл содержит только ключи, изменённые пользователем
2. Неизвестные ключи сохраняются (`strict=True` превращает это в ошибку; поведение распространяется на вложенные таблицы)
3. Diff-запись — сравнение со снимком на момент разбора; записываются только изменённые ключи
4. `None` у Optional-поля удаляет ключ при сохранении; `None` у обязательного поля вызывает `ConfigError` при сохранении
5. Атомарная запись — tempfile + `os.replace`

## Env-переопределения и горячая перезагрузка

```python
# MYAPP_SERVER__PORT=9000 overrides server.port (__ separates path segments,
# best-effort conversion to the annotated type)
app = App.load("app.toml", env_prefix="MYAPP")

# Hot reload: optional dependency watchfiles; validation failures keep the
# previous good instance and watching continues. stop_event stops it.
Server.watch("server.toml", callback, stop_event=event)
```

## Миграция

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
