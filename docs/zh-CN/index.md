# tomlclass 文档

tomlclass 是一个 TOML 配置库：无损编辑引擎 + 类型化配置注解。零第三方依赖，Python ≥ 3.10。

两层各自独立可用：

- **引擎层** — 解析任意 TOML 1.0/1.1 文档，编辑后写回，所有注释、键顺序与格式细节一个字节都不动。
- **注解层** — 用 Python 类声明配置 schema，得到带注释的模板、聚合校验与 diff 写回。

## 60 秒上手

只改一个值，不碰其他任何内容：

```python
import tomlclass

tomlclass.update("app.toml", {"server.port": 9090})
# 只有这一行变了 —— 注释、顺序、格式全部保留
```

或者通过 schema 管理配置文件：

```python
from tomlclass import Config

class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")  # 解析 + 校验 + 合并默认值
server.port = 9090
server.save("server.toml")           # diff 写回：只写变化的键
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [引擎层](engine.md) | 解析、编辑、`update()`、注释 API、错误类型 |
| [配置注解](config.md) | schema 声明、模板、load/save 语义、校验错误 |
| [注释系统](comments.md) | 注释归属、注入模式 |
| [场景示例](examples.md) | 端到端场景：pyproject 安全更新、应用配置全流程、AoT、热重载 |
| [迁移](migration.md) | 从 tomlkit 迁移，以及从 tomlclass 0.2.x 升级 |

贡献者向：[技能](skills/index.md)（任务手册）与[参考](reference/index.md)（架构与事实表）。

## 安装

```bash
pip install tomlclass
```
