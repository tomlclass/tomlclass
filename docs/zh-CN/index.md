# tomlclass 文档

tomlclass 是 TOML 配置库：无损编辑引擎 + 类型化配置注解，零第三方依赖。

写回配置文件时保留全部注释与格式；用 Python 类声明配置结构，自动完成模板生成与校验。配置语义来自 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 框架的配置系统。

## 文档导航

| 文档 | 内容 |
|---|---|
| [引擎层](engine.md) | Document、编辑、tomllib 兼容、错误 |
| [注解层](config.md) | Config、Field、视图语义、env 覆盖 |
| [注释系统](comments.md) | 归属模型、读取与替换 |
| [场景示例](examples.md) | 常见场景代码 |
| [性能](performance.md) | 基线数据与实测对比 |

## 安装

```bash
pip install tomlclass
```

Python ≥ 3.10，无第三方依赖。

## 最小示例

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
text = doc.dumps()  # 只有所触碰的行发生变化
```

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")
server.port = 9000
server.save("server.toml")
```
