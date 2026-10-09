# 技能：测试

测试套件如何组织、如何运行、新测试往哪放。

## 布局

| 路径 | 内容 |
|---|---|
| `tests/unit/` | 主题与回归文件（见下表）——套件主体 |
| `tests/property/` | 基于随机文档/随机变更的 Hypothesis 测试，覆盖四大不变量 |
| `tests/integration/` | 官方 toml-test 一致性套件；需要 `.toml-test/`（CI 拉取 v2.2.0），离线跳过 |
| `tests/corpus/` | 从 toml-test 1.5.0 内嵌的五个有效 TOML 1.1 文件，用于离线往返 |
| `scripts/bench/` | 手动基准脚本 + `BASELINE.md`；**不**被 pytest 收集 |

## 单测文件地图

| 文件 | 覆盖 |
|---|---|
| `test_api_030.py` | 0.3.0 公开面：路径文法、`Document` 映射协议、构造 API、注释寻址、扩展 `Config` |
| `test_api_modes.py` | `toml_version` / `none_value` 模式 |
| `test_compat.py` | tomllib 兼容入口 + 注释 API |
| `test_edit.py` | 编辑语义：脏拼接、pending 条目、删除、AoT |
| `test_pydantic.py` | 可选 `tomlclass.pydantic` 互操作（无 pydantic 时跳过） |
| `test_regressions_021*.py`（a–d） | 按修复批次归档的回归套件 |
| `test_roundtrip.py` | 往返公理：`dumps()` 逐字节一致 |
| `test_schema.py` | 模板、校验、load/save diff 语义 |
| `test_toml11.py` | TOML 1.1 新增语法 + 内嵌语料 |
| `test_update.py` | `tomlclass.update()` 与 `Document.set_path` |
| `test_user_scenarios.py` | 用户真实调用路径，语义 + 字节级断言 |
| `test_version.py` | 包元数据（`__version__`、`__all__` 一致性） |

## 运行

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto                                 # 全量
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""   # 3.10 门
uv run pytest tests/unit/test_edit.py -q --no-cov -p no:cacheprovider                      # 单文件
```

基线（2026-10）：离线 287 passed、6 skipped。skip 均为 toml-test 集成模块缺少 checkout——设计如此，属于绿。`-n auto` 与 CI 一致；排查偶发问题时去掉。

## 新测试去哪

1. **缺陷修复** → 对应的 `test_regressions_*` 批次文件；新批次开始时新建 `test_regressions_0XX.py`；覆盖精确缺陷**及其邻域**。
2. **新功能/API** → 主题文件（`test_api_030.py` 风格）或新建主题文件；含错误路径与 3.10 兼容性。
3. **不变量相邻的变更** → 若出现新节点类型或新变更类别，扩展 `tests/property/test_invariants.py` 的策略。

## 约定

- 测试需要 `tomllib` 且要兼容 3.10 时，用 `from tests._compat import tomllib`。
- 写 fixture 文件必须用 `write_bytes` 或 `write_text(..., newline="")`——绝不依赖平台换行翻译。
- 测试中的可变 schema 默认值带 `# noqa: RUF012` 并写明理由（可变默认值正是被测对象）。
- 测试注释客观描述行为——不写 issue 号、tracker ID 或 AI 审查标签。
- 新测试不得依赖网络；一致性数据来自钉版的 `.toml-test/` checkout 或内嵌语料。
