"""
Butler Bot — Phase 1
Discord経由でGemini APIと会話する執事ボット。
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path

import discord
from discord.ext import commands, tasks
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---- 環境変数 ----
DISCORD_TOKEN       = os.environ["DISCORD_TOKEN"]
DISCORD_GUILD_ID    = int(os.environ["DISCORD_GUILD_ID"])
CHANNEL_NOTIFY      = int(os.environ.get("DISCORD_CHANNEL_NOTIFY", "0"))
CHANNEL_CHAT        = int(os.environ.get("DISCORD_CHANNEL_CHAT", "0"))
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
CONTEXT_DIR         = Path(os.environ.get("CONTEXT_DIR", "/app/context"))
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Gemini 設定 ----
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction=(
        "あなたは「執事」です。ユーザー（主人）の生活・作業を能動的にサポートするAIエージェントです。"
        "返答は簡潔・丁寧に。日本語で答えてください。"
        "ツール操作（カレンダー・Switchbot等）は将来実装予定です。"
    ),
)

# 会話履歴の読み込み / 保存
HISTORY_FILE = CONTEXT_DIR / "conversation_history.json"

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())[-40:]  # 直近40件
        except Exception:
            return []
    return []

def save_history(history: list) -> None:
    HISTORY_FILE.write_text(json.dumps(history[-100:], ensure_ascii=False, indent=2))

# ---- Discord Bot 設定 ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log.info(f"Butler Bot 起動: {bot.user} (ID: {bot.user.id})")
    # 起動通知
    if CHANNEL_NOTIFY:
        ch = bot.get_channel(CHANNEL_NOTIFY)
        if ch:
            await ch.send(f"執事が起動しました。({datetime.now().strftime('%Y-%m-%d %H:%M')})")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # #butler-chat チャンネル、またはメンションで反応
    is_chat_channel = (CHANNEL_CHAT and message.channel.id == CHANNEL_CHAT)
    is_mentioned    = bot.user in message.mentions

    if not (is_chat_channel or is_mentioned):
        await bot.process_commands(message)
        return

    # メンション部分を除去してプロンプト取得
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not content:
        return

    async with message.channel.typing():
        history = load_history()
        # Gemini に会話履歴付きで問い合わせ
        chat = model.start_chat(history=[
            {"role": h["role"], "parts": [h["text"]]} for h in history
        ])
        try:
            response = chat.send_message(content)
            reply = response.text
        except Exception as e:
            log.error(f"Gemini API error: {e}")
            reply = f"エラーが発生しました: {e}"

        # 履歴保存
        history.append({"role": "user",  "text": content})
        history.append({"role": "model", "text": reply})
        save_history(history)

    # 長い返答はファイル添付
    if len(reply) > 1900:
        await message.reply(reply[:1900] + "\n… (続きは添付ファイル)")
    else:
        await message.reply(reply)

    await bot.process_commands(message)

# ---- 朝のデイリーブリーフィング（毎日8時）----
@tasks.loop(hours=24)
async def daily_briefing():
    if not CHANNEL_NOTIFY:
        return
    ch = bot.get_channel(CHANNEL_NOTIFY)
    if not ch:
        return
    now = datetime.now()
    msg = (
        f"**おはようございます。{now.strftime('%Y年%m月%d日')}です。**\n"
        "・サーバー稼働中\n"
        "・Googleカレンダー連携は n8n で設定してください（guide/05_n8n設定.md）"
    )
    await ch.send(msg)

@daily_briefing.before_loop
async def before_briefing():
    await bot.wait_until_ready()
    # 次の8:00まで待機
    from asyncio import sleep
    now = datetime.now()
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= target:
        from datetime import timedelta
        target += timedelta(days=1)
    await sleep((target - now).total_seconds())

# ---- コマンド ----
@bot.command(name="status")
async def status(ctx):
    """サーバー状態を表示"""
    import shutil
    disk = shutil.disk_usage("/mnt/data") if Path("/mnt/data").exists() else None
    msg = "**サーバー状態**\n"
    if disk:
        used_gb  = disk.used  / (1024**3)
        total_gb = disk.total / (1024**3)
        pct      = disk.used  / disk.total * 100
        msg += f"・ストレージ: {used_gb:.1f} GB / {total_gb:.1f} GB ({pct:.1f}%)\n"
    msg += f"・現在時刻: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    await ctx.send(msg)

@bot.command(name="clear")
async def clear_history(ctx):
    """会話履歴をリセット"""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    await ctx.send("会話履歴をリセットしました。")

if __name__ == "__main__":
    daily_briefing.start()
    bot.run(DISCORD_TOKEN)
