# coding: utf-8
"""
週次実行: 過去のレコメンド実績ログ(recommend_log.jsonl)を蒸留して、
この人の傾向を learned_prefs.md にまとめ直すジョブ。

learned_prefs.md は日次プラン生成(job_generate_daily_plan.py)とワニ博士アプリの
両方のレコメンドプロンプトに注入される。本人は履歴を振り返らない前提なので、
ログの価値は「レコメンドを本人へ寄せていく」ここだけにある。ローカル3Bの実モデル
再学習は非現実的なので、in-contextでの疑似ファインチューニングとして実装している。

ボリューム:
  /app/context = /mnt/data/ai/context  (feedback/recommend_log.jsonl, learned_prefs.md)
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from llm_client import distill_preferences

TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))
CONTEXT_DIR = os.environ.get("CONTEXT_DIR", "/app/context")
LOOKBACK_DAYS = int(os.environ.get("DISTILL_LOOKBACK_DAYS", "14"))


def _load_recent_records(path: str, since: str) -> list[dict]:
    """recommend_log.jsonl から since(YYYY-MM-DD)以降のレコードを読む。"""
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("date", "") >= since:
                    records.append(rec)
    except OSError:
        log.info("レコメンド実績ログが見つかりません: %s", path)
    return records


def main() -> int:
    log.info("学習メモ蒸留ジョブを開始します。")
    now = datetime.now(TZ)
    since = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    log_path = os.path.join(CONTEXT_DIR, "feedback", "recommend_log.jsonl")
    records = _load_recent_records(log_path, since)
    if not records:
        log.info("直近%d日のレコードが無いため、learned_prefs.mdは更新しません。", LOOKBACK_DAYS)
        return 0

    log.info("直近%d日で%d件のレコードを蒸留します...", LOOKBACK_DAYS, len(records))
    insights = distill_preferences(records)
    if not insights.strip():
        log.info("有意な傾向が抽出できなかったため、learned_prefs.mdは更新しません。")
        return 0

    header = (
        f"<!-- 自動生成: {now.isoformat()} / 直近{LOOKBACK_DAYS}日 {len(records)}件から蒸留 -->\n"
        f"# 学習したこの人の傾向\n\n"
    )
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    out = os.path.join(CONTEXT_DIR, "learned_prefs.md")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(header + insights + "\n")
    os.replace(tmp, out)

    log.info("learned_prefs.md を更新しました: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
