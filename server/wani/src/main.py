"""
ワニ博士タスク管理API + PWA配信。

- GET  /api/state                     : 気分・タスク一覧・進捗のスナップショット
- POST /api/tasks/{item_id}/status    : タスクのStatus更新(気分にも反映)
- GET  /healthz                       : 死活監視
- /                                   : PWA(static/)配信

利用者はPWA(スマホ)とbutler-bot(Discord)の2経路だが、状態は全部ここに集約する。
どちらから進捗を更新してもワニ博士の気分が同じように変わる。
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

import github_tasks
import mood
import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="wani-api")
source = github_tasks.TaskSource()

STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))


class StatusUpdate(BaseModel):
    status: str


# 進捗の分母から外すStatus。waitingは他人待ち、wish listは後回しBOX(ユーザー命名)で
# どちらも「今日の頑張り」の対象ではないため、ワニ博士の進捗バーには含めない。
EXCLUDED_FROM_PROGRESS = {"waiting", "wish list"}


def _progress(tasks: list[dict]) -> dict:
    scoped = [t for t in tasks
              if (t.get("status") or "").casefold() not in EXCLUDED_FROM_PROGRESS]
    done = sum(1 for t in scoped if (t.get("status") or "").casefold() == "done")
    total = len(scoped)
    return {
        "done": done,
        "total": total,
        "percent": round(done * 100 / total) if total else 0,
    }


def _snapshot() -> dict:
    now = datetime.now()
    state = mood.apply_decay(store.load_state(), now)
    store.save_state(state)
    try:
        tasks = source.list_tasks()
        statuses = source.status_names()
        error = None
    except Exception as e:
        log.exception("タスク取得に失敗")
        # GitHub側の失敗(権限不足・ネットワーク等)でもアプリ自体は動かし、
        # エラーバナーで理由を見せる
        tasks, statuses, error = [], github_tasks.MOCK_STATUSES, str(e)
    return {
        "mock": source.mock,
        "error": error,
        "mood": mood.summary(state, now),
        "progress": _progress(tasks),
        "tasks": tasks,
        "statuses": statuses,
        "now": now.isoformat(),
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/state")
def get_state():
    return _snapshot()


@app.post("/api/tasks/{item_id}/status")
def update_status(item_id: str, body: StatusUpdate):
    try:
        result = source.update_status(item_id, body.status)
    except Exception as e:
        log.exception("Status更新に失敗")
        raise HTTPException(status_code=502, detail=str(e))
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])

    old = (result["old_status"] or "").casefold()
    new = result["new_status"].casefold()
    event = None
    if new == "done" and old != "done":
        event = "done"
    elif old == "done" and new != "done":
        event = "undone"
    elif new in ("in progress", "review") and old not in ("in progress", "review"):
        event = "started"  # Reviewまで進めたのも「前進」として扱う

    now = datetime.now()
    state = store.load_state()
    if event:
        state = mood.apply_event(state, event, now)
    else:
        state = mood.apply_decay(state, now)
    store.save_state(state)

    return {
        "ok": True,
        "task": result["task"],
        "event": event,
        "mood": mood.summary(state, now),
    }


# 最後にマウント(APIパスを食わないように)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
