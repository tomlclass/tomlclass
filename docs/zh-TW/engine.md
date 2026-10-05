# 引擎層

引擎層面向任意 TOML 1.0/1.1 文件：解析、讀取、編輯、渲染、原子儲存——註解與格式逐位元組保留。

## 解析與渲染

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # parse from a file path -> Document
doc.dumps()                      # render to str: byte-identical to input when unedited
doc.save(path)                   # atomic write (tempfile + os.replace)
```

**往返公理**：`parse(text).dumps() == text` 逐位元組成立，每次提交都以 toml-test 1.0 套件驗證（208 個有效檔案全部精確往返；501 個無效檔案全部被拒）。

## 保留機制的原理

未觸碰的節點只在原始文本中儲存自己的 `(start, end)` 跨度（span）；渲染時直接切取原文。格式不會被記錄在任何地方——它*就是*原始文本本身，只要不去動它，它自然存活。只有當節點被編輯時，tomlclass 才為它具體化渲染輸出（標準格式），其餘部分一律保持來源切片。

由此帶來的結果：未編輯時 `dumps` 約為 O(1)，讀取路徑完全不攜帶格式資料，編輯成本取決於編輯量而非文件長度。

## tomllib 相容性

```python
data = tomlclass.loads(text)  # plain dict, same convention as tomllib.loads
data = tomlclass.load(fp)     # binary file object, same convention as tomllib.load
```

## 編輯

```python
doc["project"]["version"] = "1.0.0"   # modify: only the value on that line changes
del doc["tool"]["old"]                # delete: trailing comment removed cleanly
doc["server"]["workers"] = 4          # new key: rendered after the table's last entry
doc["logging"] = {"level": "info"}    # new table: rendered as a [logging] block
doc["products"].append(...)           # array append: spliced in place, existing elements untouched
doc["products"] = [...]               # AoT whole replace: old elements removed, new ones as blocks
```

- 被編輯的值使用標準渲染；未觸碰的部分直接讀自來源切片
- 行內表格是封閉的：請整體重新賦值，而不是向其中新增鍵
- 由點號鍵建立的表格是密封的：向其中新增的鍵會渲染成點號行，錨定在該表格最後一行實體行上

### 點號路徑存取

```python
doc.find("server.port")            # -> value or None
doc.set_path("server.port", 9090)  # assign; missing keys and intermediate tables are created
```

`set_path` 會把缺失的表格建構為包含其條目的真正 `[table]` 區塊——絕不會建成「一條點號行加一個空標頭」（那會把同一表格定義兩次）。

## TOML 版本

tomlclass **預設按 TOML 1.1 解析**；所有面向解析的入口（`parse`、`loads`、`load`、`update`、`Config.load`）都接受 `toml_version="1.0"` 以取得嚴格的舊版語義。

1.1 新增特性 —— 預設接受：`\e` 與 `\xHH` 轉義；省略秒的時間與日期時間（`13:37`）；內聯表內的換行、註解與尾逗號；非 ASCII 裸鍵。在 `toml_version="1.0"` 下，同樣的輸入將拋出 `TOMLParseError`。

## None 處理

TOML 沒有 null。需要 None 語義時，傳入哨兵值（rtoml 風格）：

```python
tomlclass.dumps(data, none_value="@None")   # None 序列化為 "@None"
tomlclass.loads(text, none_value="@None")   # 等於 "@None" 的字串讀回 None
```

`update(..., none_value=...)` 同理。不傳 `none_value` 時，`None` 拋出 `TOMLTypeError`。

## 註解


```python
tomlclass.update("app.toml", {"server.port": 9090, "name": "prod"})
```

讀取檔案、套用每一項點號鍵賦值、原子化寫回，並回傳 `Document`。若任何值無法以 TOML 表示，則不會寫入任何內容。`None` 不是 TOML 值——請改以映射 API（`del doc[...]`）刪除鍵。

## 註解

```python
doc.comment("server.port")            # -> "the port" (None when absent)
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # remove (with leading whitespace)
```

註解歸屬於它所跟隨的鍵；表格註解位於標頭行，以表格路徑定址。完整模型見[註解系統](comments.md)。

## 錯誤

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` 是 `ValueError` 的子類別。賦予不可序列化的值（`None`、函式、任意物件）會在賦值當下拋出 `TOMLTypeError`（`TypeError` 的子類別），而非等到渲染時。
