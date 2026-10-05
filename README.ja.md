[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | **日本語** | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>

# tomlclass

TOML 設定ライブラリ：自製の可逆編集エンジン + 型付き設定アノテーション、依存ゼロ。

設定ファイルを書き戻してもコメントとフォーマットを完全に保持。Python クラスで設定構造を宣言すると、コメント付きテンプレートの生成と検証を自動で行います。設定セマンティクスは [ErisPulse](https://github.com/ErisPulse/ErisPulse) フレームワークの設定システムが由来です。

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

- **可逆編集エンジン**：フル型 TOML 1.0 の解析と書き戻し、toml-test 1.0 の全 709 ケースに合格。未編集ドキュメントのレンダリングは入力とバイト単位で同一
- **型付き設定**：クラスで schema を宣言、docstring がテンプレートのコメントになり、検証はエラーを集約。デフォルト値はメモリ上でマージされるだけで書き戻されません
- **コメント操作**：キー単位でのコメント読み取り・置換・削除。schema 説明をコメントとして注入可能（3 モード）
- **tomllib 互換**：`loads` / `load` は標準ライブラリと同じ規約。移行コストゼロ

## なぜ tomlkit ではないのか

tomlkit は可逆編集のデファクトスタンダードであり、本プロジェクトのエンジンはそれをベースラインとして設計しました。tomlclass の優位点：

| 次元 | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| 解析速度（同一マシン実測） | ベースライン | **5.8–6.4× 高速** |
| プレーン dict の取得 | `parse(dumps(doc))` の往復が必要 | `to_dict()` が直接構築、往復ゼロ |
| コメント操作 | スタイルオブジェクトに埋もれ、キー単位 API なし | `doc.comment(key)` / `set_comment` が第一級 |
| schema / テンプレート / 検証 | なし — 自前で組み合わせる | `Config` に内蔵（テンプレート、集約検証、env オーバーライド、移行） |
| 常駐メモリ | ベースライン | **0.67×** |

出典：[パフォーマンス基準](tests/bench/BASELINE.md)（同一マシン・同一反復回数で実測）。

## インストール

```bash
pip install tomlclass
```

## 使い方

### TOML ファイルの編集

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # その場に挿入、コメントは保持
text = doc.dumps()                                   # 触れた行だけが変化
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


server = Server.load("server.toml")  # 読み込み + 検証 + デフォルト値マージ
server.port = 9000
server.save("server.toml")           # 変更されたキーだけ書き込みます
```

## ドキュメント

- [エンジン層](docs/ja/engine.md) — Document、編集、tomllib 互換、エラー
- [アノテーション層](docs/ja/config.md) — Config、Field、ビュー意味論、env オーバーライド
- [コメントシステム](docs/ja/comments.md) — 所有モデル、読み取りと置換
- [シナリオ例](docs/ja/examples.md) — よくあるシナリオのコード
- [パフォーマンス](docs/ja/performance.md) — ベースラインデータと実測比較

## 依存関係と環境

Python ≥ 3.10、サードパーティ依存ゼロ。

## ライセンス

[MIT](LICENSE)
