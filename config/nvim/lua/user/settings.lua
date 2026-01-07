-- ~/.config/nvim/lua/user/settings.lua

-- Clipboard
vim.opt.clipboard = 'unnamedplus'

-- Basic editor options
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 2
vim.opt.shiftwidth = 2
vim.opt.expandtab = true
vim.opt.autoindent = true

-- Set leader key
vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-- Neovide specific settings
if vim.g.neovide then
  vim.g.neovide_scroll_animation_length = 0.3
  vim.g.neovide_cursor_animation_length = 0.075
  vim.g.neovide_cursor_vignette = 0.15
  -- 透過設定 (0.0から1.0で設定)
  vim.g.neovide_transparency = 0.8
end

vim.opt.cursorline = true
