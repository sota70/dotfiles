# CLAUDE.md

このリポジトリで作業する際のガイド。

## プロジェクト概要

**httpython** は BurpSuite 拡張。Proxy history / Repeater で捕捉した HTTP
リクエストを専用タブへ転送し、`requests` モジュールを使った Python 関数へ
変換・生成する。仕様は [`ARCHITECT.md`](./ARCHITECT.md)。

## 構成

| ファイル | 役割 |
| --- | --- |
| `httpython.py` | 拡張本体（Jython / Burp Extender API・単一ファイル） |
| `ARCHITECT.md` | 仕様書（要件の一次情報） |
| `README.md` | 導入・使い方 |

## 実行・検証環境

- Burp は Python 拡張を **Jython 2.7** 経由でロードする。生成される**コードは
  Python 3 / `requests` 用**。この2つの Python バージョンを混同しないこと。
- この開発環境には Burp も Jython も無いため、UI の実機確認はできない。
- 純粋ロジック（コード生成）は、`java` / `javax.swing` / `burp` を
  スタブして Python 3 で検証する。手法は
  `scratchpad/test_gen.py`（セッションのスクラッチパッド）を参照。
  検証時は `long` / `basestring` / `unicode` を Python2 互換で定義し、
  `DefaultTableModel` を本物の基底クラスに差し替える。

## httpython.py のアーキテクチャ

- **データモデル**: `Param`（クエリ/ボディ/ヘッダの1項目）、`Rule`（抽出ルール）、
  `ReqItem`（変換対象リクエスト1件）。
- **コード生成**（純粋関数群）: `generate_script()` が入口。`_generate_function()`、
  `_rule_code()`、`_dict_code()`、`_py_literal()` など。UI に依存しないため単体検証可能。
- **文字化け対策（str/unicode 統一）**: Jython 2.7 では非 ASCII を含む**バイト文字列
  リテラル**（`u` 接頭辞なし）は UTF-8 バイト列になる。これを Swing の `setText`
  （Java String = Unicode を期待）へ渡すとバイト列がそのまま文字として解釈され、
  コメント等が文字化けする。**日本語を含む生成断片は必ず `unicode` にすること**。
  具体的には `_generate_function()` のコメント行・`join` を `u"..."` で組み、
  `item.comment`（`_as_str` で unicode 化）を Unicode で連結する。関数群が Unicode に
  なれば `generate_script()` の戻り値も Unicode に昇格し、`codeArea.setText()` で
  正しく表示される。
- **コメント行の生成方針**: `item.comment` が空のときは**コメント行を出力しない**
  （デフォルトコメントは生成しない）。`_generate_function()` はコメントがある場合のみ
  `# <comment>` を先頭行に追加する。
- **UI / Burp 連携**: `BurpExtender`（`IBurpExtender` / `ITab` /
  `IContextMenuFactory`）。Swing で構築。

### UI 状態管理の要注意点

- Swing の `ListSelectionListener`（`_on_select`）は**再入しやすい**。テーブルを
  プログラムから作り直すと選択イベントが発火し、ハンドラが再帰する。
  → `self._suppress` フラグでプログラム的更新中の選択イベントを抑止する。
  一覧の作り直し＋選択＋パネル読み込みは `_rebuild_and_select()` に集約し、
  選択ハンドラ内では全体再構築をしない（該当行だけ `_update_row_display()`）。
- **メッセージの二重取り込み対策**: `getSelectedMessages()` が返す
  `IHttpRequestResponse` は request と response を内包しており、Repeater 等では
  request 側・response 側の別オブジェクトとして同一メッセージが2回返り、
  「1回の Send to httpython で2件」取り込まれることがある。`System.identityHashCode`
  （オブジェクト同一性）では別オブジェクトの重複を取りこぼすため、`_add_requests()` は
  `_request_signature()`（`getRequest()` のバイト列を `bytesToString` した署名。
  取得失敗時のみ `identityHashCode` にフォールバック）で同一操作内の重複を除外する
  （`self._recent`、次の EDT サイクルでクリア）。Proxy history の重複返却や
  ActionListener の二重発火にも同じ仕組みで対応する。
- **生成対象の選択**: 一覧テーブル先頭に `生成` チェックボックス列（Boolean）が
  あり、`ReqItem.include` に対応する。編集は `_on_req_model_change`
  （TableModelListener）で `include` に書き戻す（`_suppress` 中は無視）。
  `_on_generate` は `include` が真のものだけを `generate_script()` へ渡す。
  列追加に伴い一覧の列インデックスは 0=生成,1=#,2=Method,3=Host,4=Path,5=Func。
  `_update_row_display()` はこのインデックスに依存する。

## 運用ルール

- **コードを変更したら、同じ作業内で必ず `CLAUDE.md` と `README.md` を更新する。**
- 生成コードの体裁は仕様書 5.4 の例（ログイン / CSRF）と一致させること。
  これが回帰確認の基準になる。
