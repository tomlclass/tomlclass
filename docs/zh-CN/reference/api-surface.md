# 公开 API 面参考

`tomlclass` 导出什么、各入口如何表现。事实源：`src/tomlclass/__init__.py`（`__all__`）与各 docstring；`tests/unit/test_version.py` 钉住元数据一致性。2026-10 核实。

## 版本

`0.3.0`（`src/tomlclass/__init__.py` 的 `__version__`，与 `pyproject.toml` 镜像）。1.0 前策略：minor 可新增 API；现有 API 保持向后兼容。

## 导出（`__all__`）

| 分组 | 符号 |
|---|---|
| 解析 / 渲染 | `parse`、`loads`、`load`、`load_path`、`dumps`、`dump`、`update` |
| 文档 | `Document` |
| 注解层 | `Config`、`Field` |
| 构造助手 | `document`、`table`、`inline_table`、`aot`、`comment`、`nl` |
| 节点类型 | `Table`、`Array`、`ArrayOfTables`、`InlineTable` |
| 错误 | `TOMLError`、`TOMLParseError`、`TOMLTypeError`、`ConfigError`、`FieldError`、`ValidationError` |
| 元数据 | `__version__` |

可选：`tomlclass.pydantic.TomlModel`（extra `pydantic`），热重载经 `Config.watch`（extra `watchfiles`）。

## 入口契约

| 入口 | 输入 → 输出 | 说明 |
|---|---|---|
| `parse(source, *, toml_version="1.1")` | str → `Document` | 无损；1.0 模式严格 |
| `loads(source, *, toml_version, none_value)` | str → dict | tomllib 兼容；`none_value` 哨兵解码 `None` |
| `load(path_or_fp, *, toml_version, none_value)` | 路径 → `Document`；二进制文件对象 → dict | 双模式 |
| `load_path(path)` | 路径 → `Document` | 恒为无损 |
| `dumps(obj, *, none_value)` | `Document` → str（未编辑时原样）；Mapping → str（规范）；无哨兵时 `None` 抛 `TOMLTypeError` | `none_value` 仅 Mapping 路径 |
| `dump(obj, fp, *, none_value)` | 写入文本/二进制文件对象 | 同 `dumps` |
| `update(path, updates, *, toml_version, none_value)` | 点号键映射；原子写；返回 `Document` | 文件对象抛 `TypeError`；任一值非法则不写 |

所有解析入口都接受 `toml_version`（默认 `"1.1"`，`"1.0"` 严格旧语义）。

## Document 要点

- 完整 `MutableMapping` 协议；按值 `==`；`|` 合并运算符。
- 路径文法（`find` / `set_path` / `comment` / `set_comment` / `update` 同一文法）：裸键、带引号键（`"a.b"`）、`[int]` AoT 索引。未索引的 AoT 遍历读投影、写广播；索引绝不自动创建。畸形路径处处抛 `ValueError`。
- 注释 API：`doc.comment(path)` / `doc.set_comment(path, text | None)`；AoT 字段需索引（`products[0].name`）。
- `save()` 原子（tempfile + `os.replace`）；`dumps()` 幂等。
- 编辑封闭：inline table（整体重赋值）、点号键表（sealed，新键渲染为锚定点号行）。AoT 重排序（`sort`/`reverse`）不支持——整体替换。

## 注解层要点

- `Config`：docstring → 模板注释；`App()` 纯默认值，`App.load(path, env_prefix=...)` 校验 + env 覆盖，`App.template()` 注释模板，`App.validate_dict(raw)` 聚合错误，`app.save()` diff 写回，`app.to_dict()`、`app.reload()`、`Config.migrate(old)` 与 `_migrate_key_map`。
- 类选项：`extra`（默认 `"allow"` / `"ignore"` / `"forbid"`）、`validate_assignment`。
- `Field` 约束：`ge / le / gt / lt / pattern / min_length / max_length / coerce`；`Annotated[X, Field(...)]` 等价；i18n 描述字典。
- 支持的注解：`bool/int/float/str/datetime/date/time`、`Optional`/联合、`Literal`、`list[X]`、`list[Config]`（AoT）、嵌套 `Config`、`dict[str, X]`、`Enum`、`Annotated`。其余报 "unsupported annotation"。
- 视图语义：默认值不落盘；未知键保留（strict 模式报错）；diff 写回；Optional 字段的 `None` 在保存时删键。

## 错误

| 错误 | 基类 | 触发场景 |
|---|---|---|
| `TOMLError` | `Exception` | 层级根 |
| `TOMLParseError` | `TOMLError`、`ValueError` | 语法/语义解析失败；携带 `line`/`col`/`offset`/`segment` |
| `TOMLTypeError` | `TOMLError`、`TypeError` | 不可表示的值（如无 `none_value` 的 `None`）——赋值时而非渲染时 |
| `ConfigError` | `TOMLError`、`ValueError` | schema 层误用 |
| `FieldError` | ——（数据类） | 单条违例：`path`、消息、可选 `description` |
| `ValidationError` | `ConfigError` | `validate_dict`/`load` 聚合的 `FieldError` 列表 |
