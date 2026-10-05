# シナリオ例

以下のコードはそのままコピーして実行できます。

## サードパーティ TOML の編集（pyproject 類）

```python
import tomlclass

doc = tomlclass.parse(pyproject_text)

doc["project"]["version"] = "1.0.0"
doc["project"]["dependencies"].append("rich>=13.0")  # その場に挿入、"click" の行末コメントは保持
doc["tool"]["mytool"] = {"cache": True}              # [tool.mytool] ブロックとして描画
```

## アプリ設定の読み書き

```python
from tomlclass import Config

class Server(Config):
    """
    HTTP server settings.

    port:
        Port to listen on.
    """

    port: int = 8000


with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp) / "server.toml"
    cfg.write_text("port = 8080  # exposed\n", encoding="utf-8")

    server = Server.load(cfg)
    server.port = 9090
    server.save(cfg)
    # 結果：port の行だけが変化し、"# exposed" コメントは保持されます
```

## テーブル配列（AoT）

```python
doc = tomlclass.parse('[[products]]\nname = "chair"\n')

doc["products"].append({"name": "lamp"})             # 追加：新しいブロックとして描画
doc["products"] = [{"name": "sofa"}]                 # 全体置換：旧要素はクリア
```

## tomllib からの移行

```python
data = tomlclass.loads(text)   # プレーン dict（tomllib.loads と同じ規約）
data = tomlclass.load(fp)      # バイナリファイルオブジェクト（tomllib.load と同じ規約）

# 可逆編集が必要なときは Document へアップグレード：
doc = tomlclass.load("pyproject.toml")  # パス引数 -> Document
```

## 環境変数オーバーライドとホットリロード

```python
# DEMO_SERVER__PORT=9000 が server.port を上書き
server = Server.load(cfg, env_prefix="DEMO")

# ホットリロード（オプション依存 watchfiles）。stop_event で別スレッドから停止できます
Server.watch("server.toml", callback, stop_event=event)
```

## schema 移行

```python
class AppV2(App):
    _migrate_key_map = {"username": "user.name"}  # 旧キー -> 新ドットパス


new = AppV2.migrate(AppV1.load("app.toml"))
```
