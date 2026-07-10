"""
Butler Bot — Phase 1
Discord経由でGemini APIと会話する執事ボット。
"""
import os
import io
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import discord
from discord.ext import commands, tasks
from openai import AsyncOpenAI
import aiohttp

import agent_tools
import web_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---- 環境変数 ----
DISCORD_TOKEN       = os.environ["DISCORD_TOKEN_BUTLER"]
DISCORD_GUILD_ID    = int(os.environ["DISCORD_GUILD_ID"])
CHANNEL_NOTIFY      = int(os.environ.get("DISCORD_CHANNEL_NOTIFY", "0"))
CHANNEL_CHAT        = int(os.environ.get("DISCORD_CHANNEL_CHAT", "0"))
LITELLM_BASE_URL    = os.environ.get("LITELLM_BASE_URL", "http://litellm:4000/v1")
LITELLM_MASTER_KEY  = os.environ["LITELLM_MASTER_KEY"]
LLM_MODEL           = os.environ.get("LLM_MODEL", "gemini-2.5-flash-vertex")
CONTEXT_DIR         = Path(os.environ.get("CONTEXT_DIR", "/app/context"))
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

# ---- エージェントモード（ホストのシェル・ファイル操作をツールとして提供）----
# DISCORD_OWNER_ID が未設定の間は完全に無効（安全側デフォルト）。
# 自分のDiscordユーザーIDを .env の DISCORD_OWNER_ID に設定すると有効化される。
DISCORD_OWNER_ID    = int(os.environ["DISCORD_OWNER_ID"]) if os.environ.get("DISCORD_OWNER_ID") else None
AGENT_SOCKET_PATH   = os.environ.get("AGENT_SOCKET_PATH", "/app/agent-socket/butler-agent.sock")
AGENT_AUDIT_LOG     = CONTEXT_DIR / "agent_audit.jsonl"
MAX_TOOL_ITERATIONS = 8

# n8nの「毎朝ブリーフィング_今日の予定取得」ワークフロー(Webhookトリガー、Google Calendar連携)。
# 同じdocker composeネットワーク上のn8nサービスにコンテナ名で到達する（詳細: guide/06_n8n設定.md）。
N8N_TODAY_SCHEDULE_URL = os.environ.get("N8N_TODAY_SCHEDULE_URL", "http://n8n:5678/webhook/today-schedule")
# ワニ博士タスク管理アプリ(plan/13_wani-app.md)。タスク・気分の状態はここに一元化されていて、
# PWA(スマホ)とこのBotのどちらから進捗を更新しても同じ状態が動く。
WANI_API_URL = os.environ.get("WANI_API_URL", "http://wani:8090")
CONFIRM_TIMEOUT_SEC = 300

# ---- LLM設定（LiteLLM経由でVertex AIのGeminiを利用）----
llm_client = AsyncOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_MASTER_KEY)

# キャラクターの口調はモデルの曖昧な知識やWeb検索に頼らず、このファイルで明示的に与える。
PERSONA_FILE = Path(__file__).parent / "persona_whisper.md"
PERSONA_STYLE = PERSONA_FILE.read_text(encoding="utf-8") if PERSONA_FILE.exists() else ""

SYSTEM_INSTRUCTION = (
    "あなたは「執事」です。ユーザー（主人）の生活・作業を能動的にサポートするAIエージェントです。\n"
    "以下は口調・キャラクターの参考資料です。これに厳密に沿って話してください。\n\n"
    f"{PERSONA_STYLE}\n\n"
    "返答は簡潔にし、日本語で答えてください。"
)
AGENT_MODE_INSTRUCTION = (
    "このメッセージの送信者は持ち主本人です。あなた(このBot)が動作しているサーバーホストは、"
    "主人様が日常使っているPCそのものです。「クラウド上のAI」と「主人様のPC」を別物として扱わないでください、"
    "同一のマシンです。あなたにはそのマシン上でシェルコマンドの実行・ファイルの読み書きを行う"
    "run_shell/read_file/write_file/list_dirツールに加え、今日の予定を調べるget_today_schedule、"
    "Web検索のweb_search、指定URLの内容を取得するfetch_url、タスク管理(GitHub Project連携の"
    "ワニ博士アプリ)のlist_tasks/update_task_statusツールが与えられています。"
    "タスクや進捗の話題ではlist_tasksを呼び、「〜終わった」「〜やった」という報告があれば"
    "該当タスクをupdate_task_statusでDoneにして、ワニ博士の気分を主人様に伝えてください。"
    "権限の有無や動作確認を聞かれたときは、説明だけで済ませず、実際にread_file/list_dir/run_shell等の"
    "軽い読み取り系ツールを呼び出して、その実行結果を根拠に答えてください。調査・診断・設定変更を"
    "頼まれた場合も同様に積極的にツールを使ってください。破壊的、または元に戻せない可能性がある操作は"
    "実行前にDiscordで持ち主の承認を求める仕組みが自動で挟まるので、あなたが遠慮したり"
    "「権限がない」と過小に答えたりする必要はありません。"
)

# 会話履歴の読み込み / 保存
HISTORY_FILE = CONTEXT_DIR / "conversation_history.json"

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())[-40:]  # 直近40件
            # 旧Gemini形式(role="model")のログをOpenAI形式(role="assistant")に変換
            for h in history:
                if h.get("role") == "model":
                    h["role"] = "assistant"
            return history
        except Exception:
            return []
    return []

def save_history(history: list) -> None:
    HISTORY_FILE.write_text(json.dumps(history[-100:], ensure_ascii=False, indent=2))

# ---- エージェントツール実行の監査ログ ----
def log_audit(event: dict) -> None:
    event["ts"] = datetime.now().isoformat()
    try:
        with open(AGENT_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        log.exception("audit log write failed")


async def request_confirmation(channel, requester, tool_name: str, args: dict) -> bool:
    """破壊的な可能性があるツール呼び出しについて、Discordのリアクションで持ち主の承認を取る。"""
    if tool_name == "write_file":
        preview = f"path: {args.get('path', '')}\n---content---\n{args.get('content', '')}"
    else:
        preview = args.get("command") or args.get("path") or ""
    try:
        msg = await channel.send(
            f"⚠️ **承認が必要な操作**\nツール: `{tool_name}`\n内容:\n```\n{preview[:1500]}\n```\n"
            f"{requester.mention} {CONFIRM_TIMEOUT_SEC // 60}分以内に ✅(承認) / ❌(却下) でリアクションしてください。"
        )
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
    except discord.Forbidden:
        await channel.send(
            "⚠️ Botに「リアクションの追加」権限がないため確認フローを実行できません。"
            "Discordサーバー設定でBotロールに Add Reactions 権限を付与してください。今回の操作は却下扱いにします。"
        )
        return False

    def check(reaction: discord.Reaction, user: discord.abc.User) -> bool:
        return (
            reaction.message.id == msg.id
            and user.id == requester.id
            and str(reaction.emoji) in ("✅", "❌")
        )

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=CONFIRM_TIMEOUT_SEC, check=check)
    except asyncio.TimeoutError:
        await msg.reply("タイムアウトしたため却下扱いにします。")
        return False

    approved = str(reaction.emoji) == "✅"
    await msg.reply("承認しました。実行します…" if approved else "却下しました。")
    return approved


async def fetch_today_schedule() -> str:
    """n8nのWebhook経由で今日のGoogleカレンダー予定を取得し、整形済みテキストを返す。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                N8N_TODAY_SCHEDULE_URL, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return f"（カレンダー取得に失敗しました: HTTP {resp.status}）"
                events = await resp.json()
    except Exception as e:
        log.error(f"calendar fetch error: {e}")
        return f"（カレンダー取得に失敗しました: {e}）"

    if not events:
        return "今日の予定はありません。"

    def sort_key(e):
        start = e.get("start", {})
        return start.get("dateTime") or start.get("date") or ""

    lines = []
    for e in sorted(events, key=sort_key):
        summary = e.get("summary", "(無題)")
        start = e.get("start", {})
        if "dateTime" in start:
            lines.append(f"・{start['dateTime'][11:16]} {summary}")
        else:
            lines.append(f"・終日 {summary}")
    return "\n".join(lines)


MOOD_LABEL = {"excellent": "エクセレント", "happy": "ごきげん", "normal": "ふつう", "tired": "ぐったり"}


def _format_mood(mood: dict) -> str:
    label = "おやすみ中" if mood.get("sleeping") else MOOD_LABEL.get(mood.get("level"), "?")
    return (f"ワニ博士の気分: {label}({mood.get('mood')}/100) "
            f"今日の完了{mood.get('today_done')}件 連続{mood.get('streak')}日")


async def wani_list_tasks() -> str:
    """ワニ博士アプリからタスク一覧+気分を取得して整形テキストで返す。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{WANI_API_URL}/api/state", timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return f"（タスク取得に失敗しました: HTTP {resp.status}）"
                state = await resp.json()
    except Exception as e:
        log.error(f"wani list_tasks error: {e}")
        return f"（タスク取得に失敗しました: {e}）"

    lines = [_format_mood(state["mood"])]
    if state.get("mock"):
        lines.append("※GitHub未設定のためモックデータです")
    p = state["progress"]
    lines.append(f"進捗: {p['done']}/{p['total']}件完了 ({p['percent']}%) "
                 "※waiting/wish listは進捗の分母に含まない")
    today = state.get("today") or {}
    today_ids = set(today.get("item_ids") or [])
    if today.get("approved"):
        lines.append("⭐=今日やるリスト(作戦会議で承認済み)")
    for t in state["tasks"]:
        ref = f"#{t['number']}" if t.get("number") else "(メモ)"
        star = "⭐" if t["item_id"] in today_ids else ""
        lines.append(f"{star}{ref} [{t.get('status') or 'Todo'}] {t['title']}")
    if not state["tasks"]:
        lines.append("(タスクなし)")
    return "\n".join(lines)


async def wani_update_status(status: str, number: int | None = None, title: str | None = None) -> str:
    """タスク番号またはタイトル→item_id解決の上でStatusを更新する。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{WANI_API_URL}/api/state", timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                state = await resp.json()
            task = None
            if number:
                task = next((t for t in state["tasks"] if t["number"] == number), None)
            elif title:
                # タイトル部分一致(一意に決まるときだけ)。Draft item(番号なし)用
                hits = [t for t in state["tasks"] if title.casefold() in t["title"].casefold()]
                if len(hits) > 1:
                    names = " / ".join(t["title"] for t in hits[:5])
                    return f"（「{title}」に複数該当します: {names}。絞り込んでください）"
                task = hits[0] if hits else None
            if task is None:
                ref = f"#{number}" if number else f"「{title}」"
                return f"（{ref} のタスクが見つかりません）"
            async with session.post(
                f"{WANI_API_URL}/api/tasks/{task['item_id']}/status",
                json={"status": status},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    return f"（更新に失敗しました: {body.get('detail', resp.status)}）"
    except Exception as e:
        log.error(f"wani update_status error: {e}")
        return f"（更新に失敗しました: {e}）"

    t = body["task"]
    ref = f"#{t['number']} " if t.get("number") else ""
    lines = [f"{ref}「{t['title']}」を {t['status']} にしました。",
             _format_mood(body["mood"])]
    if body.get("event") == "done":
        lines.append("(ワニ博士は喜んでいます)")
    return "\n".join(lines)


async def wani_create_task(title: str) -> str:
    """ワニ博士アプリ経由でタスク(Draft item)を追加する。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{WANI_API_URL}/api/tasks",
                json={"title": title},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    return f"（追加に失敗しました: {body.get('detail', resp.status)}）"
    except Exception as e:
        log.error(f"wani create_task error: {e}")
        return f"（追加に失敗しました: {e}）"
    return f"「{body['task']['title']}」をタスクに追加しました(Status: {body['task']['status']})。"


async def wani_set_today(numbers: list[int]) -> str:
    """タスク番号のリストを「今日やるリスト」として設定する。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{WANI_API_URL}/api/state", timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                state = await resp.json()
            by_number = {t["number"]: t for t in state["tasks"] if t.get("number")}
            missing = [n for n in numbers if n not in by_number]
            if missing:
                return f"（見つからない番号があります: {missing}。list_tasksで確認してください）"
            item_ids = [by_number[n]["item_id"] for n in numbers]
            async with session.post(
                f"{WANI_API_URL}/api/today",
                json={"item_ids": item_ids},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    return f"（設定に失敗しました: {body.get('detail', resp.status)}）"
    except Exception as e:
        log.error(f"wani set_today error: {e}")
        return f"（設定に失敗しました: {e}）"
    titles = "、".join(f"#{n} {by_number[n]['title']}" for n in numbers)
    return f"今日やるリストを設定しました: {titles or '(空)'}"


async def run_agent_turn(channel, requester, messages: list) -> str:
    """ツール呼び出し込みでLLMと対話し、最終的なテキスト返答を返す。"""
    for _ in range(MAX_TOOL_ITERATIONS):
        response = await llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=agent_tools.TOOLS,
        )
        choice = response.choices[0].message
        tool_calls = choice.tool_calls or []
        if not tool_calls:
            return choice.content or ""

        messages.append({
            "role": "assistant",
            "content": choice.content,
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        })

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "run_shell":
                decision = agent_tools.classify_shell(args.get("command", ""))
            elif name == "write_file":
                decision = "confirm"
            else:
                decision = "auto"

            approved = True
            if decision == "confirm":
                approved = await request_confirmation(channel, requester, name, args)

            if approved:
                # get_today_schedule/web_search/fetch_urlはホスト実行エージェント(ソケット)を
                # 介さず、Bot自身が直接外部に問い合わせる(ホストのシェル・ファイル操作ではないため
                # 権限分離の対象外)。
                if name == "get_today_schedule":
                    result = {"ok": True, "output": await fetch_today_schedule()}
                elif name == "web_search":
                    result = {"ok": True, "output": await web_tools.web_search(args.get("query", ""))}
                elif name == "fetch_url":
                    result = {"ok": True, "output": await web_tools.fetch_url(args.get("url", ""))}
                elif name == "list_tasks":
                    result = {"ok": True, "output": await wani_list_tasks()}
                elif name == "create_task":
                    result = {"ok": True, "output": await wani_create_task(args.get("title", ""))}
                elif name == "set_today_tasks":
                    result = {"ok": True, "output": await wani_set_today(
                        [int(n) for n in args.get("numbers", [])])}
                elif name == "update_task_status":
                    result = {"ok": True, "output": await wani_update_status(
                        args.get("status", ""),
                        number=int(args["number"]) if args.get("number") else None,
                        title=args.get("title"))}
                else:
                    result = await agent_tools.execute_tool(AGENT_SOCKET_PATH, name, args)
            else:
                result = {"ok": False, "output": "ユーザーが承認しませんでした。"}

            log_audit({
                "user_id": requester.id,
                "user_name": str(requester),
                "tool": name,
                "args": {k: (v[:300] if isinstance(v, str) else v) for k, v in args.items()},
                "decision": decision,
                "approved": approved,
                "ok": result.get("ok"),
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": (result.get("output") or "")[:4000],
            })

    return "ツール呼び出しの上限に達したため処理を中断しました。"

# ---- Discord Bot 設定 ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log.info(f"Butler Bot 起動: {bot.user} (ID: {bot.user.id})")
    if not daily_briefing.is_running():
        daily_briefing.start()
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

    agent_enabled = DISCORD_OWNER_ID is not None and message.author.id == DISCORD_OWNER_ID

    async with message.channel.typing():
        history = load_history()
        system_content = SYSTEM_INSTRUCTION + (f" {AGENT_MODE_INSTRUCTION}" if agent_enabled else "")
        messages = [{"role": "system", "content": system_content}]
        messages += [{"role": h["role"], "content": h["text"]} for h in history]
        messages.append({"role": "user", "content": content})
        try:
            if agent_enabled:
                reply = await run_agent_turn(message.channel, message.author, messages)
            else:
                response = await llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                )
                reply = response.choices[0].message.content
        except Exception as e:
            log.error(f"LLM API error: {e}")
            reply = f"エラーが発生しました: {e}"

        # 履歴保存
        history.append({"role": "user",      "text": content})
        history.append({"role": "assistant", "text": reply})
        save_history(history)

    # 長い返答はファイル添付（以前はメッセージを切り詰めるだけで、実際には添付ファイルを
    # 送っていなかったバグがあった。実際にdiscord.Fileとして全文を添付するよう修正）
    if len(reply) > 1900:
        file = discord.File(io.BytesIO(reply.encode("utf-8")), filename="reply.txt")
        await message.reply(reply[:1900] + "\n…（全文は添付ファイルをご覧ください）", file=file)
    else:
        await message.reply(reply)

    await bot.process_commands(message)

# ---- 朝のデイリーブリーフィング（毎日8時）----
async def suggest_today_tasks(schedule: str, tasks_text: str) -> str:
    """カレンダーの予定とタスク一覧をGeminiに渡し、今日のおすすめタスクを提案させる。"""
    prompt = (
        f"今日の予定:\n{schedule}\n\n現在のタスク:\n{tasks_text}\n\n"
        "上記を踏まえ、朝のブリーフィングとして「今日のおすすめタスク」を1〜3件提案してください。"
        "予定の空き具合との相性を理由に一言添えること。waiting(他人待ち)とwish list(後回しBOX)は"
        "原則すすめない(締切が近そうな場合のみ言及可)。全体で200字以内。"
    )
    try:
        response = await llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        log.error(f"task suggestion error: {e}")
        return ""


@tasks.loop(hours=24)
async def daily_briefing():
    if not CHANNEL_NOTIFY:
        return
    ch = bot.get_channel(CHANNEL_NOTIFY)
    if not ch:
        return
    now = datetime.now()
    schedule = await fetch_today_schedule()
    tasks_text = await wani_list_tasks()
    suggestion = await suggest_today_tasks(schedule, tasks_text)
    msg = (
        f"**おはようございます。{now.strftime('%Y年%m月%d日')}です。**\n\n"
        f"**今日の予定**\n{schedule}\n\n"
        f"**タスク**\n{tasks_text}"
    )
    if suggestion:
        msg += f"\n\n**今日のおすすめ**\n{suggestion}"
    await ch.send(msg[:2000])

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
    # butler-bot コンテナには /mnt/data/ai/context のみが /app/context としてマウントされている
    # （/mnt/data 自体はマウントされていないため、以前はここが常にNoneになっていた）
    disk = shutil.disk_usage(CONTEXT_DIR) if CONTEXT_DIR.exists() else None
    msg = "**サーバー状態**\n"
    if disk:
        used_gb  = disk.used  / (1024**3)
        total_gb = disk.total / (1024**3)
        pct      = disk.used  / disk.total * 100
        msg += f"・保存領域(会話履歴等): {used_gb:.1f} GB / {total_gb:.1f} GB ({pct:.1f}%)\n"
    msg += f"・エージェントモード: {'有効' if DISCORD_OWNER_ID else '無効(DISCORD_OWNER_ID未設定)'}\n"
    msg += f"・現在時刻: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    await ctx.send(msg)

# ---- ヘルスチェック（読み取り専用の診断。docker.sock等のホスト権限は使わない）----
HEALTH_TARGETS = [
    ("Immich",     "http://immich-server:2283/api/server/ping"),
    ("n8n",        "http://n8n:5678/healthz"),
    ("LiteLLM",    "http://litellm:4000/health/liveliness"),
    ("OpenWebUI",  "http://openwebui:8080/health"),
    ("Uptime Kuma","http://uptime-kuma:3001/"),
    ("Ollama",     "http://ollama:11434/"),
    ("Homepage",   "http://homepage:3000/"),
    ("Wani",       "http://wani:8090/healthz"),
]

async def _ping(session: aiohttp.ClientSession, url: str) -> tuple[bool, str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return True, f"HTTP {resp.status}"
    except Exception as e:
        return False, type(e).__name__

@bot.command(name="health")
async def health(ctx):
    """内部サービスの死活を1つずつ確認しながら実況する（読み取り専用）"""
    msg = await ctx.send("**ヘルスチェック開始**\n(各サービスに順番にアクセスします)")
    lines = []
    async with aiohttp.ClientSession() as session:
        for name, url in HEALTH_TARGETS:
            ok, detail = await _ping(session, url)
            mark = "🟢" if ok else "🔴"
            lines.append(f"{mark} {name}: {detail}")
            await msg.edit(content="**ヘルスチェック**\n" + "\n".join(lines))

@bot.command(name="clear")
async def clear_history(ctx):
    """会話履歴をリセット"""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    await ctx.send("会話履歴をリセットしました。")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
