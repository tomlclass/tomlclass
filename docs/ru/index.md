# Документация tomlclass

tomlclass — библиотека TOML-конфигурации: движок неразрушающего редактирования + типизированные аннотации конфигурации. Ноль сторонних зависимостей.

Запись файла конфигурации сохраняет каждый комментарий и всё форматирование; объявите структуру классами Python и получите шаблон с комментариями, валидацию и заполнение. Семантика конфигурации взята из системы конфигурации фреймворка [ErisPulse](https://github.com/ErisPulse/ErisPulse).

## Навигация

| Документ | Содержание |
|---|---|
| [Движок](engine.md) | Document, редактирование, совместимость с tomllib, ошибки |
| [Аннотации](config.md) | Config, Field, семантика представления, env-переопределения |
| [Комментарии](comments.md) | Модель принадлежности, чтение и замена |
| [Примеры](examples.md) | Код типовых сценариев |
| [Производительность](performance.md) | Базовые показатели и замеры |

## Установка

```bash
pip install tomlclass
```

Python ≥ 3.10, без сторонних зависимостей.

## Минимальный пример

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
text = doc.dumps()  # меняются только затронутые строки
```

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")
server.port = 9000
server.save("server.toml")
```
