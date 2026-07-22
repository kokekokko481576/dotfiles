"""
Butler Bot — Phase 1
Discord経由でGemini APIと会話するワニ博士ボット。
"""
import os
import io
import re
import json
import asyncio
import difflib
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
# LLMに毎回送る会話履歴の上限メッセージ数。以前は直近40件を丸ごと送っていて読み過ぎ
# だった。逆に少なすぎると「直前に何をしたか」を忘れるので、各ターンのツール実行を
# 要約してhistoryに残す(下記 actions)ことで、少ない件数でも行動の記憶は保つ。
HISTORY_MAX_MESSAGES = int(os.environ.get("HISTORY_MAX_MESSAGES", "16"))
# 履歴ファイルに保持する最大件数(送信数とは別。ローテーション用)。
HISTORY_KEEP_MESSAGES = int(os.environ.get("HISTORY_KEEP_MESSAGES", "100"))

# n8nの「毎朝ブリーフィング_今日の予定取得」ワークフロー(Webhookトリガー、Google Calendar連携)。
# 同じdocker composeネットワーク上のn8nサービスにコンテナ名で到達する（詳細: guide/06_n8n設定.md）。
N8N_TODAY_SCHEDULE_URL = os.environ.get("N8N_TODAY_SCHEDULE_URL", "http://n8n:5678/webhook/today-schedule")
# n8nの「予定追加」ワークフロー(Webhookトリガー)。Googleカレンダーに予定を1件作成する。
# 生成: scripts/n8n_calendar_workflows.py
N8N_CALENDAR_ADD_URL = os.environ.get("N8N_CALENDAR_ADD_URL", "http://n8n:5678/webhook/calendar-add")
# ワニ博士タスク管理アプリ(plan/13_wani-app.md)。タスク・気分の状態はここに一元化されていて、
# PWA(スマホ)とこのBotのどちらから進捗を更新しても同じ状態が動く。
WANI_API_URL = os.environ.get("WANI_API_URL", "http://wani:8090")
CONFIRM_TIMEOUT_SEC = 300

# ---- LLM設定（LiteLLM経由でVertex AIのGeminiを利用）----
# timeout未指定だとopenaiのデフォルトは600秒(10分)。Vertexがたまにストールすると
# Botが最大10分無応答で固まる(=「返事がない」の原因)ため、明示的に短く設定して
# 詰まったら速やかにエラー応答を返す。max_retriesも抑え、最悪待ち時間を短くする。
llm_client = AsyncOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_MASTER_KEY,
                         timeout=60.0, max_retries=1)

# キャラクターの口調はモデルの曖昧な知識やWeb検索に頼らず、このファイルで明示的に与える。
PERSONA_FILE = Path(__file__).parent / "persona_wanihakase.md"
PERSONA_STYLE = PERSONA_FILE.read_text(encoding="utf-8") if PERSONA_FILE.exists() else ""

# 3Bot共通のユーザープロフィール/大日程(docker-composeで /app/profile.md にbind-mount)。
# レコメンドのプロンプトに差し込む。未配置でも空文字で動く。
PROFILE_FILE = Path(os.environ.get("PROFILE_FILE", "/app/profile.md"))
PROFILE_TEXT = PROFILE_FILE.read_text(encoding="utf-8").strip() if PROFILE_FILE.exists() else ""

# プロフィール・大日程は全てのbutlerのLLM呼び出し(会話・朝のブリーフィング)で
# 文脈として効かせたいので、システムプロンプト本体に載せる。
_PROFILE_BLOCK = (
    f"\n\n## こっこについて(プロフィール・大日程。提案・優先順位づけの最重要の前提)\n{PROFILE_TEXT}\n"
    if PROFILE_TEXT else ""
)
SYSTEM_INSTRUCTION = (
    "あなたは「ワニ博士」です。こっこ(ユーザー)の生活・作業を能動的にサポートするAIエージェントです。\n"
    "以下は口調・キャラクターの参考資料です。これに厳密に沿って話してください。\n\n"
    f"{PERSONA_STYLE}\n\n"
    "返答は簡潔にし、日本語で答えてください。"
    f"{_PROFILE_BLOCK}"
)
AGENT_MODE_INSTRUCTION = (
    "このメッセージの送信者はこっこ本人です。あなた(このBot)が動作しているサーバーホストは、"
    "こっこが日常使っているPCそのものです。「クラウド上のAI」と「こっこのPC」を別物として扱わないでください、"
    "同一のマシンです。あなたにはそのマシン上でシェルコマンドの実行・ファイルの読み書きを行う"
    "run_shell/read_file/write_file/list_dirツールに加え、今日の予定を調べるget_today_schedule、"
    "Web検索のweb_search、指定URLの内容を取得するfetch_url、タスク管理(GitHub Project連携の"
    "ワニ博士アプリ)のlist_tasks/update_task_statusツールが与えられています。"
    "タスクや進捗の話題ではlist_tasksを呼び、「〜終わった」「〜やった」という報告があれば"
    "該当タスクをupdate_task_statusでDoneにして、ワニ博士の気分をこっこに伝えてください。"
    "『今日/明日のおすすめ』『計画して』等を頼まれたら、次の手順で考えること。"
    "(1) get_today_scheduleでその日のGoogleカレンダー予定を取得する。これは動かせない固定予定で、"
    "その日は必ずこなす前提。まず予定と予定の合間の空き時間がどれだけあるかを見積もる。"
    "(2) システムプロンプトの『こっこについて』(プロフィール・大日程)を最優先の判断基準にする。"
    "今が院試・試験・大きな締切前などの繁忙期なら、その勉強/準備を空き時間の主役に据え、"
    "それと無関係なGitHubタスク(例: はんだづけ・電子工作・研究以外の趣味)は原則すすめない。"
    "(3) list_tasksは参照するが、そのまま全部並べるのではなく、今の時期にやるべきものだけを選ぶ。"
    "適切なものが無ければ、その時期にふさわしい勉強タスクを自分で具体的に考え出して提案する"
    "(例: 過去問の復習、間違えた範囲の深掘り学習)。各タスクに所要時間の目安を添える。"
    "(4) 提案がまとまったら「Googleカレンダーに追加しますか?」と尋ね、"
    "こっこが同意したら create_calendar_event で予定を登録する(空き時間に収まる日時を提案し、"
    "最終的な時間はこっこに確認する。登録前に承認ダイアログが自動で出る)。"
    "権限の有無や動作確認を聞かれたときは、説明だけで済ませず、実際にread_file/list_dir/run_shell等の"
    "軽い読み取り系ツールを呼び出して、その実行結果を根拠に答えてください。調査・診断・設定変更を"
    "頼まれた場合も同様に積極的にツールを使ってください。破壊的、または元に戻せない可能性がある操作は"
    "実行前にDiscordでこっこの承認を求める仕組みが自動で挟まるので、あなたが遠慮したり"
    "「権限がない」と過小に答えたりする必要はありません。"
    "また、こっこが学習の進捗・過去問の得点・弱点・到達度などを話したら update_progress で"
    "その領域(院試/研究等)に記録すること(翌日の日次プランのタスク創出に使われる)。"
    "「今日のタスク入れといて」「今日のToDo作って」「今日の作戦やる」等と言われたら add_today_todos を"
    "呼び、夜間に生成された今日の創出タスクをGoogle ToDoに一括登録すること(ワニ博士アプリで討伐できる)。"
    "夜の振り返り(日記)では、まず今日の達成状況(list_tasksで確認)を踏まえて『今日は何をした?"
    "どうだった?過去問の出来は?』と親しみやすく短く問いかけ、会話する。こっこの返答から過去問の"
    "点数・学習到達度・弱点など進捗が出たら update_progress で該当領域(院試等)に記録し、"
    "話がひと段落したら save_diary でその日の日記を保存する(1日分を数行に要約)。"
)

# 夜間(task-agent daily-plan)が生成した当日プラン。butlerの朝ブリーフィングもこれを読んで、
# その場でLLMを呼ばずに使い回す(wani/Discordレコメンドと同じ「夜1回生成→読むだけ」)。
# docker-composeで /mnt/data/ai/wani を /app/wani にread-onlyマウント。
WANI_DATA_DIR = Path(os.environ.get("WANI_DATA_DIR", "/app/wani"))


def load_daily_plan_raw() -> dict | None:
    """当日のdaily_plan.jsonを辞書で返す。無い/当日分でないならNone。"""
    try:
        plan = json.loads((WANI_DATA_DIR / "daily_plan.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return plan if plan.get("date") == datetime.now().strftime("%Y-%m-%d") else None


def load_daily_plan_text() -> str | None:
    """当日のdaily_plan.jsonを朝ブリーフィング用テキストに整形する。無い/当日分でないならNone。"""
    plan = load_daily_plan_raw()
    if not plan:
        return None
    comment = (plan.get("comment") or "").strip()
    wake = (plan.get("wake_time") or "").strip()
    cd = plan.get("countdown") or {}
    lines = []
    if cd.get("days") is not None:
        lines.append(f"⏳ {cd.get('label') or '締切'}まであと{cd['days']}日")
    if comment:
        lines.append(comment)
    for p in plan.get("picks", []):
        num = f"#{p['number']} " if p.get("number") else ""
        reason = f" — {p['reason']}" if p.get("reason") else ""
        lines.append(f"・{num}{p.get('title', '')}{reason}")
    for t in plan.get("generated_tasks", []):
        mins = f"({t['estimated_minutes']}分)" if t.get("estimated_minutes") else ""
        lines.append(f"・✏️{t.get('title', '')}{mins} — {t.get('reason', '')}")
    sched = plan.get("proposed_schedule", [])
    if sched:
        head = f"🌅{wake}起床。時間割は " if wake else "時間割は "
        lines.append(head + f"{len(sched)}コマ(詳細は /plan)。")
    return "\n".join(lines) if lines else None


def format_plan_full(plan: dict) -> str:
    """/plan 用。時間割(カレンダー予定・既存ToDo込み)を実際に展開して見せる。"""
    cd = plan.get("countdown") or {}
    lines = []
    if cd.get("days") is not None:
        lines.append(f"⏳ **{cd.get('label') or '締切'}まであと{cd['days']}日**（{cd.get('date','')}）")
    if plan.get("comment"):
        lines.append(plan["comment"])
    sched = plan.get("proposed_schedule", [])
    if sched:
        lines.append("\n**🗓 今日の時間割**（固定予定・既存ToDoも含む）")
        for s in sched:
            span = f"{s.get('start','')}–{s.get('end','')}".strip("–")
            dom = f"  _{s.get('domain')}_" if s.get("domain") else ""
            lines.append(f"`{span}` {s.get('title','')}{dom}")
    picks = plan.get("picks", [])
    if picks:
        lines.append("\n**📌 GitHubタスク**")
        for p in picks:
            num = f"#{p['number']} " if p.get("number") else ""
            lines.append(f"・{num}{p.get('title','')}")
    gen = plan.get("generated_tasks", [])
    if gen:
        lines.append("\n**✏️ 今日つくったタスク**（`/todos` でToDo化して討伐）")
        for t in gen:
            mins = f"({t['estimated_minutes']}分)" if t.get("estimated_minutes") else ""
            lines.append(f"・{t.get('title','')}{mins}")
    return "\n".join(lines) if lines else "(内容なし)"


# ---- 今日の創出タスク → Google ToDo登録 ----
# ワニ博士アプリで「討伐」できるよう、生成タスクはカレンダー予定でなくGoogle ToDoにする。
N8N_TODO_ADD_URL = os.environ.get("N8N_TODO_ADD_URL", "http://n8n:5678/webhook/todo-add")


async def _todo_add(title: str, notes: str = "", due: str = "") -> tuple[bool, str]:
    """n8n経由でGoogle ToDoを1件作成する。(成功, エラー文)を返す。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                N8N_TODO_ADD_URL,
                json={"title": title, "notes": notes, "due": due},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return False, f"HTTP {resp.status} {text[:200]}"
    except Exception as e:
        log.error(f"todo add error: {e}")
        return False, str(e)
    return True, ""


def build_todo_items(plan: dict) -> list[dict]:
    """daily_planのgenerated_tasks(創出タスク)をToDo項目に変換する。
    GitHub picksは既にワニ博士アプリで扱えるのでToDo化しない(重複回避)。"""
    today = datetime.now().strftime("%Y-%m-%d")
    due = f"{today}T00:00:00.000Z"
    items = []
    for t in plan.get("generated_tasks", []):
        title = (t.get("title") or "").strip()
        if not title:
            continue
        parts = []
        if t.get("reason"):
            parts.append(t["reason"])
        if t.get("estimated_minutes"):
            parts.append(f"約{t['estimated_minutes']}分")
        if t.get("preferred_time"):
            parts.append(str(t["preferred_time"]))
        items.append({"title": title, "notes": " ｜ ".join(parts), "due": due})
    return items


async def write_todos(items: list[dict]) -> tuple[int, int]:
    """ToDoをGoogle Tasksに作成し、(成功数, 総数)を返す。"""
    ok = 0
    for it in items:
        good, _ = await _todo_add(it["title"], it.get("notes", ""), it.get("due", ""))
        if good:
            ok += 1
    return ok, len(items)


# ---- 日記(振り返り)の保存 ----
DIARY_DIR = Path(os.environ.get("DIARY_DIR", "/app/diary"))


def save_diary_entry(content: str, mood: str = "") -> str:
    """その日の日記を /app/diary/YYYY-MM-DD.md に保存(同日は追記)する。"""
    content = (content or "").strip()
    if not content:
        return "日記の内容が空です。"
    DIARY_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = DIARY_DIR / f"{now.strftime('%Y-%m-%d')}.md"
    header_needed = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if header_needed:
            f.write(f"# {now.strftime('%Y-%m-%d')} の日記\n\n")
        f.write(f"## {now.strftime('%H:%M')}" + (f"（気分: {mood}）" if mood else "") + "\n")
        f.write(content + "\n\n")
    return f"日記を保存しました（{now.strftime('%Y-%m-%d')}）。"


# ---- 進捗ステート(projects)の更新 ----
PROJECTS_DIR = CONTEXT_DIR / "projects"


def update_progress_file(domain: str, note: str) -> str:
    """管理領域の進捗メモを /app/context/projects/<domain>.md に追記する。"""
    # \w はUnicodeなので日本語もそのまま残る。/ や . を除去してパストラバーサルを防ぐ
    domain = re.sub(r"[^\w-]", "", domain or "").strip()
    note = (note or "").strip()
    if not domain:
        return "領域名が空です。"
    if not note:
        return "記録する内容が空です。"
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROJECTS_DIR / f"{domain}.md"
    today = datetime.now().strftime("%Y-%m-%d")
    new_file = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if new_file:
            f.write(f"# {domain}\n\n## 記録ログ\n")
        f.write(f"- [{today}] {note}\n")
    return f"「{domain}」に記録しました: {note}"


# 会話履歴の読み込み / 保存
HISTORY_FILE = CONTEXT_DIR / "conversation_history.json"

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())[-HISTORY_MAX_MESSAGES:]
            # 旧Gemini形式(role="model")のログをOpenAI形式(role="assistant")に変換
            for h in history:
                if h.get("role") == "model":
                    h["role"] = "assistant"
            return history
        except Exception:
            return []
    return []


def history_to_messages(history: list) -> list:
    """保存済み履歴をLLM用メッセージ列に変換する。

    各assistantターンに actions(そのターンで実行したツールの短い要約)が残っていれば、
    メッセージ本文に「〔このターンで実行: ...〕」として畳み込む。こうすると少ない履歴
    件数でも「さっき何を実行/承認したか」をモデルが思い出せる(実行済みの確認をまた
    聞き返す鈍い挙動を防ぐ)。
    """
    out = []
    for h in history:
        content = h.get("text", "")
        actions = h.get("actions")
        if actions:
            content = f"{content}\n〔このターンで実行: {' / '.join(actions)}〕".strip()
        out.append({"role": h["role"], "content": content})
    return out


def save_history(history: list) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history[-HISTORY_KEEP_MESSAGES:], ensure_ascii=False, indent=2))

# ---- エージェントツール実行の監査ログ ----
def log_audit(event: dict) -> None:
    event["ts"] = datetime.now().isoformat()
    try:
        with open(AGENT_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        log.exception("audit log write failed")


async def _read_file_via_agent(path: str) -> str:
    """agent executor経由でファイル内容を読む(差分表示用。読めなければ空文字)。"""
    try:
        res = await agent_tools.execute_tool(AGENT_SOCKET_PATH, "read_file", {"path": path})
        if res.get("ok"):
            return res.get("output") or ""
    except Exception:
        log.exception("diff用のread_fileに失敗")
    return ""


def _render_write_diff(path: str, old: str, new: str, limit: int = 1500) -> str:
    """write_fileの新旧内容の差分をDiscordの ```diff ブロックにする(色付き表示)。"""
    diff = difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")
    body = "\n".join(diff)
    if not body:
        return f"(内容に変更なし: `{path}`)"
    truncated = ""
    if len(body) > limit:
        body = body[:limit]
        truncated = "\n… (差分が長いため省略)"
    return f"```diff\n{body}{truncated}\n```"


async def request_confirmation(channel, requester, tool_name: str, args: dict) -> bool:
    """破壊的な可能性があるツール呼び出しについて、Discordのリアクションで持ち主の承認を取る。"""
    if tool_name == "write_file":
        # 全文べた貼りではなく、既存ファイルとの差分を色付き(```diff)で見せる
        path = args.get("path", "")
        old = await _read_file_via_agent(path)
        new = args.get("content", "")
        verb = "新規作成" if not old else "編集"
        detail = f"path: `{path}` ({verb})\n{_render_write_diff(path, old, new)}"
    elif tool_name == "add_today_todos":
        plan = load_daily_plan_raw()
        items = build_todo_items(plan) if plan else []
        if items:
            body = "\n".join(f"・{it['title']}" + (f"（{it['notes']}）" if it.get("notes") else "")
                             for it in items)
        else:
            body = "(登録できる創出タスクがありません)"
        detail = f"以下をGoogle ToDoに登録します(ワニ博士アプリで討伐可):\n```\n{body[:1500]}\n```"
    else:
        preview = args.get("command") or args.get("path") or ""
        detail = f"```\n{preview[:1500]}\n```"
    try:
        msg = await channel.send(
            f"⚠️ **承認が必要な操作**\nツール: `{tool_name}`\n内容:\n{detail}\n"
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
    todos = state.get("todos") or []
    if todos:
        lines.append("📝 Google ToDo:")
        for t in todos:
            mark = "(きょうまで!)" if t.get("forced") else \
                (f"期限{t['due']}" if t.get("due") else "期限なし")
            lines.append(f"・{t['title']} {mark}")
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


async def _calendar_add(summary: str, start: str, end: str, description: str = "") -> tuple[bool, str]:
    """n8n経由でGoogleカレンダーに予定を1件追加する。(成功, エラー文)を返す。"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                N8N_CALENDAR_ADD_URL,
                json={"summary": summary, "start": start, "end": end, "description": description},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return False, f"HTTP {resp.status} {text[:200]}"
    except Exception as e:
        log.error(f"calendar add error: {e}")
        return False, str(e)
    return True, ""


async def create_calendar_event(summary: str, start: str, end: str, description: str = "") -> str:
    """n8n経由でGoogleカレンダーに予定を1件追加する(LLMツール用。テキストを返す)。"""
    if not (summary and start and end):
        return "（予定の追加に失敗: タイトル・開始・終了は必須です）"
    ok, err = await _calendar_add(summary, start, end, description)
    if not ok:
        return f"（予定の追加に失敗しました: {err}）"
    return f"カレンダーに「{summary}」を追加しました({start} 〜 {end})。"


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


def _action_label(name: str, args: dict, approved: bool, result: dict) -> str:
    """このターンで実行したツールの短い要約(履歴に残して行動の記憶にする)。"""
    if not approved:
        return f"{name}(却下)"
    if name in ("write_file", "read_file"):
        a = args.get("path", "")
    elif name == "run_shell":
        a = (args.get("command", "") or "")[:40]
    elif name == "update_task_status":
        a = f"#{args.get('number')} {args.get('status', '')}" if args.get("number") \
            else f"{args.get('title', '')} {args.get('status', '')}"
    elif name == "create_calendar_event":
        a = args.get("summary", "")
    elif name == "create_task":
        a = args.get("title", "")
    elif name == "set_today_tasks":
        a = str(args.get("numbers", ""))
    else:
        a = ""
    ok = "ok" if result.get("ok") else "失敗"
    return f"{name}({a})→{ok}" if a else f"{name}→{ok}"


async def run_agent_turn(channel, requester, messages: list) -> tuple[str, list]:
    """ツール呼び出し込みでLLMと対話する。

    戻り値: (最終テキスト返答, このターンで実行したツールの要約リスト)。
    要約は呼び出し側で会話履歴に残され、次ターン以降に「さっき何をしたか」を
    思い出す手がかりになる。
    """
    actions: list[str] = []
    for _ in range(MAX_TOOL_ITERATIONS):
        response = await llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=agent_tools.TOOLS,
        )
        choice = response.choices[0].message
        tool_calls = choice.tool_calls or []
        if not tool_calls:
            return choice.content or "", actions

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
            elif name in ("write_file", "create_calendar_event", "add_today_todos"):
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
                elif name == "create_calendar_event":
                    result = {"ok": True, "output": await create_calendar_event(
                        args.get("summary", ""), args.get("start", ""),
                        args.get("end", ""), args.get("description", ""))}
                elif name == "set_today_tasks":
                    result = {"ok": True, "output": await wani_set_today(
                        [int(n) for n in args.get("numbers", [])])}
                elif name == "add_today_todos":
                    plan = load_daily_plan_raw()
                    items = build_todo_items(plan) if plan else []
                    if not items:
                        result = {"ok": False, "output": "今日の創出タスクがありません(繁忙期で0件など)。"}
                    else:
                        ok_n, total = await write_todos(items)
                        result = {"ok": ok_n > 0,
                                  "output": f"Google ToDoに{ok_n}/{total}件登録しました(ワニ博士アプリで討伐できます)。"}
                elif name == "update_progress":
                    result = {"ok": True, "output": update_progress_file(
                        args.get("domain", ""), args.get("note", ""))}
                elif name == "save_diary":
                    result = {"ok": True, "output": save_diary_entry(
                        args.get("content", ""), args.get("mood", ""))}
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
            actions.append(_action_label(name, args, approved, result))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": (result.get("output") or "")[:4000],
            })

    return "ツール呼び出しの上限に達したため処理を中断しました。", actions

# ---- Discord Bot 設定 ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
GUILD_OBJ = discord.Object(id=DISCORD_GUILD_ID)  # スラッシュコマンドをこのギルドに即時同期する

@bot.event
async def on_ready():
    log.info(f"Butler Bot 起動: {bot.user} (ID: {bot.user.id})")
    if not daily_briefing.is_running():
        daily_briefing.start()
    if not evening_reflection.is_running():
        evening_reflection.start()
    # スラッシュコマンドをギルドに同期(ギルド単位は即時反映。グローバルは反映に最大1時間)
    try:
        bot.tree.copy_global_to(guild=GUILD_OBJ)
        synced = await bot.tree.sync(guild=GUILD_OBJ)
        log.info("スラッシュコマンド同期: %d件 %s", len(synced), [c.name for c in synced])
    except Exception:
        log.exception("スラッシュコマンドの同期に失敗(applications.commandsスコープで再招待が必要かも)")
    # 起動通知
    if CHANNEL_NOTIFY:
        ch = bot.get_channel(CHANNEL_NOTIFY)
        if ch:
            await ch.send(f"ワニ博士、起動したのだ! ({datetime.now().strftime('%Y-%m-%d %H:%M')})")

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
        messages += history_to_messages(history)
        messages.append({"role": "user", "content": content})
        actions: list = []
        try:
            if agent_enabled:
                reply, actions = await run_agent_turn(message.channel, message.author, messages)
            else:
                response = await llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                )
                reply = response.choices[0].message.content
        except Exception as e:
            log.error(f"LLM API error: {e}")
            reply = f"エラーが発生しました: {e}"

        # 履歴保存。assistantターンには実行したツールの要約(actions)も残し、
        # 次ターンで「さっき実行/承認したこと」を思い出せるようにする。
        history.append({"role": "user", "text": content})
        assistant_entry = {"role": "assistant", "text": reply}
        if actions:
            assistant_entry["actions"] = actions
        history.append(assistant_entry)
        save_history(history)

    # 長い返答はファイル添付（以前はメッセージを切り詰めるだけで、実際には添付ファイルを
    # 送っていなかったバグがあった。実際にdiscord.Fileとして全文を添付するよう修正）
    if len(reply) > 1900:
        file = discord.File(io.BytesIO(reply.encode("utf-8")), filename="reply.txt")
        await message.reply(reply[:1900] + "\n…（全文は添付ファイルをご覧ください）", file=file)
    else:
        await message.reply(reply)

    await bot.process_commands(message)

# ---- 朝のデイリーブリーフィング（毎日7時）----
BRIEFING_HOUR = int(os.environ.get("BRIEFING_HOUR", "7"))
EVENING_REFLECT_HOUR = int(os.environ.get("EVENING_REFLECT_HOUR", "21"))
WAKE_CONFIRM_SEC = int(os.environ.get("WAKE_CONFIRM_SEC", "900"))  # 起床確認の猶予(15分)


def _weather_line(w: dict | None) -> str:
    if not w:
        return ""
    rain = "　☔傘を!(雨→登校長め)" if w.get("rainy") else ""
    return (f"🌤 天気: {w.get('desc','')} / 降水{w.get('pop')}% / "
            f"{w.get('tmin')}〜{w.get('tmax')}℃{rain}")


async def _await_wake_or_replan(msg, ch):
    """朝ブリーフィングに15分以内に👀が付かなければ寝坊とみなして組み直す。"""
    def check(reaction, user):
        return (reaction.message.id == msg.id and str(reaction.emoji) == "👀"
                and (DISCORD_OWNER_ID is None or user.id == DISCORD_OWNER_ID))
    try:
        await bot.wait_for("reaction_add", timeout=WAKE_CONFIRM_SEC, check=check)
        return  # 起床確認OK。朝プランのまま
    except asyncio.TimeoutError:
        await ch.send("むむ、15分反応が無いのだ…寝坊とみなして今日の予定を組み直すのだ!")
        await replan_overslept(ch)


async def replan_overslept(ch):
    """寝坊時: 今から就寝までで現実的に時間割を組み直し、daily_plan.jsonを更新して再掲する。"""
    plan = load_daily_plan_raw()
    if not plan:
        await ch.send("今日のプランが無いので組み直せないのだ。")
        return
    now = datetime.now()
    sched = plan.get("proposed_schedule", [])
    orig = "\n".join(f"{s.get('start')}-{s.get('end')} {s.get('title')}" for s in sched)
    prompt = (
        f"こっこが寝坊した。今の時刻は約{now.strftime('%H:%M')}。今日はもう筋トレはしない。"
        "以下の元の時間割を、今から就寝(22:00目標)までで現実的に組み直して。"
        "日課daily_knock(約3時間)と『過去問→振り返り』はできるだけ残し、間に合わない低優先タスクは削る。"
        "食事など固定予定は動かさない。移動と勉強を重ねない。\n"
        '次のJSONだけ出力: {"proposed_schedule":[{"start":"HH:MM","end":"HH:MM","title":"...","domain":"..."}],'
        ' "comment":"寝坊を踏まえた一言(40字以内)"}\n\n元の時間割:\n' + orig
    )
    try:
        resp = await llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": SYSTEM_INSTRUCTION},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"})
        data = json.loads(resp.choices[0].message.content)
        new_sched = data.get("proposed_schedule") or []
        if not new_sched:
            raise ValueError("空スケジュール")
        plan["proposed_schedule"] = new_sched
        plan["wake_time"] = now.strftime("%H:%M")
        plan["comment"] = data.get("comment") or plan.get("comment", "")
        plan["overslept"] = True
        (WANI_DATA_DIR / "daily_plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        await ch.send(("🐊 寝坊ルートで組み直したのだ!\n" + format_plan_full(plan))[:1990])
    except Exception as e:
        log.exception("寝坊リプランに失敗")
        await ch.send(f"組み直しに失敗したのだ({e})。/plan を手動で調整してほしいのだ。")


@tasks.loop(hours=24)
async def daily_briefing():
    if not CHANNEL_NOTIFY:
        return
    ch = bot.get_channel(CHANNEL_NOTIFY)
    if not ch:
        return
    now = datetime.now()
    plan = load_daily_plan_raw()
    parts = [f"**おはようなのだ、こっこ! {now.strftime('%Y年%m月%d日')}なのだ。**"]
    wline = _weather_line(plan.get("weather") if plan else None)
    if wline:
        parts.append(wline)
    parts.append(format_plan_full(plan) if plan else "今日のプランはまだ無いのだ(夜間4時に作るのだ)。")
    parts.append("_起きたら15分以内に 👀 を押すのだ! 押さないと寝坊とみなして予定を組み直すのだ。_")
    msg = await ch.send("\n\n".join(parts)[:2000])
    try:
        await msg.add_reaction("👀")
        asyncio.create_task(_await_wake_or_replan(msg, ch))
    except discord.Forbidden:
        pass  # リアクション権限が無ければ起床確認はスキップ


@daily_briefing.before_loop
async def before_briefing():
    await bot.wait_until_ready()
    from asyncio import sleep
    from datetime import timedelta
    now = datetime.now()
    target = now.replace(hour=BRIEFING_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    await sleep((target - now).total_seconds())


# ---- 夜の振り返り（日記。毎日21時）----
async def start_diary(ch):
    """今日の達成状況を踏まえた振り返りの問いかけを投稿する(以降は通常会話で続く)。"""
    now = datetime.now()
    status = await wani_list_tasks()
    prompt = (
        f"今は{now.strftime('%H:%M')}、一日の終わりの振り返り(日記)の時間。以下は今日のタスク状況。\n"
        f"{status}\n\n"
        "これを踏まえ、こっこに親しみやすく短く('〜のだ'口調で)問いかけて。今日やったこと・"
        "どうだったか・過去問をやったならその出来、を1〜2問だけ聞く。長くしない(120字以内)。"
    )
    try:
        resp = await llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": SYSTEM_INSTRUCTION},
                      {"role": "user", "content": prompt}])
        opening = resp.choices[0].message.content or ""
    except Exception:
        opening = ""
    opening = opening or "今日はどうだったのだ? やったこと・気づき・過去問の出来を聞かせてほしいのだ!"
    await ch.send("📔 " + opening)


@tasks.loop(hours=24)
async def evening_reflection():
    ch = bot.get_channel(CHANNEL_CHAT or CHANNEL_NOTIFY)
    if ch:
        await start_diary(ch)


@evening_reflection.before_loop
async def before_reflection():
    await bot.wait_until_ready()
    from asyncio import sleep
    from datetime import timedelta
    now = datetime.now()
    target = now.replace(hour=EVENING_REFLECT_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    await sleep((target - now).total_seconds())

# ---- コマンド ----
# ---- スラッシュコマンド(/) ----
# `!`プレフィックスは覚えにくいので、入力時に候補が出るスラッシュコマンドに統一。
# 承認は絵文字リアクションでなくボタンUI(discordネイティブで分かりやすい)。

class ConfirmView(discord.ui.View):
    """✅登録する / ❌中止 のボタン。押せるのは本人のみ。押下後はボタンを無効化する。"""

    def __init__(self, author_id: int, on_confirm):
        super().__init__(timeout=CONFIRM_TIMEOUT_SEC)
        self.author_id = author_id
        self.on_confirm = on_confirm

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("これはあなた宛ての確認ではありません。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="登録する", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)
        await self.on_confirm(interaction)
        self.stop()

    @discord.ui.button(label="中止", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(content="中止しました。", view=self)
        self.stop()


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


@bot.tree.command(name="status", description="サーバーの状態(保存領域・モード・時刻)を表示")
async def status_slash(interaction: discord.Interaction):
    import shutil
    disk = shutil.disk_usage(CONTEXT_DIR) if CONTEXT_DIR.exists() else None
    msg = "**サーバー状態**\n"
    if disk:
        msg += (f"・保存領域(会話履歴等): {disk.used/1024**3:.1f} GB / "
                f"{disk.total/1024**3:.1f} GB ({disk.used/disk.total*100:.1f}%)\n")
    msg += f"・エージェントモード: {'有効' if DISCORD_OWNER_ID else '無効(DISCORD_OWNER_ID未設定)'}\n"
    msg += f"・現在時刻: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    await interaction.response.send_message(msg)


@bot.tree.command(name="health", description="内部サービスの死活を1つずつ確認する(読み取り専用)")
async def health_slash(interaction: discord.Interaction):
    await interaction.response.send_message("**ヘルスチェック開始**\n(各サービスに順番にアクセスします)")
    msg = await interaction.original_response()
    lines = []
    async with aiohttp.ClientSession() as session:
        for name, url in HEALTH_TARGETS:
            ok, detail = await _ping(session, url)
            lines.append(f"{'🟢' if ok else '🔴'} {name}: {detail}")
            await msg.edit(content="**ヘルスチェック**\n" + "\n".join(lines))


@bot.tree.command(name="clear", description="ワニ博士との会話履歴をリセットする")
async def clear_slash(interaction: discord.Interaction):
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    await interaction.response.send_message("会話履歴をリセットしました。")


@bot.tree.command(name="plan", description="今日のおすすめ(締切・時間割・創出タスク)を表示")
async def plan_slash(interaction: discord.Interaction):
    plan = load_daily_plan_raw()
    if not plan:
        await interaction.response.send_message("今日のプランがまだありません(夜間4時に生成されます)。")
        return
    await interaction.response.send_message(f"📋 **今日の作戦**\n{format_plan_full(plan)}"[:2000])


@bot.tree.command(name="diary", description="今日の振り返り(日記)を始める。達成状況を見て質問される")
async def diary_slash(interaction: discord.Interaction):
    await interaction.response.send_message("📔 今日の振り返りをはじめるのだ!")
    await start_diary(interaction.channel)


@bot.tree.command(name="todos", description="今日の創出タスクをGoogle ToDoに登録(ワニ博士アプリで討伐)")
async def todos_slash(interaction: discord.Interaction):
    if DISCORD_OWNER_ID and interaction.user.id != DISCORD_OWNER_ID:
        await interaction.response.send_message("owner限定のコマンドです。", ephemeral=True)
        return
    plan = load_daily_plan_raw()
    if not plan:
        await interaction.response.send_message("今日のプランがまだありません(夜間4時に生成されます)。")
        return
    items = build_todo_items(plan)
    if not items:
        await interaction.response.send_message("登録できる創出タスクがありません(繁忙期で0件など)。")
        return
    preview = "\n".join(f"・{it['title']}" + (f"（{it['notes']}）" if it.get("notes") else "")
                        for it in items)

    async def do_register(inter: discord.Interaction):
        ok_n, total = await write_todos(items)
        await inter.followup.send(
            f"Google ToDoに{ok_n}/{total}件登録しました。ワニ博士アプリで討伐しよう！")

    await interaction.response.send_message(
        f"📝 以下をGoogle ToDoに登録します(ワニ博士アプリで討伐可):\n{preview}",
        view=ConfirmView(interaction.user.id, do_register))


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
