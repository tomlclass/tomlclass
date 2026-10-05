# Примеры

Приведённый код можно копировать и запускать как есть.

## Редактирование стороннего TOML (в духе pyproject)

```python
import tomlclass

doc = tomlclass.parse(pyproject_text)

doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # вставка на месте, комментарий "click" сохранён
doc["tool"]["mytool"] = {"cache": True}              # рендерится как блок [tool.mytool]
```

## Чтение и запись конфигурации приложения

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp) / "server.toml"
    cfg.write_text("port = 8080  # exposed\n", encoding="utf-8")

    server = Server.load(cfg)
    server.port = 9090
    server.save(cfg)
    # Результат: изменилась только строка port, комментарий "# exposed" сохранён
```

## Массивы таблиц (AoT)

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})             # добавление: новый блок
doc["products"] = [{"name": "sofa"}]                 # полная замена: старые элементы убраны
```

## Миграция с tomllib

```python
data = tomlclass.loads(text)   # чистый dict (как tomllib.loads)
data = tomlclass.load(fp)      # бинарный файловый объект (как tomllib.load)

# Когда нужно неразрушающее редактирование — переход на Document:
doc = tomlclass.load("pyproject.toml")  # аргумент-путь -> Document
```

## env-переопределения и горячая перезагрузка

```python
# DEMO_SERVER__PORT=9000 переопределяет server.port
server = Server.load(cfg, env_prefix="DEMO")

# Горячая перезагрузка (опциональная зависимость watchfiles); stop_event
# позволяет остановить наблюдение из другого потока
Server.watch("server.toml", callback, stop_event=event)
```

## Миграция schema

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # старый ключ -> новый точечный путь


new = AppV2.migrate(AppV1.load("app.toml"))
```
