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
- **UI / Burp 連携**: `BurpExtender`（`IBurpExtender` / `ITab` /
  `IContextMenuFactory`）。Swing で構築。

### UI 状態管理の要注意点

- Swing の `ListSelectionListener`（`_on_select`）は**再入しやすい**。テーブルを
  プログラムから作り直すと選択イベントが発火し、ハンドラが再帰する。
  → `self._suppress` フラグでプログラム的更新中の選択イベントを抑止する。
  一覧の作り直し＋選択＋パネル読み込みは `_rebuild_and_select()` に集約し、
  選択ハンドラ内では全体再構築をしない（該当行だけ `_update_row_display()`）。
- **メッセージの二重取り込み対策**: `getSelectedMessages()` の重複返却や
  ActionListener の二重発火に備え、`_add_requests()` は
  `System.identityHashCode` で同一操作内の重複を除外する（`self._recent`、
  次の EDT サイクルでクリア）。
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
