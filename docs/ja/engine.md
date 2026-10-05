# エンジン

エンジンは任意の TOML 1.0/1.1 ドキュメントを対象とします：解析・読み取り・編集・レンダリング・アトミック保存 — コメントとフォーマットはバイト単位で保持されます。

## 解析とレンダリング

```python
import tomlclass

doc = tomlclass.parse(text)      # str -> Document
doc = tomlclass.load(path)       # ファイルパスから解析 -> Document
doc.dumps()                      # str へレンダリング：未編集なら入力とバイト単位で同一
doc.save(path)                   # アトミック書き込み（tempfile + os.replace）
```

**ラウンドトリップ公理**：`parse(text).dumps() == text` はバイト単位で成立し、毎回のコミットで toml-test 1.0 スイートにより検証されます（valid 208 ファイルすべてが正確にラウンドトリップ、invalid 501 ファイルすべてが拒否）。

## 保持の仕組み

未編集のノードはソース中の `(start, end)` スパンだけを記録し、レンダリングは元テキストをスライスします。フォーマットはどこにも記録されません — ソーステキストそのものであり、触れなければ自然に残ります。ノードが編集されたときのみ、tomlclass はそのノードのレンダリング出力（正規フォーマット）を生成し、それ以外はソーススライスのままです。

帰結：未編集ドキュメントの `dumps` は約 O(1)、読み取りパスはフォーマットデータを一切保持せず、編集コストは編集サイズに比例しドキュメント全体の長さにはほぼ依存しません。

## tomllib 互換

```python
data = tomlclass.loads(text)  # プレーン dict、tomllib.loads と同じ規約
data = tomlclass.load(fp)     # バイナリファイルオブジェクト、tomllib.load と同じ規約
```

## 編集

```python
doc["project"]["version"] = "1.0.0"   # 変更：その行の値だけ変わる
del doc["tool"]["old"]                # 削除：後続コメントをきれいに除去
doc["server"]["workers"] = 4          # 新キー：テーブルの最後のエントリの後にレンダリング
doc["logging"] = {"level": "info"}    # 新テーブル：[logging] ブロックとしてレンダリング
doc["products"].append(...)           # 配列追加：その場でスライス挿入、既存要素は無傷
doc["products"] = [...]               # AoT 全体置換：旧要素を削除、新要素はブロックで
```

- 編集値は正規フォーマットでレンダリング；未編集部分はソーススライスから直接読む
- インラインテーブルは閉じている：キーを追加せず、値全体を再代入する
- ドットキーで作られたテーブルは封印されている：キーを追加すると、最後の物理行にアンカーされたドット行としてレンダリングされる

### ドットパスアクセス

```python
doc.find("server.port")            # -> 値または None
doc.set_path("server.port", 9090)  # 代入；欠けているキーと中間テーブルは自動生成
```

`set_path` は欠けているテーブルを、エントリを含む本物の `[table]` ブロックとして構築します — ドット行 + 空ヘッダ（同じテーブルを二重定義する不正な TOML）としてレンダリングされることはありません。

## ワンコール更新

```python
tomlclass.update("app.toml", {"server.port": 9090, "name": "prod"})
```

ファイルを読み、各ドットキーへの代入を適用し、アトミックに書き戻し、`Document` を返します。TOML で表現できない値が 1 つでもあれば何も書き込みません。`None` は TOML の値ではありません — キーの削除はマッピング API（`del doc[...]`）を使ってください。

## コメント

```python
doc.comment("server.port")            # -> "the port"（なければ None）
doc.set_comment("server.port", "API port")
doc.set_comment("server.port", None)  # 削除（先頭の空白ごと）
```

コメントはその後に続くキーに帰属します。テーブルコメントはヘッダ行にあり、テーブルパスで指定します。完全なモデルは[コメント](comments.md)を参照。

## エラー

```python
try:
    tomlclass.parse(text)
except tomlclass.TOMLParseError as e:
    print(e.line, e.col, e.segment)
```

`TOMLParseError` は `ValueError` のサブクラスです。シリアライズできない値（`None`、関数、任意オブジェクト）を代入すると、レンダリング時ではなく代入時に `TOMLTypeError`（`TypeError` のサブクラス）が発生します。
