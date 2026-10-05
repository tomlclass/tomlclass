# 註解層

用類別宣告設定結構：docstring 即範本註解，讀取時校驗，寫回時只動變化的鍵。

## 宣告

```python
from tomlclass import Config, Field

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


class App(Config):
    name: str = Field("demo", ge=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- docstring 首段 → 表註解；`欄位名:` 分節 → 鍵上方註解（範本中渲染為 `#` 行）
- 巢狀類別 = 巢狀表；`list[T]` 支援元素校驗；底線前綴欄位排除
- `Field` 約束：`ge / le / gt / lt / pattern / min_length / max_length / coerce`
- 欄位描述支援 i18n 字典：`Field(description={"i18n": key, "default": text})`

## 入口

```python
app = App()                        # 純預設實例
app = App.load("app.toml")         # 解析 + 校驗 + 預設合併
text = App.template()              # 帶註解範本（同一 schema 輸出逐位元組穩定）
errors = App.validate_dict(raw)    # 離線校驗，聚合全部錯誤
app.save("app.toml")               # diff 寫回（原子）
```

## 視圖語義

1. 預設值永不落盤——檔案裡只出現使用者改過的鍵
2. 未知鍵保留（`strict=True` 時報錯）
3. diff 寫回——與解析時快照比較，只寫變化的鍵
4. `None` 賦給 Optional 欄位 = 儲存時刪除該鍵；非 Optional 欄位賦 `None` 儲存時拋 `ConfigError`
5. 原子落盤——tempfile + `os.replace`

## 環境變數覆寫與熱更新

```python
# MYAPP_SERVER__PORT=9000 覆寫 server.port（__ 為路徑分隔，按註解類型盡力轉換）
app = App.load("app.toml", env_prefix="MYAPP")

# 熱更新：可選依賴 watchfiles；校驗失敗保留上一份實例並繼續監聽
Server.watch("server.toml", callback, stop_event=event)
```

## 遷移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 舊鍵 -> 新點路徑


new = AppV2.migrate(AppV1.load("app.toml"))
```
