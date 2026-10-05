# tomlclass ドキュメント

tomlclass は TOML 設定ライブラリ：可逆編集エンジン + 型付き設定アノテーション、依存ゼロ。

設定ファイルを書き戻してもコメントとフォーマットを完全に保持。Python クラスで設定構造を宣言すると、コメント付きテンプレートの生成と検証を自動で行います。設定セマンティクスは [ErisPulse](https://github.com/ErisPulse/ErisPulse) フレームワークの設定システムが由来です。

## ドキュメント一覧

| ドキュメント | 内容 |
|---|---|
| [エンジン層](engine.md) | Document、編集、tomllib 互換、エラー |
| [アノテーション層](config.md) | Config、Field、ビュー意味論、env オーバーライド |
| [コメントシステム](comments.md) | 所有モデル、読み取りと置換 |
| [シナリオ例](examples.md) | よくあるシナリオのコード |
| [パフォーマンス](performance.md) | ベースラインデータと実測比較 |

## インストール

```bash
pip install tomlclass
```

Python ≥ 3.10、サードパーティ依存ゼロ。

## 最小例

```python
import tomlclass

doc = tomlclass.parse(text)
doc["project"]["version"] = "1.0.0"
text = doc.dumps()  # 触れた行だけが変化
```

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


server = Server.load("server.toml")
server.port = 9000
server.save("server.toml")
```
