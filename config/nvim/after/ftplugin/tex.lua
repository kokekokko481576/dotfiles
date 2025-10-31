-- ~/.config/nvim/after/ftplugin/tex.lua

local opts = { noremap = true, silent = true, buffer = true }

local toggleterm_terminal_ok, term_manager = pcall(require, "toggleterm.terminal")
if not toggleterm_terminal_ok then
  vim.keymap.set('n', '<leader>lc', function() print("toggleterm.nvim terminal manager not found.") end, opts)
  vim.keymap.set('n', '<leader>lk', function() print("toggleterm.nvim terminal manager not found.") end, opts)
  return
end

local Terminal = term_manager.Terminal
local function start_latex_compile()
  local file = vim.fn.expand('%:p')
  if file == '' or vim.bo.filetype ~= 'tex' then
    print("Not a TeX file.")
    return
  end
  for _, term in ipairs(term_manager.get_all()) do
    if term.display_name == 'latexmk_pvc' then
      print("Continuous compilation is already running.")
      term:toggle()
      return
    end
  end
  local file_dir = vim.fn.fnamemodify(file, ':h')
  local file_name = vim.fn.fnamemodify(file, ':t')
  local cmd = string.format("cd %s && latexmk -pvc %s", vim.fn.shellescape(file_dir), vim.fn.shellescape(file_name))
  local term = Terminal:new({
    cmd = cmd,
    direction = 'float',
    display_name = 'latexmk_pvc',
    hidden = true,
    on_open = function(t)
      vim.schedule(function()
        print("Started continuous LaTeX compilation in the background.")
      end)
    end
  })
  term:toggle()
  vim.schedule(function()
    local pdf_file = vim.fn.fnamemodify(file, ':r') .. '.pdf'
    vim.fn.jobstart('zathura ' .. vim.fn.shellescape(pdf_file), {detach = true})
  end)
end

local function stop_latex_compile()
  for _, term in ipairs(term_manager.get_all()) do
    if term.display_name == 'latexmk_pvc' then
      print("Stopping continuous compilation.")
      term:close()
      return
    end
  end
  print("No continuous compilation is running.")
end

vim.keymap.set('n', '<leader>lc', start_latex_compile, opts)
vim.keymap.set('n', '<leader>lk', stop_latex_compile, opts)
