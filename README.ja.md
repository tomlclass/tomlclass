[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | **日本語** | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

可逆 TOML 編集と型付き設定を、依存ゼロの 1 パッケージに。

設定ファイルの 1 つの値を、コメントを 1 つも壊さずに変更。スキーマを Python クラスで宣言すれば、コメント付きテンプレート・集約バリデーション・diff 書き戻しが手に入ります。

> **バージョニング**：tomlclass は 1.0 前であり、まだセマンティックバージョニングに厳密には従っていません。プロジェクトが安定するまでの間、マイナーバージョンの更新には新しい API の追加が含まれることがあります — 既存の API は常に後方互換性を維持します。

<p>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/pypi/v/tomlclass?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/tomlclass/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/tomlclass/actions/workflows/code-quality-check.yml"><img src="https://img.shields.io/github/actions/workflow/status/wsu2059q/tomlclass/code-quality-check.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/tomlclass/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge" alt="Ruff"></a>
</p>

<br clear="both">

---

## 特徴

- **可逆編集エンジン**：TOML 1.0/1.1 の解析と書き戻し；toml-test 1.5.0 の valid テスト **187/187 満点、唯一達成したライブラリ**。未編集ドキュメントは入力とバイト単位で同一にレンダリングされます
- **TOML 1.1 バージョンダイヤル**：`\e` / `\x` エスケープ、秒を省略した時刻、インラインテーブル内の改行と末尾カンマ、非 ASCII 裸キー — デフォルトで有効。`parse` / `loads` / `load` / `update` / `Config.load` に `toml_version="1.0"` を渡すと厳格な 1.0 の拒否セマンティクスになります
- **None を自由に**：オプションの rtoml 方式 `none_value` センチネル — `dumps(data, none_value="@None")` と `loads(text, none_value="@None")` で None を TOML 文字列経由で損なく往復させます
- **ワンライン更新**：`tomlclass.update("app.toml", `tomlclass.update("app.toml", {"server.port": 9090})`)` — 読み、変更し、アトミックに書き戻す。それ以外のコメント・順序・フォーマットは保持されます
- **型付き設定**：スキーマをクラスで宣言 — docstring がテンプレートのコメントになり、検証は全エラーをフィールドの文書化された意図付きで集約、デフォルト値はメモリでマージされ決して書き戻されません
- **コメント操作**：キーごとのコメントの読み取り・置換・削除；スキーマの説明をコメントとして注入（3 戦略）
- **tomllib 互換**：`loads` / `load` は標準ライブラリの呼び出し規約に従う — 移行コストゼロ

> **TOML バージョン境界**：上記の 1.1 追加機能はデフォルトで受け入れられます。1.0 無効な入力（`13:37` のような時刻など）を*拒否*することに依存しているコードは、`toml_version="1.0"` に切り替えてください — 同じファイルが `TOMLParseError` を発生させます。

## 準拠とパフォーマンス

データは [toml-bench](https://github.com/pwwang/toml-bench) による（toml-test 1.5.0 + CPython tomllib テストデータ；速度は同一マシンでの 5000 反復の load/dump、tomlclass 0.2.0 — 方法論は[パフォーマンスベースライン](tests/bench/BASELINE.md)）：

| チェック | tomlclass 0.2.0 |
|---|---|
| toml-test 1.5.0 valid（187 ファイル） | **187/187 — 満点は唯一** |
| toml-test 1.5.0 TOML-1.1 マニフェスト（548 ファイル） | **548/548** |
| CPython tomllib テストデータ | **12/12 valid、50/50 invalid** |

速度（load / dump、5000 反復）：

| ライブラリ | rtoml コーパス | tomli コーパス |
|---|---|---|
| rtoml 0.11（Rust） | 0.72s / 0.16s | 0.52s / 0.33s |
| tomli 2.4 + tomli_w | 1.52s / 1.17s | 1.26s / 0.84s |
| tomllib（CPython） | 3.39s / — | 2.15s / — |
| **tomlclass 0.2.0** | 4.26s / 3.80s | 3.12s / 2.22s |
| qtoml 0.3 | 7.78s / 2.97s | 6.35s / 1.97s |
| tomlkit 0.15 | 60.45s / 1.75s | 36.88s / 0.81s |

可逆編集の記帳コスト：loads は tomli の約 2.5–2.8 倍、dumps は tomli_w の約 2.6–3.2 倍 — ただし tomlkit より 12–14 倍高速です。

## インストール

```bash
pip install tomlclass
```

## 使い方

### 1 つの値だけ変え、ほかはすべて保持

```python
import tomlclass

tomlclass.update("pyproject.toml", {"project.version": "1.0.0"})
# その行だけ変わる — コメント・順序・フォーマットはそのまま
```

### TOML ファイルの編集（完全な制御）

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # その場でスライス挿入、コメント保持
text = doc.dumps()                                   # 触れた行だけ変わる
```

### 宣言的設定

```python
from tomlclass import Config

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


server = Server.load("server.toml")  # 読み込み + 検証 + デフォルト値のマージ
server.port = 9000
server.save("server.toml")           # 変更されたキーだけ書き込む
```

## ドキュメント

- [エンジン](docs/ja/engine.md) — 解析、編集、`update()`、コメント API、エラー
- [設定アノテーション](docs/ja/config.md) — スキーマ宣言、テンプレート、load/save のセマンティクス、検証エラー
- [コメント](docs/ja/comments.md) — コメントの帰属、注入モード
- [ユースケース](docs/ja/examples.md) — エンドツーエンドのシナリオ
- [パフォーマンス](docs/ja/performance.md) — 実測ベースライン

## 要件

Python ≥ 3.10、サードパーティ依存なし。

## ライセンス

[MIT](LICENSE)
