# 設定アノテーション

設定構造をクラスで宣言：docstring がテンプレートのコメントになり、読み取り時に検証され、書き戻しは変更されたキーだけに触れます。

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

- docstring の最初の段落がテーブルのコメントに；`field:` セクションがキー上のコメントになる（テンプレートでは `#` 行としてレンダリング）
- ネストしたクラス = ネストしたテーブル；`list[T]` は要素検証をサポート；アンダースコア始まりのフィールドは除外
- `Field` の制約：`ge / le / gt / lt / pattern / min_length / max_length / coerce`
- フィールドの説明は i18n 辞書をサポート：`Field(description={"i18n": key, "default": text})`

## エントリポイント

```python
app = App()                        # 純デフォルト値（メモリ上）
app = App.load("app.toml")         # 解析 + 検証 + デフォルト値のマージ
text = App.template()              # コメント付きテンプレート（同一スキーマならバイト安定）
errors = App.validate_dict(raw)    # オフライン検証、全エラーを集約
app.save("app.toml")               # diff 書き戻し（アトミック）
```

## 検証エラー

`validate_dict` と `load` は、最初のエラーで失敗するのではなく、**すべての**違反を 1 つの `ValidationError` に集約します。各 `FieldError` はドットパス、何が悪いかを示し、フィールドに説明があればその文書化された意図も添えます：

```python
class Server(Config):
    """HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = Field(8000, ge=1, le=65535)


Server.validate_dict({"port": 70000})
# ValidationError: 1 validation error(s): port: value 70000 exceeds the maximum 65535 (Port to listen on.)
```

メッセージは違反した境界を平易な言葉で示し、スキーマの説明を指すので、スキーマのソースを開かなくても修正は通常明白です。

## ビューセマンティクス

1. デフォルト値は決して永続化されない — ファイルにはユーザーが変更したキーだけが入る
2. 未知のキーは保持される（`strict=True` でエラーに変わる、ネストしたテーブルにも伝播）
3. diff 書き戻し — 解析時のスナップショットと比較し、変更されたキーだけを書き込む
4. Optional フィールドへの `None` = 保存時にキーを削除；非 optional フィールドへの `None` は保存時に `ConfigError` を発生
5. アトミック書き込み — tempfile + `os.replace`

## 環境変数オーバーライドとホットリロード

```python
# MYAPP_SERVER__PORT=9000 は server.port を上書き（__ はパスセグメントの区切り、
# 注釈型へのベストエフォート変換）
app = App.load("app.toml", env_prefix="MYAPP")

# ホットリロード：オプション依存の watchfiles；検証失敗時は前の正常なインスタンスを
# 保持し監視を続けます。stop_event で別スレッドから停止できます。
Server.watch("server.toml", callback, stop_event=event)
```

## マイグレーション

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧キー -> 新ドットパス


new = AppV2.migrate(AppV1.load("app.toml"))
```
