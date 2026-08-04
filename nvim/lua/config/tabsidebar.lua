-- 画面左サイドに、タブ一覧を縦並びで表示するサイドバー
local M = {}

local WIDTH = 20
local ns = vim.api.nvim_create_namespace("tab_sidebar")

local buf = nil
local busy = false
local line_tab = {} -- サイドバーの行番号 -> tabpage (折り返しで 1 タブが複数行になる)

M.enabled = true

local function sidebar_buf()
  if buf and vim.api.nvim_buf_is_valid(buf) then
    return buf
  end
  buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].buftype = "nofile"
  vim.bo[buf].bufhidden = "hide"
  vim.bo[buf].swapfile = false
  vim.bo[buf].buflisted = false
  vim.bo[buf].filetype = "tabsidebar"
  vim.keymap.set("n", "<CR>", M.goto_tab_under_cursor, { buffer = buf, nowait = true })
  vim.keymap.set("n", "<2-LeftMouse>", M.goto_tab_under_cursor, { buffer = buf, nowait = true })
  return buf
end

-- そのタブページにあるサイドバーウィンドウ (0 = カレントタブ)
local function sidebar_win(tabpage)
  if not (buf and vim.api.nvim_buf_is_valid(buf)) then
    return nil
  end
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tabpage or 0)) do
    if vim.api.nvim_win_get_buf(win) == buf then
      return win
    end
  end
  return nil
end

local function is_float(win)
  return vim.api.nvim_win_get_config(win).relative ~= ""
end

-- 表示幅 width で折り返して、行のリストを返す (省略はしない)
local function wrap(s, width)
  if width < 1 then
    width = 1
  end
  local out = {}
  local line, line_w = "", 0
  for _, ch in ipairs(vim.fn.split(s, "\\zs")) do
    local w = vim.fn.strdisplaywidth(ch)
    if line_w + w > width and line ~= "" then
      out[#out + 1] = line
      line, line_w = "", 0
    end
    line = line .. ch
    line_w = line_w + w
  end
  out[#out + 1] = line
  return out
end

-- そのタブで「今開いているファイル」としてふさわしいウィンドウを選ぶ
local function main_win(tabpage)
  local cur = vim.api.nvim_tabpage_get_win(tabpage)
  local function ok(win)
    return vim.api.nvim_win_get_buf(win) ~= buf and not is_float(win)
  end
  if ok(cur) then
    return cur
  end
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tabpage)) do
    if ok(win) then
      return win
    end
  end
  return cur
end

local function tab_label(tabpage)
  local bufnr = vim.api.nvim_win_get_buf(main_win(tabpage))
  local name = vim.api.nvim_buf_get_name(bufnr)
  local label
  if name == "" then
    label = "[No Name]"
  else
    label = vim.fn.fnamemodify(name, ":t")
  end
  if vim.bo[bufnr].modified then
    label = label .. " +"
  end
  return label
end

function M.render()
  if not M.enabled then
    return
  end
  local b = sidebar_buf()
  local tabpages = vim.api.nvim_list_tabpages()
  local current = vim.api.nvim_get_current_tabpage()
  local lines, cur_line = {}, 1

  line_tab = {}
  for i, tabpage in ipairs(tabpages) do
    local is_cur = (tabpage == current)
    local prefix = string.format("%s ", is_cur and "▸" or " ")
    local indent = string.rep(" ", vim.fn.strdisplaywidth(prefix))
    local chunks = wrap(tab_label(tabpage), WIDTH - 1 - vim.fn.strdisplaywidth(prefix))
    for j, chunk in ipairs(chunks) do
      lines[#lines + 1] = (j == 1 and prefix or indent) .. chunk
      line_tab[#lines] = tabpage
      if is_cur and j == 1 then
        cur_line = #lines
      end
    end
  end

  vim.bo[b].modifiable = true
  vim.api.nvim_buf_set_lines(b, 0, -1, false, lines)
  vim.bo[b].modifiable = false
  vim.bo[b].modified = false

  vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
  for i = 1, #lines do
    if line_tab[i] == current then
      vim.api.nvim_buf_set_extmark(b, ns, i - 1, 0, { line_hl_group = "TabLineSel" })
    end
  end

  local win = sidebar_win(0)
  if win then
    pcall(vim.api.nvim_win_set_cursor, win, { cur_line, 0 })
  end
end

function M.open()
  if not M.enabled or busy then
    return
  end
  if sidebar_win(0) then
    return
  end
  if is_float(vim.api.nvim_get_current_win()) then
    return
  end

  busy = true
  local prev = vim.api.nvim_get_current_win()
  local b = sidebar_buf()

  vim.cmd("noautocmd topleft vertical " .. WIDTH .. " split")
  local win = vim.api.nvim_get_current_win()
  vim.api.nvim_win_set_buf(win, b)

  local wo = vim.wo[win]
  wo.number = false
  wo.relativenumber = false
  wo.wrap = false
  wo.winfixwidth = true
  wo.signcolumn = "no"
  wo.foldcolumn = "0"
  wo.cursorline = true
  wo.list = false
  wo.spell = false
  wo.winfixbuf = true -- このウィンドウで別のバッファを開かせない

  if vim.api.nvim_win_is_valid(prev) then
    vim.api.nvim_set_current_win(prev)
  end
  busy = false
end

function M.close_all()
  for _, tabpage in ipairs(vim.api.nvim_list_tabpages()) do
    local win = sidebar_win(tabpage)
    if win then
      pcall(vim.api.nvim_win_close, win, true)
    end
  end
end

function M.goto_tab_under_cursor()
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local tabpage = line_tab[line]
  if tabpage and vim.api.nvim_tabpage_is_valid(tabpage) then
    vim.api.nvim_set_current_tabpage(tabpage)
    local win = main_win(tabpage)
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_set_current_win(win)
    end
  end
end

function M.toggle()
  M.enabled = not M.enabled
  if M.enabled then
    M.open()
    M.render()
  else
    M.close_all()
  end
end

function M.focus()
  M.open()
  local win = sidebar_win(0)
  if win then
    vim.api.nvim_set_current_win(win)
  end
end

function M.setup()
  vim.o.showtabline = 0 -- 上部のタブラインは使わない

  local group = vim.api.nvim_create_augroup("TabSidebar", { clear = true })

  vim.api.nvim_create_autocmd(
    { "VimEnter", "TabNew", "TabEnter", "TabClosed", "WinEnter", "BufEnter", "BufWritePost", "BufFilePost" },
    {
      group = group,
      callback = vim.schedule_wrap(function()
        if busy or not M.enabled then
          return
        end
        M.open()
        M.render()
      end),
    }
  )

  -- 残りがサイドバーだけになる場合は一緒に閉じる
  vim.api.nvim_create_autocmd("QuitPre", {
    group = group,
    callback = function()
      local others = 0
      for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
        if vim.api.nvim_win_get_buf(win) ~= buf and not is_float(win) then
          others = others + 1
        end
      end
      if others <= 1 then
        local win = sidebar_win(0)
        if win then
          pcall(vim.api.nvim_win_close, win, true)
        end
      end
    end,
  })

  vim.api.nvim_create_user_command("TabSidebarToggle", M.toggle, {})
  vim.api.nvim_create_user_command("TabSidebarFocus", M.focus, {})
  -- 実際にウィンドウを作るのは起動完了後 (VimEnter) 以降。
  -- 起動途中に split すると、引数で開くファイルがサイドバー側に入ってしまう。
end

return M
