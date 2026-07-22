"""
Ollama（自宅サーバー上のローカルLLM、llama3.2:3b）呼び出し。

定例タスクの優先度判断・返信パースは緊急性がないため、Vertex AI Geminiではなく
無料のローカルモデルを使う。3Bクラスの小型モデルは「一発で複雑な指示を全部やらせる」
より「1件ずつ個別に考えさせて、後でまとめる」方が安定した結果になりやすいため、
issue単位・返信単位に分解した逐次プロンプトにしている（時間はかかるが、定例バッチなので
問題ない）。
"""
import json
import logging
import os
import re
from pathlib import Path
import glob

import requests
from datetime import datetime, timedelta, date

import config

log = logging.getLogger(__name__)

_CHAT_URL = f"{config.OLLAMA_BASE_URL}/api/chat"

# 3Bot共通のユーザープロフィール/大日程(docker-composeで /app/profile.md にbind-mount)。
# まとめプロンプトに差し込み、大日程の締切等が優先度に効くようにする。未配置なら空文字。
_PROFILE_FILE = Path(os.environ.get("PROFILE_FILE", "/app/profile.md"))
try:
    PROFILE_TEXT = _PROFILE_FILE.read_text(encoding="utf-8").strip()
except OSError:
    PROFILE_TEXT = ""

# 主要イベントログ（docker-composeで /app/context/major_events にbind-mount）。
# 過去の文脈としてプロンプトに差し込む。
_MAJOR_EVENTS_DIR = Path("/app/context/major_events")

def _load_major_events() -> str:
    """直近＋これからのMajor Eventsログを読み込む (前月〜先2ヶ月)。

    レコメンドは締切ベースの優先付けなので「これから」の月(院試・論文締切など)こそ
    最重要。以前は現在月と前月だけを見ていたため、翌月以降のイベントが入らなかった。
    """
    if not _MAJOR_EVENTS_DIR.is_dir():
        log.info(f"Major Eventsディレクトリが見つかりません: {_MAJOR_EVENTS_DIR}")
        return ""

    all_events_text = []
    today = datetime.now()

    # 前月(-1)〜先2ヶ月(+2)のファイル名を月演算で正確に組み立てる
    target_filenames = set()
    for offset in (-1, 0, 1, 2):
        m = today.month + offset
        y = today.year + (m - 1) // 12
        mm = (m - 1) % 12 + 1
        target_filenames.add(f"{y}_{mm:02d}_major_events.md")

    log.info(f"Major Eventsの検索対象ファイル名パターン: {target_filenames}")

    # os.walk を使ってディレクトリを再帰的に走査
    for root, _, files in os.walk(_MAJOR_EVENTS_DIR):
        for file in files:
            if file in target_filenames:
                event_file_path = Path(root) / file
                try:
                    all_events_text.append(event_file_path.read_text(encoding="utf-8").strip())
                    log.info(f"Major Eventファイル {event_file_path} を読み込みました。")
                except OSError:
                    log.warning(f"Major Eventファイル {event_file_path} の読み込みに失敗しました。")

    if not all_events_text:
        log.info("読み込めるMajor Eventsファイルがありませんでした。")

    return "\n\n".join(all_events_text)

MAJOR_EVENTS_TEXT = _load_major_events()

# 週1の蒸留ジョブ(job_distill_prefs.py)が過去のレコメンド履歴から抽出した
# 「学習した好み・傾向」。プロンプトに差し込み、レコメンドを徐々に本人へ寄せる
# (ローカル3Bの実モデル再学習は非現実的なので、in-contextでの疑似ファインチューニング)。
_LEARNED_PREFS_FILE = Path(os.environ.get(
    "LEARNED_PREFS_FILE", "/app/context/learned_prefs.md"))


def _load_learned_prefs() -> str:
    """週次蒸留された学習メモを毎回読み直す(バッチなので都度読みで十分)。"""
    try:
        return _LEARNED_PREFS_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# 「GitHubのissueにはしないが管理対象」の領域(院試勉強・研究・バイト等)の進捗ステート。
# /mnt/data/ai/context/projects/*.md (git管理外)を読み、次にやるべき具体タスクの創出に使う。
_PROJECTS_DIR = Path(os.environ.get("PROJECTS_DIR", "/app/context/projects"))


def _load_projects() -> str:
    """projects/*.md を結合して返す(過去問分析・得点率・学習到達度・弱点など)。"""
    if not _PROJECTS_DIR.is_dir():
        return ""
    parts = []
    for p in sorted(_PROJECTS_DIR.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            parts.append(f"#### 領域: {p.stem}\n{text}")
    return "\n\n".join(parts)


def _chat_json(prompt: str) -> dict:
    resp = requests.post(
        _CHAT_URL,
        json={
            "model": config.OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        },
        timeout=180,
    )
    resp.raise_for_status()
    text = resp.json()["message"]["content"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.error("Ollamaの応答がJSONとして解釈できません: %s", text)
        raise


# ---- LiteLLM(Gemini) ----
# 判断が要るタスク(日次プランの選抜・学習メモの蒸留)は、指示追従の弱いllama3.2:3bでは
# プロフィールの「院試最優先」等のルールすら守れなかったため、butler-bot/waniと同じ
# LiteLLM経由のGeminiを主経路にする。1日1コール程度なので実質コストは無視できる。
# キー未設定/呼び出し失敗時はOllama(_chat_json)へ自動フォールバックする。
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://litellm:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash-vertex")


# 日次プランは picks+タスク創出+時間割 まで出させるので出力が大きく、litellmの既定
# request_timeout(30秒)では間に合わずタイムアウトする。per-requestで timeout を延ばす
# (litellmは body の timeout でグローバル設定を上書きできる)。
_JUDGE_TIMEOUT = int(os.environ.get("JUDGE_LLM_TIMEOUT", "90"))


def _gemini_chat_json(prompt: str) -> dict:
    resp = requests.post(
        f"{LITELLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "timeout": _JUDGE_TIMEOUT,  # litellmのrequest_timeout(30s)を上書き
        },
        timeout=_JUDGE_TIMEOUT + 15,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


# 直近の_judge_chat_jsonが実際に使ったモデル名(daily_plan.jsonのmodel欄に正しく残すため)
_last_judge_model: str | None = None


def _judge_chat_json(prompt: str) -> dict:
    """判断系タスク用: Gemini優先、キー未設定/失敗時はOllamaにフォールバック。"""
    global _last_judge_model
    if LITELLM_MASTER_KEY:
        try:
            data = _gemini_chat_json(prompt)
            _last_judge_model = LLM_MODEL
            return data
        except Exception:
            log.exception("Gemini呼び出しに失敗、Ollamaにフォールバックします")
    data = _chat_json(prompt)
    _last_judge_model = config.OLLAMA_MODEL
    return data


def _context_blocks() -> str:
    """プロフィール・大日程・学習メモをプロンプト冒頭に差し込むブロックを組み立てる。"""
    profile_block = f"""【あなたについて】
{PROFILE_TEXT}

""" if PROFILE_TEXT else ""
    major_block = f"""【大日程・主要イベント（これから来る締切含む。最優先で考慮）】
{MAJOR_EVENTS_TEXT}

""" if MAJOR_EVENTS_TEXT else ""
    prefs = _load_learned_prefs()
    learned_block = f"""【過去のレコメンド履歴から学習したこの人の傾向（できるだけ従う）】
{prefs}

""" if prefs else ""
    return profile_block + major_block + learned_block


def _score_issue(issue: dict) -> dict:
    """1件のissueについて優先度を評価する（issueごとに個別に考えさせる）。"""
    prompt = f"""あなたは個人のタスク管理アシスタントです。以下のGitHub issue 1件について、
今日着手すべき優先度を考えてください。焦らず、じっくり考えて構いません。

タイトル: {issue['title']}
リポジトリ: {issue['repo']}
ラベル: {', '.join(issue['labels']) or 'なし'}
現在のステータス: {issue['status'] or '未設定'}
本文(先頭500字): {issue['body'] or '(本文なし)'}

以下のJSON形式のみで出力してください（他のテキストは含めない）:
{{"urgency": 1から5の整数（5が最優先）, "reason": "40字程度の短い理由"}}
"""
    return _chat_json(prompt)


def generate_recommendation(items: list[dict]) -> dict:
    """
    issueを1件ずつ評価してから、まとめてDiscord投稿文を作る2段階構成。
    戻り値: {"discord_message": str, "highlighted_issues": [{"repo","number","reason"}]}
    """
    scored = []
    for item in items:
        try:
            score = _score_issue(item)
        except Exception:
            log.exception("issue %s#%s の評価に失敗、スキップ", item["repo"], item["number"])
            continue
        scored.append({**item, **score})

    scored.sort(key=lambda s: s.get("urgency", 0), reverse=True)
    scored_text = "\n".join(
        f"- [{s['repo']}#{s['number']}] {s['title']} "
        f"(urgency={s.get('urgency', '?')}, labels: {', '.join(s['labels']) or 'なし'}, "
        f"理由: {s.get('reason', '')})"
        for s in scored
    )
    profile_block = f"""【あなたについて】
{PROFILE_TEXT}

""" if PROFILE_TEXT else ""
    prompt = f"""{profile_block}以下は個別に優先度評価済みのissue一覧です（urgencyが高いほど優先度が高い）。

{scored_text or '(現在オープンなissueはありません)'}

上記のプロフィール・大日程を最優先で踏まえてください。もしプロフィールに院試・試験・
大きな締切前などの繁忙期が書かれていて今がその時期なら、これらのGitHubタスクは無理に
勧めず、「今は◯◯(その時期にやるべきこと)に集中を」と一言添えたうえで、緊急のものだけ
簡潔に挙げるに留めてください。繁忙期でなければ、締切が近いもの・所要時間や重さも考慮しつつ、
ラベル(research/personal/hobby:*)ごとにグルーピングし、urgencyが高いものを優先的に
紹介する形で、Discordにそのまま投稿できるMarkdown形式のメッセージ文にしてください。
全体は800字程度に収めてください。

以下のJSON形式のみで出力してください（他のテキストは含めない）:
{{"discord_message": "Discordに投稿するMarkdownテキスト"}}
"""
    result = _chat_json(prompt)
    result["highlighted_issues"] = [
        {"repo": s["repo"], "number": s["number"], "reason": s.get("reason", "")}
        for s in scored[:5]
    ]
    return result


def parse_reply(issues: list[dict], status_options: list[str], reply_text: str) -> dict:
    """
    1件のDiscord返信について、対応するissueとステータス変化を考える（返信ごとに個別処理）。
    戻り値: {"matched": bool, "repo": str, "number": int, "status": str, "note": str}
    """
    issues_text = "\n".join(f"- [{it['repo']}#{it['number']}] {it['title']}" for it in issues)
    prompt = f"""以下はGitHub issue一覧と、それに対するDiscordでの1件の返信です。

【issue一覧】
{issues_text or '(なし)'}

【返信】
{reply_text}

【Statusフィールドで選択可能な値】
{', '.join(status_options) or '(取得できませんでした)'}

この返信がどのissueについて何を報告しているか、じっくり考えてください。一覧のどれにも
該当しない場合、またはStatusの選択可能な値に対応する明確な変化がない場合は、
matchedをfalseにしてください（自信のない推測はしないこと）。

以下のJSON形式のみで出力してください（他のテキストは含めない）:
{{"matched": true または false, "repo": "owner/repo", "number": 123,
  "status": "選択可能な値のいずれか", "note": "根拠にした返信の要約"}}
"""
    return _chat_json(prompt)


def _next_deadline(today: date) -> tuple[int, str, str] | None:
    """major_eventsから直近の未来の日付(締切)を1件見つける。

    見出し例 "## 2026-08-18 ~ 2026-08-19 大阪大学...一般入試" から日付とラベルを拾い、
    今日以降で最も近いものを (残り日数, YYYY-MM-DD, ラベル) で返す。無ければNone。
    残り日数を逆算ペース配分の材料にする。
    """
    if not MAJOR_EVENTS_TEXT:
        return None
    best = None
    for m in re.finditer(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})([^\n]*)", MAJOR_EVENTS_TEXT):
        try:
            dt = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        days = (dt - today).days
        if days < 0:
            continue
        if best is None or days < best[0]:
            # 見出しが日付範囲("~ 2026-08-19 …")のとき、先頭の終了日を落としてラベル化
            tail = re.sub(r"^[~\-–—〜\s]*20\d{2}[-/]\d{1,2}[-/]\d{1,2}", "", m.group(4))
            label = tail.strip(" ~-–—:：#〜").strip()[:40]
            best = (days, dt.isoformat(), label)
    return best


def _iso_hm(v) -> str:
    """カレンダーの日時(dateTime/date, dict or str)を "HH:MM" か "終日" に丸める。"""
    if isinstance(v, dict):
        v = v.get("dateTime") or v.get("date") or ""
    v = str(v)
    if "T" in v:
        return v[11:16]
    return "終日"


def generate_daily_plan(github_items: list[dict], calendar_events: list[dict],
                        existing_todos: list[dict] | None = None) -> dict:
    """
    GitHub issue・カレンダー・既存ToDo・進捗ステート(projects)・生活リズムを元に、その日の計画を作る。

    従来の「GitHub issueから選ぶ(picks)」に加えて:
      - generated_tasks: 進捗(過去問得点率・学習到達度・弱点など)から創出した具体タスク
      - proposed_schedule: 固定予定・食事を避け、空き時間に配置した時間割(起床〜就寝)
      - wake_time: 起床の推奨時刻
    を生成する。picksはUIがタスク解決できるよう番号→item_idで引き直す(モデル非依存で頑健)。

    戻り値:
      {picks, generated_tasks, proposed_schedule, wake_time, comment, candidates, model}
    """
    numbered = list(enumerate(github_items, start=1))
    issue_lines = "\n".join(
        f"{n}. {it['title']} "
        f"(repo: {it.get('repo') or 'なし'}, labels: {', '.join(it.get('labels', [])) or 'なし'}, "
        f"status: {it.get('status') or '未設定'})"
        + (f"\n   概要: {it['body'][:200]}" if it.get("body") else "")
        for n, it in numbered
    ) or "（GitHubタスクはなし）"
    calendar_events_text = "\n".join(
        f"- {_iso_hm(e.get('start'))}〜{_iso_hm(e.get('end'))} {e.get('summary') or e.get('title') or '(無題)'}"
        for e in calendar_events
    ) or "（固定予定なし）"

    todos_text = "\n".join(
        f"- {t.get('title')}" + (f"（期限{t['due']}）" if t.get("due") else "")
        for t in (existing_todos or [])
    ) or "（なし）"

    projects_text = _load_projects()
    projects_block = f"""【管理中の領域と進捗(次タスク創出の材料)】
{projects_text}

""" if projects_text else ""

    deadline = _next_deadline(datetime.now().date())
    deadline_block = ""
    if deadline:
        d_days, d_date, d_label = deadline
        deadline_block = (
            f"【最重要締切】{d_label or '次の大きな予定'}（{d_date}）まで **あと{d_days}日**。\n"
            f"残り日数から逆算して、今日やるべき分量・範囲を現実的に決めること"
            f"(締切が近いほど演習・総仕上げに寄せ、遠いなら基礎固めでよい)。\n\n"
        )

    prompt = f"""{_context_blocks()}{deadline_block}{projects_block}あなたは個人のタスク管理アシスタント「ワニ博士」です。
今日1日の計画を、次の3つを含めて立ててください。

A) GitHubタスクの選抜(picks): 下の候補から今日やるべきものを番号で選ぶ(0〜5件)。
B) タスクの創出(generated_tasks): 上の「管理中の領域と進捗」から、今日やるべき具体的な
   勉強/作業タスクを自分で考え出す。例: 院試なら弱点(得点率が低い/到達度が低い分野)や
   頻出テーマを優先し「電磁気の境界値問題を過去問3年分」のように具体化。各タスクに所要時間
   の目安(estimated_minutes)と領域(domain)と望ましい時間帯(preferred_time)を付ける。
   ★ただし下の「既にあるToDo」と同じ内容は generated_tasks に入れない(重複禁止)。
C) 時間割(proposed_schedule): 起床(wake_time)から就寝までを、下の固定予定と食事を避け、
   空き時間に配置する。配置する対象は「A/Bのタスク」＋「下の既にあるToDo」。
   既にあるToDoは必ず時間割のどこかに組み込むこと(期限が近いものは優先)。
   生活リズムの「集中できる時間帯」を守る(午前=重い等)。詰め込みすぎず休憩を挟む。
   各項目は start/end(HH:MM)。

最重要ルール:
- 大日程・今の時期を最優先。院試・試験・大きな締切前などの繁忙期は、その勉強/準備を時間割の
  主役にし、無関係な趣味/GitHubタスクは入れない(commentで理由を一言添える)。
- 学習した傾向(あれば)に沿う。着手済み(In Progress/Review)は完遂を優先。
- **進捗ステート/生活リズムに書かれた所要時間・手順は厳守**する。特に:
  ・日課(例: daily_ knock 等)は指定の所要時間を、**途中で分割せず連続した1つの枠**で確保する
    (他タスクで割り込まない。勝手に短縮しない)。
  ・過去問(年度単位。例:「流力2023」のような年度名のタスク/ToDo)を解くブロックの**直後**に、
    その年度の「振り返り」枠を置く(長引く前提で余裕を持たせる)。スケジュールに無い年度の
    振り返りは作らない。
  ・起床の分岐条件(何時までに起きたら何をする等)に従って朝の並びを決める。
  枠が足りない場合は優先度の低いタスクを削って調整し、上記(日課の所要時間・振り返り)は削らない。

【既にあるGoogle ToDo(未完了。既に「やること」として登録済み。時間割に組み込むが、
generated_tasksとして作り直さない)】
{todos_text}

【今日の固定予定(動かせない)】
{calendar_events_text}

【GitHubタスク候補(番号付き)】
{issue_lines}

以下のJSON形式のみで出力してください（他のテキストは含めない）:
{{"picks": [{{"n": 番号(整数), "urgency": 1から5, "reason": "20〜40字"}}],
  "generated_tasks": [{{"title": "具体タスク名", "reason": "なぜ今日やるか(20〜40字)",
    "estimated_minutes": 分(整数), "domain": "領域名", "preferred_time": "morning|afternoon|evening"}}],
  "wake_time": "HH:MM",
  "proposed_schedule": [{{"start": "HH:MM", "end": "HH:MM", "title": "項目名", "domain": "領域名"}}],
  "comment": "全体への一言(繁忙期の注意喚起や励まし。40字以内)"}}
"""
    by_n = {n: it for n, it in numbered}
    picks: list[dict] = []
    generated_tasks: list[dict] = []
    proposed_schedule: list[dict] = []
    wake_time = ""
    comment = ""
    generation_ok = False  # 呼び出し成功か(空picks=意図的な0件と区別する)
    try:
        result = _judge_chat_json(prompt)
        generation_ok = True
        comment = str(result.get("comment", ""))[:80]
        wake_time = str(result.get("wake_time", ""))[:5]

        seen = set()
        for p in result.get("picks", []):
            try:
                n = int(p.get("n"))
            except (TypeError, ValueError):
                continue
            if n not in by_n or n in seen:
                continue
            seen.add(n)
            it = by_n[n]
            try:
                urgency = int(p.get("urgency"))
            except (TypeError, ValueError):
                urgency = None
            picks.append({
                "item_id": it["item_id"], "number": it.get("number"),
                "title": it["title"], "repo": it.get("repo"),
                "labels": it.get("labels", []), "urgency": urgency,
                "reason": str(p.get("reason", ""))[:60],
            })

        for t in (result.get("generated_tasks") or [])[:6]:
            try:
                mins = int(t.get("estimated_minutes"))
            except (TypeError, ValueError):
                mins = None
            title = str(t.get("title", "")).strip()[:100]
            if not title:
                continue
            generated_tasks.append({
                "title": title, "reason": str(t.get("reason", ""))[:80],
                "estimated_minutes": mins, "domain": str(t.get("domain", ""))[:24],
                "preferred_time": str(t.get("preferred_time", ""))[:12],
            })

        for s in (result.get("proposed_schedule") or [])[:24]:
            title = str(s.get("title", "")).strip()[:100]
            if not title:
                continue
            proposed_schedule.append({
                "start": str(s.get("start", ""))[:5], "end": str(s.get("end", ""))[:5],
                "title": title, "domain": str(s.get("domain", ""))[:24],
            })
    except Exception:
        log.exception("日次プランの生成に失敗、先頭数件でフォールバック")

    # 呼び出しが失敗したときだけ機械的フォールバック(GitHub先頭数件)。生成成功で空なのは
    # 繁忙期にモデルが意図的に0件にしたケースなので尊重する。
    if not generation_ok and github_items:
        for it in github_items[:3]:
            picks.append({
                "item_id": it["item_id"], "number": it.get("number"),
                "title": it["title"], "repo": it.get("repo"),
                "labels": it.get("labels", []), "urgency": None,
                "reason": "候補の上位のため",
            })
        comment = comment or "(自動選抜: 先頭から選びました)"

    picks = picks[:5]
    urg_by_id = {pk["item_id"]: pk["urgency"] for pk in picks}
    candidates = [
        {"item_id": it["item_id"], "number": it.get("number"), "title": it["title"],
         "repo": it.get("repo"), "labels": it.get("labels", []),
         "urgency": urg_by_id.get(it["item_id"]), "reason": ""}
        for it in github_items
    ]
    model = _last_judge_model or (LLM_MODEL if LITELLM_MASTER_KEY else config.OLLAMA_MODEL)
    countdown = None
    if deadline:
        countdown = {"days": deadline[0], "date": deadline[1], "label": deadline[2]}
    return {
        "picks": picks,
        "generated_tasks": generated_tasks,
        "proposed_schedule": proposed_schedule,
        "wake_time": wake_time,
        "countdown": countdown,
        "comment": comment,
        "candidates": candidates,
        "model": model,
    }


# 完了タスクを分類するための既定カテゴリ(本人が例示したもの＋プロフィール由来)。
# 環境変数で上書き可。GitHubのrepo/labelsやタイトルをヒントにLLMがここへ振り分ける。
_DEFAULT_CATEGORIES = "院試勉強,研究,研究室の雑務,アルバイト,ロボコン,趣味,その他"
DISTILL_CATEGORIES = [
    c.strip() for c in os.environ.get("DISTILL_CATEGORIES", _DEFAULT_CATEGORIES).split(",")
    if c.strip()
] or [c.strip() for c in _DEFAULT_CATEGORIES.split(",")]  # 空指定は既定にフォールバック


def _fmt_task_list(tasks: list[dict]) -> str:
    """{title,repo,labels}のリストを分類ヒント付きの短い文字列にする。"""
    if not tasks:
        return "なし"
    parts = []
    for t in tasks:
        hint = []
        if t.get("repo"):
            hint.append(f"repo:{t['repo']}")
        if t.get("labels"):
            hint.append(f"labels:{'/'.join(t['labels'])}")
        parts.append(f"「{t.get('title')}」({', '.join(hint) or 'ヒントなし'})")
    return " ; ".join(parts)


def distill_preferences(feedback_records: list[dict]) -> str:
    """
    過去数日のレコメンド履歴(recommend_log.jsonl)から、この人の傾向を
    箇条書きのMarkdownメモに蒸留する(週次)。learned_prefs.md として保存され、
    以降のレコメンドプロンプトに注入される = in-contextな疑似ファインチューニング。

    各レコードは job_generate_daily_plan.py が書く:
      {date, recommended:[{title,repo,labels,urgency,reason}], accepted_titles:[...],
       completed:[{title,repo,labels}], completed_recommended_titles:[...],
       outcome:{done,started}, ...}
    完了タスクはrepo/labels/タイトルを手がかりにカテゴリ(院試勉強/研究/研究室の雑務/
    アルバイト等)へ分類し、カテゴリごとの傾向も学ぶ。
    戻り値: learned_prefs.md に書く本文(Markdown)。
    """
    if not feedback_records:
        return ""

    lines = []
    for r in feedback_records:
        lines.append(
            f"- {r.get('date')}:\n"
            f"    提案 = {_fmt_task_list(r.get('recommended', []))}\n"
            f"    今日やると承認 = {r.get('accepted_titles', []) or 'なし'}\n"
            f"    実際に完了 = {_fmt_task_list(r.get('completed', []))}\n"
            f"    (うち提案通り = {r.get('completed_recommended_titles', []) or 'なし'}, "
            f"その日の完了合計={r.get('outcome', {}).get('done', 0)}件)"
        )
    history_text = "\n".join(lines)

    profile_block = f"""【あなたについて】
{PROFILE_TEXT}

""" if PROFILE_TEXT else ""
    prompt = f"""{profile_block}あなたは個人のタスク管理アシスタント「ワニ博士」の学習担当です。
以下は日別のレコメンド実績ログです。各日について「何を提案したか」「本人が今日やると
承認したのはどれか」「実際に完了したのはどれか(repo/labelsのヒント付き)」が並んでいます。

【レコメンド実績ログ】
{history_text}

まず、提案・完了した各タスクを次のカテゴリのいずれかに分類してください(repo・labels・
タイトルから推測。カレンダー由来などヒントが乏しいものは「その他」でよい):
{', '.join(DISTILL_CATEGORIES)}

そのうえで、今後のレコメンドを本人に寄せるための「学習メモ」を作ってください。特に:
- どのカテゴリのタスクが承認・完了されやすい/されにくいか
- 曜日や時期(大日程)とカテゴリの関係
- 提案件数のうち実際に消化される件数の目安
- urgencyと実際の承認・完了のズレ
根拠が薄い項目は無理に書かない。確かな傾向だけを簡潔な箇条書き(最大8項目)で。
可能な項目にはカテゴリ名を含めること(例:「研究室の雑務は承認されるが夕方だと未完のまま」)。

以下のJSON形式のみで出力してください（他のテキストは含めない）:
{{"insights": ["傾向1(30〜60字)", "傾向2", "..."]}}
"""
    try:
        result = _judge_chat_json(prompt)
        insights = [str(x).strip() for x in result.get("insights", []) if str(x).strip()]
    except Exception:
        log.exception("学習メモの蒸留に失敗")
        insights = []

    if not insights:
        return ""
    return "\n".join(f"- {x}" for x in insights[:8])
