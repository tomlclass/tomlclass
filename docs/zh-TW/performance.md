# 效能

基線資料、實測口徑與維護約定見 [BASELINE](../../tests/bench/BASELINE.md)。復現：

```bash
uv run --with tomli --with tomlkit python tests/bench/bench.py --compare --iterations 500
```

## 速覽（v0.1.0 實測）

| 指標 | 數值 | 對比 |
|---|---|---|
| 解析 | 1.73× / 1.94× tomli（兩份語料） | 對 tomlkit 0.15.1 快 5.8–6.4× |
| 未編輯 `dumps` | 近似 O(1) | 源切片拼接 |
| 編輯後 `dumps` | O(編輯規模) | 僅髒節點重渲染 |
| 常駐記憶體 | 0.67× tomlkit（預算 ≤0.7×） | 高於 tomli（保真樣式成本） |
| 合規 | toml-test 1.0：valid 208 個檔案全過、invalid 501 個檔案全拒 | tomlkit invalid 自測 208/214 |

## 架構

1. **源切片直讀**：未觸碰節點渲染直接取 `source[span]`，未編輯文件的 `dumps` 近似 O(1)
2. **物化於編輯**：trivia/樣式元數據只在節點被寫入時構建，讀取路徑零樣式成本
3. **單遍字符分派解析**：預編譯正則塊匹配，無逐字符循環、無逐 token 正則風暴
