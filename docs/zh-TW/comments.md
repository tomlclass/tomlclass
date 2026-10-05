# 註解系統

註解歸屬於它所跟隨的鍵；表格註解位於標頭行，以表格路徑定址。

## 引擎層

```python
doc = tomlclass.parse('port = 8000  # the port\n')

doc.comment("port")               # -> "the port" (None when absent)
doc.set_comment("port", "API port")
doc.set_comment("port", None)     # remove (with leading whitespace)
```

- 替換時保留原有的前導空白；移除時則乾淨地去掉
- 刪除鍵會一併移除其行尾註解；獨立的整行註解原地保留

## 註解層：參數化注入

`Config.load` 的 `comments` 參數控制是否把 schema 描述注入為註解：

| 模式 | 行為 |
|---|---|
| `"none"`（預設） | 檔案原封不動 |
| `"missing"` | 只為「檔案中存在且尚無註解」的鍵注入 docstring 描述 |
| `"all"` | 為檔案中出現的所有 schema 欄位重寫註解 |

不變式：預設值永不具體化（不在檔案中的鍵不會被注入）；未知鍵及其註解原樣保留。

## 多行字串

含換行的字串值會渲染為多行字串：優先使用 `"""`；當內容與 `"""` 衝突且不需要跳脫字元時，改用 `'''`。開頭定界符獨佔第一行——內容從下一行開始，即使內容本身只有一行。
