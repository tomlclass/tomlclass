# ユースケース

エンドツーエンドのシナリオ。すべてのコードはそのまま実行できます。

## サードパーティ TOML の安全な更新（pyproject 風）

他のツールが所有するファイルのバージョンを上げたい、フラグを切りたい — でもコメントは壊したくない：

```python
import tomlclass

tomlclass.update("pyproject.toml", {
    "project.version": "1.0.0",
    "tool.mytool.cache": True,       # [tool.mytool] がなければ作成
})
```

以降、触れていない行 — 他ツールのコメント、妙な空白、キー順序 — はバイト単位で同一です。

もっと外科的な操作には、エンジンを直接使います：

```python
doc = tomlclass.load("pyproject.toml")

doc["project"]["dependencies"].append("rich>=13.0")  # その場でスライス挿入、
                                                     # "click" のコメントは保持
doc["tool"]["mytool"] = {"cache": True}              # [tool.mytool] ブロックとしてレンダリング
doc.save("pyproject.toml")
```

## アプリ設定：初回起動から安定運用へ

典型的なアプリケーションのライフサイクル：初回起動でコメント付きテンプレートを配布、以降は検証とマージ、書き戻しは変更分だけ。

```python
from pathlib import Path

from tomlclass import Config, Field

class Server(Config):
    """HTTP server settings.

    host:
        Address to bind.
    port:
        Port to listen on.
    """

    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)


class App(Config):
    """Application configuration."""

    name: str = "demo"
    debug: bool = False
    server: Server


CONFIG = Path("app.toml")


def load_config() -> App:
    if not CONFIG.exists():
        CONFIG.write_text(App.template(), encoding="utf-8")  # 初回：コメント付きテンプレート
    return App.load(CONFIG, env_prefix="APP")                # 検証 + デフォルト + 環境変数


app = load_config()
app.debug = True
app.save(CONFIG)  # diff 書き戻し：debug だけ変更。ユーザーのコメントは保持される
```

不正な値を入れたとき、ユーザーに見えるのは：

```
ValidationError: 1 validation error(s): server.port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

説明はスキーマの docstring から直接来る — エラーは数値だけでなく、文書化された制約を指します。

## 完全な制御付きの一括編集

```python
import tomlclass

doc = tomlclass.load("app.toml")

doc.set_path("server.port", 9090)          # 変更；その行のコメントは保持
doc.set_path("logging.level", "debug")     # [logging] テーブルを作成
doc.set_comment("server.port", "exposed")  # コメントも差し替え
doc.save("app.toml")                       # 1 回のアトミック書き込み
```

## テーブルの配列（AoT）

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})  # 追加：新しいブロックとしてレンダリング
doc["products"] = [{"name": "sofa"}]      # 全体置換：旧要素は削除
```

## tomllib からの移行

```python
data = tomlclass.loads(text)   # プレーン dict（tomllib.loads と同じ規約）
data = tomlclass.load(fp)      # バイナリファイルオブジェクト（tomllib.load と同じ規約）

# 可逆編集が必要になったらいつでもアップグレード：
doc = tomlclass.load("pyproject.toml")  # パス引数 -> Document
```

## 環境変数オーバーライドとホットリロード

```python
# APP_SERVER__PORT=9000 は server.port を上書き（__ はパスセグメントの区切り）
server = Server.load("server.toml", env_prefix="APP")

# ホットリロード（オプション依存の watchfiles）；stop_event で別スレッドから停止。
# 検証失敗時は前の正常なインスタンスを保持し監視を続けます。
Server.watch("server.toml", callback, stop_event=event)
```

## スキーママイグレーション

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧キー -> 新ドットパス


new = AppV2.migrate(AppV1.load("app.toml"))
```
