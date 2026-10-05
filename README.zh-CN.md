[English](README.md) | **简体中文**

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

TOML 1.0/1.1 解析库：无损编辑 + 类型化配置。

解析产出可编辑的文档树：未修改的内容字节级往返，编辑只重写触碰的行——注释、顺序与格式全部保留。在此之上，用 Python 类声明 schema 即可获得带注释的模板、聚合校验与 diff 写回。

配置语义源自 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 框架的配置系统。

> **版本说明**：1.0 之前。次版本更新可能新增 API；既有 API 保持向后兼容。

<p>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/pypi/v/tomlclass?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/tomlclass/actions/workflows/code-quality-check.yml"><img src="https://img.shields.io/github/actions/workflow/status/wsu2059q/tomlclass/code-quality-check.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/tomlclass/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge" alt="Ruff"></a>
</p>

<br clear="both">

---

## 能力

- **无损编辑** —— 未修改内容字节级往返；编辑只重写触碰的行。toml-test 1.5.0 有效测试 187/187
- **TOML 1.1 语义可选** —— 默认启用 1.1 规则；`toml_version="1.0"` 恢复严格的 1.0 拒绝语义
- **类型化配置** —— 用类声明 schema：带注释模板、聚合校验、diff 写回、env 覆盖
- **注释访问** —— 按键读取、替换、删除注释；可选注入 schema 描述
- **tomllib 兼容入口** —— `loads` / `load` 遵循标准库调用约定

**不适合** 只需把 TOML 读成字典、追求极致速度的场景——那请用标准库 [tomllib](https://docs.python.org/3/library/tomllib.html) 或 [tomli](https://github.com/hukkin/tomli)。tomlclass 以部分解析速度（当前硬件上约为 tomllib 的 1.5 倍以内）换取可编辑性与 schema 工具。

## 合规与性能

数据来自 [toml-bench](https://github.com/pwwang/toml-bench)（toml-test 1.5.0 + CPython tomllib 测试数据；速度为同机 5000 次迭代的 load/dump，tomlclass 0.2.1 —— 方法论见[性能基线](tests/bench/BASELINE.md)）：

| 校验 | 结果 |
|---|---|
| toml-test 1.5.0 valid（187 个文件） | 187/187 |
| toml-test 1.5.0 TOML-1.1 清单（548 个文件） | 548/548 |
| CPython tomllib 测试数据 | 12/12 valid，50/50 invalid |

速度（load / dump，5000 次迭代）：

| 库 | rtoml 语料 | tomli 语料 |
|---|---|---|
| rtoml 0.11（Rust） | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib（CPython） | 3.39s / — | 2.15s / — |
| **tomlclass 0.2.1** | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

## 安装

```bash
pip install tomlclass
```

## 用法

### 解析并编辑

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # 原位拼接，注释保留
text = doc.dumps()                                   # 只有触碰的行变化
```

### 一行更新键值

```python
tomlclass.update("pyproject.toml", {"project.version": "1.0.0", "tool.x.y": True})
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

- [引擎层](docs/zh-CN/engine.md) —— 解析、编辑、版本选择、注释 API、错误、边界
- [配置注解](docs/zh-CN/config.md) —— schema 声明、模板、load/save 语义、校验
- [注释系统](docs/zh-CN/comments.md) —— 注释归属、注入模式
- [场景示例](docs/zh-CN/examples.md) —— 端到端场景
- [性能](docs/zh-CN/performance.md) —— 实测基线

## 环境要求

Python ≥ 3.10，无第三方依赖。

## 许可证

[MIT](LICENSE)
