#!/bin/bash
set -e

DOTFILES_DIR=$(cd "$(dirname "$0")"; pwd)
source "$DOTFILES_DIR/lib/utils.sh"

echo -e "${COLOR_BLUE}================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}   Kokko's Dotfiles Installer   ${COLOR_RESET}"
echo -e "${COLOR_BLUE}================================${COLOR_RESET}"

# --- 依存パッケージのチェックとインストール ---
check_dependencies() {
    log_info "必要なパッケージをチェック中..."
    
    deps=("zsh" "git" "curl" "tmux" "mosh") # mosh: Wi-Fi切替/一時切断に強いSSH代替(guide/17)
    to_install=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            log_warn "$dep が見つかりません。"
            to_install+=("$dep")
        fi
    done

    if [ ${#to_install[@]} -ne 0 ]; then
        log_info "不足しているパッケージ (${to_install[*]}) をインストールします..."
        log_info "sudoパスワードを求められる場合があります👇"
        sudo apt update
        sudo apt install -y "${to_install[@]}"
        log_success "インストール完了！"
    else
        log_info "依存パッケージはすべて揃っています。"
    fi
}

show_menu() {
    echo "インストール方法を選んでね："
    echo "1) Recommended (全部入り: Zsh, Neovim, VSCode, tmux, Mozc, Git)"
    echo "2) Custom (ひとつずつ選ぶ)"
    echo "3) Zsh only"
    echo "4) Neovim only"
    echo "5) VSCode only"
    echo "6) tmux only"
    echo "7) Git only"
    echo "q) 終了"
}

# コンポーネントごとのセットアップ関数
install_zsh()    { bash "$DOTFILES_DIR/scripts/setup_zsh.sh"; }
install_neovim() { bash "$DOTFILES_DIR/scripts/setup_neovim.sh"; }
install_vscode() { bash "$DOTFILES_DIR/scripts/setup_vscode.sh"; }
install_tmux()   { bash "$DOTFILES_DIR/scripts/setup_tmux.sh"; }
install_mozc()   { bash "$DOTFILES_DIR/scripts/setup_mozc.sh"; }
install_git()    { bash "$DOTFILES_DIR/scripts/setup_git.sh"; }

# --- メイン処理開始 ---
check_dependencies

while true; do
    show_menu
    read -p "Selection: " choice
    echo ""
    
    case $choice in
        1)
            # 全部入り
            log_info "Starting Recommended Install..."
            install_zsh
            install_neovim
            install_vscode
            install_tmux
            install_mozc
            install_git
            break
            ;;
        2)
            # カスタムインストール
            log_info "Starting Custom Install..."
            if ask_yes_no "Zsh (Shell) の設定をインストールしますか？"; then install_zsh; fi
            echo ""
            if ask_yes_no "Neovim (Editor) の設定をインストールしますか？"; then install_neovim; fi
            echo ""
            if ask_yes_no "VSCode (Editor) の設定をインストールしますか？"; then install_vscode; fi
            echo ""
            if ask_yes_no "tmux (Terminal Multiplexer) の設定をインストールしますか？"; then install_tmux; fi
            echo ""
            if ask_yes_no "Mozc (Japanese Input) の設定をインストールしますか？(Linux only)"; then install_mozc; fi
            echo ""
            if ask_yes_no "Git の設定をインストールしますか？"; then install_git; fi
            break
            ;;
        3) install_zsh; break ;;
        4) install_neovim; break ;;
        5) install_vscode; break ;;
        6) install_tmux; break ;;
        7) install_git; break ;;
        q) exit 0 ;;
        *) log_error "無効な選択だぜ" ;;
    esac
done

echo ""
log_success "すべての処理が完了したよ！"
echo "新しい設定を反映するには、一度ログアウトして再ログインしてね✨"
