"""
Job A（毎朝実行）: GitHub Projectのopen issueを取得し、Ollama(llama3.2:3b)でレコメンドを
生成してDiscordに投稿する。スレッドを立てて夜のJob B（job_collect.py）が返信を回収できる
ようにする。
"""
import logging
import sys

import config
import logstore
from discord_client import DiscordClient
from github_client import GithubProjectClient
from llm_client import generate_recommendation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    doc_id = logstore.today_doc_id()

    github = GithubProjectClient()
    items = github.fetch_open_items()

    llm_result = generate_recommendation(items)
    discord_message = llm_result.get("discord_message")
    if not discord_message:
        log.error("Ollamaがdiscord_messageを返しませんでした: %s", llm_result)
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
    log.info("レコメンド投稿完了: %d件のissueを提示 (thread=%s)", len(items), thread_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
