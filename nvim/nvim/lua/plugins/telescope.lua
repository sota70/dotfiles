local actions = require('telescope.actions')

-- word wrap in preview
vim.api.nvim_create_autocmd('User', {
    pattern = 'TelescopePreviewerLoaded',
    callback = function(args)
        vim.wo.wrap = true
        vim.wo.linebreak = true
    end,
})

return {
    'nvim-telescope/telescope.nvim', tag = '0.1.8',
    dependencies = { 'nvim-lua/plenary.nvim' },
    opts = {
        defaults = {
            sorting_strategy = 'ascending',
            wrap_results = true,
            layout_strategy = 'horizontal',
            layout_config = {
                vertical = { width = 0.8 },
                horizontal = { width = 0.95 },
            },
            mappings = {
                n = {
                    ['<C-j>'] = actions.preview_scrolling_down,
                    ['<C-k>'] = actions.preview_scrolling_up,
                },
                i = {
                    ['<C-j>'] = actions.preview_scrolling_down,
                    ['<C-k>'] = actions.preview_scrolling_up,
                },
            },
        },
    },
}
