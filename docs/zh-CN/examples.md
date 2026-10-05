# 场景示例

以下代码均可直接复制运行。

## 编辑第三方 TOML（pyproject 类）

```python
import tomlclass

doc = tomlclass.parse(pyproject_text)

doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # 原位插入，"click" 的行尾注释保留
doc["tool"]["mytool"] = {"cache": True}              # 渲染为 [tool.mytool] 块
```

## 应用配置读写

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp) / "server.toml"
    cfg.write_text("port = 8080  # exposed\n", encoding="utf-8")

    server = Server.load(cfg)
    server.port = 9090
    server.save(cfg)
    # 结果：只有 port 一行变化，"# exposed" 注释保留
```

## 数组表（AoT）

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})             # 追加：渲染为新块
doc["products"] = [{"name": "sofa"}]                 # 整体替换：旧元素清除
```

## tomllib 迁移

```python
data = tomlclass.loads(text)   # 纯 dict（tomllib.loads 同约定）
data = tomlclass.load(fp)      # 二进制文件对象（tomllib.load 同约定）

# 需要无损编辑时升级到 Document：
doc = tomlclass.load("pyproject.toml")  # 路径入参 -> Document
```

## 环境变量覆盖与热更新

```python
# DEMO_SERVER__PORT=9000 覆盖 server.port
server = Server.load(cfg, env_prefix="DEMO")

# 热更新（可选依赖 watchfiles）；stop_event 可从其他线程停止
Server.watch("server.toml", callback, stop_event=event)
```

## schema 迁移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧键 -> 新点路径


new = AppV2.migrate(AppV1.load("app.toml"))
```
