"""
ワニ博士Bot用のエージェントツール定義 + ホスト実行エージェント(agent_executor.py)への接続クライアント。

Botコンテナ自身にはホストのシェル・ファイルへの直接アクセスを持たせず、
Unixソケット経由でこのプロトコルだけを叩かせることで、Discord/LLM API と直接やり取りする
(＝サードパーティ依存が多く攻撃面が広い)このプロセスから、ホスト実行権限を分離する。
"""
import asyncio
import json
import re

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "サーバーホスト上でシェルコマンドを実行する(kokkoユーザー権限、sudo可)。"
                "調査・設定変更・サービス管理などに使う。"
                "破壊的・変更を伴うコマンドは実行前にDiscordで持ち主の承認を求める仕組みが自動で挟まる。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "実行するシェルコマンド"},
                    "cwd": {"type": "string", "description": "作業ディレクトリ(省略時は ~/dotfiles/server)"},
                    "timeout": {"type": "integer", "description": "タイムアウト秒数(省略時60、最大300)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "サーバーホスト上のファイルを読む(認証情報らしきパスは拒否される)",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "サーバーホスト上にファイルを書き込む(新規作成・上書き問わず常に持ち主の承認が必要)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "サーバーホスト上のディレクトリの中身を一覧表示する",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_schedule",
            "description": (
                "Googleカレンダーから今日の予定一覧を取得する(n8n経由)。"
                "「今日の予定は?」等と聞かれたら使う。ホスト実行エージェントは経由しない。"
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Google検索を行い、検索結果の要約と参照元URLを返す。"
                "最新情報や知らない話題を調べるときに使う。詳細が必要なら参照元URLを"
                "fetch_urlで読む。ホスト実行エージェントは経由しない。"
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "検索クエリ"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "指定したURLのWebページ内容を取得し、HTMLタグを除いたテキストとして返す。"
                "ホスト実行エージェントは経由しない。"
            ),
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "取得するURL(http/https)"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": (
                "タスク一覧と今日の進捗・ワニ博士の気分を取得する(ワニ博士アプリのAPI経由、"
                "タスクの正はGitHub Project)。タスク・進捗・予定の話題ではまずこれを呼ぶ。"
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": (
                "新しいタスクを追加する(GitHub ProjectのDraft itemとして作成、Status=Todo)。"
                "「〜をタスクに入れといて」「TODO追加」等の依頼で使う。"
            ),
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string", "description": "タスクのタイトル(簡潔に)"}},
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_today_tasks",
            "description": (
                "「今日やるタスク」リストを設定する(朝の作戦会議)。numbersにタスク番号を"
                "渡すとそのタスクだけが今日の隊列に出る。「今日は#10と#15やる」のような"
                "依頼で使う。既存の今日リストは上書きされる。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "numbers": {"type": "array", "items": {"type": "integer"},
                                "description": "今日やるタスク番号のリスト"},
                },
                "required": ["numbers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": (
                "Googleカレンダーに予定を1件追加する(n8n経由)。こっこの勉強・作業の計画を"
                "提案したうえで「カレンダーに追加しますか?」と尋ね、同意が得られたときに使う。"
                "例: 『流体力学の過去問の復習』を明日14:00-16:00に登録。"
                "実行前にDiscordでこっこの承認を必ず求める(この確認は自動で挟まる)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "予定のタイトル(何をするか。簡潔に)"},
                    "start": {"type": "string",
                              "description": "開始日時。RFC3339(例 2026-07-19T14:00:00+09:00)。"
                                             "終日予定なら日付のみ(例 2026-07-19)"},
                    "end": {"type": "string",
                            "description": "終了日時。startと同じ形式。終日なら翌日の日付"},
                    "description": {"type": "string", "description": "詳細メモ(任意)"},
                },
                "required": ["summary", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": (
                "タスクの進捗状態を変更する。番号付きタスクはnumber、番号のないメモ(Draft)は"
                "titleで指定する。statusは waiting/Todo/In Progress/Review/Done/wish list "
                "のいずれか(完了・着手・レビュー・待ち・後回し などの日本語も可)。"
                "完了にするとワニ博士の気分が上がる。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "タスク番号(#の数字)。メモの場合は省略"},
                    "title": {"type": "string", "description": "タスク名(番号がない場合。部分一致可)"},
                    "status": {"type": "string", "description": "新しい状態"},
                },
                "required": ["status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_today_todos",
            "description": (
                "夜間に生成された今日の創出タスク(daily_plan.jsonのgenerated_tasks)を、Google ToDoに"
                "一括登録する。こっこが「今日のタスク入れといて」「今日のToDo作って」「今日の作戦やる」等と"
                "言ったら呼ぶ。登録するとワニ博士アプリで討伐(完了)できるようになる。実行前に一覧を見せて"
                "承認を得る(この確認は自動で挟まる)。"
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_diary",
            "description": (
                "その日の日記(振り返り)を保存する。夜の振り返りで、こっこが話した『今日やったこと・"
                "気づき・気分・過去問の出来』などを1日分の短い記録にまとめて呼ぶ。1日1ファイル。"
                "会話がひと段落したら呼ぶ(過去問の点数など進捗はこれとは別に update_progress でも記録する)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string",
                                "description": "その日の日記本文(こっこの発言を踏まえた3〜8行程度の要約)"},
                    "mood": {"type": "string",
                             "description": "その日の気分・調子(任意。例: 上々/普通/疲れた)"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_progress",
            "description": (
                "管理中の領域(院試/研究/バイト等)の進捗を記録する。こっこが学習の進み具合・過去問の得点・"
                "弱点・到達度などを報告したら呼ぶ。例:『過去問2020の電磁気7割だった』『流体の教科書3章まで終わった』。"
                "記録は次の日次プラン生成で『次にやるべきタスク』の材料になる。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string",
                               "description": "領域名(例: 院試, 研究, バイト)。進捗ファイル名になる"},
                    "note": {"type": "string",
                             "description": "記録内容(例: 過去問2020の電磁気7割、流体3章まで完了、微分方程式が弱点)"},
                },
                "required": ["domain", "note"],
            },
        },
    },
]

# 認証情報・秘密鍵など、エージェントに読み書きさせてはいけないパス(部分一致・大文字小文字無視)。
# 注意: run_shell 経由での間接的な読み出し(例: base64やpythonでの読み込み)までは防げない。
# 単一ユーザー運用・ローカルネットワーク限定という前提のもとでの最低限のガードである。
SENSITIVE_PATH_HINTS = [
    ".env", ".ssh/", "id_rsa", "id_ed25519", "id_ecdsa", "vertex-sa.json",
    ".pem", ".key", "/etc/shadow", "/etc/sudoers", "known_hosts",
]


def is_sensitive_path(path: str) -> bool:
    lowered = path.lower()
    return any(hint in lowered for hint in SENSITIVE_PATH_HINTS)


# 確認なしで自動実行してよい「読み取り専用・調査用」コマンドの先頭パターン。
# 許可リスト方式(未知のコマンドはすべて要確認)にすることで、危険コマンドの列挙漏れを避ける。
_SAFE_PREFIXES = [
    r"ls\b", r"cat\b", r"pwd\b", r"whoami\b", r"id\b", r"uname\b",
    r"df\b", r"du\b", r"free\b", r"uptime\b", r"date\b",
    r"ps\b", r"top -bn ?1\b", r"vmstat\b", r"sensors\b",
    r"ip a(ddr)?\b", r"ss\b", r"netstat\b",
    r"git status\b", r"git log\b", r"git diff\b", r"git show\b", r"git branch\b",
    r"docker ps\b", r"docker images\b", r"docker version\b", r"docker inspect\b",
    r"docker compose ps\b", r"docker compose config\b", r"docker compose logs\b",
    r"docker logs\b", r"docker stats --no-stream\b",
    r"systemctl status\b", r"systemctl is-active\b", r"systemctl list-units\b",
    r"journalctl\b",
    r"curl (-s ?)?(-I ?)?(-o /dev/null ?)?http://(localhost|127\.0\.0\.1|[a-z0-9_.-]+):[0-9]+",
    r"smartctl -a\b", r"smartctl -H\b",
    r"grep\b", r"which\b", r"echo\b",
]
_SAFE_RE = re.compile("|".join(f"(?:{p})" for p in _SAFE_PREFIXES))

# 複合コマンド(連結・パイプ・リダイレクト・置換)が含まれる場合は、
# 見た目が安全なコマンドでも安全側に倒して必ず確認を求める。
_COMPOUND_HINTS = ["&&", "||", ";", "|", "$(", "`", ">", "<("]


def classify_shell(command: str) -> str:
    """コマンド文字列を見て 'auto'(自動実行可) か 'confirm'(要承認) かを判定する。"""
    stripped = command.strip()
    if not stripped:
        return "confirm"
    if any(hint in stripped for hint in _COMPOUND_HINTS):
        return "confirm"
    if _SAFE_RE.match(stripped):
        return "auto"
    return "confirm"


class ExecutorError(RuntimeError):
    pass


async def call_executor(socket_path: str, request: dict, timeout: float = 310.0) -> dict:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(socket_path), timeout=5.0
        )
    except Exception as e:
        raise ExecutorError(
            f"agent_executorに接続できません({socket_path}): {type(e).__name__}: {e}"
        ) from e

    try:
        writer.write((json.dumps(request, ensure_ascii=False) + "\n").encode())
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not line:
            raise ExecutorError("agent_executorから応答がありませんでした")
        return json.loads(line.decode())
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def execute_tool(socket_path: str, name: str, args: dict) -> dict:
    """ツール呼び出しを実行し、{"ok": bool, "output": str} 形式の結果を返す。"""
    if name in ("read_file", "write_file", "list_dir"):
        path = args.get("path", "")
        if is_sensitive_path(path):
            return {
                "ok": False,
                "output": f"拒否: 認証情報を含む可能性のあるパスへのアクセスはできません: {path}",
            }

    if name == "run_shell":
        timeout = min(int(args.get("timeout") or 60), 300)
        req = {"op": "run_shell", "command": args.get("command", ""), "cwd": args.get("cwd"), "timeout": timeout}
    elif name == "read_file":
        req = {"op": "read_file", "path": args.get("path", "")}
    elif name == "write_file":
        req = {"op": "write_file", "path": args.get("path", ""), "content": args.get("content", "")}
    elif name == "list_dir":
        req = {"op": "list_dir", "path": args.get("path", "")}
    else:
        return {"ok": False, "output": f"未知のツールです: {name}"}

    try:
        return await call_executor(socket_path, req)
    except ExecutorError as e:
        return {"ok": False, "output": str(e)}
