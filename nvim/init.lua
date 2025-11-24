vim.opt.clipboard = "unnamedplus"
vim.o.number = true
vim.o.cursorline = true
vim.o.expandtab = true
vim.o.tabstop = 4
vim.o.shiftwidth = 4

require("config.lazy")
require("config.mappings")

vim.cmd.colorscheme "vim"
