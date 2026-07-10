#!/usr/bin/env bash
# ワニ博士TWA APKのビルドスクリプト。
#   1. ビルド用dockerイメージ(wani-twa-builder)が無ければ作る
#   2. 署名キーストアが無ければ生成(/mnt/data/ai/wani/twa/、gitには入れない)
#   3. bubblewrapでAPKをビルド
#   4. assetlinks.json(Digital Asset Links)を生成
#   5. APKを配信ディレクトリ(/mnt/data/ai/wani/assets/wani.apk)へ配置
# 実行: server/wani/ で ./tools/build_apk.sh
set -euo pipefail

WANI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TWA_DATA=/mnt/data/ai/wani/twa
ASSETS=/mnt/data/ai/wani/assets
IMAGE=wani-twa-builder

sudo mkdir -p "$TWA_DATA" "$ASSETS"

# 1. ビルドイメージ
if ! docker image inspect $IMAGE >/dev/null 2>&1; then
  echo "== ビルドイメージを作成(初回のみ、数分かかる) =="
  docker build -t $IMAGE "$WANI_DIR/twa"
fi

# 2. キーストア(パスワードは隣のファイルに保存。漏らさないこと)
if ! sudo test -f "$TWA_DATA/wani.keystore"; then
  echo "== 署名キーストアを生成 =="
  PASS=$(openssl rand -hex 16)
  echo -n "$PASS" | sudo tee "$TWA_DATA/keystore.pass" >/dev/null
  sudo chmod 600 "$TWA_DATA/keystore.pass"
  docker run --rm -v "$TWA_DATA":/twa-data $IMAGE \
    keytool -genkeypair -v -keystore /twa-data/wani.keystore -alias wani \
      -keyalg RSA -keysize 2048 -validity 10000 \
      -storepass "$PASS" -keypass "$PASS" \
      -dname "CN=Wani Hakase, OU=Home, O=kokko, L=Toyonaka, ST=Osaka, C=JP"
fi
PASS=$(sudo cat "$TWA_DATA/keystore.pass")

# 3. APKビルド(作業ディレクトリはコンテナ内に隔離)
echo "== APKビルド =="
docker run --rm --network host \
  -v "$WANI_DIR/twa/twa-manifest.json":/project/twa-manifest.json:ro \
  -v "$TWA_DATA":/twa-data \
  -e BUBBLEWRAP_KEYSTORE_PASSWORD="$PASS" \
  -e BUBBLEWRAP_KEY_PASSWORD="$PASS" \
  $IMAGE bash -c '
    set -e
    cp /project/twa-manifest.json /tmp/build/twa-manifest.json 2>/dev/null || {
      mkdir -p /tmp/build && cp /project/twa-manifest.json /tmp/build/; }
    cd /tmp/build
    # updateでAndroidプロジェクトを非対話生成してからbuild(再生成プロンプト回避)。
    # キーストアのパスワードはBUBBLEWRAP_*環境変数で渡している
    bubblewrap update --skipVersionUpgrade
    bubblewrap build --skipPwaValidation
    cp app-release-signed.apk /twa-data/wani.apk
  '

# 4. assetlinks.json (署名証明書のSHA256を埋める)
echo "== assetlinks.json生成 =="
FP=$(docker run --rm -v "$TWA_DATA":/twa-data $IMAGE \
  keytool -list -v -keystore /twa-data/wani.keystore -alias wani \
    -storepass "$PASS" | grep "SHA256:" | head -1 | sed 's/.*SHA256: //')
sudo tee "$TWA_DATA/assetlinks.json" >/dev/null <<EOF
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "dev.kokko.wani",
    "sha256_cert_fingerprints": ["$FP"]
  }
}]
EOF

# 5. 配信ディレクトリへ
sudo cp "$TWA_DATA/wani.apk" "$ASSETS/wani.apk"
echo "== 完了 =="
echo "APK: https://kokko-server-pavilion.tailed0412.ts.net:8443/assets/wani.apk"
echo "assetlinks: https://kokko-server-pavilion.tailed0412.ts.net/.well-known/assetlinks.json"
