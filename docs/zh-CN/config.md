# 注解层

用类声明配置结构：docstring 即模板注释，读取时校验，写回时只动变化的键。

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
    name: str = Field("demo", ge=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- docstring 首段 → 表注释；`字段名:` 分节 → 键上方注释（模板中渲染为 `#` 行）
- 嵌套类 = 嵌套表；`list[T]` 支持元素校验；下划线前缀字段排除
- `Field` 约束：`ge / le / gt / lt / pattern / min_length / max_length / coerce`
- 字段描述支持 i18n 字典：`Field(description={"i18n": key, "default": text})`

## 入口

```python
app = App()                        # 纯默认实例
app = App.load("app.toml")         # 解析 + 校验 + 默认合并
text = App.template()              # 带注释模板（同 schema 输出逐字节稳定）
errors = App.validate_dict(raw)    # 离线校验，聚合全部错误
app.save("app.toml")               # diff 写回（原子）
```

## 视图语义

1. 默认值永不落盘——文件里只出现用户改过的键
2. 未知键保留（`strict=True` 时报错）
3. diff 写回——与解析时快照比较，只写变化的键
4. `None` 赋给 Optional 字段 = 保存时删除该键；非 Optional 字段赋 `None` 保存时抛 `ConfigError`
5. 原子落盘——tempfile + `os.replace`

## 环境变量覆盖与热更新

```python
# MYAPP_SERVER__PORT=9000 覆盖 server.port（__ 为路径分隔，按注解类型尽力转换）
app = App.load("app.toml", env_prefix="MYAPP")

# 热更新：可选依赖 watchfiles；校验失败保留上一份实例并继续监听
Server.watch("server.toml", callback, stop_event=event)
```

## 迁移

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧键 -> 新点路径


new = AppV2.migrate(AppV1.load("app.toml"))
```
