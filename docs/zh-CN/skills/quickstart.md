# 技能：快速上手

进入本仓库的前十五分钟：把工具链跑绿、认路、完成第一次安全改动。

## 0. 前置条件

Git 与 [uv](https://docs.astral.sh/uv/) —— uv 自己管理 Python 工具链（3.10+），不需要折腾虚拟环境。别无他物：本库零运行时依赖；extras 负责拉取 pytest、ruff、basedpyright。

## 1. 绿色基线（约两分钟）

```bash
uv sync --extra test --extra lint
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto
```

干净检出的预期（2026-10）：**287 passed、6 skipped**。6 个 skip 是 toml-test 一致性模块在没有 `.toml-test/` checkout 时跳过——设计如此，不是失败。

交付前的完整四门：

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto                                 # 全量套件
uv run ruff check src/ tests/ scripts/                                                      # Lint
uv run basedpyright src/tomlclass                                                           # 类型
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""    # 3.10 门
```

二分偶发测试时去掉 `-n auto`。3.10 门是强制的——多个版本曾带着 3.10 独有导入 bug 发布。

## 2. 六十秒认路

| 你想改… | 去哪 |
|---|---|
| 接受哪些 TOML 语法 | `src/tomlclass/parser.py` |
| 节点/编辑语义、一次变更会动什么 | `src/tomlclass/nodes.py`、`src/tomlclass/engine_set.py` |
| 被编辑的输出如何渲染 | `src/tomlclass/render.py` |
| `Document` API、路径文法、`dumps`/`save` | `src/tomlclass/_document.py` |
| schema、`Config`/`Field`、校验、diff 写回 | `src/tomlclass/schema.py`（pydantic 互操作：`pydantic.py`） |
| 错误类型与消息 | `src/tomlclass/errors.py` |
| 测试 | `tests/unit/`（主题 + 回归）、`tests/property/`（不变量）、`tests/integration/`（一致性） |
| 基准 | `scripts/bench/` —— 手动工具，pytest 与 CI 都不会跑它 |
| 用户文档 | `docs/en/` **和** `docs/zh-CN/` —— 永远两边一起改 |

结构细节见[架构](../reference/architecture.md)。

## 3. 绝不能破的四条铁律

1. **往返公理**：未修改文档的 `dumps()` 与源文本逐字节一致。
2. **注释保留**：注释、顺序与格式在每次读-改-存循环中存活。
3. **默认值不落盘**：内存中的 schema 默认值绝不写入文件。
4. **CRLF 保真**：读取不做换行翻译；生成行遵循文件自身的换行。

外加路由规则：所有 `Table`/`Array` 变更器必须经由引擎钩子（`engine_set`/`engine_del`）——裸 dict/list 写入会让内存与输出分叉。完整说明见[不变量](../reference/invariants.md)。

## 4. 你的第一次改动（端到端）

1. 复现：`uv run pytest tests -q --no-cov -p no:cacheprovider --tb=long -x`（或先写失败用例）。
2. 定位缺陷所属的管线环节，而不是症状出现的位置——见[修复缺陷](fixing-defects.md)。
3. 在该环节修复；禁止补丁摞补丁。
4. 为精确缺陷**及其邻域**补 pytest 用例——见[测试](testing.md)。
5. 跑上面四门；必须全净。
6. 受影响文档双语同步更新，用户可见变更写 `CHANGELOG.md`——见[更新文档](updating-docs.md)。
7. 提交：一个主题、单行标题；除非用户要求，不 amend、不强推——见 `AGENTS.md`。

## 5. 会浪费一下午的坑

| 坑 | 现实 |
|---|---|
| `.venv/Scripts/python.exe`（旧文档、旧习惯） | 仓库里没有 `.venv`——一切走 `uv run …` |
| 去 `tests/` 底下找基准脚本 | 已迁到 `scripts/bench/`；它是手动工具，不是测试 |
| 去翻 `.zcode/verify_*.py` 矩阵 | 已不存在；属性测试 + 回归套件是其后继 |
| 在需兼容 3.10 的测试里 `import tomllib` | 用 `from tests._compat import tomllib` |
| 用 `write_text(text)` 写 fixture | 用 `write_bytes` 或 `write_text(..., newline="")`——翻译会掩盖 CRLF 缺陷 |
| 新增变更器直接改底层 dict/list | 必须经 `engine_set`/`engine_del` 路由，否则内存与输出分叉 |
| 只改 `docs/en/` | `docs/zh-CN/` 同步维护 |
| 手改性能表里的数字 | 那些数字是实测值；重跑 `scripts/bench/bench.py` 并遵循 `scripts/bench/BASELINE.md` |

## 6. 接下来去哪

| | |
|---|---|
| 手册 | [修复缺陷](fixing-defects.md) · [扩展 API](extending-api.md) · [测试](testing.md) · [更新文档](updating-docs.md) · [发布](releasing.md) |
| 事实表 | [架构](../reference/architecture.md) · [不变量](../reference/invariants.md) · [验证门](../reference/verification.md) · [API 面](../reference/api-surface.md) |
| 仓库规则 | 根目录 `AGENTS.md` |
