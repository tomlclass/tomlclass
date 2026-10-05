# 情境範例

端到端情境；每個程式碼片段都可原樣執行。

## 安全地更新第三方 TOML（pyproject 風格）

你只想在別的工具擁有的檔案裡調一個版本號或翻轉一個開關——而不毀掉它的註解：

```python
import tomlclass

tomlclass.update("pyproject.toml", {
    "project.version": "1.0.0",
    "tool.mytool.cache": True,       # creates [tool.mytool] if absent
})
```

之後每一行未觸碰的內容——其他工具的註解、奇怪的空白、鍵順序——都逐位元組不變。

需要更精細的手術時，直接使用引擎層：

```python
doc = tomlclass.load("pyproject.toml")

doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, the
                                                     # "click" comment survives
doc["tool"]["mytool"] = {"cache": True}              # rendered as a [tool.mytool] block
doc.save("pyproject.toml")
```

## 應用設定：從首次執行到穩定狀態

典型的應用程式生命週期：首次執行時寫出帶註解的範本，之後的執行進行驗證與合併，只寫回變更過的內容。

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
        CONFIG.write_text(App.template(), encoding="utf-8")  # first run: commented template
    return App.load(CONFIG, env_prefix="APP")                # validate + defaults + env overrides


app = load_config()
app.debug = True
app.save(CONFIG)  # diff write-back: only debug changed; user comments survive
```

值無效時使用者看到的內容：

```
ValidationError: 1 validation error(s): server.port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

描述直接來自 schema docstring——錯誤訊息指向文件中記載的約束，而不只是一個數字。

## 完全掌控的批次編輯

```python
import tomlclass

doc = tomlclass.load("app.toml")

doc.set_path("server.port", 9090)          # change; comment on that line survives
doc.set_path("logging.level", "debug")     # creates the [logging] table
doc.set_comment("server.port", "exposed")  # replace the comment too
doc.save("app.toml")                       # one atomic write
```

## 表陣列（AoT）

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})  # append: rendered as a new block
doc["products"] = [{"name": "sofa"}]      # whole replace: old elements removed
```

## tomllib 遷移

```python
data = tomlclass.loads(text)   # plain dict (same convention as tomllib.loads)
data = tomlclass.load(fp)      # binary file object (same convention as tomllib.load)

# Upgrade to lossless editing when needed:
doc = tomlclass.load("pyproject.toml")  # path argument -> Document
```

## env 覆寫與熱重載

```python
# APP_SERVER__PORT=9000 overrides server.port (__ separates path segments)
server = Server.load("server.toml", env_prefix="APP")

# Hot reload (optional dependency watchfiles); stop_event stops from another thread.
# Validation failures keep the previous good instance and watching continues.
Server.watch("server.toml", callback, stop_event=event)
```

## schema 遷移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
