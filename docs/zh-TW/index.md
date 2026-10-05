# tomlclass 文件

tomlclass 是一個 TOML 設定庫：無損編輯引擎加上類型化設定註解。零第三方依賴，Python ≥ 3.10。

兩個分層，各自可獨立使用：

- **引擎層** —— 解析任意 TOML 1.0 文件、編輯後寫回，每一條註解、鍵順序與各種格式癖好都完好保留。
- **註解層** —— 以 Python 類別宣告設定 schema，獲得帶註解的範本、聚合驗證與基於 diff 的寫回。

## 60 秒快速導覽

只改一個值，其餘完全不動：

```python
import tomlclass

tomlclass.update("app.toml", {"server.port": 9090})
# only that line changed — comments, ordering and formatting all intact
```

或透過 schema 管理設定檔：

```python
from tomlclass import Config

class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")  # parse + validate + merge defaults
server.port = 9090
server.save("server.toml")           # diff write-back: only changed keys are written
```

## 目錄

| 文件 | 內容 |
|---|---|
| [引擎層](engine.md) | 解析、編輯、`update()`、註解 API、錯誤 |
| [配置註解](config.md) | schema 宣告、範本、載入/儲存語義、驗證錯誤 |
| [註解系統](comments.md) | 註解歸屬、注入模式 |
| [情境範例](examples.md) | 端到端情境：pyproject 更新、應用設定生命週期、AoT（表陣列）、熱重載 |
| [效能](performance.md) | 實測基線與測量方法 |

## 安裝

```bash
pip install tomlclass
```
