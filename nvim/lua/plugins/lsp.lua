return {
  -- 補完エンジンとその補完ソース
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      "hrsh7th/cmp-nvim-lsp", -- LSPからの補完
      "hrsh7th/cmp-buffer",   -- バッファ内文字列からの補完
      "hrsh7th/cmp-path",     -- ファイルパス補完
      "L3MON4D3/LuaSnip",     -- スニペットエンジン
      "saadparwaiz1/cmp_luasnip",
    },
    config = function()
      local cmp = require("cmp")
      local luasnip = require("luasnip")

      -- 補完の挙動とキーバインドの設定
      cmp.setup({
        -- 入力中に自動で候補を表示させない設定
        completion = {
          autocomplete = false,
        },
        -- ドキュメント（詳細説明）ウィンドウに専用ハイライトを適用
        window = {
          documentation = cmp.config.window.bordered({
            winhighlight = "Normal:CmpDocumentation,FloatBorder:CmpDocumentationBorder",
          }),
        },
        snippet = {
          expand = function(args)
            luasnip.lsp_expand(args.body)
          end,
        },
        mapping = cmp.mapping.preset.insert({
          ["<C-n>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_next_item()
            else
              cmp.complete()
            end
          end, { "i", "c" }),
          ["<C-p>"] = cmp.mapping.select_prev_item(),
          ["<C-e>"] = cmp.mapping.abort(),
          ["<CR>"] = cmp.mapping.confirm({ select = true }),
        }),
        sources = cmp.config.sources({
          { name = "nvim_lsp" },
          { name = "luasnip" },
        }, {
          { name = "buffer" },
          { name = "path" },
        }),
      })

      -- 候補詳細（ドキュメント）ウィンドウの色を変更（Pmenuより少し暗く）
      -- colorscheme切り替え時にハイライトが消されても再適用されるようにする
      local function set_cmp_doc_hl()
        vim.api.nvim_set_hl(0, "CmpDocumentation", { bg = "#1d2021", fg = "#ebdbb2" })
        vim.api.nvim_set_hl(0, "CmpDocumentationBorder", { bg = "#1d2021", fg = "#3c3836" })
      end
      set_cmp_doc_hl()
      vim.api.nvim_create_autocmd("ColorScheme", {
        callback = set_cmp_doc_hl,
      })
    end,
  },

  -- 各言語のLSPサーバー導入・設定 (JS/TS, PHP, Go, Python)
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      "williamboman/mason.nvim",
      "williamboman/mason-lspconfig.nvim",
    },
    config = function()
      require("mason").setup()

      -- 構文エラーなど診断表示の無効化
      vim.diagnostic.config({
        virtual_text = false,
        signs = false,
        underline = false,
        update_in_insert = false,
        severity_sort = false,
      })

      local servers = {
        "ts_ls",        -- JavaScript/TypeScript
        "intelephense", -- PHP
        "gopls",        -- Go
        "pyright",      -- Python
      }

      require("mason-lspconfig").setup({
        ensure_installed = servers,
      })

      local capabilities = require("cmp_nvim_lsp").default_capabilities()
      local lspconfig = require("lspconfig")

      -- コードジャンプ等、LSPアタッチ時のキーバインド
      -- 一番上の候補へ、新しいタブ（既に開いていればそのタブ）でジャンプする
      local function find_tab_with_file(path)
        for _, tabpage in ipairs(vim.api.nvim_list_tabpages()) do
          for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tabpage)) do
            local bufname = vim.api.nvim_buf_get_name(vim.api.nvim_win_get_buf(win))
            if vim.fn.fnamemodify(bufname, ":p") == path then
              return tabpage, win
            end
          end
        end
        return nil, nil
      end

      local function jump_to_first(lsp_func)
        return function()
          lsp_func({
            on_list = function(options)
              local item = options.items[1]
              if not item then
                return
              end

              -- ジャンプ前の位置をジャンプリストに記録（<C-o>で戻れるようにする）
              vim.cmd("normal! m'")

              local path = vim.fn.fnamemodify(item.filename, ":p")
              local tabpage, win = find_tab_with_file(path)

              if tabpage then
                vim.api.nvim_set_current_tabpage(tabpage)
                vim.api.nvim_set_current_win(win)
              else
                vim.cmd("tabedit " .. vim.fn.fnameescape(item.filename))
              end

              vim.api.nvim_win_set_cursor(0, { item.lnum, math.max(item.col - 1, 0) })
            end,
          })
        end
      end

      local on_attach = function(_, bufnr)
        local opts = { buffer = bufnr }
        vim.keymap.set("n", "gd", jump_to_first(vim.lsp.buf.definition), opts)
        vim.keymap.set("n", "gD", jump_to_first(vim.lsp.buf.declaration), opts)
        vim.keymap.set("n", "gi", jump_to_first(vim.lsp.buf.implementation), opts)
        vim.keymap.set("n", "gr", jump_to_first(vim.lsp.buf.references), opts)
        vim.keymap.set("n", "<leader>k", vim.lsp.buf.hover, opts)
      end

      for _, server in ipairs(servers) do
        lspconfig[server].setup({
          capabilities = capabilities,
          on_attach = on_attach,
        })
      end
    end,
  },
}
