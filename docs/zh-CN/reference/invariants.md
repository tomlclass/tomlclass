# 不变量参考

四条不容破坏的保证。属性测试在 `tests/property/test_invariants.py`；一致性钉在 `tests/integration/test_toml_test.py`。

| # | 不变量 | 陈述 | 执行位置 |
|---|---|---|---|
| 1 | **往返公理** | 未修改文档的 `dumps()` 与源文本逐字节一致。任何改变未触碰输出的变更都是缺陷。 | `tests/unit/test_roundtrip.py`、属性测试、toml-test 有效文件（逐字节） |
| 2 | **注释保留** | 注释、键序与格式在每次读-改-存循环中存活。数组拼接保留逐元素注释；AoT 与表编辑保留节注释。 | 属性测试、`test_edit.py`、`test_compat.py`（注释 API）、toml-test 往返 |
| 3 | **默认值不落盘** | 内存中合并的 schema 默认值绝不写入文件——包括文件中不存在的字段和 `[[aot]]` 数组内的元素。 | 属性测试（defaults 场景）、`test_schema.py`、`test_pydantic.py` |
| 4 | **CRLF 保真** | 读取不做通用换行翻译；生成行遵循文件的换行；赋值字符串值内的 CR 被转义而非原样写入。 | 属性测试（CRLF 场景）、`test_regressions_021c.py` fixture（`write_bytes`/`newline=""`） |

## 违例怎么读

- 违反 1 → 怀疑 span 漂移或节点被误标 dirty（`parser.py`、`render.py`）。
- 违反 2 → `nodes.py` / `render.py` 的 trivia 处理；拼接路径（数组）与节路径（AoT/表）都查。
- 违反 3 → `schema.py` 的 diff 遍历（`_apply_diff`、`_diff_config_aot`）或 `pydantic.py` 的快照基准。
- 违反 4 → 任何不经 `read_bytes()` 的读取路径，或含原始 `\r` 的生成字符串。

## 相关保证（弱于不变量，仍是契约）

- `dumps()` 幂等：`dumps(parse(dumps(doc))) == dumps(doc)`（编辑/回归套件断言）。
- 原子写：`Document.save` / `Config.save` 经 tempfile + `os.replace`——失败的保存绝不截断文件。
- 未触碰的 `dumps()` 近似 O(1)；编辑成本随编辑量而非文档长度伸缩（见[架构](architecture.md#保真为何逐字节成立)）。

变更触及核心模块（`parser`、`nodes`、`engine_set`、`render`、`schema`）时，为精确缺陷及其邻域新增或更新 pytest 用例，并重跑[验证](verification.md)全部门。
