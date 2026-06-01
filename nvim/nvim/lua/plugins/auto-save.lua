return {
  "Pocco81/auto-save.nvim",
  version = "*",
  lazy = false,
  dependencies = {},
  config = function()
    require("auto-save").setup {
      trigger_events = {"InsertLeave", "BufLeave", "FocusLost"},
    }
  end,
}
