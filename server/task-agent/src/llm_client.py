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

import requests

import config

log = logging.getLogger(__name__)

_CHAT_URL = f"{config.OLLAMA_BASE_URL}/api/chat"


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
    prompt = f"""以下は個別に優先度評価済みのissue一覧です（urgencyが高いほど優先度が高い）。

{scored_text or '(現在オープンなissueはありません)'}

これをラベル(research/personal/hobby:*)ごとにグルーピングし、urgencyが高いものを
優先的に紹介する形で、Discordにそのまま投稿できるMarkdown形式のメッセージ文にしてください。
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
