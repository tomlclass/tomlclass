# 迁移

## 从 0.2.x 到 0.3.0

0.3.0 全面泛化公开 API。以下是全部破坏面：

| 变更 | 0.2.x | 0.3.0 |
|---|---|---|
| 非 ASCII 裸键 | 默认接受（1.1 草案行为） | 按官方 v1.1.0 规范拒绝——请加引号（`"κ" = 1`） |
| `import tomlclass.document` | 子模块 | 改名为 `tomlclass._document`；`tomlclass.document()` 现在是构造函数 |
| `doc.to_dict()` 的日期时间 | 私有 `_Date`/`_DateTime` 子类 | 标准 `datetime`/`date`/`time` |
| `Table.update/setdefault/pop/popitem/clear` | 静默绕过编辑引擎（输出不变） | 走引擎——输出如实反映 |
| `doc.add(key, value)` | — | 新增；键已存在时抛 `KeyError` |
| 畸形点号路径（`"a..b"`、`"a[01]"`） | 静默错配 | 所有入口统一抛 `ValueError` |
| 新建的根级表 | 渲染在首个键值行之后 | 渲染到文件末尾 |
| 隐式父表写入（`[db.pool]` + `doc["db"]["host"]`） | 点号线落进错误块（语义静默损坏） | 文件末尾生成独立 `[db]` 块 |
| `find`/`set_path` 的引号键与 `[int]` 索引 | 不识别 | 一等公民（见[引擎](engine.md#路径寻址)） |

0.2.x 之后新增：`document()` / `table()` / `inline_table()` / `aot()` / `comment()` / `nl()`、
`dump()` / `load_path()`、`unwrap()` / `as_string()` / `add()`、`Table.to_dict()` /
`Table.comments[key]`、`doc.comment("it[0].n")`、表头与 API 新建键注释、
`Config` 的 `dict[str, X]` / `Enum` / `Annotated[X, Field(...)]` / `default_factory` / `to_dict()` /
`reload()` / `validate_assignment` / `extra`。

## 从 tomlkit

tomlclass 以相同的调用形态覆盖核心编辑面——并以极低的成本保住你的注释。schema 校验
（`Config`/`Field`）在 tomlkit 中没有对应物。

| tomlkit | tomlclass | 说明 |
|---|---|---|
| `tomlkit.parse(text)` | `tomlclass.parse(text)` | 返回 `Document`（完整 `MutableMapping`） |
| `tomlkit.loads` / `dumps` | `tomlclass.loads` / `dumps` | 同约定 |
| `tomlkit.dump(o, fp)` / `load(fp)` | `tomlclass.dump(o, fp)` / `load(fp)` | `load` 为双模：传路径返回 `Document`——明确场景请用 `load_path` |
| `doc.unwrap()` / `doc.as_string()` | 同名 | |
| `tomlkit.document()` / `table()` / `inline_table()` / `aot()` | `tomlclass.document()` / `table()` / `inline_table()` / `aot()` | |
| `tomlkit.comment("x")` / `nl()` | `tomlclass.comment("x")` / `nl()` | 经 `doc.add(...)` 附着；不提供 `ws()` |
| `doc.add(key, value)` | 同名 | 键已存在时抛 `KeyError` |
| `doc["a"] = 1` | 同名 | 编辑原位拼接；未触碰行逐字节不变 |
| `doc.body` | — | 通过映射 API 编辑，或用 `document()` 构建；新键注释用 `set_comment` |
| `register_encoder` 与 item 类型（`item()`、`string()` 等） | — | 不提供：值保持普通 Python 类型 |
