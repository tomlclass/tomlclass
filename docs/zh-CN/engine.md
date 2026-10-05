# 引擎层

引擎面向任意 TOML 1.0/1.1 文档：解析、读取、编辑、渲染、原子写回 —— 注释与格式逐字节保留。

## 解析与渲染

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # 从文件路径解析 -> Document
doc.dumps()                      # 渲染为 str：未编辑时与输入逐字节相同
doc.save(path)                   # 原子写（tempfile + os.replace）
```

**往返公理**：`parse(text).dumps() == text` 逐字节成立，每次提交都由 toml-test 1.0 套件验证（208 个 valid 文件全部精确往返，501 个 invalid 文件全部拒绝）。

## 无损的原理

未触碰的节点只记录其在源文本中的 `(start, end)` 跨度；渲染时直接切原文。格式不是"存"下来的 —— 它就是源文本本身，只要不碰就自然保留。只有节点被编辑时，tomlclass 才为它物化渲染输出（规范格式），其余部分仍是源切片。

推论：未编辑文档的 `dumps` 近似 O(1)，读取路径完全不携带格式数据，编辑成本与编辑规模成正比、与文档总长基本无关。

## tomllib 兼容

```python
data = tomlclass.loads(text)  # 纯 dict，约定与 tomllib.loads 一致
data = tomlclass.load(fp)     # 二进制文件对象，约定与 tomllib.load 一致
```

## 编辑

```python
doc["project"]["version"] = "1.0.0"   # 修改：只改该行的值
del doc["tool"]["old"]                # 删除：尾随注释干净移除
doc["server"]["workers"] = 4          # 新键：渲染在表内最后一个条目之后
doc["logging"] = {"level": "info"}    # 新表：渲染为 [logging] 块
doc["products"].append(...)           # 数组追加：原位拼接，既有元素不动
doc["products"].insert(0, ...)        # AoT 插入：新元素渲染在该位置的既有元素之前
doc["products"].extend([...])         # 扩展数组或 AoT：新值的渲染方式与追加一致
doc["products"][0] = {...}            # AoT 元素替换：该位置的块重新渲染
doc["products"] = [...]               # AoT 整体替换：旧元素移除，新元素以块渲染
```

- 编辑值使用规范渲染；未触碰部分直接读源切片
- 内联表是封闭的：请整体重新赋值，而不是向其加键
- 点号键创建的表是密封的：向其加键会渲染为锚定在其最后物理行之后的点号行
- AoT 不支持重排（`sort()` / `reverse()`）——请通过 `doc[key] = [...]` 整体替换

### 副作用与边界

在 `dumps()` / `save()` 之前不会写入任何内容——以下变更都只存在于内存，且 `dumps()` 幂等。各动作在赋值之外的影响：

| 动作 | 副作用 | 清除 / 规避 |
|---|---|---|
| 值编辑 | 仅该行的值按规范重渲染；行尾注释与文件其余部分不动 | 重新赋回旧值 |
| `del doc[...]` | 该行及其行尾注释从输出中消失 | 重新赋值该键（全新渲染） |
| `set_path` / `update` 穿过 `[[aot]]` 段 | 写入**每个**元素 | 通过 `doc["it"][i]` 写单个元素 |
| `aot[i] = {...}` | 被替换元素以全新规范块渲染——其行内注释与原始格式丢失 | 原地改字段（`aot[i]["n"] = ...`） |
| `doc[key] = [...]` AoT 整体替换 | 所有元素块规范重渲染；原元素注释丢失 | 原地编辑元素 |
| AoT `append` / `insert` / `extend` | 追加全新的 `[[块]]` 段（文档结构增长） | `pop()` 该元素 |
| 点号键表 | 密封：新键渲染为锚定在其最后物理行之后的点号行 | — |
| 内联表 | 封闭：加键报错；请整体重新赋值 | — |

未触碰的值按源文本原样渲染；赋过的值按规范重渲染（赋值的日期时间用 `isoformat()`，不再保留文件原拼写）。`Config.save()` 基于差异——与快照相等的值不触碰、从未落盘的默认值不写入、可选字段赋 `None` 删除该键。`Config.load(env_prefix=...)` 在加载时读取环境变量——来自文件之外的状态。

### 点号路径访问

```python
doc.find("server.port")            # -> 值或 None
doc.set_path("server.port", 9090)  # 赋值；缺失的键与中间表自动创建
doc.find("products.name")          # -> ["a", "b"] —— [[products]] 段把剩余路径投影到每个元素上
doc.set_path("products.tag", "x")  # 广播：向每个元素赋值
```

`set_path` 把缺失的表构造成包含其条目的真实 `[table]` 块 —— 绝不会生成点号行加空表头（那会重复定义同一张表）。作为末段时，`find` 返回数组本身。

## TOML 版本

tomlclass **默认按 TOML 1.1 解析**；所有面向解析的入口（`parse`、`loads`、`load`、`update`、`Config.load`）都接受 `toml_version="1.0"` 以获得严格的旧版语义。

1.1 新增特性 —— 默认接受：`\e` 与 `\xHH` 转义；省略秒的时间与日期时间（`13:37`）；内联表内的换行、注释与尾逗号；非 ASCII 裸键。在 `toml_version="1.0"` 下，同样的输入将抛出 `TOMLParseError`。

## None 处理

TOML 没有 null。需要 None 语义时，传入哨兵值（rtoml 风格）：

```python
tomlclass.dumps(data, none_value="@None")   # None 序列化为 "@None"
tomlclass.loads(text, none_value="@None")   # 等于 "@None" 的字符串读回 None
```

`update(..., none_value=...)` 同理。不传 `none_value` 时，`None` 抛出 `TOMLTypeError`。

## 一次调用完成更新


```python
tomlclass.update("app.toml", {"server.port": 9090, "name": "prod"})
```

读文件、逐个应用点号键赋值、原子写回，并返回 `Document`。任何一个值无法表示为 TOML 时，什么都不写。`None` 不是 TOML 值 —— 删除键请走映射 API（`del doc[...]`）。

## 注释

```python
doc.comment("server.port")            # -> "the port"（无注释时为 None）
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # 移除（连同前导空白）
```

注释归属于它尾随的键；表注释在表头行上，按表路径寻址。完整模型见[注释系统](comments.md)。

## 错误

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` 是 `ValueError` 的子类。赋值不可序列化的值（`None`、函数、任意对象）会在赋值时（而非渲染时）抛出 `TOMLTypeError`（`TypeError` 的子类）。
