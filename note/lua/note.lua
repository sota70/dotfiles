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
    local file_desc = filename .. ":" .. start_pos
    if start_pos ~= end_pos then
        file_desc = file_desc .. " ~ " .. end_pos
    end
    return string.format([[

    

%s

%s
```
%s
```
    ]], memo, file_desc, file_content)
end

-- note command impl
function note_cmd(opts)
    if table.getn(opts.fargs) < 3 then
        print("Too few arguments")
        return
    end
    local memo = opts.fargs[3]
    local content = vim.api.nvim_buf_get_lines(0, tonumber(opts.fargs[1]) - 1, tonumber(opts.fargs[2]), true)
    local filename = vim.api.nvim_buf_get_name(0)
    insert_note(decorate_content(filename, opts.fargs[1], opts.fargs[2], table.concat(content, "\n"), memo))
end

-- input ui component
function ui_show_input(submit_handler)
    local Input = require("nui.input")
    local event = require("nui.utils.autocmd").event

    local input = Input({
      position = "50%",
      size = {
        width = 20,
      },
      border = {
        style = "single",
        text = {
          top = "[Take a memo]",
          top_align = "center",
        },
      },
      win_options = {
        winhighlight = "Normal:Normal,FloatBorder:Normal",
      },
    }, {
      prompt = "> ",
      default_value = "",
      on_submit = submit_handler,
      on_close = function()
      end
    })

    -- unmount component when cursor leaves buffer
    input:on(event.BufLeave, function()
      input:unmount()
    end)

    input:map("n", "<Esc>", function()
        input:unmount()
    end, { noremap = true })

    -- mount/open the component
    input:mount()

    vim.schedule(function()
        vim.api.nvim_command("startinsert!")
    end)
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
            ui_show_input(function (memo)
                vim.cmd(string.format(":Note %s %s %s", top_line, bottom_line, memo))
            end)
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
