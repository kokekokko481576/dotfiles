"""
ワニ博士タスク管理API + PWA配信。

- GET  /api/state                     : 気分・タスク一覧・進捗のスナップショット
- POST /api/tasks/{item_id}/status    : タスクのStatus更新(気分にも反映)
- GET  /healthz                       : 死活監視
- /                                   : PWA(static/)配信

利用者はPWA(スマホ)とbutler-bot(Discord)の2経路だが、状態は全部ここに集約する。
どちらから進捗を更新してもワニ博士の気分が同じように変わる。
"""
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
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


@app.middleware("http")
async def no_cache(request, call_next):
    """Cache-Control無しだとブラウザが推測キャッシュ(Last-Modified経過の10%)で
    古いUIを使い続け、デプロイが端末に届かない。no-cacheで毎回再検証させる
    (ETagがあるので実体は304で軽い)。"""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-cache")
    return response

STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))

# n8nの「毎朝ブリーフィング_今日の予定取得」Webhook(butler-botと同じもの)。
# 冒険モードで「予定の時間になったら敵として割り込む」ために使う
N8N_TODAY_SCHEDULE_URL = os.environ.get(
    "N8N_TODAY_SCHEDULE_URL", "http://n8n:5678/webhook/today-schedule")
# Google ToDo(Google Tasks)。n8nの「ワニ博士_ToDo取得/完了」ワークフロー経由
N8N_TODOS_URL = os.environ.get("N8N_TODOS_URL", "http://n8n:5678/webhook/todos")
N8N_TODO_COMPLETE_URL = os.environ.get(
    "N8N_TODO_COMPLETE_URL", "http://n8n:5678/webhook/todo-complete")
EVENTS_CACHE_TTL = 300

# 朝の作戦会議のレコメンド用LLM(LiteLLM経由のGemini、butler-botと同じ経路)。
# キー未設定なら簡易ヒューリスティックにフォールバックする
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://litellm:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash-vertex")

_events_lock = threading.Lock()
_events_cache: list | None = None
_events_at = 0.0


def fetch_today_events() -> list[dict]:
    """今日のGoogleカレンダー予定を{title, start, end, all_day}に正規化して返す。"""
    global _events_cache, _events_at
    with _events_lock:
        if _events_cache is not None and time.time() - _events_at < EVENTS_CACHE_TTL:
            return _events_cache
    events = []
    try:
        resp = requests.get(N8N_TODAY_SCHEDULE_URL, timeout=10)
        resp.raise_for_status()
        for e in resp.json() or []:
            start = e.get("start", {})
            end = e.get("end", {})
            events.append({
                "title": e.get("summary", "(無題)"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "all_day": "dateTime" not in start,
            })
        events.sort(key=lambda e: e["start"] or "")
    except Exception as e:
        log.warning("カレンダー取得に失敗(予定なし扱い): %s", e)
        events = []
    with _events_lock:
        _events_cache = events
        _events_at = time.time()
    return events


class StatusUpdate(BaseModel):
    status: str


class TaskCreate(BaseModel):
    title: str


class TaskMove(BaseModel):
    after_item_id: str | None = None  # Noneなら先頭へ


class TaskDue(BaseModel):
    due: str | None = None  # "YYYY-MM-DD" | null(クリア)


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


def _snapshot(fresh: bool = False) -> dict:
    now = datetime.now()
    state = mood.apply_decay(store.load_state(), now)
    store.save_state(state)
    try:
        tasks = source.list_tasks(force_refresh=fresh)
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
        "events": fetch_today_events(),
        "todos": _todos_view(now),
        "today": store.load_today(now.strftime("%Y-%m-%d")),
        "now": now.isoformat(),
    }


# ---- Google ToDo(Google Tasks) ----
_todos_lock = threading.Lock()
_todos_cache: list | None = None
_todos_at = 0.0


def fetch_todos(fresh: bool = False) -> list[dict]:
    """未完了のGoogle ToDoを{id, title, due, notes}に正規化して返す。

    モックモード(GitHub未設定)はローカルJSON。n8n側ワークフロー未作成でも
    空リストで劣化動作する。
    """
    global _todos_cache, _todos_at
    if source.mock:
        return store.load_mock_todos()
    with _todos_lock:
        if not fresh and _todos_cache is not None and time.time() - _todos_at < EVENTS_CACHE_TTL:
            return _todos_cache
    todos = []
    try:
        resp = requests.get(N8N_TODOS_URL, timeout=10)
        resp.raise_for_status()
        body = resp.json() or []
        if isinstance(body, dict):
            body = [body]
        for t in body:
            due = t.get("due")
            todos.append({
                "id": t.get("id"),
                "title": t.get("title", "(無題)"),
                "due": due[:10] if due else None,  # RFC3339 → YYYY-MM-DD
                "notes": t.get("notes", ""),
            })
    except Exception as e:
        log.warning("ToDo取得に失敗(ToDoなし扱い): %s", e)
        todos = []
    with _todos_lock:
        _todos_cache = todos
        _todos_at = time.time()
    return todos


def _todos_view(now: datetime) -> list[dict]:
    """フロント向け: forced(期限が今日以前=問答無用でその日にやる)を付与。"""
    today_str = now.strftime("%Y-%m-%d")
    out = []
    for t in fetch_todos():
        out.append({**t, "forced": bool(t["due"]) and t["due"] <= today_str})
    return out


@app.post("/api/todos/{todo_id}/complete")
def complete_todo(todo_id: str):
    """Google ToDoを完了にする(=モンスター討伐)。気分+18、討伐数に記録。"""
    global _todos_at
    now = datetime.now()
    if source.mock:
        todos = store.load_mock_todos()
        if not any(t["id"] == todo_id for t in todos):
            raise HTTPException(status_code=404, detail="ToDoが見つかりません")
        store.save_mock_todos([t for t in todos if t["id"] != todo_id])
    else:
        try:
            resp = requests.post(N8N_TODO_COMPLETE_URL, json={"taskId": todo_id}, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            log.exception("ToDo完了の書き戻しに失敗")
            raise HTTPException(status_code=502, detail=f"Google側の更新に失敗: {e}")
        with _todos_lock:
            _todos_at = 0.0  # キャッシュ破棄

    today = store.load_today(now.strftime("%Y-%m-%d"))
    if todo_id not in today["done_todos"]:
        today["done_todos"].append(todo_id)
        store.save_today(today)

    state = mood.apply_event(store.load_state(), "done", now)
    store.save_state(state)
    return {"ok": True, "event": "done", "mood": mood.summary(state, now)}


# ---- 朝の作戦会議(今日やるリスト) ----

EXCLUDED_FROM_TODAY = EXCLUDED_FROM_PROGRESS | {"done"}


def _active_tasks(tasks):
    return [t for t in tasks
            if (t.get("status") or "").casefold() not in EXCLUDED_FROM_TODAY]


def _heuristic_recommend(active: list[dict]) -> dict:
    picks = [{"item_id": t["item_id"], "reason": "隊列の前のほうにいたので"}
             for t in active[:3]]
    return {"picks": picks, "comment": "(LLM未設定のため先頭から選びました)"}


def _llm_recommend(active: list[dict], events: list[dict], now: datetime) -> dict:
    task_lines = "\n".join(
        f"- item_id={t['item_id']} #{t['number'] or 'メモ'} [{t['status']}] "
        f"{t['title']} (repo: {t['repo'] or 'なし'})"
        for t in active)
    event_lines = "\n".join(
        f"- {'終日' if e['all_day'] else (e['start'] or '')[11:16]} {e['title']}"
        for e in events) or "(予定なし)"
    weekday = "月火水木金土日"[now.weekday()]
    prompt = (
        f"今日は{now.strftime('%m月%d日')}({weekday}曜日)。\n"
        f"## 今日の予定\n{event_lines}\n\n## タスク一覧\n{task_lines}\n\n"
        "この人が今日やるタスクを2〜4件選んでください。予定の空き時間との相性、"
        "着手済み(In Progress/Review)の完遂優先、作業の重さのバランスを考慮すること。\n"
        "次のJSONだけを出力: {\"picks\": [{\"item_id\": \"...\", \"reason\": \"20字以内\"}], "
        "\"comment\": \"全体への励まし一言(40字以内)\"}"
    )
    resp = requests.post(
        f"{LITELLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=45,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    valid_ids = {t["item_id"] for t in active}
    picks = [p for p in data.get("picks", []) if p.get("item_id") in valid_ids][:4]
    if not picks:
        raise ValueError("LLMの提案が空")
    return {"picks": picks, "comment": str(data.get("comment", ""))[:60]}


@app.post("/api/today/recommend")
def recommend_today():
    """Geminiが今日やるタスクを提案する(保存はしない)。"""
    now = datetime.now()
    try:
        tasks = source.list_tasks()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    active = _active_tasks(tasks)
    # 期限なしのGoogle ToDoも候補に含める(期限付きはforcedで自動出撃するため除外)
    active += [{"item_id": f"todo:{t['id']}", "number": None, "title": t["title"],
                "status": "ToDo", "repo": "GoogleToDo"}
               for t in fetch_todos() if not t["due"]]
    if not active:
        return {"picks": [], "comment": "アクティブなタスクがありません"}
    if not LITELLM_MASTER_KEY:
        return _heuristic_recommend(active)
    try:
        return _llm_recommend(active, fetch_today_events(), now)
    except Exception as e:
        log.warning("LLMレコメンド失敗、ヒューリスティックで代替: %s", e)
        result = _heuristic_recommend(active)
        result["comment"] = f"(Gemini提案に失敗したので先頭から: {e})"[:80]
        return result


class TodayUpdate(BaseModel):
    item_ids: list[str]


@app.post("/api/today")
def set_today(body: TodayUpdate):
    """今日やるリストを保存(承認)する。GitHubのitem_idと todo:<id> が混在できる。"""
    now = datetime.now()
    try:
        valid_ids = {t["item_id"] for t in source.list_tasks()}
        valid_ids |= {f"todo:{t['id']}" for t in fetch_todos()}
    except Exception:
        valid_ids = None  # 外部不調時は検証スキップ(リスト自体はローカル保存)
    item_ids = [i for i in body.item_ids if valid_ids is None or i in valid_ids]
    prev = store.load_today(now.strftime("%Y-%m-%d"))
    data = {"date": now.strftime("%Y-%m-%d"), "item_ids": item_ids,
            "approved": True, "done_todos": prev.get("done_todos", [])}
    store.save_today(data)
    return {"ok": True, "today": data}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/.well-known/assetlinks.json")
def assetlinks():
    """TWA(Androidアプリ)のDigital Asset Links。
    APKビルド時に生成される署名証明書のフィンガープリント入りJSONを
    DATA_DIR/twa/assetlinks.json から配信する(guide/14参照)。"""
    path = DATA_DIR / "twa" / "assetlinks.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="assetlinks.json未生成")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/state")
def get_state(fresh: bool = False):
    """fresh=1でGitHub側の60秒キャッシュも飛ばして取り直す(手動更新ボタン用)。"""
    return _snapshot(fresh=fresh)


@app.post("/api/tasks")
def create_task(body: TaskCreate):
    """タスク(Draft item)を追加する。PWAの+ボタンとbutler-botのcreate_taskが使う。"""
    try:
        result = source.create_task(body.title)
    except Exception as e:
        log.exception("タスク追加に失敗")
        raise HTTPException(status_code=502, detail=str(e))
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/tasks/{item_id}/move")
def move_task(item_id: str, body: TaskMove):
    """タスクの並び順を変更する(GitHub Projectの手動並び順にも反映)。"""
    try:
        result = source.move_item(item_id, body.after_item_id)
    except Exception as e:
        log.exception("並び替えに失敗")
        raise HTTPException(status_code=502, detail=str(e))
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/tasks/{item_id}/due")
def update_due(item_id: str, body: TaskDue):
    """期限(Projectの日付フィールド)を設定・クリアする。"""
    if body.due is not None:
        try:
            datetime.strptime(body.due, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="dueはYYYY-MM-DD形式で指定してください")
    try:
        result = source.update_due(item_id, body.due)
    except Exception as e:
        log.exception("期限の更新に失敗")
        raise HTTPException(status_code=502, detail=str(e))
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


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


# ユーザーがローカルに置いた画像(例: 公式ワニ博士のwani.png)の配信。
# リポジトリには含めず、/mnt/data/ai/wani/assets/ に置いたものだけが使われる
ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# 最後にマウント(APIパスを食わないように)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
