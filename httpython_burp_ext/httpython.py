# -*- coding: utf-8 -*-
"""
httpython - BurpSuite extension

Proxy history / Repeater で捕捉した HTTP リクエストを httpython タブへ転送し、
`requests` モジュールを使った Python 関数へ変換・生成する拡張。

ロード方法:
  Extender -> Options で Jython スタンドアロン JAR を設定した上で、
  Extender -> Extensions -> Add -> Extension type: Python -> このファイルを選択。

仕様: ARCHITECT.md
"""

import json
import re as _re
import urllib

import java.lang
from java.awt import BorderLayout, Dimension, FlowLayout, Font, Toolkit
from java.awt.datatransfer import StringSelection
from javax.swing import (
    BorderFactory, DefaultCellEditor, JButton, JComboBox, JFileChooser,
    JLabel, JMenuItem, JOptionPane, JPanel, JScrollPane, JSplitPane, JTable,
    JTextArea, JTextField, ListSelectionModel, SwingUtilities,
)
from javax.swing.table import DefaultTableModel

from burp import IBurpExtender, IContextMenuFactory, ITab


# --------------------------------------------------------------------------
# 抽出方式のキー
# --------------------------------------------------------------------------
EXTRACT_METHODS = [
    "resobj",   # return res
    "status",   # return res.status_code
    "text",     # return res.text
    "json",     # return res.json()[...]
    "header",   # return res.headers[...]
    "cookie",   # return res.cookies[...]
    "regex",    # return re.search(...).group(1)
    "custom",   # 任意の Python 式
]


# --------------------------------------------------------------------------
# データモデル
# --------------------------------------------------------------------------
class Param(object):
    """パラメータ化対象となる 1 項目 (クエリ/ボディ/ヘッダ)。"""

    def __init__(self, section, key, value):
        self.section = section          # "query" | "body" | "header"
        self.key = key
        self.value = value              # str もしくは JSON 値
        self.parameterize = False
        self.arg_name = _sanitize_ident(key)


class Rule(object):
    """レスポンス抽出ルール 1 件。"""

    def __init__(self, method="resobj", expr=""):
        self.method = method
        self.expr = expr


class ReqItem(object):
    """httpython タブに転送された変換対象リクエスト 1 件。"""

    def __init__(self):
        self.method = "GET"
        self.scheme = "https"
        self.host = ""
        self.port = -1
        self.path = "/"
        self.func_name = "req"
        self.comment = ""
        self.query = []             # [Param]
        self.body_params = []       # [Param]  (json / form)
        self.headers = []           # [Param]
        self.body_kind = "none"     # "json" | "form" | "raw" | "none"
        self.raw_body = ""
        self.content_type = None
        self.rules = [Rule("resobj", "")]
        self.include = True         # 生成対象に含めるか

    def all_params(self):
        """パラメータ化トグルの並び (クエリ -> ボディ -> ヘッダ)。"""
        return self.query + self.body_params + self.headers

    def display(self):
        host = self.host
        if self.port not in (-1, 80, 443):
            host = "%s:%d" % (host, self.port)
        return (self.method, host, self.path, self.func_name)


# --------------------------------------------------------------------------
# ヘルパ
# --------------------------------------------------------------------------
def _sanitize_ident(name):
    """任意の文字列を Python 識別子として妥当な小文字名へ変換する。"""
    s = _re.sub(r"[^0-9a-zA-Z_]", "_", str(name)).lower()
    if not s:
        s = "arg"
    if s[0].isdigit():
        s = "_" + s
    return s


def _is_valid_ident(name):
    return bool(_re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name or ""))


def _as_bool(v):
    """DefaultTableModel が返す java.lang.Boolean / None を Python bool へ。"""
    if v is None:
        return False
    try:
        return bool(v.booleanValue())
    except AttributeError:
        return bool(v)


def _as_str(v):
    return u"" if v is None else unicode(v)


def _py_literal(v):
    """Python ソースとして妥当なリテラル文字列を返す。"""
    if v is True:
        return "True"
    if v is False:
        return "False"
    if v is None:
        return "None"
    if isinstance(v, (int, long, float)):
        return repr(v)
    if isinstance(v, basestring):
        # json.dumps はダブルクオートで妥当な Python 文字列リテラルを生成する
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        items = ", ".join(
            '%s: %s' % (_py_literal(k), _py_literal(val)) for k, val in v.items()
        )
        return "{%s}" % items
    if isinstance(v, (list, tuple)):
        return "[%s]" % ", ".join(_py_literal(x) for x in v)
    return json.dumps(str(v), ensure_ascii=False)


def _dict_code(pairs):
    """(key, value_code) のリストから複数行の dict リテラル文字列を生成する。"""
    if not pairs:
        return "{}"
    lines = ['        %s: %s' % (json.dumps(k, ensure_ascii=False), code)
             for k, code in pairs]
    return "{\n" + ",\n".join(lines) + "\n    }"


# --------------------------------------------------------------------------
# 抽出ルール -> 式コード
# --------------------------------------------------------------------------
def _json_keypath_code(keypath):
    code = "res.json()"
    if not keypath.strip():
        return code
    for token in keypath.strip().split("."):
        token = token.strip()
        if token == "":
            continue
        if _re.match(r"^-?\d+$", token):
            code += "[%s]" % token
        else:
            code += "[%s]" % json.dumps(token, ensure_ascii=False)
    return code


def _regex_code(pattern):
    if "'" not in pattern:
        return "re.search(r'%s', res.text).group(1)" % pattern
    if '"' not in pattern:
        return 're.search(r"%s", res.text).group(1)' % pattern
    return "re.search(%s, res.text).group(1)" % json.dumps(pattern, ensure_ascii=False)


def _rule_code(rule):
    m = rule.method
    if m == "resobj":
        return "res"
    if m == "status":
        return "res.status_code"
    if m == "text":
        return "res.text"
    if m == "json":
        return _json_keypath_code(rule.expr)
    if m == "header":
        return "res.headers[%s]" % json.dumps(rule.expr, ensure_ascii=False)
    if m == "cookie":
        return "res.cookies[%s]" % json.dumps(rule.expr, ensure_ascii=False)
    if m == "regex":
        return _regex_code(rule.expr)
    if m == "custom":
        return rule.expr.strip()
    return "res"


# --------------------------------------------------------------------------
# コード生成
# --------------------------------------------------------------------------
class GenerationError(Exception):
    pass


def _param_value_code(p):
    """パラメータ化されていれば引数名、そうでなければリテラル。"""
    if p.parameterize:
        return p.arg_name
    return _py_literal(p.value)


def _generate_function(item):
    """1 件の ReqItem を Python 関数ソースへ変換する。"""
    args = ["base_url"]
    for p in item.all_params():
        if p.parameterize:
            args.append(p.arg_name)

    # 呼び出し引数フラグメントを組み立てる
    path = item.path if item.path else "/"
    frags = ['base_url + %s' % json.dumps(path, ensure_ascii=False)]

    if item.headers:
        frags.append("headers=" + _dict_code(
            [(p.key, _param_value_code(p)) for p in item.headers]))

    if item.query:
        frags.append("params=" + _dict_code(
            [(p.key, _param_value_code(p)) for p in item.query]))

    if item.body_kind == "json" and item.body_params:
        frags.append("json=" + _dict_code(
            [(p.key, _param_value_code(p)) for p in item.body_params]))
    elif item.body_kind == "form" and item.body_params:
        frags.append("data=" + _dict_code(
            [(p.key, _param_value_code(p)) for p in item.body_params]))
    elif item.body_kind == "raw" and item.raw_body:
        frags.append("data=" + _py_literal(item.raw_body))

    frags.append("proxies=PROXIES")
    frags.append("verify=False")

    call = "requests.%s(%s)" % (item.method.lower(), ", ".join(frags))

    return_expr = ", ".join(_rule_code(r) for r in item.rules) or "res"

    comment = _as_str(item.comment).strip()

    lines = []
    if comment:
        lines.append(u"# " + comment)
    lines.extend([
        u"def %s(%s):" % (item.func_name, u", ".join(args)),
        u"    res = " + call,
        u"    return " + return_expr,
    ])
    return u"\n".join(lines)


def generate_script(requests_list, proxy_url):
    """全リクエストから完全な Python スクリプトを生成する。検証を含む。"""
    # --- バリデーション (ARCHITECT.md 7章) ---
    if not (proxy_url or "").strip():
        raise GenerationError(u"プロキシ URL が未設定です。生成できません。")
    if not requests_list:
        raise GenerationError(u"変換対象リクエストが 0 件です。")

    seen_funcs = set()
    for item in requests_list:
        if not _is_valid_ident(item.func_name):
            raise GenerationError(
                u"関数名が空または不正です: '%s'" % item.func_name)
        if item.func_name in seen_funcs:
            raise GenerationError(u"関数名が重複しています: '%s'" % item.func_name)
        seen_funcs.add(item.func_name)

        arg_seen = set(["base_url"])
        for p in item.all_params():
            if not p.parameterize:
                continue
            if not _is_valid_ident(p.arg_name):
                raise GenerationError(
                    u"[%s] 引数名が不正です: '%s'" % (item.func_name, p.arg_name))
            if p.arg_name in arg_seen:
                raise GenerationError(
                    u"[%s] 引数名が重複しています: '%s'" % (item.func_name, p.arg_name))
            arg_seen.add(p.arg_name)

        for r in item.rules:
            if r.method in ("regex", "custom", "json", "header", "cookie") \
                    and not r.expr.strip():
                raise GenerationError(
                    u"[%s] 抽出ルール(%s)の入力が空です。" % (item.func_name, r.method))

    # --- import ---
    need_re = any(r.method == "regex"
                  for item in requests_list for r in item.rules)
    imports = []
    if need_re:
        imports.append("import re")
    imports.append("import requests")

    proxies_block = (
        "PROXIES = {\n"
        '    "http": %s,\n'
        '    "https": %s,\n'
        "}"
    ) % (json.dumps(proxy_url.strip(), ensure_ascii=False),
         json.dumps(proxy_url.strip(), ensure_ascii=False))

    funcs = [_generate_function(item) for item in requests_list]

    return ("\n".join(imports) + "\n\n"
            + proxies_block + "\n\n\n"
            + "\n\n\n".join(funcs) + "\n")


# --------------------------------------------------------------------------
# Swing テーブルモデル
# --------------------------------------------------------------------------
class ReqListModel(DefaultTableModel):
    # 先頭列は「生成対象に含めるか」のチェックボックス
    def __init__(self):
        DefaultTableModel.__init__(
            self, [], ["生成", "#", "Method", "Host", "Path", "Func"])

    def getColumnClass(self, col):
        if col == 0:
            return java.lang.Boolean
        return java.lang.String

    def isCellEditable(self, row, col):
        return col == 0


class ParamTableModel(DefaultTableModel):
    COLS = ["Section", "Key", "Value", "Param?", "Arg name"]

    def __init__(self):
        DefaultTableModel.__init__(self, [], self.COLS)

    def getColumnClass(self, col):
        if col == 3:
            return java.lang.Boolean
        return java.lang.String

    def isCellEditable(self, row, col):
        return col in (3, 4)


class RuleTableModel(DefaultTableModel):
    def __init__(self):
        DefaultTableModel.__init__(self, [], ["Method", "Expression / KeyPath"])

    def isCellEditable(self, row, col):
        return True


# --------------------------------------------------------------------------
# 拡張本体
# --------------------------------------------------------------------------
class BurpExtender(IBurpExtender, ITab, IContextMenuFactory):

    # -- Burp entry point --
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        callbacks.setExtensionName("httpython")

        self.requests = []          # [ReqItem]
        self.current = -1           # 選択中インデックス
        self._suppress = False      # プログラム的なテーブル更新中の選択イベント抑止
        self._recent = set()        # 同一操作内で取り込み済みリクエストの署名(二重取り込み防止)

        self._build_ui()
        callbacks.customizeUiComponent(self.root)
        callbacks.addSuiteTab(self)
        callbacks.registerContextMenuFactory(self)
        self._set_status(u"準備完了。プロキシ URL を設定してください。")

    # -- ITab --
    def getTabCaption(self):
        return "httpython"

    def getUiComponent(self):
        return self.root

    # -- IContextMenuFactory --
    def createMenuItems(self, invocation):
        item = JMenuItem("Send to httpython")

        def _send(evt):
            msgs = invocation.getSelectedMessages()
            if msgs:
                self._add_requests(list(msgs))

        item.addActionListener(_send)
        return [item]

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        self.root = JPanel(BorderLayout())

        # --- NORTH: プロキシ設定 ---
        north = JPanel(FlowLayout(FlowLayout.LEFT))
        north.add(JLabel("Proxy URL:"))
        self.proxyField = JTextField("http://127.0.0.1:8080", 24)
        north.add(self.proxyField)
        self.statusLabel = JLabel(" ")
        self.statusLabel.setForeground(java.awt.Color(0x88, 0x44, 0x00))
        north.add(self.statusLabel)
        self.root.add(north, BorderLayout.NORTH)

        # --- 左: リクエスト一覧 ---
        self.reqModel = ReqListModel()
        self.reqModel.addTableModelListener(self._on_req_model_change)
        self.reqTable = JTable(self.reqModel)
        self.reqTable.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        self.reqTable.getSelectionModel().addListSelectionListener(self._on_select)
        self.reqTable.getColumnModel().getColumn(0).setPreferredWidth(36)
        self.reqTable.getColumnModel().getColumn(0).setMaxWidth(48)
        self.reqTable.getColumnModel().getColumn(1).setPreferredWidth(28)
        self.reqTable.getColumnModel().getColumn(1).setMaxWidth(40)

        left = JPanel(BorderLayout())
        left.setBorder(BorderFactory.createTitledBorder(u"リクエスト一覧 (「生成」列で対象を選択)"))
        left.add(JScrollPane(self.reqTable), BorderLayout.CENTER)
        lbtns = JPanel(FlowLayout(FlowLayout.LEFT))
        for label, handler in (
            (u"↑", self._on_move_up),
            (u"↓", self._on_move_down),
            (u"削除", self._on_delete),
        ):
            b = JButton(label)
            b.addActionListener(handler)
            lbtns.add(b)
        left.add(lbtns, BorderLayout.SOUTH)

        # --- 右: 変換設定パネル ---
        right = self._build_settings_panel()

        topSplit = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, left, right)
        topSplit.setResizeWeight(0.35)
        topSplit.setDividerLocation(360)

        # --- 下: 出力エリア ---
        bottom = JPanel(BorderLayout())
        bottom.setBorder(BorderFactory.createTitledBorder(u"出力"))
        obtns = JPanel(FlowLayout(FlowLayout.LEFT))
        self.generateBtn = JButton("Generate")
        self.generateBtn.addActionListener(self._on_generate)
        obtns.add(self.generateBtn)
        copyBtn = JButton(u"コピー")
        copyBtn.addActionListener(self._on_copy)
        obtns.add(copyBtn)
        saveBtn = JButton(u"保存")
        saveBtn.addActionListener(self._on_save)
        obtns.add(saveBtn)
        bottom.add(obtns, BorderLayout.NORTH)

        self.codeArea = JTextArea()
        self.codeArea.setEditable(False)
        self.codeArea.setFont(Font("Monospaced", Font.PLAIN, 12))
        bottom.add(JScrollPane(self.codeArea), BorderLayout.CENTER)

        mainSplit = JSplitPane(JSplitPane.VERTICAL_SPLIT, topSplit, bottom)
        mainSplit.setResizeWeight(0.6)
        mainSplit.setDividerLocation(360)
        self.root.add(mainSplit, BorderLayout.CENTER)

    def _build_settings_panel(self):
        panel = JPanel(BorderLayout())
        panel.setBorder(BorderFactory.createTitledBorder(u"変換設定"))

        # 関数名 / コメント
        form = JPanel(FlowLayout(FlowLayout.LEFT))
        form.add(JLabel(u"関数名:"))
        self.funcField = JTextField("", 14)
        form.add(self.funcField)
        form.add(JLabel(u"コメント:"))
        self.commentField = JTextField("", 24)
        form.add(self.commentField)
        panel.add(form, BorderLayout.NORTH)

        # パラメータ表
        self.paramModel = ParamTableModel()
        self.paramTable = JTable(self.paramModel)
        paramWrap = JPanel(BorderLayout())
        paramWrap.setBorder(BorderFactory.createTitledBorder(
            u"パラメータ化 (クエリ / ボディ / ヘッダ)"))
        paramWrap.add(JScrollPane(self.paramTable), BorderLayout.CENTER)

        # 抽出ルール表
        self.ruleModel = RuleTableModel()
        self.ruleTable = JTable(self.ruleModel)
        combo = JComboBox(EXTRACT_METHODS)
        self.ruleTable.getColumnModel().getColumn(0).setCellEditor(
            DefaultCellEditor(combo))
        ruleWrap = JPanel(BorderLayout())
        ruleWrap.setBorder(BorderFactory.createTitledBorder(u"返り値の抽出ルール"))
        ruleWrap.add(JScrollPane(self.ruleTable), BorderLayout.CENTER)
        rbtns = JPanel(FlowLayout(FlowLayout.LEFT))
        addRule = JButton(u"ルール追加")
        addRule.addActionListener(self._on_add_rule)
        rbtns.add(addRule)
        delRule = JButton(u"ルール削除")
        delRule.addActionListener(self._on_del_rule)
        rbtns.add(delRule)
        ruleWrap.add(rbtns, BorderLayout.SOUTH)

        inner = JSplitPane(JSplitPane.VERTICAL_SPLIT, paramWrap, ruleWrap)
        inner.setResizeWeight(0.6)
        inner.setDividerLocation(200)
        panel.add(inner, BorderLayout.CENTER)
        return panel

    # ---------------------------------------------------------- 状態同期
    def _set_status(self, text):
        self.statusLabel.setText(text)

    def _refresh_req_table(self):
        self.reqModel.setRowCount(0)
        for i, item in enumerate(self.requests):
            method, host, path, func = item.display()
            self.reqModel.addRow([java.lang.Boolean(item.include),
                                  str(i + 1), method, host, path, func])

    def _sync_from_ui(self):
        """UI の内容を現在選択中の ReqItem へ書き戻す。"""
        if not (0 <= self.current < len(self.requests)):
            return
        self._stop_edits()
        item = self.requests[self.current]
        item.func_name = _as_str(self.funcField.getText()).strip()
        item.comment = _as_str(self.commentField.getText())

        # パラメータ表 -> Param オブジェクト (all_params と同じ並び)
        params = item.all_params()
        for r in range(min(self.paramModel.getRowCount(), len(params))):
            params[r].parameterize = _as_bool(self.paramModel.getValueAt(r, 3))
            params[r].arg_name = _as_str(self.paramModel.getValueAt(r, 4)).strip()

        # 抽出ルール表 -> Rule
        rules = []
        for r in range(self.ruleModel.getRowCount()):
            method = _as_str(self.ruleModel.getValueAt(r, 0)).strip() or "resobj"
            expr = _as_str(self.ruleModel.getValueAt(r, 1))
            rules.append(Rule(method, expr))
        item.rules = rules if rules else [Rule("resobj", "")]

    def _load_to_ui(self, item):
        self.funcField.setText(item.func_name)
        self.commentField.setText(item.comment)

        self.paramModel.setRowCount(0)
        for p in item.all_params():
            self.paramModel.addRow([
                p.section, p.key, _as_str(p.value),
                java.lang.Boolean(p.parameterize), p.arg_name,
            ])

        self.ruleModel.setRowCount(0)
        for r in item.rules:
            self.ruleModel.addRow([r.method, r.expr])

    def _clear_ui(self):
        self.funcField.setText("")
        self.commentField.setText("")
        self.paramModel.setRowCount(0)
        self.ruleModel.setRowCount(0)

    def _stop_edits(self):
        for t in (self.paramTable, self.ruleTable):
            if t.isEditing():
                t.getCellEditor().stopCellEditing()

    def _update_row_display(self, i):
        """一覧の 1 行分の表示を対応する ReqItem で更新する(選択・チェックは変えない)。"""
        if not (0 <= i < len(self.requests)) or i >= self.reqModel.getRowCount():
            return
        method, host, path, func = self.requests[i].display()
        self.reqModel.setValueAt(method, i, 2)
        self.reqModel.setValueAt(host, i, 3)
        self.reqModel.setValueAt(path, i, 4)
        self.reqModel.setValueAt(func, i, 5)

    def _on_req_model_change(self, evt):
        """一覧の「生成」チェックボックス編集を ReqItem.include へ書き戻す。"""
        if self._suppress:
            return
        if evt.getColumn() != 0:
            return
        row = evt.getFirstRow()
        if 0 <= row < len(self.requests):
            self.requests[row].include = _as_bool(self.reqModel.getValueAt(row, 0))

    def _rebuild_and_select(self, index):
        """一覧を作り直して index を選択し、その内容を設定パネルへ読み込む。

        テーブル再構築・選択操作は選択リスナーを発火させるため、抑止フラグで
        再入を防いだ上で、選択状態と設定パネルをこのメソッドが直接管理する。
        """
        self._suppress = True
        try:
            self._refresh_req_table()
            if 0 <= index < len(self.requests):
                self.reqTable.setRowSelectionInterval(index, index)
            else:
                self.reqTable.clearSelection()
        finally:
            self._suppress = False
        self.current = index if 0 <= index < len(self.requests) else -1
        if self.current >= 0:
            self._load_to_ui(self.requests[self.current])
        else:
            self._clear_ui()

    # ----------------------------------------------------- イベント
    def _on_select(self, evt):
        if evt.getValueIsAdjusting() or self._suppress:
            return
        row = self.reqTable.getSelectedRow()
        if row == self.current:
            return
        self._sync_from_ui()
        self._update_row_display(self.current)   # 関数名の変更を一覧へ反映
        self.current = row
        if 0 <= row < len(self.requests):
            self._load_to_ui(self.requests[row])
        else:
            self._clear_ui()

    def _on_move_up(self, evt):
        self._sync_from_ui()
        i = self.current
        if i <= 0:
            return
        self.requests[i - 1], self.requests[i] = self.requests[i], self.requests[i - 1]
        self._rebuild_and_select(i - 1)

    def _on_move_down(self, evt):
        self._sync_from_ui()
        i = self.current
        if not (0 <= i < len(self.requests) - 1):
            return
        self.requests[i + 1], self.requests[i] = self.requests[i], self.requests[i + 1]
        self._rebuild_and_select(i + 1)

    def _on_delete(self, evt):
        i = self.current
        if not (0 <= i < len(self.requests)):
            return
        del self.requests[i]
        if self.requests:
            self._rebuild_and_select(min(i, len(self.requests) - 1))
        else:
            self._rebuild_and_select(-1)

    def _on_add_rule(self, evt):
        self.ruleModel.addRow(["resobj", ""])

    def _on_del_rule(self, evt):
        r = self.ruleTable.getSelectedRow()
        if r >= 0:
            self.ruleModel.removeRow(r)

    def _on_generate(self, evt):
        self._sync_from_ui()
        self._update_row_display(self.current)
        targets = [it for it in self.requests if it.include]
        if self.requests and not targets:
            msg = u"生成対象が選択されていません。一覧の「生成」列にチェックしてください。"
            self._set_status(msg)
            JOptionPane.showMessageDialog(
                self.root, msg, u"httpython", JOptionPane.WARNING_MESSAGE)
            return
        try:
            code = generate_script(targets,
                                   _as_str(self.proxyField.getText()))
        except GenerationError as e:
            self.codeArea.setText("")
            self._set_status(u"生成エラー: " + unicode(e))
            JOptionPane.showMessageDialog(
                self.root, unicode(e), u"httpython",
                JOptionPane.WARNING_MESSAGE)
            return
        except Exception as e:  # 想定外
            self._set_status(u"内部エラー: " + unicode(e))
            JOptionPane.showMessageDialog(
                self.root, unicode(e), u"httpython",
                JOptionPane.ERROR_MESSAGE)
            return
        self.codeArea.setText(code)
        self.codeArea.setCaretPosition(0)
        self._set_status(u"生成しました (%d 関数 / 一覧 %d 件)。"
                         % (len(targets), len(self.requests)))

    def _on_copy(self, evt):
        text = self.codeArea.getText()
        if not text:
            return
        Toolkit.getDefaultToolkit().getSystemClipboard().setContents(
            StringSelection(text), None)
        self._set_status(u"クリップボードへコピーしました。")

    def _on_save(self, evt):
        text = self.codeArea.getText()
        if not text:
            self._set_status(u"生成コードがありません。")
            return
        chooser = JFileChooser()
        chooser.setSelectedFile(java.io.File("httpython_generated.py"))
        if chooser.showSaveDialog(self.root) != JFileChooser.APPROVE_OPTION:
            return
        path = chooser.getSelectedFile().getAbsolutePath()
        try:
            w = open(path, "w")
            try:
                w.write(text.encode("utf-8"))
            finally:
                w.close()
        except Exception as e:
            self._set_status(u"保存失敗: " + unicode(e))
            return
        self._set_status(u"保存しました: " + path)

    # --------------------------------------------- リクエスト取り込み
    def _request_signature(self, messageInfo):
        """メッセージのリクエスト部分から重複除外用の署名を作る。

        request と response を内包する別オブジェクトでも、同一メッセージなら
        リクエストバイト列は一致するため署名も一致する。取得に失敗した場合は
        オブジェクト同一性へフォールバックする。
        """
        try:
            req = messageInfo.getRequest()
            if req is not None:
                return ("req", self._helpers.bytesToString(req))
        except Exception:
            pass
        return ("id", java.lang.System.identityHashCode(messageInfo))

    def _add_requests(self, msgs):
        """選択メッセージ群を一括で取り込む。

        getSelectedMessages() が返す IHttpRequestResponse は request と response を
        内包しており、Repeater 等では request 側・response 側の別オブジェクトとして
        同一メッセージが重複して返ることがある。加えて Proxy history の重複返却や
        ActionListener の二重発火もあるため、同一操作内で取り込み済みのメッセージを
        「リクエスト内容の署名」で除外する。オブジェクト同一性(identityHashCode)では
        別オブジェクトの重複を取りこぼすので採用しない。除外集合は次の EDT サイクルで
        クリアするので、ユーザが後から改めて同じ内容を送る操作は妨げない。
        """
        fresh = []
        for m in msgs:
            h = self._request_signature(m)
            if h in self._recent:
                continue
            self._recent.add(h)
            fresh.append(m)
        if not fresh:
            return

        items = []
        for m in fresh:
            try:
                items.append(self._parse_request(m))
            except Exception as e:
                self._set_status(u"取り込み失敗: " + unicode(e))

        def _apply():
            self._sync_from_ui()
            self._update_row_display(self.current)
            for it in items:
                self.requests.append(it)
            self._rebuild_and_select(len(self.requests) - 1)
            self._set_status(u"リクエストを転送しました (%d 件 / 計 %d 件)。"
                             % (len(items), len(self.requests)))

        if items:
            SwingUtilities.invokeLater(_apply)
        # 同一ユーザ操作(二重発火)を過ぎたら除外集合をリセットする
        SwingUtilities.invokeLater(self._recent.clear)

    def _parse_request(self, messageInfo):
        analyzed = self._helpers.analyzeRequest(messageInfo)
        url = analyzed.getUrl()
        item = ReqItem()
        item.method = analyzed.getMethod()
        item.scheme = url.getProtocol()
        item.host = url.getHost()
        item.port = url.getPort()
        item.path = url.getPath() or "/"

        # ヘッダ (先頭のリクエストラインは除外)
        headers = list(analyzed.getHeaders())
        for h in headers[1:]:
            if ":" not in h:
                continue
            name, _, value = h.partition(":")
            name = name.strip()
            value = value.strip()
            low = name.lower()
            if low in ("host", "content-length"):
                continue
            if low == "content-type":
                item.content_type = value
            item.headers.append(Param("header", name, value))

        # クエリ
        query = url.getQuery()
        if query:
            for pair in query.split("&"):
                if not pair:
                    continue
                k, _, v = pair.partition("=")
                item.query.append(Param("query",
                                        _urldecode(k), _urldecode(v)))

        # ボディ
        body_offset = analyzed.getBodyOffset()
        req_bytes = messageInfo.getRequest()
        body = self._helpers.bytesToString(req_bytes[body_offset:])
        self._parse_body(item, body)

        # 関数名の初期値: パスの末尾要素
        seg = [s for s in item.path.split("/") if s]
        item.func_name = _sanitize_ident(seg[-1]) if seg else "req"
        return item

    def _parse_body(self, item, body):
        if body is None or body == "":
            item.body_kind = "none"
            return
        ct = (item.content_type or "").lower()
        if "application/json" in ct:
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    item.body_kind = "json"
                    for k, v in data.items():
                        item.body_params.append(Param("body", k, v))
                    return
            except Exception:
                pass
            # JSON として解釈できなければ生ボディ扱い
            item.body_kind = "raw"
            item.raw_body = body
        elif "x-www-form-urlencoded" in ct:
            item.body_kind = "form"
            for pair in body.split("&"):
                if not pair:
                    continue
                k, _, v = pair.partition("=")
                item.body_params.append(
                    Param("body", _urldecode(k), _urldecode(v)))
        else:
            item.body_kind = "raw"
            item.raw_body = body


def _urldecode(s):
    try:
        return urllib.unquote_plus(s)
    except Exception:
        return s
