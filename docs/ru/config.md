# Аннотации

Структура конфигурации объявляется классами: docstring — это комментарии шаблона, при чтении выполняется валидация, запись затрагивает только изменённые ключи.

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

- Первый абзац docstring → комментарий таблицы; секции `имя_поля:` → комментарии над ключами (в шаблоне рендерятся строками `#`)
- Вложенный класс = вложенная таблица; `list[T]` поддерживает валидацию элементов; поля с подчёркиванием в начале исключаются
- Ограничения `Field`: `ge / le / gt / lt / pattern / min_length / max_length / coerce`
- Описания полей поддерживают i18n-словари: `Field(description={"i18n": key, "default": text})`

## Точки входа

```python
app = App()                        # чистый экземпляр по умолчанию
app = App.load("app.toml")         # разбор + валидация + слияние значений по умолчанию
text = App.template()              # шаблон с комментариями (байт-стабилен для schema)
errors = App.validate_dict(raw)    # офлайн-валидация, агрегирует все ошибки
app.save("app.toml")               # запись через diff (атомарная)
```

## Семантика представления

1. Значения по умолчанию никогда не записываются — в файле только ключи, изменённые пользователем
2. Неизвестные ключи сохраняются (`strict=True` превращает это в ошибку)
3. Запись через diff — сравнение со снимком на момент разбора, записываются только изменённые ключи
4. `None` у Optional-поля = удаление ключа при записи; `None` у не-optional поля при записи вызывает `ConfigError`
5. Атомарная запись — tempfile + `os.replace`

## env-переопределения и горячая перезагрузка

```python
# MYAPP_SERVER__PORT=9000 переопределяет server.port (__ разделяет сегменты пути,
# преобразование в тип аннотации — best effort)
app = App.load("app.toml", env_prefix="MYAPP")

# Горячая перезагрузка: опциональная зависимость watchfiles; при ошибке валидации
# сохраняется предыдущий корректный экземпляр, наблюдение продолжается
Server.watch("server.toml", callback, stop_event=event)
```

## Миграция

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # старый ключ -> новый точечный путь


new = AppV2.migrate(AppV1.load("app.toml"))
```
