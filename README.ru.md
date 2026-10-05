[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | **Русский**

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

Неразрушающее редактирование TOML и типизированная конфигурация в одном пакете без зависимостей.

Изменяйте одно значение в файле конфигурации, не ломая ни одного комментария; объявляйте схемы классами Python и получайте шаблоны с комментариями, агрегированную валидацию и diff-запись обратно.

> **Версионирование**: tomlclass ещё не достиг версии 1.0 и пока строго не следует SemVer. До стабилизации проекта минорные обновления могут добавлять новые API — существующие API сохранят обратную совместимость.

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

- **Движок неразрушающего редактирования**: разбор и запись обратно TOML 1.0/1.1; единственная библиотека с идеальным результатом 187/187 в valid-тестах toml-test 1.5.0. Нетронутые документы рендерятся побайтово идентично вводу
- **TOML 1.1 с переключателем версий**: экранирование `\e` / `\x`, время без секунд, переводы строк и хвостовые запятые в инлайн-таблицах, не-ASCII голые ключи — включены по умолчанию; передайте `toml_version="1.0"` в `parse` / `loads` / `load` / `update` / `Config.load` для строгой семантики отклонения 1.0
- **None по-вашему**: опциональный часовой `none_value` в стиле rtoml — `dumps(data, none_value="@None")` и `loads(text, none_value="@None")` передают None через TOML-строки без потерь
- **Обновление одной строкой**: `tomlclass.update("app.toml", `tomlclass.update("app.toml", {"server.port": 9090})`)` — чтение, изменение, атомарная запись; комментарии, порядок и форматирование сохраняются везде остальном
- **Типизированная конфигурация**: объявите схему классами — docstring становятся комментариями шаблона, валидация агрегирует все ошибки с документированным смыслом каждого поля, значения по умолчанию сливаются в памяти и никогда не записываются
- **Операции с комментариями**: чтение, замена и удаление комментариев по ключу; описания схемы могут быть внедрены как комментарии (три стратегии)
- **Совместимость с tomllib**: `loads` / `load` следуют соглашениям стандартной библиотеки — миграция ничего не стоит

> **Граница версий TOML**: дополнения 1.1 выше принимаются по умолчанию. Если ваш код полагается на *отклонение* невалидного для 1.0 ввода (например, время `13:37`), переключитесь на `toml_version="1.0"` — те же файлы вызовут `TOMLParseError`.

## Соответствие и производительность

Данные получены с помощью [toml-bench](https://github.com/pwwang/toml-bench) (toml-test 1.5.0 + тестовые данные CPython tomllib; скорость = load/dump за 5000 итераций на одной машине, tomlclass 0.2.0 — методология в [базовом отчёте](tests/bench/BASELINE.md)):

| Проверка | tomlclass 0.2.0 |
|---|---|
| toml-test 1.5.0 valid (187 файлов) | **187/187 — единственная библиотека с идеальным результатом** |
| манифест TOML-1.1 toml-test 1.5.0 (548 файлов) | **548/548** |
| тестовые данные CPython tomllib | **12/12 valid, 50/50 invalid** |

Скорость (load / dump, 5000 итераций):

| Библиотека | корпус rtoml | корпус tomli |
|---|---|---|
| rtoml 0.11 (Rust) | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib (CPython) | 3.39s / — | 2.15s / — |
| **tomlclass 0.2.0** | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

Неразрушающее редактирование платит за учёт: loads в ~2,5–2,8× tomli, dumps в ~2,6–3,2× tomli_w — и в 12–14× быстрее tomlkit.

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
