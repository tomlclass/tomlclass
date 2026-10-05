# 性能

基线数据、测量方法与维护规则：[BASELINE](../../tests/bench/BASELINE.md)。复现方式：

```bash
uv run --with tomli --with tomlkit python tests/bench/bench.py --compare --iterations 500
```

## 摘要（v0.1.0 实测；0.1.1 未触碰引擎热路径）

| 指标 | 数值 | 对比 |
|---|---|---|
| 解析 | tomli 的 1.73× / 1.94×（两个语料） | 比 tomlkit 0.15.1 快 5.8–6.4× |
| 未编辑 `dumps` | ~O(1) | 源切片拼接 |
| 编辑后 `dumps` | O(编辑规模) | 仅脏节点重渲染 |
| 常驻内存 | tomlkit 的 0.67×（预算 ≤0.7×） | 高于 tomli（保真的固有成本） |
| 合规 | toml-test 1.0：208 个 valid 全部逐字节通过，501 个 invalid 全部拒绝 | tomlkit invalid 自测 208/214 |

## 原理

1. **源切片渲染**：未触碰节点直接从 `source[span]` 渲染；未编辑文档的 `dumps` 近似 O(1)
2. **编辑时物化**：格式数据只在节点被写入时构建 —— 读取路径零样式成本
3. **单遍字符分派解析**：预编译正则块匹配，无逐字符循环，无逐 token 正则风暴
