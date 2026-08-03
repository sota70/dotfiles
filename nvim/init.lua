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

-- タブ一覧を画面左のサイドバーに縦並びで表示する
require("config.tabsidebar").setup()
