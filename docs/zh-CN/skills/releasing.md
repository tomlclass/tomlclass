# 技能：发布

发版流程。**发布需要用户明确批准——未经批准绝不创建 GitHub Release 或 tag。**

## 发布门（全部必须绿）

1. `uv run pytest tests -q --no-cov -p no:cacheprovider -n auto` —— 全量套件
2. `uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""` —— 3.10 门（多个版本曾带着 3.10 独有导入 bug 发布；这道门因它们而设）
3. `uv run ruff check src/ tests/ scripts/` 与 `uv run basedpyright src/tomlclass` —— 全净
4. 引擎有变更时必做：重跑基准并按其方法论更新 `scripts/bench/BASELINE.md` 与 README 性能表。

## 发布前检查单

- [ ] 版本号在 `pyproject.toml`（`[project].version`）与 `src/tomlclass/__init__.py`（`__version__`）**两处**定稿——`test_version.py` 钉住两者一致。
- [ ] `CHANGELOG.md` 当前条目：按主题合并（只记最终状态），用户批准后把 `> Pending release` 翻转为 `> Released` 并定日期。
- [ ] 文档面已更新（README 双语镜像、`docs/en` + `docs/zh-CN`、含破坏性变更时更新 migration 页）。
- [ ] `uv build` 产出干净的 sdist/wheel（打 tag 前的合理性检查）。

## 发布流程

1. 取得用户对发布的明确批准。
2. 提交发布状态（一个主题：本次发布）。
3. 在 `main` 上创建 GitHub Release/tag——触发 `.github/workflows/pypi-publish.yml`（监听 `release` 事件与 `workflow_dispatch`），自动发布 PyPI。无需手动 `twine`。
4. 确认 CI 绿、新版本出现在 PyPI。

## 发布前后的 git 流

- 默认：常规分段提交，一次一个主题，单行标题，不 amend、不强推。
- 待发布 squash 模式（历史收敛进唯一 `init` 提交后强推）**仅在用户明确要求**该发布使用时执行。

## 发布之后

- 第一个发布后变更落地时，在 `CHANGELOG.md` 开出新条目 `## [x.y.z] - Pending`。
- 引擎有变更且 `BASELINE.md` 的预算过期时，安排重新基线化（见其 "Re-baselining" 说明）。
