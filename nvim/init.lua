vim.opt.clipboard = "unnamedplus"
vim.o.number = true
vim.o.cursorline = true
vim.o.expandtab = true
vim.o.tabstop = 4
vim.o.shiftwidth = 4

require("config.lazy")
require("config.mappings")

vim.cmd.colorscheme "vim"
vim.api.nvim_set_hl(0, "Pmenu", { bg = "#282828", fg = "#ebdbb2" })
vim.api.nvim_set_hl(0, "PmenuSel", { bg = "#458588", fg = "#282828" })
vim.api.nvim_set_hl(0, "PmenuSbar", { bg = "#3c3836" })
vim.api.nvim_set_hl(0, "PmenuThumb", { bg = "#665c54" })

-- show only filename in tab
function MyTabLine()
  local s = ''
  for i = 1, vim.fn.tabpagenr('$') do
    -- Highlight the selected tab
    if i == vim.fn.tabpagenr() then
      s = s .. '%#TabLineSel#'
    else
      s = s .. '%#TabLine#'
    end

    -- Set the tab page number (for mouse clicks)
    s = s .. '%' .. i .. 'T'

    -- Get the filename only
    local buflist = vim.fn.tabpagebuflist(i)
    local winnr = vim.fn.tabpagewinnr(i)
    local bufnr = buflist[winnr]
    local file = vim.fn.bufname(bufnr)
    
    if file == '' then
      s = s .. ' [No Name] '
    else
      -- ":t" modifier extracts the tail (filename)
      s = s .. ' ' .. vim.fn.fnamemodify(file, ':t') .. ' '
    end
  end

  s = s .. '%#TabLineFill#%T'
  return s
end

vim.o.tabline = '%!v:lua.MyTabLine()'
