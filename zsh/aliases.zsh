# --- Aliases ---
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias open='xdg-open'

# Git aliases (if any needed)
# alias gst='git status'

# --- Functions ---

# C++ファイルをコンパイルして即実行
rcpp() {
  if [[ "$1" == *.cpp ]]; then
    g++ "$1" -o /tmp/cpp_temp && /tmp/cpp_temp
  else
    echo "エラー: C++のファイル（.cpp）以外は実行できないよ！"
  fi
}
