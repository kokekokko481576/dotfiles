"""
Job B（毎晩実行）: 当日Job Aが立てたDiscordスレッドの返信を回収し、Ollama(llama3.2:3b)で
返信ごとにパースしてGitHub ProjectのStatusフィールドを更新する。やり取りの生ログをローカルに
追記する。
"""
import logging
import sys

import logstore
from discord_client import DiscordClient
from github_client import GithubProjectClient
from llm_client import parse_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _same_issue(a, b) -> bool:
    """issue番号の比較。Ollamaが文字列("123")で返しても一致させる。"""
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return False


def main() -> int:
    doc_id = logstore.today_doc_id()
    record = logstore.get_recommendation(doc_id)
    if record is None:
        log.warning("本日(%s)のレコメンドログが見つかりません。job_recommendが未実行の可能性があります。", doc_id)
        return 0

    discord = DiscordClient()
    replies = discord.fetch_replies(record["thread_id"])
    if not replies:
        log.info("本日(%s)のスレッドに返信はありませんでした。", doc_id)
        logstore.save_collection_result(doc_id, replies=[], parsed_updates=[], update_results=[])
        return 0

    github = GithubProjectClient()
    github.fetch_open_items()  # project_id / status_field_id / status_optionsを取得するために呼ぶ
    status_options = list(github.status_options)
    issues = record.get("issues", [])

    parsed_updates = []
    update_results = []
    for reply in replies:
        try:
            parsed = parse_reply(issues, status_options, reply["content"])
        except Exception:
            log.exception("返信のパースに失敗、スキップ: %s", reply["content"])
            continue
        parsed_updates.append(parsed)

        if not parsed.get("matched"):
            continue

        target = next(
            (
                it
                for it in issues
                if it["repo"] == parsed.get("repo") and _same_issue(it["number"], parsed.get("number"))
            ),
            None,
        )
        if target is None:
            log.warning("パース結果のissueが本日の一覧に見つかりません: %s", parsed)
            update_results.append({**parsed, "applied": False, "reason": "issue not found"})
            continue

        try:
            applied = github.update_status(target["item_id"], parsed.get("status", ""))
        except Exception:
            log.exception("Status更新に失敗、この件はスキップして続行: %s", parsed)
            applied = False
        update_results.append({**parsed, "applied": applied})

    logstore.save_collection_result(
        doc_id, replies=replies, parsed_updates=parsed_updates, update_results=update_results
    )
    log.info(
        "返信%d件を回収、%d件のStatus更新を適用",
        len(replies),
        sum(1 for r in update_results if r["applied"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
