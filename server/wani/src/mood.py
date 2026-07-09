"""
たまごっち風の気分エンジン。

気分は0-100の連続値で、タスクの進捗イベントで上がり、時間経過で下がる。
- Done +18 / In Progress +6 / Doneから戻す -10
- 起きている時間帯(7時-24時)は1.5/時間で減衰、夜間(0時-7時)は減衰なし(睡眠)
- 表示レベル: excellent(>=75) / happy(>=45) / normal(>=20) / tired(<20)
- 夜間はレベルにかかわらずスプライトは睡眠(sleeping)扱い(フロント側で判定)

streak(連続日数)は「その日1件以上Doneにした」日が続いた数。気分とは独立に表示用。
"""
from datetime import datetime, timedelta

DECAY_PER_HOUR = 1.5
WAKE_HOUR = 7  # これより前は睡眠扱い(減衰なし)

EVENT_DELTA = {
    "done": 18.0,
    "started": 6.0,
    "undone": -10.0,
}

LEVELS = [
    (75, "excellent"),
    (45, "happy"),
    (20, "normal"),
    (0, "tired"),
]


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _awake_hours_between(start: datetime, end: datetime) -> float:
    """start→endのうち、起きている時間帯(7:00-24:00)に該当する時間数を返す。"""
    if end <= start:
        return 0.0
    total = 0.0
    cur = start
    while cur < end:
        next_hour = (cur + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        step_end = min(next_hour, end)
        if cur.hour >= WAKE_HOUR:
            total += (step_end - cur).total_seconds() / 3600
        cur = step_end
    return total


def apply_decay(state: dict, now: datetime) -> dict:
    """前回計算時刻からの減衰を気分に反映する。"""
    updated_at = state.get("updated_at")
    if updated_at:
        try:
            last = datetime.fromisoformat(updated_at)
            hours = _awake_hours_between(last, now)
            state["mood"] = _clamp(state["mood"] - hours * DECAY_PER_HOUR)
        except ValueError:
            pass
    state["updated_at"] = now.isoformat()
    return state


def apply_event(state: dict, event: str, now: datetime) -> dict:
    """進捗イベントを気分・履歴・streakに反映する。"""
    apply_decay(state, now)
    state["mood"] = _clamp(state["mood"] + EVENT_DELTA.get(event, 0.0))

    today = now.strftime("%Y-%m-%d")
    day = state["history"].setdefault(today, {"done": 0, "started": 0})
    if event == "done":
        day["done"] += 1
        last = state.get("last_done_date")
        if last != today:
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            state["streak"] = state.get("streak", 0) + 1 if last == yesterday else 1
            state["last_done_date"] = today
    elif event == "started":
        day["started"] += 1
    elif event == "undone":
        day["done"] = max(0, day["done"] - 1)

    # 履歴は直近60日分だけ保持
    if len(state["history"]) > 60:
        for key in sorted(state["history"])[:-60]:
            del state["history"][key]
    return state


def level(mood: float) -> str:
    for threshold, name in LEVELS:
        if mood >= threshold:
            return name
    return "tired"


def is_sleeping(now: datetime) -> bool:
    return now.hour < WAKE_HOUR


def summary(state: dict, now: datetime) -> dict:
    """フロント・Discord向けの気分サマリ。"""
    today = now.strftime("%Y-%m-%d")
    day = state["history"].get(today, {"done": 0, "started": 0})
    return {
        "mood": round(state["mood"], 1),
        "level": level(state["mood"]),
        "sleeping": is_sleeping(now),
        "streak": state.get("streak", 0),
        "today_done": day["done"],
        "today_started": day["started"],
    }
