# エンジン層

エンジン層は任意の TOML 1.0 ドキュメントを対象とします：解析・読み取り・変更・レンダリング・アトミック保存、コメントとフォーマットはバイト単位で保持されます。

## 解析とレンダリング

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # ファイルパスから解析
doc.dumps()                      # str へレンダリング：未編集時は入力とバイト単位で同一
doc.save(path)                   # アトミック書き込み（tempfile + os.replace）
```

**ラウンドトリップ公理**：`parse(text).dumps() == text` がバイト単位で成立。全 PR で検証されます。

## tomllib 互換

```python
data = tomlclass.loads(text)  # プレーン dict、tomllib.loads と同じ規約
data = tomlclass.load(fp)     # バイナリファイルオブジェクト、tomllib.load と同じ規約
```

## 編集

```python
doc["project"]["version"] = "1.0.0"   # 変更：行の中で値だけが置き換わる
del doc["tool"]["old"]                # 削除：コメントと先行空白もきれいに除去
doc["server"]["workers"] = 4          # 新キー：テーブルの最終エントリの後に描画
doc["logging"] = {"level": "info"}    # 新テーブル：[logging] ブロックとして描画
doc["products"].append(...)           # 配列追加：ソーススプライス、既存要素とコメントは不変
doc["products"] = [...]               # AoT 全体置換：旧要素を消去、新要素をブロックで描画
```

- 編集は正規レンダリングを使用：新しく書き込まれる値は標準書式
- 未触碰部分はソーススライスを直接読みます
- インラインテーブルはクローズド：全体を再代入してください

## コメント

```python
doc.comment("server.port")            # -> "the port"（コメントなしは None）
doc.set_comment("server.port", "API ポート")
doc.set_comment("server.port", None)  # 削除（先行空白も含めて）
```

コメントはそのキーに紐付きます。テーブルコメントはヘッダ行にあり、テーブルパスで指定します。

## エラー

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` は `ValueError` のサブクラスです。シリアライズ不可能な値（`None`、関数など）を代入すると `TOMLTypeError`（`TypeError` サブクラス）が発生します。
