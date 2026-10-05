# アノテーション層

クラスで設定構造を宣言：docstring がテンプレートのコメントになり、読み取り時に検証、書き戻しは変更されたキーだけに触れます。

## 宣言

```python
from tomlclass import Config, Field

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


class App(Config):
    name: str = Field("demo", ge=1)
    debug: bool = False
    server: Server
    tags: list[str] = []
```

- docstring の最初の段落 → テーブルコメント。`フィールド名:` 節 → キー上のコメント（テンプレート内で `#` 行として描画）
- ネストしたクラス = ネストしたテーブル。`list[T]` は要素検証に対応。アンダースコア始まりのフィールドは除外
- `Field` 制約：`ge / le / gt / lt / pattern / min_length / max_length / coerce`
- フィールド説明は i18n 辞書対応：`Field(description={"i18n": key, "default": text})`

## エントリポイント

```python
app = App()                        # 純粋なデフォルトインスタンス
app = App.load("app.toml")         # 解析 + 検証 + デフォルトマージ
text = App.template()              # コメント付きテンプレート（同一 schema ならバイト安定）
errors = App.validate_dict(raw)    # オフライン検証、全エラーを集約
app.save("app.toml")               # diff 書き戻し（アトミック）
```

## ビュー意味論

1. デフォルト値は永不落盤——ファイルにはユーザーが変更したキーしか現れません
2. 未知キーは保持（`strict=True` でエラーに変更可能）
3. diff 書き戻し——解析時スナップショットと比較し、変更のあったキーだけ書き込みます
4. Optional フィールドへの `None` = 保存時にキー削除。非 Optional への `None` は保存時に `ConfigError`
5. アトミック書き込み——tempfile + `os.replace`

## 環境変数オーバーライドとホットリロード

```python
# MYAPP_SERVER__PORT=9000 が server.port を上書き（__ はパス区切り、注解型への変換はベストエフォート）
app = App.load("app.toml", env_prefix="MYAPP")

# ホットリロード：オプション依存 watchfiles。検証失敗時は前の正常インスタンスを維持し監視を継続
Server.watch("server.toml", callback, stop_event=event)
```

## 移行

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧キー -> 新ドットパス


new = AppV2.migrate(AppV1.load("app.toml"))
```
