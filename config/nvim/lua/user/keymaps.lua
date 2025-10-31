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
