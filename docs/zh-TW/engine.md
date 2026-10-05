# 引擎層

引擎層面向任意 TOML 1.0 文件：解析、讀取、修改、渲染、原子保存，註解與格式逐位元組保留。

## 解析與渲染

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # 從檔案路徑解析
doc.dumps()                      # 渲染為 str：未編輯時與輸入逐位元組相同
doc.save(path)                   # 原子寫（tempfile + os.replace）
```

**往返公理**：`parse(text).dumps() == text` 逐位元組成立，隨每個 PR 驗證。

## tomllib 相容

```python
data = tomlclass.loads(text)  # 純 dict，與 tomllib.loads 同約定
data = tomlclass.load(fp)     # 二進位檔案物件，與 tomllib.load 同約定
```

## 編輯

```python
doc["project"]["version"] = "1.0.0"   # 修改：整行中只有值被替換
del doc["tool"]["old"]                # 刪除：連同註解與前導空白乾淨移除
doc["server"]["workers"] = 4          # 新鍵：渲染於所屬表末條目之後
doc["logging"] = {"level": "info"}    # 新表：渲染為 [logging] 區塊
doc["products"].append(...)           # 陣列追加：源切片拼接，既有元素與註解不動
doc["products"] = [...]               # AoT 整體替換：舊元素清除，新元素渲染為區塊
```

- 編輯採用規範渲染：新寫入的值使用標準書寫形態
- 未觸碰的部分直讀源文字切片
- 內聯表是閉合的：整體重新賦值即可

## 註解

```python
doc.comment("server.port")            # -> "the port"（無註解為 None）
doc.set_comment("server.port", "API 連接埠")
doc.set_comment("server.port", None)  # 刪除（連同前導空白）
```

註解歸屬其尾隨的鍵；表註解在表頭行上，按表路徑定址。

## 錯誤

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` 是 `ValueError` 子類別。賦值不可序列化值（`None`、函式等）拋 `TOMLTypeError`（`TypeError` 子類別）。
