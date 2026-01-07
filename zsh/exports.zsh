# --- Environment Variables ---

# PATH settings
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/appimage:$PATH"
export PATH="$HOME/bin:$PATH"

# Node.js (NVM)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# C++
export CPLUS_INCLUDE_PATH="$HOME/.local/include:$CPLUS_INCLUDE_PATH"
