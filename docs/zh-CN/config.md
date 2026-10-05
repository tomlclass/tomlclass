# 配置注解

用类声明配置结构：docstring 成为模板注释，读取时校验，写回只触碰变化的键。

## 声明

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
    name: str = Field("demo", min_length=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- docstring 的第一段成为表注释；`field:` 小节成为键上方的注释（模板中渲染为 `#` 行）。多行与同行两种格式等价：`host: 绑定地址` 等价于 `host:` 小节
- 嵌套类 = 嵌套表；`list[T]` 支持元素校验；下划线开头的字段被排除
- `Field` 约束：`ge / le / gt / lt / pattern / min_length / max_length / coerce`
- `Field(default_factory=list)` 为每个实例产出全新可变默认值（类级 `= []` 默认跨实例共享——推荐工厂）
- `Annotated[int, Field(ge=1)]` 在类型旁声明选项——等价于类级 `Field`
- 字段描述支持 i18n 字典：`Field(description={"i18n": key, "default": text})`

## 支持的注解

`bool / int / float / str / datetime / date / time`、`Optional[X]` 与联合、`Literal[...]`、
`list[X]`、`list[Config]`（`[[aot]]`——逐元素逐字段 diff）、嵌套 `Config`、
**`dict[str, X]`**（以内联表往返）、**`Enum`**（文件存成员值，读回成员本身）、
**`Annotated[X, Field(...)]`**。其余注解报"unsupported annotation"错误。

## 入口

```python
app = App()                        # 纯默认值（内存中，不做校验 —— 需要校验请用 load()）
app = App.load("app.toml")         # 解析 + 校验 + 合并默认值
text = App.template()              # 带注释模板（同一 schema 字节稳定）
errors = App.validate_dict(raw)    # 离线校验，聚合全部错误
app.save("app.toml")               # diff 写回（原子）
```

## 校验错误

`validate_dict` 与 `load` 把**所有**违规聚合进一个 `ValidationError`，而不是在第一个错误处失败。每个 `FieldError` 说明点号路径、错在哪里，并在字段有描述时附上该字段的文档化意图：

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

消息用平实的语言指出被违反的边界，并指向 schema 描述 —— 通常不必翻 schema 源码就知道该怎么改。

## 视图语义

1. 默认值永不持久化 —— 文件里只有用户改过的键
2. 未知键保留（`strict=True` 将其视为错误，嵌套表同样透传）
3. diff 写回 —— 与解析时快照比较，只写变化的键
4. Optional 字段赋 `None` = 保存时删除该键（键本就不在文件里时不做任何事）；非 optional 字段赋 `None` 在保存时抛 `ConfigError`
5. 原子写 —— tempfile + `os.replace`

## 环境变量覆盖与热重载

```python
# MYAPP_SERVER__PORT=9000 覆盖 server.port（__ 分隔路径段，
# 尽力转换为注解类型）
app = App.load("app.toml", env_prefix="MYAPP")

# 热重载：可选依赖 watchfiles；校验失败保留上一个可用实例并继续监听。
# stop_event 可从其他线程停止。
Server.watch("server.toml", callback, stop_event=event)
```

## 迁移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧键 -> 新点号路径


new = AppV2.migrate(AppV1.load("app.toml"))
```

## 类选项

以带注解的类属性声明（无注解的赋值会变成字段）：

```python
class App(Config):
    extra: ClassVar[str] = "forbid"              # "allow"（默认）| "ignore" | "forbid" —— 未知键
    validate_assignment: ClassVar[bool] = True   # 属性赋值时校验并转换

    name: str = "demo"
```

- `extra="forbid"` 在 `load` / `validate_dict` 时把未知键变成校验错误
- `validate_assignment=True` 对每次 `app.name = ...` 立即校验（不匹配抛 `ValidationError`，应用 `coerce` 转换）
