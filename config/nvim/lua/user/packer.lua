-- ~/.config/nvim/lua/user/packer.lua

-- Packer bootstrap
local fn = vim.fn
local install_path = fn.stdpath('data') .. '/site/pack/packer/start/packer.nvim'
local packer_bootstrap = false
if fn.empty(fn.glob(install_path)) > 0 then
  packer_bootstrap = true
  fn.system({'git', 'clone', '--depth', '1', 'https://github.com/wbthomason/packer.nvim', install_path})
  vim.cmd [[packadd packer.nvim]]
end

local status_ok, packer = pcall(require, "packer")
if not status_ok then
  return
end

packer.init {
  display = {
    open_fn = function()
      return require("packer.util").float { border = "rounded" }
    end,
  },
}

return packer.startup(function(use)
  -- Packer
  use 'wbthomason/packer.nvim'

  -- UI
  use {'folke/tokyonight.nvim', as = 'tokyonight', config = function() vim.cmd('colorscheme tokyonight') end}
  use {'nvim-tree/nvim-tree.lua', requires = {'nvim-tree/nvim-web-devicons'}, config = function() require('nvim-tree').setup{} end}
  use {'nvim-lualine/lualine.nvim', requires = { 'nvim-tree/nvim-web-devicons', opt = true }, config = function() require('lualine').setup{options = {theme = 'tokyonight'}} end}
  use {'akinsho/bufferline.nvim', requires = 'nvim-tree/nvim-web-devicons', config = function() require('bufferline').setup{} end}

  -- Core
  use {'nvim-telescope/telescope.nvim', tag = '0.1.8', requires = { {'nvim-lua/plenary.nvim'} } }
  use {'VonHeikemen/lsp-zero.nvim', branch = 'v3.x', requires = {
      {'neovim/nvim-lspconfig'},
      {'williamboman/mason.nvim'},
      {'williamboman/mason-lspconfig.nvim'},
      {'hrsh7th/nvim-cmp'},
      {'hrsh7th/cmp-nvim-lsp'},
      {'L3MON4D3/LuaSnip'},
    }}
  use 'lewis6991/gitsigns.nvim'
  use 'github/copilot.vim'
  use 'nvimtools/none-ls.nvim'
  use 'windwp/nvim-autopairs'
  use 'numToStr/Comment.nvim'
  use {'iamcco/markdown-preview.nvim', run = 'cd app && npm install'}
  use {'folke/which-key.nvim', config = function() require('which-key').setup() end}
  use {'akinsho/toggleterm.nvim', tag = '*' , config = function() require("toggleterm").setup({direction = 'float'}) end}
  use {"lervag/vimtex", config = function() vim.g.vimtex_view_method = "zathura" end}

  -- Auto-sync on bootstrap
  if packer_bootstrap then
    require('packer').sync()
  end
end)