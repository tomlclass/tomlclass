# 注释系统

注释归属其尾随的键；表注释在表头行上，按表路径寻址。

## 引擎层

```python
doc = tomlclass.parse('port = 8000  # the port\n')

doc.comment("port")               # -> "the port"（无注释为 None）
doc.set_comment("port", "API 端口")
doc.set_comment("port", None)     # 删除（连同前导空白）
```

- 替换沿用原前导空白；删除连同前导空白干净移除
- 删除键时其行尾注释一并移除；独立整行注释留在原位

## 注解层：参数化注入

`Config.load` 的 `comments` 参数控制 schema 描述是否注入为注释：

| 模式 | 行为 |
|---|---|
| `"none"`（默认） | 文件原样 |
| `"missing"` | 仅为没有注释且已在文件中的键注入 docstring 描述 |
| `"all"` | 所有已在文件中的 schema 字段注释按 schema 重写 |

不变式：默认值永不物化（未落盘的键不注入）；未知键与其注释原样保留。

## 多行字符串

含换行的字符串值渲染为多行字符串：`"""` 优先，内容与 `"""` 冲突且无转义需求时改用 `'''`。首行 `"""` 后内容从下一行开始。
