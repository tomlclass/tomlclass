# Движок

Движок работает с любым документом TOML 1.0: разбор, чтение, редактирование, рендеринг, атомарное сохранение — с сохранением комментариев и форматирования побайт-в-байт.

## Разбор и рендеринг

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # parse from a file path -> Document
doc.dumps()                      # render to str: byte-identical to input when unedited
doc.save(path)                   # atomic write (tempfile + os.replace)
```

**Аксиома round-trip**: `parse(text).dumps() == text` выполняется побайтово; это проверяется при каждом коммите набором toml-test 1.0 (все 208 валидных файлов проходят round-trip в точности; все 501 невалидный файл отклоняется).

## Как устроено сохранение

Нетронутые узлы хранят в исходнике только свой спан `(start, end)`; при рендеринге исходный текст вырезается по этому спану. Форматирование нигде не записывается — оно *и есть* исходный текст и выживает просто потому, что его не трогают. Лишь когда узел редактируется, tomlclass материализует для него отрендеренный вывод (каноническое форматирование); всё остальное остаётся срезом исходника.

Следствия: `dumps` без правок — примерно O(1), путь чтения вообще не несёт данных о форматировании, а стоимость правки зависит от размера правки, а не от длины документа.

## Совместимость с tomllib

```python
data = tomlclass.loads(text)  # plain dict, same convention as tomllib.loads
data = tomlclass.load(fp)     # binary file object, same convention as tomllib.load
```

## Редактирование

```python
doc["project"]["version"] = "1.0.0"   # modify: only the value on that line changes
del doc["tool"]["old"]                # delete: trailing comment removed cleanly
doc["server"]["workers"] = 4          # new key: rendered after the table's last entry
doc["logging"] = {"level": "info"}    # new table: rendered as a [logging] block
doc["products"].append(...)           # array append: spliced in place, existing elements untouched
doc["products"] = [...]               # AoT whole replace: old elements removed, new ones as blocks
```

- Отредактированные значения рендерятся канонически; нетронутые части читаются напрямую из срезов исходника
- Инлайн-таблицы закрыты: переприсваивайте значение целиком вместо добавления в них ключей
- Таблицы, созданные точечными ключами (dotted keys), запечатаны: добавленные в них ключи рендерятся как строки в точечной записи, привязанные к последней физической строке таблицы

### Доступ по точечному пути

```python
doc.find("server.port")            # -> value or None
doc.set_path("server.port", 9090)  # assign; missing keys and intermediate tables are created
```

`set_path` строит недостающие таблицы как настоящие блоки `[table]`, содержащие их записи, — никогда как строку в точечной записи плюс пустой заголовок (что определило бы таблицу дважды).

## Обновление одним вызовом

```python
tomlclass.update("app.toml", {"server.port": 9090, "name": "prod"})
```

Читает файл, применяет все присваивания по точечным путям, атомарно записывает файл обратно и возвращает `Document`. Если какое-либо значение невозможно представить в TOML, ничего не записывается. `None` — не значение TOML; удаляйте ключи через mapping-API (`del doc[...]`).

## Комментарии

```python
doc.comment("server.port")            # -> "the port" (None when absent)
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # remove (with leading whitespace)
```

Комментарий принадлежит ключу, за которым он следует; комментарии таблицы живут в строке заголовка и адресуются путём таблицы. Полная модель — в разделе [Комментарии](comments.md).

## Ошибки

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` — подкласс `ValueError`. Присваивание несериализуемых значений (`None`, функций, произвольных объектов) вызывает `TOMLTypeError` (подкласс `TypeError`) в момент присваивания, а не в момент рендеринга.
