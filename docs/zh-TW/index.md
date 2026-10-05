# tomlclass 文件

tomlclass 是 TOML 設定庫：無損編輯引擎 + 類型化設定註解，零第三方依賴。

寫回設定檔時保留全部註解與格式；用 Python 類別宣告設定結構，自動完成範本產生與校驗。設定語義來自 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 框架的設定系統。

## 文件導航

| 文件 | 內容 |
|---|---|
| [引擎層](engine.md) | Document、編輯、tomllib 相容、錯誤 |
| [註解層](config.md) | Config、Field、視圖語義、env 覆寫 |
| [註解系統](comments.md) | 歸屬模型、讀取與替換 |
| [場景示例](examples.md) | 常見場景程式碼 |
| [效能](performance.md) | 基線資料與實測對比 |

## 安裝

```bash
pip install tomlclass
```

Python ≥ 3.10，無第三方依賴。

## 最小示例

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
text = doc.dumps()  # 只有所觸碰的行發生變化
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
