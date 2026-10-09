# 架构参考

`src/tomlclass/` 代码库的事实。2026-10 对照源码核实；代码变更时保持同步。

## 模块清单

| 模块 | 行数* | 职责 |
|---|---|---|
| `parser.py` | ~880 | 文本 → CST。产出节点树与 `parts`（源 span 的有序列表）。默认执行 TOML 1.1，`toml_version="1.0"` 时严格 1.0。 |
| `nodes.py` | ~640 | CST 节点类型：`Table`、`InlineTable`、`Array`、`ArrayOfTables`、`Trivia`（独立注释/空行）。携带 `(start, end)` 源 span；变更器即引擎钩子。 |
| `engine_set.py` | ~260 | `engine_set` / `engine_del` / `mark_dead`：所有变更由此流过；决定拼接、重渲染还是删除。 |
| `render.py` | ~450 | 脏节点的规范渲染；未触碰的输出来自源文本切片，而非存储的格式数据。 |
| `_document.py` | ~540 | `Document`：根表之上的 `MutableMapping` 门面、路径文法（`find`/`set_path`/`comment`/`set_comment`）、`dumps`/`save`（原子 tempfile + `os.replace`）。 |
| `schema.py` | ~1110 | 注解层：`Config`/`Field`、docstring → 模板注释、聚合错误校验、env 覆盖、diff 写回、热重载、迁移。 |
| `pydantic.py` | ~430 | 可选互操作（`TomlModel`）：pydantic 负责校验，tomlclass 负责无损 load/save 与逐元素 AoT diff。 |
| `errors.py` | ~120 | `TOMLError` 层级（见 [API 面](api-surface.md#errors)）。 |
| `__init__.py` | ~320 | 公开 API 再导出、`__all__`、模块级入口（`parse`/`loads`/`load`/`dumps`/`dump`/`update`/`load_path`、构造助手）。 |

\* 行数为近似值；引用他处前先 `wc -l` 核实。

## 管线

```
源文本
   │  parser.py（默认 1.1 / 严格 1.0）
   ▼
CST：Table / Array / ArrayOfTables 节点，各带源 span
   │  _document.py 的 Document（MutableMapping + 路径文法）
   ▼  变更
engine_set.py —— engine_set / engine_del / mark_dirty
   │
   ▼  dumps()/save()
render.py —— 未触碰节点：原样切片源文本；脏节点：规范渲染
   │
   ▼
schema.py / pydantic.py —— 在同一 Document 之上做校验与 diff 写回
```

## 保真为何逐字节成立

未触碰的节点**完全不存格式数据**——只有 `(start, end)` span。渲染就是切片原文，"保留"未触碰输出等于**没碰它**。只有被编辑的节点才会物化规范渲染输出。推论：

- 未编辑的 `dumps()` 便宜且天然幂等（双 `dumps()` 在测试中断言）；
- 编辑成本随编辑量伸缩，与文档长度无关；
- 任何重建未触碰节点的代码路径都是缺陷（见[不变量](invariants.md)）。

## 编辑路由规则

所有 `Table`/`Array` 变更器（`__setitem__`、`append`、`insert`、`pop`……）都经引擎钩子路由。这正是内存树与渲染输出不分叉的原因——`Table.update/setdefault/...` 曾静默绕过引擎是 0.3.0 的真实 bug（已修，见 `docs/zh-CN/migration.md`）。新增绕过底层 dict/list 直接写入的变更器，就是在重新引入这类 bug。

## 数据边界要点

- 文件经 `read_bytes()` 读取——不做通用换行翻译，CRLF 保持 CRLF；生成行遵循文件本身的换行；赋值字符串中的 `\r` 被转义。
- TOML 没有 null：不用 `none_value` 哨兵时 `None` 抛 `TOMLTypeError`；Optional schema 字段在保存时删除对应键。
- 非 ASCII 裸键按官方 v1.1.0 规范拒绝——带引号的键是一等公民（路径文法亦然）。
