# 技能：修复缺陷

适用于测试失败、不变量被破坏或错误暴露的场景。方法：先根因，后动手——禁止补丁摞补丁（历史上的回归正是这么来的）。

## 1. 复现与定位

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto --tb=long -x
```

- 读失败信息中的文件/行号；打开 `src/tomlclass/` 下对应模块，确认它属于管线哪一环（`parser → nodes → engine_set/del → render → schema/pydantic`）。
- 动手前先双向追溯：渲染 bug 可能是 parser span 的锅，schema bug 可能是引擎变更的锅。

## 2. 先对号不变量

提假设之前，先对照四大不变量（见[不变量参考](../reference/invariants.md)）——本仓库绝大多数缺陷是其中之一：

| 症状 | 可疑环节 | 典型成因 |
|---|---|---|
| 输出中未修改的文本变了 | render / parser | span 漂移、节点被误标 dirty |
| 注释丢失或重复 | render / `nodes.py` | trivia 未随行携带或被重复挂载 |
| schema 默认值泄漏进文件 | `schema.py` diff 遍历 | 快照比对基准错误 |
| CRLF 变 LF（或 `\r` 原样写入） | 加载 / render | 换行翻译、生成字符串未转义 `\r` |

## 3. 先写失败测试

核心模块（`parser`、`nodes`、`engine_set`、`render`、`schema`）的变更必须有 pytest 用例覆盖**精确缺陷及其邻域**（同一代码路径、相邻节点类型、边界值）。归档到对应的 `tests/unit/test_regressions_*` 或主题文件——见[测试技能](testing.md)。

## 4. 在架构层修复

- 把缺陷修在它所在的管线环节，而不是症状出现的地方。
- 所有 `Table`/`Array` 变更器必须继续经由引擎钩子（`engine_set`/`engine_del`）——绝不用裸 dict/list 写入绕过它。
- 不许在库代码里为某个测试输入开特例。

## 5. 验证全链路

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto      # 全量套件
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""   # 3.10 门
uv run ruff check src/ tests/ scripts/
uv run basedpyright src/tomlclass
```

四项必须全绿。数组/AoT 相关的重度修复，另跑 `tests/unit/test_roundtrip.py`、`test_edit.py`、`test_regressions_021d.py`——它们断言各级嵌套下的幂等双 `dumps()` 与原位拼接行为。

## 6. 记录结果

- 用户可见的修复 → 按当前版本条目写入 `CHANGELOG.md`（见[更新文档](updating-docs.md)）。
- 若修复使某条文档或本手册的陈述失效，同一变更中同步更新该文档。
