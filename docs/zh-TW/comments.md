# 註解系統

註解歸屬其尾隨的鍵；表註解在表頭行上，按表路徑定址。

## 引擎層

```python
doc = tomlclass.parse('port = 8000  # the port\n')

doc.comment("port")               # -> "the port"（無註解為 None）
doc.set_comment("port", "API 連接埠")
doc.set_comment("port", None)     # 刪除（連同前導空白）
```

- 替換沿用原前導空白；刪除連同前導空白乾淨移除
- 刪除鍵時其行尾註解一併移除；獨立整行註解留在原位

## 註解層：參數化注入

`Config.load` 的 `comments` 參數控制 schema 描述是否注入為註解：

| 模式 | 行為 |
|---|---|
| `"none"`（預設） | 檔案原樣 |
| `"missing"` | 僅為沒有註解且已在檔案中的鍵注入 docstring 描述 |
| `"all"` | 所有已在檔案中的 schema 欄位註解按 schema 重寫 |

不變式：預設值永不物化（未落盤的鍵不注入）；未知鍵與其註解原樣保留。

## 多行字串

含換行的字串值渲染為多行字串：`"""` 優先，內容與 `"""` 衝突且無轉義需求時改用 `'''`。首行 `"""` 後內容從下一行開始。
