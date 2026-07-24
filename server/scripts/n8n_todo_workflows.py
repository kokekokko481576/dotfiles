#!/usr/bin/env python3
"""ワニ博士のGoogle ToDo連携用n8nワークフロー2本を生成・インポートする。

前提: n8nのUIで Google Tasks のOAuth2クレデンシャルを作成済みであること
(Credentials → Add → Google Tasks OAuth2 API → Googleアカウントで同意)。
このスクリプトはDBからそのクレデンシャルIDを見つけて、
  1. ワニ博士_ToDo取得  : GET  /webhook/todos         → 未完了タスク一覧
  2. ワニ博士_ToDo完了  : POST /webhook/todo-complete → {taskId} を完了に
  3. ワニ博士_ToDo追加  : POST /webhook/todo-add      → {title,notes?,due?} を1件作成
  4. ワニ博士_ToDo削除  : POST /webhook/todo-delete   → {taskId} を削除
を作成し、publish+n8n再起動まで行う。

削除は「討伐しきれなかった自動生成ToDoを翌朝の再編で消して溜めない」ために使う
(job_generate_daily_plan.py が #wani-auto マーカー付きの未完了ToDoだけを削除する)。

実行: sudo python3 scripts/n8n_todo_workflows.py  (server/ディレクトリで)
"""
import json
import sqlite3
import subprocess
import sys
import uuid

DB = "/mnt/data/ai/n8n/database.sqlite"


def find_credential():
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = db.execute(
        "SELECT id, name FROM credentials_entity WHERE type='googleTasksOAuth2Api'"
        " ORDER BY \"createdAt\" DESC LIMIT 1").fetchone()
    if not row:
        sys.exit("Google Tasksのクレデンシャルがまだn8nにありません。"
                 "n8n UIのCredentialsから作成してください(guide/06参照)。")
    return {"id": row[0], "name": row[1]}


def wf_fetch(cred):
    return {
        "id": "waniTodoFetch01",
        "name": "ワニ博士_ToDo取得",
        "settings": {},
        "nodes": [
            {
                "parameters": {"httpMethod": "GET", "path": "todos",
                               "authentication": "none",
                               "responseMode": "responseNode", "options": {}},
                "id": str(uuid.uuid4()), "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
                "position": [240, 300], "webhookId": str(uuid.uuid4()),
            },
            {
                "parameters": {
                    "operation": "getAll",
                    "task": "@default",
                    "returnAll": True,
                    "additionalFields": {"showCompleted": False},
                },
                "id": str(uuid.uuid4()), "name": "Google Tasks",
                "type": "n8n-nodes-base.googleTasks", "typeVersion": 1,
                "position": [460, 300],
                "credentials": {"googleTasksOAuth2Api": cred},
            },
            {
                "parameters": {"respondWith": "allIncomingItems", "options": {}},
                "id": str(uuid.uuid4()), "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5,
                "position": [680, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Google Tasks", "type": "main", "index": 0}]]},
            "Google Tasks": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
        },
    }


def wf_complete(cred):
    return {
        "id": "waniTodoDone01",
        "name": "ワニ博士_ToDo完了",
        "settings": {},
        "nodes": [
            {
                "parameters": {"httpMethod": "POST", "path": "todo-complete",
                               "authentication": "none",
                               "responseMode": "responseNode", "options": {}},
                "id": str(uuid.uuid4()), "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
                "position": [240, 300], "webhookId": str(uuid.uuid4()),
            },
            {
                "parameters": {
                    "operation": "update",
                    "task": "@default",
                    "taskId": "={{ $json.body.taskId }}",
                    "updateFields": {"status": "completed"},
                },
                "id": str(uuid.uuid4()), "name": "Google Tasks",
                "type": "n8n-nodes-base.googleTasks", "typeVersion": 1,
                "position": [460, 300],
                "credentials": {"googleTasksOAuth2Api": cred},
            },
            {
                "parameters": {"respondWith": "allIncomingItems", "options": {}},
                "id": str(uuid.uuid4()), "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5,
                "position": [680, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Google Tasks", "type": "main", "index": 0}]]},
            "Google Tasks": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
        },
    }


def wf_add(cred):
    """POST /webhook/todo-add {title, notes?, due?} → Google Tasksに1件作成。
    creates a Google Task so it appears in ワニ博士アプリ(討伐対象)。"""
    return {
        "id": "waniTodoAdd01",
        "name": "ワニ博士_ToDo追加",
        "settings": {},
        "nodes": [
            {
                "parameters": {"httpMethod": "POST", "path": "todo-add",
                               "authentication": "none",
                               "responseMode": "responseNode", "options": {}},
                "id": str(uuid.uuid4()), "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
                "position": [240, 300], "webhookId": str(uuid.uuid4()),
            },
            {
                "parameters": {
                    "operation": "create",
                    "task": "@default",
                    "title": "={{ $json.body.title }}",
                    "additionalFields": {
                        "notes": "={{ $json.body.notes || '' }}",
                        "dueDate": "={{ $json.body.due || '' }}",
                    },
                },
                "id": str(uuid.uuid4()), "name": "Google Tasks",
                "type": "n8n-nodes-base.googleTasks", "typeVersion": 1,
                "position": [460, 300],
                "credentials": {"googleTasksOAuth2Api": cred},
            },
            {
                "parameters": {"respondWith": "allIncomingItems", "options": {}},
                "id": str(uuid.uuid4()), "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5,
                "position": [680, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Google Tasks", "type": "main", "index": 0}]]},
            "Google Tasks": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
        },
    }


def wf_delete(cred):
    """POST /webhook/todo-delete {taskId} → Google Tasksから1件削除。
    未完了のまま繰り越された自動生成ToDoを翌朝の再編で消すために使う。"""
    return {
        "id": "waniTodoDel01",
        "name": "ワニ博士_ToDo削除",
        "settings": {},
        "nodes": [
            {
                "parameters": {"httpMethod": "POST", "path": "todo-delete",
                               "authentication": "none",
                               "responseMode": "responseNode", "options": {}},
                "id": str(uuid.uuid4()), "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
                "position": [240, 300], "webhookId": str(uuid.uuid4()),
            },
            {
                "parameters": {
                    "operation": "delete",
                    "task": "@default",
                    "taskId": "={{ $json.body.taskId }}",
                },
                "id": str(uuid.uuid4()), "name": "Google Tasks",
                "type": "n8n-nodes-base.googleTasks", "typeVersion": 1,
                "position": [460, 300],
                "credentials": {"googleTasksOAuth2Api": cred},
            },
            {
                "parameters": {"respondWith": "allIncomingItems", "options": {}},
                "id": str(uuid.uuid4()), "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5,
                "position": [680, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Google Tasks", "type": "main", "index": 0}]]},
            "Google Tasks": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
        },
    }


def main():
    cred = find_credential()
    print(f"クレデンシャル: {cred['name']} ({cred['id']})")
    wfs = [wf_fetch(cred), wf_complete(cred), wf_add(cred), wf_delete(cred)]
    with open("/tmp/wani_todo_wfs.json", "w", encoding="utf-8") as f:
        json.dump(wfs, f, ensure_ascii=False)
    run = lambda *a: subprocess.run(a, check=False, capture_output=True, text=True)
    print(run("docker", "cp", "/tmp/wani_todo_wfs.json", "n8n:/tmp/wani_todo_wfs.json").stderr or "cp OK")
    r = run("docker", "exec", "n8n", "n8n", "import:workflow", "--input=/tmp/wani_todo_wfs.json")
    print(r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    for wid in ("waniTodoFetch01", "waniTodoDone01", "waniTodoAdd01", "waniTodoDel01"):
        run("docker", "exec", "n8n", "n8n", "publish:workflow", f"--id={wid}")
    print("publish済み。n8nを再起動します…")
    run("docker", "compose", "restart", "n8n")
    print("完了。curl -XPOST http://localhost:5678/webhook/todo-add -d '{\"title\":\"テスト\"}' で確認")


if __name__ == "__main__":
    main()
