[English](README.md) | **简体中文** | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>

# tomlclass

TOML 配置库：自研无损编辑引擎 + 类型化配置注解，零第三方依赖。

写回配置文件时保留全部注释与格式；用 Python 类声明配置结构，自动生成带注释的模板并完成校验。配置语义来自 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 框架的配置系统。

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

- **无损编辑引擎**：全类型 TOML 1.0 解析与写回，toml-test 1.0 全部 709 个用例通过；未编辑文档渲染与输入逐字节相同
- **类型化配置**：类声明 schema，docstring 生成模板注释，校验聚合报错，默认值只在内存合并、不写回文件
- **注释操作**：按键读取、替换、删除注释；schema 描述可注入为注释（三档策略）
- **tomllib 兼容**：`loads` / `load` 与标准库同约定，迁移零成本

## 为什么不用 tomlkit

tomlkit 是无损编辑的事实标准，本项目的引擎设计以其为对照基准。tomlclass 的优势：

| 维度 | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| 解析速度（同机实测） | 基准 | **快 5.8–6.4×** |
| 取纯 dict | 需 `parse(dumps(doc))` 往返 | `to_dict()` 直接构建，零往返 |
| 注释操作 | 埋在样式对象里，无按键 API | `doc.comment(key)` / `set_comment` 一等公民 |
| schema / 模板 / 校验 | 无，需自行拼装 | `Config` 内置（模板、聚合校验、env 覆盖、迁移） |
| 内存常驻 | 基准 | **0.67×** |

数据出处：[性能基线](tests/bench/BASELINE.md)（同机、同迭代次数实测）。

## 安装

```bash
pip install tomlclass
```

## 用法

### 编辑 TOML 文件

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # 原位插入，注释保留
text = doc.dumps()                                   # 只有所触碰的行发生变化
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


server = Server.load("server.toml")  # 读取 + 校验 + 默认值合并
server.port = 9000
server.save("server.toml")           # 只写回变化的键
```

## 文档

- [引擎层](docs/zh-CN/engine.md) — Document、编辑、tomllib 兼容、错误
- [注解层](docs/zh-CN/config.md) — Config、Field、视图语义、env 覆盖
- [注释系统](docs/zh-CN/comments.md) — 归属模型、读取与替换
- [场景示例](docs/zh-CN/examples.md) — 常见场景代码
- [性能](docs/zh-CN/performance.md) — 基线数据与实测对比

## 依赖与环境

Python ≥ 3.10，无第三方依赖。

## 许可证

[MIT](LICENSE)
