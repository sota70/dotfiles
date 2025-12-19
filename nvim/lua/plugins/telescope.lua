return {
    'nvim-telescope/telescope.nvim', tag = '0.1.8',
    dependencies = { 'nvim-lua/plenary.nvim' },
    opts = {
        defaults = {
            wrap_results = true,
            sorting_strategy = 'ascending',
            layout_strategy = 'vertical',
        },
    },
}
