[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | **Русский**

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

Неразрушающее редактирование TOML и типизированная конфигурация в одном пакете без зависимостей.

Изменяйте одно значение в файле конфигурации, не ломая ни одного комментария; объявляйте схемы классами Python и получайте шаблоны с комментариями, агрегированную валидацию и diff-запись обратно.

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

- **Движок неразрушающего редактирования**: разбор и запись обратно TOML 1.0 с поддержкой всех типов; все 709 кейсов toml-test 1.0 проходят. Нетронутые документы рендерятся побайтово идентично вводу
- **Обновление одной строкой**: `tomlclass.update("app.toml", {"server.port": 9090})` — прочитать, изменить, атомарно записать обратно; комментарии, порядок и форматирование сохраняются во всём остальном
- **Типизированная конфигурация**: объявите схему классами — docstring'и становятся комментариями шаблона, валидация агрегирует все ошибки вместе с задокументированным смыслом каждого поля, значения по умолчанию сливаются в памяти и никогда не записываются в файл
- **Операции с комментариями**: чтение, замена и удаление комментариев по ключу; описания схемы можно внедрять как комментарии (три стратегии)
- **Совместимость с tomllib**: `loads` / `load` следуют соглашению stdlib о вызовах — миграция ничего не стоит

## Почему не tomlkit

tomlkit — фактический стандарт неразрушающего редактирования, и движок этого проекта создавался с ним в качестве базовой линии. Где tomlclass выигрывает:

| Аспект | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| Скорость разбора (та же машина) | базовая линия | **в 5.8–6.4 раза быстрее** |
| Получение обычного dict | round trip `parse(dumps(doc))` | `to_dict()` строит его напрямую, без round trip |
| Операции с комментариями | спрятаны в объектах стиля, нет API по ключу | `doc.comment(key)` / `set_comment` как первоклассные средства |
| Схема / шаблон / валидация | нет — собирайте сами | встроено в `Config` (шаблон, агрегированная валидация, env-переопределения, миграция) |
| Резидентная память | базовая линия | **0.67×** |

Источник: [базовые показатели производительности](tests/bench/BASELINE.md) (та же машина, то же число итераций).

## Установка

```bash
pip install tomlclass
```

## Использование

### Изменить одно значение, сохранив всё остальное

```python
import tomlclass

tomlclass.update("pyproject.toml", {"project.version": "1.0.0"})
# only that line changed — comments, ordering and formatting all intact
```

### Редактирование TOML-файла (полный контроль)

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, comments kept
text = doc.dumps()                                   # only touched lines change
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


server = Server.load("server.toml")  # read + validate + merge defaults
server.port = 9000
server.save("server.toml")           # only changed keys are written
```

## Документация

- [Движок](docs/ru/engine.md) — разбор, редактирование, `update()`, API комментариев, ошибки
- [Конфигурация](docs/ru/config.md) — объявление схемы, шаблон, семантика load/save, ошибки валидации
- [Комментарии](docs/ru/comments.md) — принадлежность комментариев, режимы внедрения
- [Примеры](docs/ru/examples.md) — сквозные сценарии
- [Производительность](docs/ru/performance.md) — измеренная база

## Требования

Python ≥ 3.10, без сторонних зависимостей.

## Лицензия

[MIT](LICENSE)
