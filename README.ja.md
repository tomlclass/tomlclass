[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | **日本語** | [Русский](README.ru.md)

<p align="center">
  <img src=".github/assets/tomlclass-logo.svg" alt="tomlclass" width="520">
</p>


# tomlclass

可逆 TOML 編集と型付き設定を、依存ゼロの 1 パッケージに。

設定ファイルの 1 つの値を、コメントを 1 つも壊さずに変更。スキーマを Python クラスで宣言すれば、コメント付きテンプレート・集約バリデーション・diff 書き戻しが手に入ります。

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

- **可逆編集エンジン**：フルタイプの TOML 1.0 解析と書き戻し；toml-test 1.0 の全 709 ケースに合格。未編集ドキュメントは入力とバイト単位で同一にレンダリング
- **ワンライン更新**：`tomlclass.update("app.toml", {"server.port": 9090})` — 読み、変更し、アトミックに書き戻す。それ以外のコメント・順序・フォーマットは保持
- **型付き設定**：スキーマをクラスで宣言 — docstring がテンプレートのコメントになり、検証は全エラーをフィールドの文書化された意図付きで集約、デフォルト値はメモリでマージされ決して書き戻されない
- **コメント操作**：キーごとのコメントの読み取り・置換・削除；スキーマの説明をコメントとして注入（3 戦略）
- **tomllib 互換**：`loads` / `load` は標準ライブラリの呼び出し規約に従う — 移行コストゼロ

## なぜ tomlkit ではないのか

tomlkit は可逆編集の事実上の標準であり、本プロジェクトのエンジンはそれをベースラインとして作られました。tomlclass が勝る点：

| 次元 | tomlkit 0.15 | tomlclass 0.1 |
|---|---|---|
| 解析速度（同一マシン） | ベースライン | **5.8–6.4× 高速** |
| プレーン dict の取得 | `parse(dumps(doc))` の往復 | `to_dict()` が直接構築、往復ゼロ |
| コメント操作 | スタイルオブジェクトの奥に埋もれ、キーごとの API なし | `doc.comment(key)` / `set_comment` が第一級 |
| スキーマ / テンプレート / 検証 | なし — 自分で組み立てる | `Config` に内蔵（テンプレート、集約検証、環境変数オーバーライド、マイグレーション） |
| 常駐メモリ | ベースライン | **0.67×** |

出典：[パフォーマンスベースライン](tests/bench/BASELINE.md)（同一マシン、同一反復回数）。

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
