"""
ローカル状態(気分・日次履歴・モックタスク)のJSON保存。

保存先はdocker-composeで/mnt/data/ai/waniがマウントされる/app/data。
GitHub Projectが「タスクの正」で、ここには気分などGitHubに置けない状態だけを持つ。
"""
import json
import os
import threading
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
STATE_FILE = DATA_DIR / "wani_state.json"
MOCK_TASKS_FILE = DATA_DIR / "mock_tasks.json"

_lock = threading.Lock()

_DEFAULT_STATE = {
    "mood": 50.0,
    "updated_at": None,   # 最後に気分を計算したISO時刻
    "streak": 0,          # 1件以上Doneにした連続日数
    "last_done_date": None,
    "history": {},        # "YYYY-MM-DD" -> {"done": n, "started": n}
}

# GitHub未設定時に使うモックタスク。実物と同じ形にしておくことで、
# フロント・butler-botからはモックか本物かを意識せずに扱える。
_DEFAULT_MOCK_TASKS = [
    {"item_id": "mock-1", "number": 1, "title": "ワニ博士アプリのUIを確認する",
     "url": "", "repo": "mock/personal-tasks", "labels": ["dev"], "status": "Todo", "draft": False},
    {"item_id": "mock-2", "number": 2, "title": "GitHub PATを設定して本物のProjectに切り替える",
     "url": "", "repo": "mock/personal-tasks", "labels": ["setup"], "status": "Todo", "draft": False},
    {"item_id": "mock-3", "number": 3, "title": "研究ノートを1ページ書く",
     "url": "", "repo": "mock/personal-tasks", "labels": ["research"], "status": "In Progress", "draft": False},
    {"item_id": "mock-4", "number": 4, "title": "Discordから進捗更新を試す",
     "url": "", "repo": "mock/personal-tasks", "labels": ["dev"], "status": "Todo", "draft": False},
    {"item_id": "mock-5", "number": 5, "title": "共同研究の返信待ち",
     "url": "", "repo": "mock/personal-tasks", "labels": [], "status": "waiting", "draft": False},
    {"item_id": "mock-6", "number": None, "title": "いつかやる: 3Dプリンタのファーム更新",
     "url": "", "repo": "", "labels": [], "status": "wish list", "draft": True},
]


def _load(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return json.loads(json.dumps(default))


def _save(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_state() -> dict:
    with _lock:
        state = _load(STATE_FILE, _DEFAULT_STATE)
        # 追加フィールドが増えたときも既存ファイルを壊さない
        for k, v in _DEFAULT_STATE.items():
            state.setdefault(k, v)
        return state


def save_state(state: dict) -> None:
    with _lock:
        _save(STATE_FILE, state)


def load_mock_tasks() -> list[dict]:
    with _lock:
        tasks = _load(MOCK_TASKS_FILE, _DEFAULT_MOCK_TASKS)
        if not MOCK_TASKS_FILE.exists():
            _save(MOCK_TASKS_FILE, tasks)
        return tasks


def save_mock_tasks(tasks: list[dict]) -> None:
    with _lock:
        _save(MOCK_TASKS_FILE, tasks)
