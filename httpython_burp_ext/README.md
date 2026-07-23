# httpython

BurpSuite 拡張。Proxy history / Repeater で捕捉した HTTP リクエストを、
`requests` モジュールを使った Python 関数へ変換・生成する。

仕様は [`ARCHITECT.md`](./ARCHITECT.md) を参照。

## 構成

- `httpython.py` — 拡張本体（Jython / 単一ファイル）

## 導入

Burp は Python 拡張を Jython 経由でロードする。

1. [Jython Standalone JAR](https://www.jython.org/download) を入手する。
2. Burp の **Extender → Options → Python Environment** で、その JAR を指定する。
3. **Extender → Extensions → Add**
   - Extension type: **Python**
   - Extension file: `httpython.py`
4. ロードすると **httpython** タブが追加され、右クリックメニューに
   **Send to httpython** が現れる。

## 使い方

1. Proxy history / Repeater でリクエストを選択し、右クリック
   → **Send to httpython**。複数選択の一括転送に対応。
2. **httpython** タブでリクエストを選び、変換設定を行う。
   - 一覧の先頭 **「生成」列のチェックボックス**で、コード生成に使う
     リクエストを選ぶ。既定は全てチェック済み。チェックを外したものは
     出力スクリプトに含まれない（一覧からは消えない）。
   - **関数名 / コメント**
   - **パラメータ化**：クエリ / ボディ / ヘッダの各項目を「リテラル」か
     「関数の引数」かトグルし、引数名を編集できる。
   - **返り値の抽出ルール**：方式（`resobj` / `status` / `text` / `json` /
     `header` / `cookie` / `regex` / `custom`）を選び、必要な入力を与える。
     複数ルールを追加するとタプルで返る。
3. 上部の **Proxy URL** を設定する（例 `http://127.0.0.1:8080`）。
   **未設定では生成不可**。
4. **Generate** で「生成」列にチェックしたリクエストを 1 スクリプトへ出力し、
   **コピー / 保存**する。1 件も選ばれていない場合は生成できない。

### 抽出方式と入力欄

| 方式 | 入力欄の意味 | 生成される式 |
| --- | --- | --- |
| `resobj` | （なし） | `res` |
| `status` | （なし） | `res.status_code` |
| `text` | （なし） | `res.text` |
| `json` | ドット区切りキーパス `data.token` / `items.0.id` | `res.json()["data"]["token"]` |
| `header` | ヘッダ名 | `res.headers["Location"]` |
| `cookie` | Cookie 名 | `res.cookies["session"]` |
| `regex` | 正規表現（group(1) を返す） | `re.search(r'...', res.text).group(1)` |
| `custom` | 任意の Python 式（`res` 参照可） | そのまま |

## 生成コードの仕様

- 先頭に必要な import（`requests`、正規表現ルールがあれば `re`）。
- グローバル定数 `PROXIES` を 1 つだけ定義し、全関数が `proxies=PROXIES` で共有。
- 送信は常に `proxies=PROXIES` かつ `verify=False`。
- 各リクエストは `def <func>(base_url, <引数...>):` の関数となり、
  一覧の並び順で出力される。
- 関数には 1 行コメントが付く。

## 制約・注意

- Jython は Python 2.7 相当。**生成されるコードは Python 3 / `requests` 用**。
- プロキシ URL・各リクエストの変換設定はセッション中のみ保持（永続化しない）。
- ヘッダは `Host` / `Content-Length` を除外して取り込む。
- **Send to httpython の二重取り込み対策**：Burp の選択が同一リクエストを
  重複して返す／メニューのアクションが二重発火するケースでも、同一操作内では
  同じリクエストを1件だけ取り込む。意図して同じ内容を後から再度送る操作は妨げない。
