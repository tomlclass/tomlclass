# 技能：更新文档

有哪些文档面、各自的结构约束、以及同步规则。

## 受维护的文档面

| 文档面 | 受众 | 语言规则 |
|---|---|---|
| `README.md` / `README.zh-CN.md` | 项目门面 | 互为镜像 |
| `README.pypi.md` | PyPI 页面 | 仅英文；用绝对 GitHub 链接（在仓库外渲染） |
| `docs/en/`、`docs/zh-CN/` | 用户文档 | 逐页镜像：`index`、`engine`、`config`、`comments`、`examples`、`migration` |
| `docs/skills/`、`docs/reference/` | 代理/贡献者手册与事实表 | `docs/en/` 是事实源；面向用户的内容保持 `docs/zh-CN/` 同步 |
| `CHANGELOG.md` | 发布日志 | 英文；结构见下 |

不存在其他语言——不要新建。

## 结构锁

- **README 顺序**固定：logo → 简介 → ErisPulse 来源说明 → 版本策略 → 徽章 → 能力（≤5 条，schema/config 层在前）→ "不适合"边界段 → 一致性与性能 → 安装 → 用法（先声明式 `Config`；后 parse/edit 与 `update()`）→ 文档 → 环境要求 → 许可证。语气客观，无营销话术。
- **engine.md** 必须保持 TOML 版本边界（默认 1.1、`toml_version="1.0"` 严格模式）与 None 处理（`none_value` 哨兵）两节在 `docs/en` 与 `docs/zh-CN` 间同步。
- **一致性数字**（205/474、214/467）钉在 `tests/integration/test_toml_test.py` 的 toml-test ref 与 CI 上。它们只与 `TOML_TEST_REF` 一起变更。
- **性能表**只能按 `scripts/bench/BASELINE.md` 的方法论重新实测后更新——绝不手改测量数字。

## CHANGELOG

`CHANGELOG.md` **由维护者撰写**：条目带 `@GithubUsername` 署名，且只记录用户可见的库行为变更。不要自行撰写条目——在交接中说明用户可见的变更，由维护者记录。纯文档与内部改动按该文件自身的 "No trivia" 规则不予记录。

维护者撰写时遵守文件自身的 "Writing rules"：

- 只记最终状态；不写过程；版本内修复并入所属特性条目；回滚不留痕；不记琐事；按主题合并；summary ≤ 3 句；条目署名 `@GithubUsername`；日期 `YYYY/MM/DD`。
- 发布翻转（`> Pending release` → `> Released` + 日期）只在[发布流程](releasing.md)中发生。

## skills/reference 文件

`docs/skills/` 的手册与 `docs/reference/` 的事实表描述仓库的真实状态。代码变更使其中陈述失效时，同一变更中更新该文件——过期的操作文档比没有更糟。交叉链接保持相对路径（`../reference/...`），保证从任何查看器都能用。

## 验证

纯文档变更也要过检查：

```bash
uv run ruff check src/ tests/ scripts/          # 未改动，但成本极低
git diff --stat                        # 确认只有预期文件变动
```

外加人工一遍：改过的每个代码片段原样可跑、从被编辑文件出发的每个站内链接可解析。
