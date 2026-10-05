# 配置註解

以類別宣告設定結構：docstring 成為範本註解，讀取時進行驗證，寫回只觸碰變更過的鍵。

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

- docstring 的第一段成為表格註解；`field:` 區段成為鍵上方的註解（在範本中渲染為 `#` 行）
- 巢狀類別 = 巢狀表格；`list[T]` 支援元素級驗證；底線開頭的欄位會被排除
- `Field` 的約束條件：`ge / le / gt / lt / pattern / min_length / max_length / coerce`
- 欄位描述支援 i18n 字典：`Field(description={"i18n": key, "default": text})`

## 進入點

```python
app = App()                        # pure defaults (in memory)
app = App.load("app.toml")         # parse + validate + merge defaults
text = App.template()              # commented template (byte-stable per schema)
errors = App.validate_dict(raw)    # offline validation, aggregates all errors
app.save("app.toml")               # diff write-back (atomic)
```

## 驗證錯誤

`validate_dict` 與 `load` 會把**所有**違規聚合進單一 `ValidationError`，而不是在第一個錯誤就失敗。每個 `FieldError` 都會指出點號路徑、錯在哪裡，以及——當欄位有描述時——該欄位在文件中記載的意圖：

```python
class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = Field(8000, ge=1, le=65535)


Server.validate_dict({"port": 70000})
# ValidationError: 1 validation error(s): port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

訊息以直白的語言點明違反的邊界，並指向 schema 描述，因此通常不必翻開 schema 原始碼就知道該怎麼修。

## 視圖語義

1. 預設值永不持久化——檔案只包含使用者變更過的鍵
2. 未知鍵會被保留（`strict=True` 會把它變成錯誤，並向巢狀表格傳遞）
3. diff 寫回——與解析時的快照比較，只寫入變更過的鍵
4. Optional 欄位設為 `None` 會在儲存時刪除該鍵；非 Optional 欄位設為 `None` 會在儲存時拋出 `ConfigError`
5. 原子寫入——tempfile + `os.replace`

## env 覆寫與熱重載

```python
# MYAPP_SERVER__PORT=9000 overrides server.port (__ separates path segments,
# best-effort conversion to the annotated type)
app = App.load("app.toml", env_prefix="MYAPP")

# Hot reload: optional dependency watchfiles; validation failures keep the
# previous good instance and watching continues. stop_event stops it.
Server.watch("server.toml", callback, stop_event=event)
```

## 遷移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # old key -> new dotted path


new = AppV2.migrate(AppV1.load("app.toml"))
```
