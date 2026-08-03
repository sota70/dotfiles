-- 画面左サイドに、タブ一覧を縦並びで表示するサイドバー
local M = {}

local WIDTH = 20
local ns = vim.api.nvim_create_namespace("tab_sidebar")

local buf = nil
local busy = false

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

local function truncate(s, width)
  if vim.fn.strdisplaywidth(s) <= width then
    return s
  end
  local out = s
  while vim.fn.strdisplaywidth(out) > width - 1 and vim.fn.strchars(out) > 0 do
    out = vim.fn.strcharpart(out, 0, vim.fn.strchars(out) - 1)
  end
  return out .. "…"
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

  for i, tabpage in ipairs(tabpages) do
    if tabpage == current then
      cur_line = i
    end
    local mark = (tabpage == current) and "▸" or " "
    lines[i] = truncate(string.format("%s%d %s", mark, i, tab_label(tabpage)), WIDTH - 1)
  end

  vim.bo[b].modifiable = true
  vim.api.nvim_buf_set_lines(b, 0, -1, false, lines)
  vim.bo[b].modifiable = false
  vim.bo[b].modified = false

  vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
  for i = 1, #lines do
    vim.api.nvim_buf_set_extmark(b, ns, i - 1, 0, {
      line_hl_group = (i == cur_line) and "TabLineSel" or "TabLine",
    })
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
  local tabpage = vim.api.nvim_list_tabpages()[line]
  if tabpage then
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
