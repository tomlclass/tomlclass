# 场景示例

端到端场景；每个代码片段均可原样运行。

## 安全更新第三方 TOML（pyproject 风格）

只想在别的工具拥有的文件里改一个版本号或翻转一个开关 —— 又不想毁掉它的注释：

```python
import tomlclass

tomlclass.update("pyproject.toml", {
    "project.version": "1.0.0",
    "tool.mytool.cache": True,       # [tool.mytool] 不存在时自动创建
})
```

之后每一行未触碰的内容 —— 其他工具的注释、奇怪的空格、键顺序 —— 都逐字节不变。

需要更精细的操作时，直接用引擎：

```python
doc = tomlclass.load("pyproject.toml")

doc["project"]["dependencies"].append("rich>=13.0")  # 原位拼接，
                                                     # "click" 的注释保留
doc["tool"]["mytool"] = {"cache": True}              # 渲染为 [tool.mytool] 块
doc.save("pyproject.toml")
```

## 应用配置：从首次运行到稳定运行

典型的应用生命周期：首次运行发放带注释模板，后续运行校验并合并，写回只含变化。

```python
from pathlib import Path

from tomlclass import Config, Field

class Server(Config):
    """HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)


class App(Config):
    """Application configuration."""

    name: str = "demo"
    debug: bool = False
    server: Server


CONFIG = Path("app.toml")


def load_config() -> App:
    if not CONFIG.exists():
        CONFIG.write_text(App.template(), encoding="utf-8")  # 首次运行：带注释模板
    return App.load(CONFIG, env_prefix="APP")                # 校验 + 默认值 + 环境变量覆盖


app = load_config()
app.debug = True
app.save(CONFIG)  # diff 写回：只有 debug 变了；用户注释保留
```

用户填了非法值时会看到：

```
ValidationError: 1 validation error(s): server.port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

描述直接来自 schema docstring —— 错误指向文档化的约束，而不是只给一个数字。

## 完全可控的批量编辑

```python
import tomlclass

doc = tomlclass.load("app.toml")

doc.set_path("server.port", 9090)          # 修改；该行注释保留
doc.set_path("logging.level", "debug")     # 创建 [logging] 表
doc.set_comment("server.port", "exposed")  # 顺带替换注释
doc.save("app.toml")                       # 一次原子写
```

## 表数组（AoT）

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})  # 追加：渲染为新块
doc["products"] = [{"name": "sofa"}]      # 整体替换：旧元素移除
```

## tomllib 迁移

```python
data = tomlclass.loads(text)   # 纯 dict（约定与 tomllib.loads 一致）
data = tomlclass.load(fp)      # 二进制文件对象（约定与 tomllib.load 一致）

# 需要无损编辑时随时升级：
doc = tomlclass.load("pyproject.toml")  # 路径参数 -> Document
```

## 环境变量覆盖与热重载

```python
# APP_SERVER__PORT=9000 覆盖 server.port（__ 分隔路径段）
server = Server.load("server.toml", env_prefix="APP")

# 热重载（可选依赖 watchfiles）；stop_event 可从其他线程停止。
# 校验失败保留上一个可用实例并继续监听。
Server.watch("server.toml", callback, stop_event=event)
```

## Schema 迁移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧键 -> 新点号路径


new = AppV2.migrate(AppV1.load("app.toml"))
```
