"""
環境変数の読み込み・共通設定。
GitHub/Ollama関連はtask-agent固有の設定としてtask-agent/.envから読む。DISCORD_TOKEN/
DISCORD_CHANNEL_IDはdocker-compose.yml側でserver/.envのDISCORD_TOKEN_OLLAMA/
DISCORD_CHANNEL_OLLAMA（butler-botのDISCORD_TOKEN_BUTLERとは別の専用Bot）から
このプロセス内の変数名にマッピングされて渡ってくる。同じBot名でGemini(butler-bot)と
Ollama(task-agent)の発言が混在すると分かりにくいため、Botを分けている。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"環境変数 {name} が設定されていません")
    return value


# ---- GitHub ----
GITHUB_TOKEN = _require("GITHUB_TOKEN")
GITHUB_PROJECT_OWNER = _require("GITHUB_PROJECT_OWNER")  # 個人Organizationのlogin名
GITHUB_PROJECT_OWNER_TYPE = os.environ.get("GITHUB_PROJECT_OWNER_TYPE", "organization")  # organization | user
GITHUB_PROJECT_NUMBER = int(_require("GITHUB_PROJECT_NUMBER"))
GITHUB_STATUS_FIELD_NAME = os.environ.get("GITHUB_STATUS_FIELD_NAME", "Status")

# ---- Discord ----
# task-agent専用のBot（butler-botとは別）。取得手順: guide/12_タスク管理エージェント設定.md
DISCORD_TOKEN = _require("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = _require("DISCORD_CHANNEL_ID")

# ---- Ollama（自宅サーバー上のローカルLLM。定例タスクで緊急性がないため採用）----
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# ---- 生ログ・日次状態の保存先 ----
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

# ---- 挙動調整 ----
TASK_LABELS = [
    label.strip()
    for label in os.environ.get("TASK_LABELS", "").split(",")
    if label.strip()
]
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Tokyo")
