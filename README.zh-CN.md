[English](README.md) | **简体中文** | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

无损 TOML 编辑 + 类型化配置，装进同一个零依赖的包。

改配置文件里的一个值，不破坏任何一条注释；用 Python 类声明 schema，得到带注释的模板、聚合校验与 diff 写回。

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

- **无损编辑引擎**：全类型 TOML 1.0/1.1 解析与写回；709 个 toml-test 1.0 用例全部通过。未编辑文档渲染与输入逐字节相同
- **一行更新**：`tomlclass.update("app.toml", {"server.port": 9090})` —— 读取、修改、原子写回；其余地方的注释、顺序与格式全部保留
- **类型化配置**：用类声明 schema —— docstring 成为模板注释，校验聚合全部错误并附字段文档描述，默认值在内存合并、永不写回
- **注释操作**：按键读取、替换、删除注释；schema 描述可作为注释注入（三种策略）
- **tomllib 兼容**：`loads` / `load` 遵循标准库调用约定 —— 迁移零成本

## 为什么不用 tomlkit

tomlkit 是无损编辑的事实标准，本项目的引擎正是以它为基线打造的。tomlclass 赢在：

| 维度 | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| 解析速度（同机） | 基线 | **快 5.8–6.4×** |
| 获取纯 dict | `parse(dumps(doc))` 往返 | `to_dict()` 直接构建，零往返 |
| 注释操作 | 埋在样式对象里，无按键 API | `doc.comment(key)` / `set_comment` 一等公民 |
| Schema / 模板 / 校验 | 无 —— 自己组装 | 内置于 `Config`（模板、聚合校验、环境变量覆盖、迁移） |
| 常驻内存 | 基线 | **0.67×** |

来源：[性能基线](tests/bench/BASELINE.md)（同机、同迭代次数）。

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
