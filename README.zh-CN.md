[English](README.md) | **简体中文** | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

无损 TOML 编辑 + 类型化配置，装进同一个零依赖的包。

改配置文件里的一个值，不破坏任何一条注释；用 Python 类声明 schema，得到带注释的模板、聚合校验与 diff 写回。

> **版本说明**：tomlclass 尚处于 1.0 之前，暂未严格遵循语义化版本。在项目稳定之前，次版本号更新可能包含新增 API —— 但既有 API 始终保持向后兼容。

<p>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/pypi/v/tomlclass?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/tomlclass/actions/workflows/code-quality-check.yml"><img src="https://img.shields.io/github/actions/workflow/status/wsu2059q/tomlclass/code-quality-check.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/tomlclass/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge" alt="Ruff"></a>
</p>

<br clear="both">

---

## 特性

- **无损编辑引擎**：TOML 1.0/1.1 解析与写回；toml-test 1.5.0 有效测试 **187/187 满分，唯一达成的库**。未编辑文档渲染与输入逐字节相同
- **TOML 1.1 版本调控**：`\e` / `\x` 转义、省略秒的时间、内联表换行与尾逗号、非 ASCII 裸键 —— 默认开启；向 `parse` / `loads` / `load` / `update` / `Config.load` 传 `toml_version="1.0"` 即得严格的 1.0 拒绝语义
- **None 由你定义**：可选的 rtoml 风格 `none_value` 哨兵 —— `dumps(data, none_value="@None")` 与 `loads(text, none_value="@None")` 让 None 经 TOML 字符串无损往返
- **一行更新**：`tomlclass.update("app.toml", `tomlclass.update("app.toml", {"server.port": 9090})`)` —— 读取、修改、原子写回；其余位置的注释、顺序与格式全部保留
- **类型化配置**：用类声明 schema —— docstring 成为模板注释，校验聚合全部错误并附字段文档描述，默认值在内存合并、永不写回
- **注释操作**：按键读取、替换、删除注释；schema 描述可作为注释注入（三种策略）
- **tomllib 兼容**：`loads` / `load` 遵循标准库调用约定 —— 迁移零成本

> **TOML 版本边界**：上述 1.1 新增特性默认接受。若你的代码依赖*拒绝* 1.0 非法输入（如 `13:37` 时间），切换到 `toml_version="1.0"` —— 同样的文件将抛出 `TOMLParseError`。

## 合规与性能

数据来自 [toml-bench](https://github.com/pwwang/toml-bench)（toml-test 1.5.0 + CPython tomllib 测试数据；速度为同机 5000 次迭代的 load/dump，tomlclass 0.2.0 —— 方法论见[性能基线](tests/bench/BASELINE.md)）：

| 校验 | tomlclass 0.2.0 |
|---|---|
| toml-test 1.5.0 valid（187 个文件） | **187/187 —— 唯一满分的库** |
| toml-test 1.5.0 TOML-1.1 清单（548 个文件） | **548/548** |
| CPython tomllib 测试数据 | **12/12 valid，50/50 invalid** |

速度（load / dump，5000 次迭代）：

| 库 | rtoml 语料 | tomli 语料 |
|---|---|---|
| rtoml 0.11（Rust） | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib（CPython） | 3.39s / — | 2.15s / — |
| **tomlclass 0.2.0** | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

无损编辑的记账成本：loads 约为 tomli 的 2.5–2.8 倍，dumps 约为 tomli_w 的 2.6–3.2 倍 —— 但比 tomlkit 快 12–14 倍。

## 安装

```bash
pip install tomlclass
```

## 用法

### 只改一个值，其他全保留

```python
import tomlclass

tomlclass.update("pyproject.toml", {"project.version": "1.0.0"})
# 只有这一行变了 —— 注释、顺序、格式全部原样
```

### 编辑 TOML 文件（完全可控）

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # 原位拼接，注释保留
text = doc.dumps()                                   # 只改动触碰的行
```

### 声明式配置

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = 8000


server = Server.load("server.toml")  # 读取 + 校验 + 合并默认值
server.port = 9000
server.save("server.toml")           # 只写变化的键
```

## 文档

- [引擎层](docs/zh-CN/engine.md) — 解析、编辑、`update()`、注释 API、错误类型
- [配置注解](docs/zh-CN/config.md) — schema 声明、模板、load/save 语义、校验错误
- [注释系统](docs/zh-CN/comments.md) — 注释归属、注入模式
- [场景示例](docs/zh-CN/examples.md) — 端到端场景
- [性能](docs/zh-CN/performance.md) — 实测基线

## 环境要求

Python ≥ 3.10，无第三方依赖。

## 许可证

[MIT](LICENSE)
