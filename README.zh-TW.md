[English](README.md) | [简体中文](README.zh-CN.md) | **繁體中文** | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

一個零依賴套件，同時提供無損 TOML 編輯與類型化設定。

改動設定檔裡的一個值而不弄壞任何一條註解；以 Python 類別宣告 schema，獲得帶註解的範本、聚合驗證與基於 diff 的寫回。

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

- **無損編輯引擎**：全型別 TOML 1.0/1.1 解析與寫回；toml-test 1.0 全部 709 個用例通過。未觸碰的文件渲染結果與輸入逐位元組一致
- **一行式更新**：`tomlclass.update("app.toml", {"server.port": 9090})` —— 讀取、修改、原子寫回；其餘每一處的註解、順序與格式都原樣保留
- **類型化設定**：以類別宣告 schema —— docstring 成為範本註解，驗證聚合全部錯誤並附上每個欄位在文件中記載的意圖，預設值只在記憶體合併、永不寫回
- **註解操作**：按鍵讀取、替換與刪除註解；schema 描述可注入為註解（三種策略）
- **tomllib 相容**：`loads` / `load` 遵循標準庫呼叫約定 —— 遷移零成本

## 為什麼不用 tomlkit

tomlkit 是無損編輯的事實標準，本專案的引擎正是以它為對照基準而構建。tomlclass 勝出的地方：

| 維度 | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| 解析速度（同一台機器） | 基準 | **快 5.8–6.4×** |
| 取得純 dict | `parse(dumps(doc))` 往返 | `to_dict()` 直接構建，零往返 |
| 註解操作 | 埋在樣式物件裡，沒有按鍵級 API | `doc.comment(key)` / `set_comment` 一等公民 |
| schema / 範本 / 驗證 | 無 —— 自行拼裝 | `Config` 內建（範本、聚合驗證、env 覆寫、遷移） |
| 常駐記憶體 | 基準 | **0.67×** |

資料來源：[效能基線](tests/bench/BASELINE.md)（同一台機器、相同迭代次數）。

## 安裝

```bash
pip install tomlclass
```

## 用法

### 只改一個值，其餘全部保留

```python
import tomlclass

tomlclass.update("pyproject.toml", {"project.version": "1.0.0"})
# only that line changed — comments, ordering and formatting all intact
```

### 編輯 TOML 檔案（完全掌控）

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # spliced in place, comments kept
text = doc.dumps()                                   # only touched lines change
```

### 宣告式設定

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


server = Server.load("server.toml")  # read + validate + merge defaults
server.port = 9000
server.save("server.toml")           # only changed keys are written
```

## 文件

- [引擎層](docs/zh-TW/engine.md) —— 解析、編輯、`update()`、註解 API、錯誤
- [配置註解](docs/zh-TW/config.md) —— schema 宣告、範本、載入/儲存語義、驗證錯誤
- [註解系統](docs/zh-TW/comments.md) —— 註解歸屬、注入模式
- [情境範例](docs/zh-TW/examples.md) —— 端到端情境
- [效能](docs/zh-TW/performance.md) —— 實測基線

## 環境需求

Python ≥ 3.10，無第三方依賴。

## 授權條款

[MIT](LICENSE)
