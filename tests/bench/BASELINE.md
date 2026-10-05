# 性能基线（v0.1.0，实测）

> **口径**：同一台机器、同一进程环境、同一迭代次数（500）实机测得，非引用历史数据。
> 环境：Windows 11（10.0.26300），AMD Ryzen（Zen4，Family 25 Model 97），CPython 3.14.6，
> tomli 2.4.1，tomlkit 0.15.1。
> 复现：`uv run --with tomli --with tomlkit python tests/bench/bench.py --compare --iterations 500`
> 语料：`tests/bench/data/`——data0（26,529 B，pytomlpp 基准）、data2（3,893 B，tomli 基准），
> 与社区历史横评同源，可直接对比第三方 published 数字。

## 解析（纯 parse，500 iters 实测）

| 库 | data0（26.5 KB） | data2（3.9 KB） | 相对 tomli | 相对 tomlclass |
|---|---|---|---|---|
| tomli 2.4.1 | 0.80 s | 0.12 s | 1.00× | 0.58× / 0.52× |
| **tomlclass 0.1.0** | **1.38 s** | **0.23 s** | **1.73× / 1.94×** | 1.00× |
| tomlkit 0.15.1 | 8.83 s | 1.33 s | 11.0× / 11.1× | 6.4× / 5.8× |

- 预算：解析 ≤ 2× tomli —— **达标**（data2 贴线 1.94×，小文件固定开销占比高，波动 ±5%）
- **对 tomlkit 0.15.1 实测 5.8–6.4 倍快**；2022 年社区横评中该差距约为 19–20×（tomlkit 后续有优化）——
  不影响结论：保真实现不必以 20× 慢为代价

## 渲染（dumps，500 iters 实测）

| 场景 | 库 | data0 | data2 |
|---|---|---|---|
| 未编辑 | tomlclass | 0.28 s | 0.051 s |
| 未编辑 | tomlkit | 0.41 s | 0.08 s |
| **编辑 1 键后** | **tomlclass** | **0.29 s** | **0.052 s** |

- 未编辑：源切片拼接（近似 O(1)）；编辑后：仅脏节点重渲染——**编辑成本与编辑规模相关，
  与文档总长基本无关**（对比：tomli / tomli_w 写回必须全量重序列化，且丢注释）
- toml-test invalid 数据出处说明：500 条来自 **toml-test 官方 1.0 manifest 的 invalid 清单**
  （随语料 vendored 并做数量底线断言，见测试套件），非自建用例
- 内存预算 0.7× 的依据：tomlkit 每个值都携带 trivia/样式对象图，tomlclass 未触碰节点只存
  `(start, end)` span 与已解析值——0.67× 即"主动不做 per-value 样式对象"的差量；进一步压缩
  需 arena/驻留技巧（后续优化项）

## 内存（常驻，50 份文档均摊，tracemalloc 实测）

| 库 | 每文档常驻 |
|---|---|
| tomli（纯 dict，无样式） | 74 KB |
| **tomlclass**（CST + span） | **445 KB** |
| tomlkit 0.15.1 | 669 KB |

- 预算 ≤ 0.7× tomlkit —— **达标**（实测 0.67×）；span + 已解析值的存储已是无损 CST 的合理下限，
  进一步压缩需 arena/驻留类技巧（列为后续优化项）；与 tomli 的差距即保真样式的固有成本

## 合规（toml-test 1.0 官方清单，随测试套件常驻验证）

- **valid：208 个 .toml 文件**全部通过（含逐字节往返公理）
- **invalid：500 个 .toml 文件**全部正确拒绝（清单数经测试套件底线断言锁定；
  对照：tomlkit 0.15 官方自测 invalid 208/214，本基线引用其 published 数字并注明版本）

## 维护约定

- 性能 job 随 PR 验证预算；预算调整需修订本文件并说明依据
- 第三方库数值必须**同机实测**并记录版本号——引用历史数据须显式标注来源与日期，不得混入实测表
- 基准数值随版本更新重测记录于此
