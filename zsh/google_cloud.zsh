# --- Google Cloud SDK Settings ---
export GOOGLE_CLOUD_PROJECT="uoo-ship-project"
export GOOGLE_CLOUD_LOCATION="us-central1"

# SDKのパス設定 (インストール場所を複数チェック)
for _gcloud_dir in \
    "$HOME/google-cloud-sdk" \
    "$HOME/y/google-cloud-sdk" \
    "/opt/google-cloud-sdk"; do
    if [ -f "$_gcloud_dir/path.zsh.inc" ]; then
        . "$_gcloud_dir/path.zsh.inc"
        [ -f "$_gcloud_dir/completion.zsh.inc" ] && . "$_gcloud_dir/completion.zsh.inc"
        break
    fi
done
unset _gcloud_dir
