# 验证门参考

每条必须通过的命令、实际检查什么、同一检查在 CI 哪个 job。工具链是 **uv**；所有命令在仓库根目录运行。

| 门 | 命令 | 检查 | CI job |
|---|---|---|---|
| 全量套件 | `uv run pytest tests -q --no-cov -p no:cacheprovider -n auto` | 全部 unit + property + integration 测试（integration 离线跳过） | `pytest-check`（7 平台矩阵，Python 3.10–3.14） |
| 3.10 门 | `uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""` | 单测套件在最低支持版本上可导入、可通过 | 由矩阵覆盖 |
| Lint | `uv run ruff check src/ tests/ scripts/` | 按 `pyproject.toml` 的 E/W/F/I/B/C4/UP/SIM/RET/PIE/RUF/PTH/PERF/FURB/PL/N | `ruff-check`（阻断式，PR 评论） |
| 类型 | `uv run basedpyright src/tomlclass` | 期望 0 错误；`pyproject.toml` 的晋升规则即契约 | `typecheck` |
| 一致性 | 全量套件带 `.toml-test/` checkout 时自动 | 官方 toml-test 双清单钉在 `TOML_TEST_REF`（v2.2.0）：1.0 严格 205/474，1.1 214/467 | 在 `pytest-check` 内拉取并运行 |
| 安全 | `uv export ... \| uvx pip-audit -r requirements-audit.txt --strict` | 锁定依赖审计 | `security-audit` |
| 基准（手动） | `uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500` | 解析/导出计时对比 tomli/tomlkit；结果归档 `scripts/bench/BASELINE.md` | 不在 CI |

## 值得记住的事实

- 离线基线（2026-10，本仓库，`-n auto`）：**287 passed、6 skipped**——skip 全是 toml-test 集成模块缺 checkout（设计如此，见 `tests/integration/test_toml_test.py` docstring）。3.10 门：281 passed、1 skipped。
- 3.10 门上的 `-o addopts=""` 剥掉仓库级 pytest addopts（coverage/timeout 配置假设主 venv）。
- `-n auto`（pytest-xdist）与 CI 一致；二分偶发测试时去掉。
- `.toml-test/` 与 `.zcode/` 只存在于工作区、永不提交（`.zcode/` 经 `.gitignore` 忽略；旧的 `.zcode/verify_*.py` 矩阵已不存在——属性测试 + 回归套件是其后继）。

## 发布附加

发布前另跑 `uv build` 确保 sdist/wheel 干净，并完成[发布](../skills/releasing.md)检查单。
