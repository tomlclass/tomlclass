# tomlclass ドキュメント

tomlclass は TOML 設定ライブラリ：可逆編集エンジン + 型付き設定アノテーション。依存ゼロ、Python ≥ 3.10。

2 レイヤーはそれぞれ単独で使えます：

- **エンジン層** — 任意の TOML 1.0/1.1 ドキュメントを解析・編集し、すべてのコメント・キー順序・フォーマットをバイト単位で保ったまま書き戻します。
- **アノテーション層** — Python クラスで設定スキーマを宣言すると、コメント付きテンプレート・集約バリデーション・diff 書き戻しが手に入ります。

## 60 秒ツアー

1 つの値だけ変更し、ほかには何も触れない：

```python
import tomlclass

tomlclass.update("app.toml", {"server.port": 9090})
# その行だけ変わる — コメント・順序・フォーマットはすべて保持
```

またはスキーマ経由で設定ファイルを管理：

```python
from tomlclass import Config

class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")  # 解析 + 検証 + デフォルト値のマージ
server.port = 9090
server.save("server.toml")           # diff 書き戻し：変更されたキーだけ書き込み
```

## 目次

| ドキュメント | 内容 |
|---|---|
| [エンジン](engine.md) | 解析、編集、`update()`、コメント API、エラー |
| [設定アノテーション](config.md) | スキーマ宣言、テンプレート、load/save のセマンティクス、検証エラー |
| [コメント](comments.md) | コメントの帰属、注入モード |
| [ユースケース](examples.md) | エンドツーエンドのシナリオ：pyproject の安全な更新、アプリ設定のライフサイクル、AoT、ホットリロード |
| [パフォーマンス](performance.md) | 実測ベースラインと測定方法 |

## インストール

```bash
pip install tomlclass
```
