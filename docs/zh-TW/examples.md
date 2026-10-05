# 場景示例

以下程式碼均可直接複製執行。

## 編輯第三方 TOML（pyproject 類）

```python
import tomlclass

doc = tomlclass.parse(pyproject_text)

doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # 原位插入，"click" 的行尾註解保留
doc["tool"]["mytool"] = {"cache": True}              # 渲染為 [tool.mytool] 區塊
```

## 應用配置讀寫

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
    # 結果：只有 port 一行變化，"# exposed" 註解保留
```

## 陣列表（AoT）

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})             # 追加：渲染為新區塊
doc["products"] = [{"name": "sofa"}]                 # 整體替換：舊元素清除
```

## tomllib 遷移

```python
data = tomlclass.loads(text)   # 純 dict（tomllib.loads 同約定）
data = tomlclass.load(fp)      # 二進位檔案物件（tomllib.load 同約定）

# 需要無損編輯時升級到 Document：
doc = tomlclass.load("pyproject.toml")  # 路徑入參 -> Document
```

## 環境變數覆寫與熱更新

```python
# DEMO_SERVER__PORT=9000 覆寫 server.port
server = Server.load(cfg, env_prefix="DEMO")

# 熱更新（可選依賴 watchfiles）；stop_event 可從其他執行緒停止
Server.watch("server.toml", callback, stop_event=event)
```

## schema 遷移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 舊鍵 -> 新點路徑


new = AppV2.migrate(AppV1.load("app.toml"))
```
