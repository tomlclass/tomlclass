# 性能

基线数据、实测口径与维护约定见 [BASELINE](../../tests/bench/BASELINE.md)。复现：

```bash
uv run --with tomli --with tomlkit python tests/bench/bench.py --compare --iterations 500
```

## 速览（v0.1.0 实测）

| 指标 | 数值 | 对比 |
|---|---|---|
| 解析 | 1.73× / 1.94× tomli（两份语料） | 对 tomlkit 0.15.1 快 5.8–6.4× |
| 未编辑 `dumps` | 近似 O(1) | 源切片拼接 |
| 编辑后 `dumps` | O(编辑规模) | 仅脏节点重渲染 |
| 常驻内存 | 0.67× tomlkit（预算 ≤0.7×） | 高于 tomli（保真样式成本） |
| 合规 | toml-test 1.0：valid 208 个文件全过、invalid 501 个文件全拒 | tomlkit invalid 自测 208/214 |

## 架构

1. **源切片直读**：未触碰节点渲染直接取 `source[span]`，未编辑文档的 `dumps` 近似 O(1)
2. **物化于编辑**：trivia/样式元数据只在节点被写入时构建，读取路径零样式成本
3. **单遍字符分派解析**：预编译正则块匹配，无逐字符循环、无逐 token 正则风暴
