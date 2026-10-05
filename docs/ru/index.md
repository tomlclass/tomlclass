# Документация tomlclass

tomlclass — библиотека для TOML-конфигурации: движок редактирования без потерь плюс типизированные аннотации конфигурации. Ноль сторонних зависимостей, Python ≥ 3.10.

Два слоя, каждый из которых можно использовать самостоятельно:

- **Движок** — разбор любого документа TOML 1.0, редактирование и запись обратно с сохранением каждого комментария, порядка ключей и любых особенностей форматирования.
- **Аннотации** — объявите схему конфигурации классами Python и получите шаблон с комментариями, агрегированную валидацию и diff-запись обратно.

## Обзор за 60 секунд

Измените одно значение, не трогая ничего больше:

```python
import tomlclass

tomlclass.update("app.toml", {"server.port": 9090})
# only that line changed — comments, ordering and formatting all intact
```

Или управляйте файлом конфигурации через схему:

```python
from tomlclass import Config

class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")  # parse + validate + merge defaults
server.port = 9090
server.save("server.toml")           # diff write-back: only changed keys are written
```

## Содержание

| Документ | Содержание |
|---|---|
| [Движок](engine.md) | разбор, редактирование, `update()`, API комментариев, ошибки |
| [Конфигурация](config.md) | объявление схемы, шаблон, семантика load/save, ошибки валидации |
| [Комментарии](comments.md) | принадлежность комментариев, режимы внедрения |
| [Примеры](examples.md) | сквозные сценарии: обновление pyproject, жизненный цикл конфигурации приложения, AoT, горячая перезагрузка |
| [Производительность](performance.md) | измеренная база и методика |

## Установка

```bash
pip install tomlclass
```
