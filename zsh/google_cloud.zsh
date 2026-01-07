# --- Google Cloud SDK Settings ---
export GOOGLE_CLOUD_PROJECT="uoo-ship-project"
export GOOGLE_CLOUD_LOCATION="us-central1"

# SDKのパス設定 (もしインストールされていれば読み込む)
if [ -f "$HOME/y/google-cloud-sdk/path.zsh.inc" ]; then 
    . "$HOME/y/google-cloud-sdk/path.zsh.inc"
fi

# 補完機能 (もしインストールされていれば読み込む)
if [ -f "$HOME/y/google-cloud-sdk/completion.zsh.inc" ]; then 
    . "$HOME/y/google-cloud-sdk/completion.zsh.inc"
fi
