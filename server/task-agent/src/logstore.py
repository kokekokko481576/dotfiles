"""
やり取りの生ログ・日次状態の保存。

LLM呼び出しをOllama（自宅サーバー内）にしたことで処理全体が自宅サーバー内で完結するため、
クラウド(Firestore等)は使わずローカルファイル(DATA_DIR配下、1日1ファイルのJSON)に保存する。
docker-compose上は/mnt/data/ai/task-agentがマウントされ、restic日次バックアップの対象範囲内
（guide/10_バックアップ.md）。
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config

log = logging.getLogger(__name__)

_DATA_DIR = Path(config.DATA_DIR)
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def today_doc_id() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d")


def _path(doc_id: str) -> Path:
    return _DATA_DIR / f"{doc_id}.json"


def _write(doc_id: str, data: dict) -> None:
    """一時ファイルに書いてからrenameする（processが途中でkillされても本ファイルが
    壊れたJSON状態になるのを防ぐ。同一ファイルシステム上のrenameはatomic）。"""
    path = _path(doc_id)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def save_recommendation(doc_id: str, *, channel_id: str, message_id: str, thread_id: str,
                         issues: list[dict], llm_result: dict) -> None:
    _write(
        doc_id,
        {
            "date": doc_id,
            "created_at": datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(),
            "channel_id": channel_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "issues": issues,
            "recommendation": llm_result,
        },
    )
    log.info("レコメンドログを保存: %s", _path(doc_id))


def get_recommendation(doc_id: str) -> dict | None:
    path = _path(doc_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.error("%s が壊れたJSONです。存在しないものとして扱います。", path)
        return None


def save_collection_result(doc_id: str, *, replies: list[dict], parsed_updates: list[dict],
                            update_results: list[dict]) -> None:
    data = get_recommendation(doc_id) or {"date": doc_id}
    data["collected_at"] = datetime.now(ZoneInfo(config.TIMEZONE)).isoformat()
    data["replies"] = replies
    data["parsed_updates"] = parsed_updates
    data["update_results"] = update_results
    _write(doc_id, data)
    log.info("収集結果を追記: %s", _path(doc_id))
