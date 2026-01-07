#!/bin/bash
set -e

DOTFILES_DIR=$(cd "$(dirname "$0")"; pwd)
source "$DOTFILES_DIR/lib/utils.sh"

echo -e "${COLOR_BLUE}================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}   Kokko's Dotfiles Installer   ${COLOR_RESET}"
echo -e "${COLOR_BLUE}================================${COLOR_RESET}"

show_menu() {
    echo "インストールする項目を選んでね（1つずつ選んでね）"
    echo "1) 全てインストール (Zsh, Neovim, VSCode)"
    echo "2) Zsh設定のみ (Prezto + P10k + 分割設定)"
    echo "3) Neovim設定のみ"
    echo "4) VSCode設定のみ"
    echo "q) 終了"
}

while true; do
    show_menu
    read -p "Selection: " choice
    case $choice in
        1)
            bash "$DOTFILES_DIR/scripts/setup_zsh.sh"
            bash "$DOTFILES_DIR/scripts/setup_neovim.sh"
            bash "$DOTFILES_DIR/scripts/setup_vscode.sh"
            break
            ;;
        2)
            bash "$DOTFILES_DIR/scripts/setup_zsh.sh"
            break
            ;;
        3)
            bash "$DOTFILES_DIR/scripts/setup_neovim.sh"
            break
            ;;
        4)
            bash "$DOTFILES_DIR/scripts/setup_vscode.sh"
            break
            ;;
        q)
            exit 0
            ;;
        *)
            log_error "無効な選択だぜ"
            ;;
    esac
done

log_success "セットアップ完了！"
echo "新しい設定を反映するには 'source ~/.zshrc' を実行するか、シェルを再起動してね✨"