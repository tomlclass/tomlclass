# Движок

Движок работает с любым документом TOML 1.0: разбор, чтение, изменение, рендеринг, атомарная запись — с сохранением комментариев и форматирования побайтово.

## Разбор и рендеринг

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # разбор из файла по пути
doc.dumps()                      # рендер в str: для неизменённого документа совпадает с вводом побайтово
doc.save(path)                   # атомарная запись (tempfile + os.replace)
```

**Аксиома обратного прохода**: `parse(text).dumps() == text` побайтово, проверяется на каждом PR.

## Совместимость с tomllib

```python
data = tomlclass.loads(text)  # чистый dict, как tomllib.loads
data = tomlclass.load(fp)     # бинарный файловый объект, как tomllib.load
```

## Редактирование

```python
doc["project"]["version"] = "1.0.0"   # изменение: на строке заменяется только значение
del doc["tool"]["old"]                # удаление: комментарий и ведущие пробелы убираются чисто
doc["server"]["workers"] = 4          # новый ключ: после последней записи таблицы
doc["logging"] = {"level": "info"}    # новая таблица: как блок [logging]
doc["products"].append(...)           # добавление в массив: сплайс на месте, существующие элементы не тронуты
doc["products"] = [...]               # полная замена AoT: старые элементы убираются, новые — блоками
```

- Правки используют канонический рендеринг: новые значения пишутся в стандартном виде
- Нетронутые части читаются напрямую из срезов исходного текста
- Инлайн-таблицы закрыты: переприсвойте значение целиком

## Комментарии

```python
doc.comment("server.port")            # -> "the port" (None, если комментария нет)
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # удалить (вместе с ведущими пробелами)
```

Комментарий принадлежит ключу, за которым он следует; комментарий таблицы находится в строке заголовка и адресуется путём таблицы.

## Ошибки

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` — подкласс `ValueError`. Присвоение несериализуемых значений (`None`, функции и т.п.) вызывает `TOMLTypeError` (подкласс `TypeError`).
