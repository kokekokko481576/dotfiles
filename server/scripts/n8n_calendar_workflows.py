#!/usr/bin/env python3
"""執事Bot(ワニ博士)の「予定追加」用n8nワークフローを生成・インポートする。

前提: n8nのUIで Google Calendar のOAuth2クレデンシャルを作成済みであること
(今日の予定取得ワークフローで既に使っている `googleCalendarOAuth2Api`)。
このスクリプトはDBからそのクレデンシャルIDを見つけて、
  予定追加  : POST /webhook/calendar-add
    body例: {"summary":"流体の過去問復習","start":"2026-07-19T14:00:00+09:00",
             "end":"2026-07-19T16:00:00+09:00","description":"間違えた範囲を中心に"}
を作成し、publish + n8n再起動まで行う。

実行: sudo python3 scripts/n8n_calendar_workflows.py  (server/ディレクトリで)
"""
import json
import sqlite3
import subprocess
import sys
import uuid

DB = "/mnt/data/ai/n8n/database.sqlite"
# 予定を書き込む対象カレンダー(今日の予定取得と同じ、こっこのprimary)。
TARGET_CALENDAR = "kogakou.k@gmail.com"


def find_credential():
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = db.execute(
        "SELECT id, name FROM credentials_entity WHERE type='googleCalendarOAuth2Api'"
        " ORDER BY \"createdAt\" DESC LIMIT 1").fetchone()
    if not row:
        sys.exit("Google Calendarのクレデンシャルがn8nにありません(guide/06参照)。")
    return {"id": row[0], "name": row[1]}


def wf_add(cred):
    return {
        "id": "waniCalAdd01",
        "name": "ワニ博士_予定追加",
        "settings": {},
        "nodes": [
            {
                "parameters": {"httpMethod": "POST", "path": "calendar-add",
                               "authentication": "none",
                               "responseMode": "responseNode", "options": {}},
                "id": str(uuid.uuid4()), "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
                "position": [240, 300], "webhookId": str(uuid.uuid4()),
            },
            {
                # Google Calendar「イベント作成」。型・クレデンシャルは既存の
                # 今日の予定取得ワークフロー(typeVersion 1.3)に合わせる。
                # start/end は RFC3339 か 日付のみ(終日)。タイトル・説明は追加フィールド。
                "parameters": {
                    "resource": "event",
                    "operation": "create",
                    "calendar": {"__rl": True, "mode": "id", "value": TARGET_CALENDAR},
                    "start": "={{ $json.body.start }}",
                    "end": "={{ $json.body.end }}",
                    "additionalFields": {
                        "summary": "={{ $json.body.summary }}",
                        "description": "={{ $json.body.description }}",
                    },
                },
                "id": str(uuid.uuid4()), "name": "Google Calendar",
                "type": "n8n-nodes-base.googleCalendar", "typeVersion": 1.3,
                "position": [460, 300],
                "credentials": {"googleCalendarOAuth2Api": cred},
            },
            {
                "parameters": {"respondWith": "allIncomingItems", "options": {}},
                "id": str(uuid.uuid4()), "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5,
                "position": [680, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Google Calendar", "type": "main", "index": 0}]]},
            "Google Calendar": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
        },
    }


def main():
    cred = find_credential()
    print(f"クレデンシャル: {cred['name']} ({cred['id']})")
    wfs = [wf_add(cred)]
    with open("/tmp/wani_calendar_wfs.json", "w", encoding="utf-8") as f:
        json.dump(wfs, f, ensure_ascii=False)
    run = lambda *a: subprocess.run(a, check=False, capture_output=True, text=True)
    print(run("docker", "cp", "/tmp/wani_calendar_wfs.json", "n8n:/tmp/wani_calendar_wfs.json").stderr or "cp OK")
    r = run("docker", "exec", "n8n", "n8n", "import:workflow", "--input=/tmp/wani_calendar_wfs.json")
    print(r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    run("docker", "exec", "n8n", "n8n", "publish:workflow", "--id=waniCalAdd01")
    print("publish済み。n8nを再起動します…")
    run("docker", "compose", "restart", "n8n")
    print('完了。確認: curl -XPOST http://localhost:5678/webhook/calendar-add '
          '-H "Content-Type: application/json" -d \'{"summary":"テスト",'
          '"start":"2026-12-31T10:00:00+09:00","end":"2026-12-31T11:00:00+09:00"}\'')


if __name__ == "__main__":
    main()
