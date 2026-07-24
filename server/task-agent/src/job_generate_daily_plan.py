# coding: utf-8
"""
ワニ博士アプリ（Wani）向けに、1日の推奨タスクを生成するジョブ（毎朝4時に実行）。

- ローカルLLM(Ollama)で当日の推奨タスクを item_id 付きで生成し、
  /app/data/daily_plan.json (最新) と /app/data/daily_plan/<date>.json (履歴) に保存する。
  Waniアプリはこの daily_plan.json を「朝の作戦会議」でそのまま読んで表示する。
- 生成の前に、前日の「提案 vs 実際に承認・完了したか」を突き合わせて
  /app/context/feedback/recommend_log.jsonl に1行追記する。
  週次の蒸留ジョブ(job_distill_prefs.py)がこのログから learned_prefs.md を作り、
  以降のレコメンドに反映する = 履歴を使ったin-contextな自己強化ループ。

ボリューム:
  /app/data    = /mnt/data/ai/wani     (waniアプリと共有: daily_plan.json, today.json, wani_state.json)
  /app/context = /mnt/data/ai/context  (major_events, feedback/, learned_prefs.md)
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# srcディレクトリのパスをsys.pathに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from github_client import GithubProjectClient
from llm_client import generate_daily_plan

TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
CONTEXT_DIR = os.environ.get("CONTEXT_DIR", "/app/context")
# 今日のGoogleカレンダー予定(butler-botと同じn8n Webhook)。空き時間の時間割生成に使う。
N8N_TODAY_SCHEDULE_URL = os.environ.get(
    "N8N_TODAY_SCHEDULE_URL", "http://n8n:5678/webhook/today-schedule")
# 未完了のGoogle ToDo。既にある「やること」を時間割に組み込む/重複生成しないために渡す。
N8N_TODOS_URL = os.environ.get("N8N_TODOS_URL", "http://n8n:5678/webhook/todos")
# 未完了ToDoの削除(討伐しきれず繰り越した自動生成ToDoを毎朝消して溜めないため)。
N8N_TODO_DELETE_URL = os.environ.get("N8N_TODO_DELETE_URL", "http://n8n:5678/webhook/todo-delete")

# 執事Bot(ai/src/bot.py)が自動生成ToDoの notes 末尾に付けるマーカー。これが付いた未完了ToDoは
# 「前日以前に討伐しきれなかった自動タスク」なので、翌朝の再編時に削除して繰り越し候補として
# 作り直す。手動で自分が追加したToDoには付かないので消さない。★bot.py側と文字列一致必須。
AUTO_TODO_MARKER = "#wani-auto"


def _fetch_today_events() -> list:
    """今日の固定予定を取得する。失敗しても計画生成は続けたいので空リストで劣化。"""
    try:
        resp = requests.get(N8N_TODAY_SCHEDULE_URL, timeout=15)
        resp.raise_for_status()
        return resp.json() or []
    except Exception as e:
        log.warning("カレンダー取得に失敗(予定なし扱い): %s", e)
        return []


# 天気(Open-Meteo。APIキー不要・無料)。既定は阪大吹田キャンパス付近。env で上書き可。
WEATHER_LAT = os.environ.get("WEATHER_LAT", "34.82")
WEATHER_LON = os.environ.get("WEATHER_LON", "135.52")
_WMO = {0: "快晴", 1: "晴れ", 2: "晴れ時々曇り", 3: "曇り", 45: "霧", 48: "霧",
        51: "小雨", 53: "雨", 55: "強い雨", 61: "雨", 63: "雨", 65: "強い雨",
        71: "雪", 73: "雪", 75: "大雪", 80: "にわか雨", 81: "にわか雨", 82: "激しいにわか雨",
        95: "雷雨", 96: "雷雨", 99: "激しい雷雨"}


def _fetch_weather() -> dict | None:
    """今日の天気(降水確率・天気概況・気温)を取得する。失敗時はNone(天気なし扱い)。"""
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}"
               f"&longitude={WEATHER_LON}&daily=weather_code,precipitation_probability_max,"
               "temperature_2m_max,temperature_2m_min&timezone=Asia%2FTokyo&forecast_days=1")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        dj = resp.json()["daily"]
        code = dj["weather_code"][0]
        pop = dj["precipitation_probability_max"][0]
        rainy = (code is not None and code >= 51) or (pop is not None and pop >= 50)
        return {"desc": _WMO.get(code, "不明"), "pop": pop,
                "tmax": dj["temperature_2m_max"][0], "tmin": dj["temperature_2m_min"][0],
                "rainy": rainy}
    except Exception as e:
        log.warning("天気取得に失敗(天気なし扱い): %s", e)
        return None


def _fetch_todos() -> list:
    """未完了のGoogle ToDoを取得して{id,title,due,notes}に正規化する。失敗時は空。

    id は削除(自動生成ToDoの繰り越しクリア)に、notes は自動/手動の判別(AUTO_TODO_MARKER)に使う
    ので、ここでは notes を丸めない。"""
    try:
        resp = requests.get(N8N_TODOS_URL, timeout=15)
        resp.raise_for_status()
        body = resp.json() or []
        if isinstance(body, dict):
            body = [body]
        out = []
        for t in body:
            title = (t.get("title") or "").strip()
            if not title:
                continue
            due = t.get("due") or ""
            out.append({"id": t.get("id") or "", "title": title,
                        "due": due[:10], "notes": t.get("notes") or ""})
        return out
    except Exception as e:
        log.warning("ToDo取得に失敗(なし扱い): %s", e)
        return []


def _delete_todo(task_id: str) -> bool:
    """未完了のまま繰り越された自動生成ToDoをGoogle Tasksから削除する。失敗しても続行。"""
    if not task_id:
        return False
    try:
        resp = requests.post(N8N_TODO_DELETE_URL, json={"taskId": task_id}, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.warning("ToDo削除に失敗(%s): %s", task_id, e)
        return False


def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _record_yesterday_feedback(today_str: str) -> None:
    """前日の「提案」と「実際に承認・完了したか」を突き合わせてログに1行追記する。

    - 提案: daily_plan/<yesterday>.json の picks
    - 承認: today.json (approvedかつ日付が一致するときの item_ids)
    - 完了: wani_state.json の history[yesterday] (done/started の集計)
    週次蒸留(job_distill_prefs.py)の入力になる。
    """
    yesterday = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    plan = _read_json(os.path.join(DATA_DIR, "daily_plan", f"{yesterday}.json"), None)
    if not plan or not plan.get("picks"):
        log.info("前日(%s)のプランが無いためフィードバック記録をスキップ", yesterday)
        return

    today_state = _read_json(os.path.join(DATA_DIR, "today.json"), {})
    approved_ids = set(today_state.get("item_ids", [])) \
        if today_state.get("approved") and today_state.get("date") == yesterday else set()

    history = _read_json(os.path.join(DATA_DIR, "wani_state.json"), {}).get("history", {})
    outcome = history.get(yesterday, {"done": 0, "started": 0})

    recommended = [
        {"title": p.get("title"), "repo": p.get("repo"), "labels": p.get("labels", []),
         "urgency": p.get("urgency"), "reason": p.get("reason")}
        for p in plan["picks"]
    ]
    accepted_titles = [p.get("title") for p in plan["picks"] if p.get("item_id") in approved_ids]

    # 実際に完了したタスク(wani側がDone時にlabels/repo込みでスナップショットしたもの)。
    # これが「そのタスクが何にあたるか(院試勉強/研究/雑務/バイト…)」の分類材料になる。
    done_items = [
        {"title": d.get("title"), "repo": d.get("repo"), "labels": d.get("labels", [])}
        for d in outcome.get("done_items", [])
    ]
    done_ids = {d.get("item_id") for d in outcome.get("done_items", [])}
    completed_recommended = [p.get("title") for p in plan["picks"] if p.get("item_id") in done_ids]

    record = {
        "date": yesterday,
        "recommended": recommended,
        # accepted = 提案のうち本人が「今日やる」に入れたもの。
        # そもそも当日アプリで承認しなかった日は approved_ids が空になり、accepted も空。
        "accepted_titles": accepted_titles,
        "approved_at_all": bool(approved_ids),
        # completed = その日実際にDoneになったタスク全部(提案外も含む。labels/repo付き)。
        # completed_recommended = そのうち提案していたもの = レコメンド的中。
        "completed": done_items,
        "completed_recommended_titles": completed_recommended,
        "n_recommended": len(plan["picks"]),
        "n_accepted": len(accepted_titles),
        "n_completed": len(done_items),
        "outcome": {"done": outcome.get("done", 0), "started": outcome.get("started", 0)},
        "comment": plan.get("comment", ""),
    }

    feedback_dir = os.path.join(CONTEXT_DIR, "feedback")
    os.makedirs(feedback_dir, exist_ok=True)
    with open(os.path.join(feedback_dir, "recommend_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info("前日(%s)のフィードバックを記録しました (承認%d/%d件)",
             yesterday, record["n_accepted"], record["n_recommended"])


def main() -> int:
    """メイン処理"""
    log.info("日次計画生成ジョブを開始します。")

    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")

    os.makedirs(DATA_DIR, exist_ok=True)
    archive_dir = os.path.join(DATA_DIR, "daily_plan")
    os.makedirs(archive_dir, exist_ok=True)

    try:
        # 0. 前日分のフィードバックを記録(生成の失敗に巻き込まれないよう先に)
        try:
            _record_yesterday_feedback(today_str)
        except Exception:
            log.exception("前日フィードバックの記録に失敗しましたが、生成は続行します")

        # 1. コンテキスト情報を収集する
        log.info("GitHubからオープンなIssueを取得します...")
        github = GithubProjectClient()
        github_items = github.fetch_open_items()

        # 今日の固定予定(空き時間へのタスク配置に使う)
        calendar_events = _fetch_today_events()
        log.info("今日の固定予定を%d件取得", len(calendar_events))

        # 既存の未完了ToDoを取得し、自動生成の未達分と手動追加分に振り分ける。
        #   - 自動生成の未達(#wani-auto付き) = 昨日までに討伐しきれなかったもの。
        #     一旦削除して溜めず、「繰り越し候補」として今日のプランに現実的な分量で作り直させる。
        #   - 手動追加(マーカー無し) = 本人が自分で入れたToDo。消さずに時間割へ組み込む。
        raw_todos = _fetch_todos()
        carried_over = [t for t in raw_todos if AUTO_TODO_MARKER in (t.get("notes") or "")]
        existing_todos = [t for t in raw_todos if AUTO_TODO_MARKER not in (t.get("notes") or "")]
        deleted = sum(1 for t in carried_over if _delete_todo(t.get("id", "")))
        log.info("未完了ToDo: 手動%d件は保持 / 自動生成の未達%d件を削除(繰り越し候補, 削除成功%d件)",
                 len(existing_todos), len(carried_over), deleted)

        # 今日の天気(雨なら登校を多めに取る等の判断に使う)
        weather = _fetch_weather()
        log.info("天気: %s", weather)

        log.info("ローカルLLMを呼び出して日次計画を生成します...")
        # 2. LLMを呼び出して計画を生成 (picksはitem_id付き)
        daily_plan = generate_daily_plan(
            github_items=github_items,
            calendar_events=calendar_events,
            existing_todos=existing_todos,
            carried_over=carried_over,
            weather=weather,
        )

        # 3. メタ情報を付与(modelは実際に使われたものをgenerate_daily_planが返す)
        daily_plan["date"] = today_str
        daily_plan.setdefault("model", os.environ.get("OLLAMA_MODEL", "llama3.2:3b"))
        daily_plan["generated_at"] = now.isoformat()

        # 4. 最新(daily_plan.json) と 履歴(daily_plan/<date>.json) の両方に保存
        for out in (os.path.join(DATA_DIR, "daily_plan.json"),
                    os.path.join(archive_dir, f"{today_str}.json")):
            tmp = out + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(daily_plan, f, ensure_ascii=False, indent=2)
            os.replace(tmp, out)

        log.info("日次計画を保存しました (%s, picks=%d件)", today_str, len(daily_plan.get("picks", [])))

    except Exception as e:
        log.error(f"日次計画の生成中にエラーが発生しました: {e}", exc_info=True)
        return 1

    log.info("日次計画生成ジョブが正常に完了しました。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
