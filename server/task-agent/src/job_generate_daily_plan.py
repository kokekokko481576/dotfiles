# coding: utf-8
"""
ワニ博士アプリ（Wani）向けに、1日の推奨タスクを生成するジョブ。
夜間に実行され、ローカルLLM(Ollama)を使って結果を生成し、
/app/data/daily_plan.json に保存する。
"""

import logging
import os
import sys
import json
from datetime import datetime, timezone

# logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# srcディレクトリのパスをsys.pathに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from github_client import GithubProjectClient
from llm_client import generate_daily_plan

def main() -> int:
    """メイン処理"""
    log.info("日次計画生成ジョブを開始します。")

    # `docker-compose.yml`でマウントされる想定のパス
    output_dir = "/app/data"
    output_file = os.path.join(output_dir, "daily_plan.json")

    # 出力先ディレクトリがなければ作成
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log.info(f"出力先ディレクトリを作成しました: {output_dir}")

    try:
        # 1. コンテキスト情報を収集する
        log.info("GitHubからオープンなIssueを取得します...")
        github = GithubProjectClient()
        github_items = github.fetch_open_items()

        # TODO: カレンダー連携モジュールから予定を取得する
        calendar_events = []

        log.info("ローカルLLMを呼び出して日次計画を生成します...")
        # 2. LLMを呼び出して計画を生成
        daily_plan = generate_daily_plan(
            github_items=github_items,
            calendar_events=calendar_events
        )

        # 3. 生成日時の情報を付与
        daily_plan["generated_at"] = datetime.now(timezone.utc).isoformat()

        # 4. JSONファイルとして保存
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(daily_plan, f, ensure_ascii=False, indent=2)

        log.info(f"日次計画をファイルに保存しました: {output_file}")

    except Exception as e:
        log.error(f"日次計画の生成中にエラーが発生しました: {e}", exc_info=True)
        return 1

    log.info("日次計画生成ジョブが正常に完了しました。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
