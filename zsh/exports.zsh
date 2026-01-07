# --- Environment Variables ---

# PATH settings
# 重複しないように、必要なものだけシンプルに追加
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/appimage:$PATH"
export PATH="$HOME/bin:$PATH"

# Node.js (NVM)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Google Cloud SDK
export GOOGLE_CLOUD_PROJECT="uoo-ship-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
# 絶対パスで指定されているので、動的に $HOME を使う形に統一
if [ -f "$HOME/y/google-cloud-sdk/path.zsh.inc" ]; then . "$HOME/y/google-cloud-sdk/path.zsh.inc"; fi
if [ -f "$HOME/y/google-cloud-sdk/completion.zsh.inc" ]; then . "$HOME/y/google-cloud-sdk/completion.zsh.inc"; fi

# C++
export CPLUS_INCLUDE_PATH="$HOME/.local/include:$CPLUS_INCLUDE_PATH"