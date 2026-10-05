# 引擎层

引擎层面向任意 TOML 1.0 文档：解析、读取、修改、渲染、原子保存，注释与格式逐字节保留。

## 解析与渲染

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # 从文件路径解析
doc.dumps()                      # 渲染为 str：未编辑时与输入逐字节相同
doc.save(path)                   # 原子写（tempfile + os.replace）
```

**往返公理**：`parse(text).dumps() == text` 逐字节成立，随每个 PR 验证。

## tomllib 兼容

```python
data = tomlclass.loads(text)  # 纯 dict，与 tomllib.loads 同约定
data = tomlclass.load(fp)     # 二进制文件对象，与 tomllib.load 同约定
```

## 编辑

```python
doc["project"]["version"] = "1.0.0"   # 修改：整行中只有值被替换
del doc["tool"]["old"]                # 删除：连带注释与前导空白干净移除
doc["server"]["workers"] = 4          # 新键：渲染于所属表末条目之后
doc["logging"] = {"level": "info"}    # 新表：渲染为 [logging] 块
doc["products"].append(...)           # 数组追加：源切片拼接，既有元素与注释不动
doc["products"] = [...]               # AoT 整体替换：旧元素清除，新元素渲染为块
```

- 编辑采用规范渲染：新写入的值使用标准书写形态
- 未触碰的部分直读源文本切片
- 内联表是闭合的：整体重新赋值即可

## 注释

```python
doc.comment("server.port")            # -> "the port"（无注释为 None）
doc.set_comment("server.port", "API 端口")
doc.set_comment("server.port", None)  # 删除（连同前导空白）
```

注释归属其尾随的键；表注释在表头行上，按表路径寻址。

## 错误

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` 是 `ValueError` 子类。赋值不可序列化值（`None`、函数等）抛 `TOMLTypeError`（`TypeError` 子类）。
