"""
執事Bot用のエージェントツール定義 + ホスト実行エージェント(agent_executor.py)への接続クライアント。

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
