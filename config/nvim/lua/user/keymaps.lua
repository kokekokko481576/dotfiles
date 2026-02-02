-- ~/.config/nvim/lua/user/keymaps.lua

local function set_keymaps()
  local opts = { noremap = true, silent = true }

  -- NvimTree
  vim.keymap.set('n', '<leader>e', ':NvimTreeToggle<CR>', opts)

  -- ToggleTerm
  vim.keymap.set('n', '<leader>t', ':ToggleTerm<CR>', opts)
end

-- Define keymaps after all plugins are loaded
vim.api.nvim_create_autocmd("VimEnter", {
  pattern = "*",
  callback = set_keymaps,
})

 -- build123d / ocp_vscode 自動更新設定
vim.api.nvim_create_autocmd("BufWritePost", {
  pattern = "*.py",
  callback = function()
  -- カレントディレクトリに .venv があるか確認
    local venv_python = vim.fn.getcwd() .. "/.venv/bin/python"
    if vim.fn.executable(venv_python) == 1 then
  -- 非同期で実行（Neovimが固まらないように）
       vim.fn.jobstart({venv_python, vim.fn.expand("%")})
    end
   end,
})

 -- CADビューアーサーバーを裏で立ち上げるコマンド
vim.api.nvim_create_user_command('CADServe', function()
  vim.fn.jobstart({vim.fn.getcwd() .. "/.venv/bin/python", "-m", "ocp_vscode"})
  print("CAD Viewer Server started!")
end, {})

