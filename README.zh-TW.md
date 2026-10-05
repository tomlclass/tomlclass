[English](README.md) | [简体中文](README.zh-CN.md) | **繁體中文** | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

一個零依賴套件，同時提供無損 TOML 編輯與類型化設定。

改動設定檔裡的一個值而不弄壞任何一條註解；以 Python 類別宣告 schema，獲得帶註解的範本、聚合驗證與基於 diff 的寫回。

> **版本說明**：tomlclass 尚處於 1.0 之前，暫未嚴格遵循語意化版本。在專案穩定之前，次版本號更新可能包含新增 API —— 但既有 API 始終保持向後相容。

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

- **無損編輯引擎**：TOML 1.0/1.1 解析與寫回；toml-test 1.5.0 有效測試 **187/187 滿分，唯一達成的庫**。未觸碰的文件渲染結果與輸入逐位元組一致
- **TOML 1.1 版本調控**：`\e` / `\x` 轉義、省略秒的時間、內聯表換行與尾逗號、非 ASCII 裸鍵 —— 預設開啟；向 `parse` / `loads` / `load` / `update` / `Config.load` 傳 `toml_version="1.0"` 即得嚴格的 1.0 拒絕語義
- **None 由你定義**：可選的 rtoml 風格 `none_value` 哨兵 —— `dumps(data, none_value="@None")` 與 `loads(text, none_value="@None")` 讓 None 經 TOML 字串無損往返
- **一行更新**：`tomlclass.update("app.toml", `tomlclass.update("app.toml", {"server.port": 9090})`)` —— 讀取、修改、原子寫回；其餘位置的註解、順序與格式全部保留
- **型別化配置**：用類別宣告 schema —— docstring 成為範本註解，驗證聚合全部錯誤並附欄位文件描述，預設值在記憶體合併、永不寫回
- **註解操作**：按鍵讀取、替換、刪除註解；schema 描述可作為註解注入（三種策略）
- **tomllib 相容**：`loads` / `load` 遵循標準庫呼叫慣例 —— 遷移零成本

> **TOML 版本邊界**：上述 1.1 新增特性預設接受。若你的程式碼依賴*拒絕* 1.0 非法輸入（如 `13:37` 時間），切換到 `toml_version="1.0"` —— 同樣的檔案將拋出 `TOMLParseError`。

## 合規與效能

資料來自 [toml-bench](https://github.com/pwwang/toml-bench)（toml-test 1.5.0 + CPython tomllib 測試資料；速度為同機 5000 次迭代的 load/dump，tomlclass 0.2.0 —— 方法論見[效能基線](tests/bench/BASELINE.md)）：

| 校驗 | tomlclass 0.2.0 |
|---|---|
| toml-test 1.5.0 valid（187 個檔案） | **187/187 —— 唯一滿分的庫** |
| toml-test 1.5.0 TOML-1.1 清單（548 個檔案） | **548/548** |
| CPython tomllib 測試資料 | **12/12 valid，50/50 invalid** |

速度（load / dump，5000 次迭代）：

| 函式庫 | rtoml 語料 | tomli 語料 |
|---|---|---|
| rtoml 0.11（Rust） | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib（CPython） | 3.39s / — | 2.15s / — |
| **tomlclass 0.2.0** | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

無損編輯的記帳成本：loads 約為 tomli 的 2.5–2.8 倍，dumps 約為 tomli_w 的 2.6–3.2 倍 —— 但比 tomlkit 快 12–14 倍。

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
