[English](README.md) | [简体中文](README.zh-CN.md) | **繁體中文** | [日本語](README.ja.md) | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>

# tomlclass

TOML 設定庫：自研無損編輯引擎 + 類型化設定註解，零第三方依賴。

寫回設定檔時保留全部註解與格式；用 Python 類別宣告設定結構，自動產生帶註解的範本並完成校驗。設定語義來自 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 框架的設定系統。

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

- **無損編輯引擎**：全型別 TOML 1.0 解析與寫回，toml-test 1.0 全部 709 個用例通過；未編輯文件渲染與輸入逐位元組相同
- **類型化設定**：類別宣告 schema，docstring 產生範本註解，校驗聚合報錯，預設值只在記憶體合併、不寫回檔案
- **註解操作**：按鍵讀取、替換、刪除註解；schema 描述可注入為註解（三檔策略）
- **tomllib 相容**：`loads` / `load` 與標準庫同約定，遷移零成本

## 為什麼不用 tomlkit

tomlkit 是無損編輯的事實標準，本專案的引擎設計以其為對照基準。tomlclass 的優勢：

| 維度 | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| 解析速度（同機實測） | 基準 | **快 5.8–6.4×** |
| 取純 dict | 需 `parse(dumps(doc))` 往返 | `to_dict()` 直接構建，零往返 |
| 註解操作 | 埋在樣式物件裡，無按鍵 API | `doc.comment(key)` / `set_comment` 一等公民 |
| schema / 範本 / 校驗 | 無，需自行拼裝 | `Config` 內建（範本、聚合校驗、env 覆寫、遷移） |
| 記憶體常駐 | 基準 | **0.67×** |

數據出處：[效能基線](tests/bench/BASELINE.md)（同機、同迭代次數實測）。

## 安裝

```bash
pip install tomlclass
```

## 用法

### 編輯 TOML 檔案

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # 原位插入，註解保留
text = doc.dumps()                                   # 只有所觸碰的行發生變化
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


server = Server.load("server.toml")  # 讀取 + 校驗 + 預設值合併
server.port = 9000
server.save("server.toml")           # 只寫回變化的鍵
```

## 文件

- [引擎層](docs/zh-TW/engine.md) — Document、編輯、tomllib 相容、錯誤
- [註解層](docs/zh-TW/config.md) — Config、Field、視圖語義、env 覆寫
- [註解系統](docs/zh-TW/comments.md) — 歸屬模型、讀取與替換
- [場景示例](docs/zh-TW/examples.md) — 常見場景程式碼
- [效能](docs/zh-TW/performance.md) — 基線資料與實測對比

## 依賴與環境

Python ≥ 3.10，無第三方依賴。

## 授權

[MIT](LICENSE)
