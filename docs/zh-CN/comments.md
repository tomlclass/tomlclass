# 注释系统

注释归属其尾随的键；表注释位于表头行上，按表路径寻址；AoT 元素字段用索引寻址。

## 可寻址范围

以下目标全部适用于 `doc.comment(path)` / `doc.set_comment(path, text | None)`：

| 目标 | 路径 | 说明 |
|---|---|---|
| 键值行 | `server.port` | 替换沿用原前导空白；`None` 干净剥离 |
| 表头行 | `server` | `[db] # note` —— 原地替换，缺失时行尾追加 |
| 点号键叶子 | `a.b` | 解析到物理点号行 |
| API 新建键 | `t.fresh` | 渲染在其生成的 `key = value  # comment` 行上 |
| AoT 元素字段 | `products[0].name` | 必须显式索引——未索引的 AoT 段有歧义，解析为 `None` |

独立排版行通过 `doc.add(tomlclass.comment("text"))` / `doc.add(tomlclass.nl())` 附着。

## 引擎层

```python
doc = tomlclass.parse('port = 8000  # the port\n')

doc.comment("port")               # -> "the port"（无注释时为 None）
doc.set_comment("port", "API port")
doc.set_comment("port", None)     # 移除（连同前导空白）
```

- 替换沿用原前导空白；移除时干净剥离
- 删除键会一并移除其尾随注释；独立整行注释保持原位
- 上表所有条目（含 API 新建键的注释）都在读-改-存循环中存活

## 注解层：参数化注入

`Config.load` 的 `comments` 参数控制是否把 schema 描述注入为注释：

| 模式 | 行为 |
|---|---|
| `"none"`（默认） | 文件完全按原样保留 |
| `"missing"` | 仅为没有注释且存在于文件中的键注入 docstring 描述 |
| `"all"` | 重写文件中所有 schema 字段的注释 |

不变式：默认值永不物化（不在文件中的键不注入）；未知键及其注释原样保留。

## 多行字符串

含换行的字符串值渲染为多行字符串：优先 `"""`；当内容与 `"""` 冲突且无需转义时改用 `'''`。开头的三引号独占首行 —— 内容从下一行开始，即使内容只有一行。
