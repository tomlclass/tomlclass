[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | **Русский**

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>

# tomlclass

Библиотека TOML-конфигурации: собственный движок неразрушающего редактирования + типизированные аннотации конфигурации. Ноль сторонних зависимостей.

Запись файла конфигурации сохраняет каждый комментарий и всё форматирование; объявите структуру классами Python и получите шаблон с комментариями и валидацию. Семантика конфигурации взята из системы конфигурации фреймворка [ErisPulse](https://github.com/ErisPulse/ErisPulse).

<p>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/pypi/v/tomlclass?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/tomlclass/actions/workflows/code-quality-check.yml"><img src="https://img.shields.io/github/actions/workflow/status/wsu2059q/tomlclass/code-quality-check.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/tomlclass/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge" alt="Ruff"></a>
</p>

<br clear="both">

---

## Возможности

- **Движок неразрушающего редактирования**: полный разбор и запись TOML 1.0, все 709 случаев toml-test 1.0 пройдены; неизменённый документ рендерится побайтово идентично вводу
- **Типизированная конфигурация**: schema объявляется классами, docstring становится комментариями шаблона, валидация агрегирует все ошибки, значения по умолчанию объединяются только в памяти и не записываются
- **Операции с комментариями**: чтение, замена и удаление по ключу; описания schema могут вставляться как комментарии (три режима)
- **Совместимость с tomllib**: `loads` / `load` следуют соглашениям стандартной библиотеки — миграция ничего не стоит

## Почему не tomlkit

tomlkit — фактический стандарт неразрушающего редактирования, движок этого проекта проектировался с ним в качестве базовой линии. Преимущества tomlclass:

| Измерение | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| Скорость разбора (одна машина) | базовая линия | **в 5,8–6,4 раза быстрее** |
| Получение чистого dict | нужен цикл `parse(dumps(doc))` | `to_dict()` строит напрямую, без цикла |
| Операции с комментариями | спрятаны в объектах стиля, нет API по ключам | `doc.comment(key)` / `set_comment` — полноценный API |
| Schema / шаблон / валидация | нет — собирайте сами | встроено в `Config` (шаблон, агрегированная валидация, env-переопределения, миграция) |
| Память | базовая линия | **0.67×** |

Источник: [базлайн производительности](tests/bench/BASELINE.md) (одна машина, одно число итераций).

## Установка

```bash
pip install tomlclass
```

## Использование

### Редактирование TOML-файла

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # вставка на месте, комментарии сохранены
text = doc.dumps()                                   # меняются только затронутые строки
```

### Декларативная конфигурация

```python
from tomlclass import Config

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


server = Server.load("server.toml")  # чтение + валидация + слияние значений по умолчанию
server.port = 9000
server.save("server.toml")           # записываются только изменённые ключи
```

## Документация

- [Движок](docs/ru/engine.md) — Document, редактирование, совместимость с tomllib, ошибки
- [Аннотации](docs/ru/config.md) — Config, Field, семантика представления, env-переопределения
- [Комментарии](docs/ru/comments.md) — модель принадлежности, чтение и замена
- [Примеры](docs/ru/examples.md) — код типовых сценариев
- [Производительность](docs/ru/performance.md) — базовые показатели и замеры

## Зависимости и окружение

Python ≥ 3.10, без сторонних зависимостей.

## Лицензия

[MIT](LICENSE)
