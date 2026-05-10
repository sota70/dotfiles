local note = {}

note.config = {
    note_file_path = "/tmp/note.md"
}

-- insert file into note
function insert_note(content)
    local f = io.open(note.config.note_file_path, "a")
    f:write(content)
    f:close()
end

function decorate_content(filename, start_pos, end_pos, file_content, memo)
    local file_desc = ""
    if start_pos == start_end then
        file_desc = filename .. ":" .. start_pos
    else
        file_desc = filename .. ":" .. start_pos .. " ~ " .. end_pos
    end
    return "\n\n\n" .. memo .. "\n\n" .. file_desc .. "\n```\n" .. file_content .. "\n```"
end

-- note command impl
function note_cmd(opts)
    local memo = opts.fargs[3]
    local content = vim.api.nvim_buf_get_lines(0, tonumber(opts.fargs[1]) - 1, tonumber(opts.fargs[2]), true)
    local filename = vim.api.nvim_buf_get_name(0)
    insert_note(decorate_content(filename, opts.fargs[1], opts.fargs[2], table.concat(content, "\n"), memo))
end

-- setup vim command
function setup_cmd()
    vim.api.nvim_create_user_command("Note", note_cmd, { nargs="*" })
end

-- setup keybind
function setup_keybind()
    vim.keymap.set("v", "N", function()
        vim.api.nvim_input("<esc>")
        vim.schedule(function()
            local start_pos = vim.fn.getpos("'<")[2]
            local end_pos = vim.fn.getpos("'>")[2]
            local top_line = math.min(start_pos, end_pos)
            local bottom_line = math.max(start_pos, end_pos)
            local memo = vim.fn.input("MEMO: ")
            vim.cmd(":Note " .. top_line .. " " .. bottom_line .. " " .. memo)
        end)
    end)
end

-- plugin setup
note.setup = function(args)
    note.config = vim.tbl_deep_extend("force", note.config, args or {})
    setup_cmd()
    setup_keybind()
end

return note
