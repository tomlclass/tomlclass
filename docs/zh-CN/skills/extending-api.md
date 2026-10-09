# 技能：扩展 API

适用于新增或修改任何用户可调用的对象：导出函数、`Document`/节点方法、`Config`/`Field` 选项，以及可选的 `tomlclass.pydantic` 层。

## 1. 对着两层设计

- **引擎层**（`parse`/`loads`/`load`/`dumps`/`update`、`Document`、节点）：无损、不感知 schema。新变更器必须走引擎钩子——`src/tomlclass/engine_set.py` 的 `engine_set` / `engine_del`——内存与输出才不会分叉。
- **注解层**（`Config`、`Field`、`tomlclass.pydantic.TomlModel`）：构建在引擎之上。新字段类型/选项扩展 `schema.py` 的 `_FieldSpec` 与校验器；pydantic 支持在 `pydantic.py` 中镜像。

动手前先看文档边界：本库是配置/TOML 工具，不是通用数据框架。能放在用户代码里解决的，就明说不加。

## 2. 守住同步契约

公开 API 变更在以下内容**全部**同步之前不算完成：

1. 实现，带 reST 文档字符串（`:param:` / `:returns:` / `:raises:`）。
2. `src/tomlclass/__init__.py` 的 `__all__`（仅新导出符号；`test_version.py` 钉住元数据）。
3. 每个受影响公开方法的文档字符串。
4. 用户文档：`docs/en/` 与 `docs/zh-CN/` 对应页面（见[更新文档](updating-docs.md)）。
5. 当前版本条目下的 `CHANGELOG.md`。
6. 测试：新公开面在 `tests/unit/test_api_030.py`（或新主题文件）补用例，含错误路径。

## 3. 尊重类型门

- `basedpyright src/tomlclass` 保持 0 错误——`pyproject.toml` 中的晋升规则（`reportReturnType`、`reportArgumentType`、可选访问、重写兼容性）就是契约。
- `ruff check src/ tests/ scripts/` 全绿；惰性导入仅限现有代码已有的位置（见 `pyproject.toml` 中 `PLC0415` 的忽略理由）。
- Python ≥ 3.10：不允许未经 `_compat` 垫片就使用 3.11+ 语法/标准库（`tests/_compat.py` 是样板；运行时代码不依赖 `tomli`）。

## 4. 遵守入口约定

- 双模式 `load()`（路径 → `Document`，文件对象 → dict）与 `none_value` 处理存在于每个解析入口（`parse`、`loads`、`load`、`update`、`Config.load`）。新解析入口必须接受 `toml_version`（默认 `"1.1"` / `"1.0"` 严格），涉及 dict 输出时透传 `none_value`。
- 错误：解析问题抛 `TOMLParseError`（`ValueError` 子类），不可表示的值**在赋值时**抛 `TOMLTypeError`（`TypeError` 子类），schema 问题聚合为携带 `FieldError` 的 `ValidationError`。不许向公开面泄漏裸异常。
- 零运行时依赖——可选能力挂在 extras（`pydantic`、`watch`）后，并优雅处理 `importorskip`/`ImportError`。

## 5. 验证

```bash
uv run pytest tests -q --no-cov -p no:cacheprovider -n auto
uv run ruff check src/ tests/ scripts/
uv run basedpyright src/tomlclass
uv run --python 3.10 --extra test pytest tests/unit -q -p no:cacheprovider -o addopts=""
```

然后以用户视角重读你改过的文档：新文档段里的每个代码片段必须能对新 API 原样跑通。
