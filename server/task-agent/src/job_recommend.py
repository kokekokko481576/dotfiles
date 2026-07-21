"""
Job A（毎朝実行）: 夜間(4時)に daily-plan ジョブがGeminiで生成した当日の推奨プラン
(daily_plan.json)を読み込み、Discordに投稿する。スレッドを立てて夜のJob B
（job_collect.py）が返信を回収できるようにする。

以前は毎朝ここでOllama(llama3.2:3b)にissueを1件ずつ評価させて生成していたが、
夜間に1回Geminiで計算した結果をwani・Discordの両方が読むだけにして計算回数を節約する。
daily_plan.jsonが無い/当日分でない場合のみ、従来のOllama生成にフォールバックする。
"""
import json
import logging
import os
import sys
from pathlib import Path

import config
import logstore
from discord_client import DiscordClient
from github_client import GithubProjectClient
from llm_client import generate_recommendation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# 夜間daily-planが書く当日プラン。task-agent-recommendサービスは /mnt/data/ai/wani を
# /app/wani にread-onlyでマウントしている(docker-compose.yml)。
DAILY_PLAN_FILE = Path(os.environ.get("DAILY_PLAN_FILE", "/app/wani/daily_plan.json"))


def _load_daily_plan(doc_id: str) -> dict | None:
    """当日分のdaily_plan.jsonを読む。無い/当日分でないならNone。"""
    try:
        plan = json.loads(DAILY_PLAN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("daily_plan.json が読めません: %s", DAILY_PLAN_FILE)
        return None
    if plan.get("date") != doc_id:
        log.warning("daily_plan.json が当日(%s)分ではありません(date=%s)", doc_id, plan.get("date"))
        return None
    return plan


def _format_discord_message(plan: dict) -> str:
    """daily_plan.jsonのpicks/commentをDiscord投稿用Markdownに整形する。"""
    comment = (plan.get("comment") or "").strip()
    picks = plan.get("picks", [])
    lines = ["🐊 **今日のおすすめ**"]
    if comment:
        lines.append("")
        lines.append(comment)
    if picks:
        lines.append("")
        for p in picks:
            num = f"#{p['number']} " if p.get("number") else ""
            repo = f" `{p['repo']}`" if p.get("repo") else ""
            urg = f" (urgency {p['urgency']})" if p.get("urgency") is not None else ""
            lines.append(f"- **{num}{p.get('title', '(無題)')}**{repo}{urg}")
            if p.get("reason"):
                lines.append(f"  ↳ {p['reason']}")
    else:
        # 繁忙期(院試等)にGeminiが「今日はGitHubタスク0件」と判断したケース。
        # commentだけで完結させる(存在しないタスクをでっち上げない)。
        if not comment:
            lines.append("")
            lines.append("今日はおすすめタスクなし。ゆっくりいこう。")
    lines.append("")
    lines.append("_進捗があればこのスレッドに返信してね(夜にまとめてStatusへ反映します)_")
    return "\n".join(lines)


def main() -> int:
    doc_id = logstore.today_doc_id()

    github = GithubProjectClient()
    # issue一覧は夜のjob_collectが返信とissueを突き合わせるために保存が必要(LLMではなくAPI)。
    items = github.fetch_open_items()

    # 夜間にGeminiで作った当日プランを最優先で読む(計算を使い回す)
    plan = _load_daily_plan(doc_id)
    if plan is not None:
        discord_message = _format_discord_message(plan)
        llm_result = {"source": "daily_plan", "model": plan.get("model"),
                      "picks": plan.get("picks", []), "comment": plan.get("comment", ""),
                      "discord_message": discord_message}
        log.info("daily_plan.json(%s, %d件)を読み込んで投稿します", plan.get("model"),
                 len(plan.get("picks", [])))
    else:
        # フォールバック: 夜間プランが無い/壊れているときだけ、その場でOllama生成する
        log.info("当日のdaily_plan.jsonが無いため、Ollamaでその場生成します(フォールバック)")
        llm_result = generate_recommendation(items)
        llm_result.setdefault("source", "ollama_fallback")
        discord_message = llm_result.get("discord_message")
        if not discord_message:
            log.error("フォールバック生成もdiscord_messageを返しませんでした: %s", llm_result)
            return 1

    discord = DiscordClient()
    chunks = discord.split_chunks(discord_message)
    message = discord.post_message(config.DISCORD_CHANNEL_ID, chunks[0])
    thread_id = discord.start_thread(config.DISCORD_CHANNEL_ID, message["id"], f"{doc_id} タスク進捗")
    # 2000字を超えた分はスレッド作成後にスレッド内へ投稿する（チャンネル本体に漏れさせない）
    for chunk in chunks[1:]:
        discord.post_message(thread_id, chunk)

    logstore.save_recommendation(
        doc_id,
        channel_id=config.DISCORD_CHANNEL_ID,
        message_id=message["id"],
        thread_id=thread_id,
        issues=items,
        llm_result=llm_result,
    )
    log.info("レコメンド投稿完了: %d件のissueを提示 (thread=%s, source=%s)",
             len(items), thread_id, llm_result.get("source"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
