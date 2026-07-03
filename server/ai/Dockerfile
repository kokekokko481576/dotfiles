FROM python:3.12-slim

WORKDIR /app

# 依存パッケージインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコピー
COPY src/ ./src/

# コンテキスト保存用ディレクトリ
RUN mkdir -p /app/context

CMD ["python", "-u", "src/bot.py"]
