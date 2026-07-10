# ワニ博士TWA(Androidアプリ)ビルド環境。
# bubblewrap + JDK17 + Android SDKを焼き込んだイメージ。
# 使い方: tools/build_apk.sh (このイメージのビルドとAPK生成を自動でやる)
FROM node:20-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jdk-headless unzip wget \
    && rm -rf /var/lib/apt/lists/*

# Android SDK (cmdline-tools + build-tools)
ENV ANDROID_HOME=/opt/android-sdk
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/clt.zip \
    && unzip -q /tmp/clt.zip -d ${ANDROID_HOME}/cmdline-tools \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm /tmp/clt.zip \
    && yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager --licenses > /dev/null \
    && ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager \
        "platform-tools" "platforms;android-34" "build-tools;34.0.0" > /dev/null \
    # bubblewrapはSDK直下にbin/(またはtools/)がある自動インストール版レイアウトを
    # 期待して検証するため、シンボリックリンクで合わせる
    && ln -s ${ANDROID_HOME}/cmdline-tools/latest/bin ${ANDROID_HOME}/bin

RUN npm install -g @bubblewrap/cli

# bubblewrapに既存のJDK/SDKを使わせる(対話プロンプト回避)
RUN mkdir -p /root/.bubblewrap \
    && echo "{\"jdkPath\": \"/usr/lib/jvm/java-17-openjdk-amd64\", \"androidSdkPath\": \"${ANDROID_HOME}\"}" \
       > /root/.bubblewrap/config.json

WORKDIR /project
