#!/usr/bin/env python3
"""
Butler Bot ホスト実行エージェント。

Discordの執事Bot(butler-botコンテナ)から、Unixドメインソケット経由でホストOS上の
コマンド実行・ファイル操作リクエストを受け取り、kokkoユーザーの権限で実行する。

設計意図: Botコンテナ自体にホストのシェルやdocker.sockを直接渡すのではなく、
この最小限のプロトコルだけを経由させることで、Discord/LLM APIと直接やり取りし
サードパーティ依存が多いbotプロセス(攻撃面が広い)から、実際のホスト実行権限を分離する。
何を安全に自動実行してよいか/確認が必要かの判断は ai/src/agent_tools.py 側(Bot側)で行う。
このexecutor自身はリクエストされた内容をそのまま実行するだけで、判断ロジックは持たない。

起動方法: systemd (scripts/systemd/butler-agent.service) で kokko ユーザーとして常駐させる。
    sudo cp scripts/systemd/butler-agent.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now butler-agent.service
"""
import asyncio
import json
import logging
import os
import signal
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("butler-agent")

SOCKET_PATH = Path(os.environ.get("AGENT_SOCKET_PATH", "/mnt/data/ai/agent/butler-agent.sock"))
DEFAULT_CWD = os.environ.get("AGENT_DEFAULT_CWD", "/home/kokko/dotfiles/server")
MAX_OUTPUT_CHARS = 8000
MAX_READ_FILE_BYTES = 500_000


async def run_shell(command: str, cwd: str | None, timeout: int) -> dict:
    cwd = cwd or DEFAULT_CWD
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid,
        )
    except Exception as e:
        return {"ok": False, "output": f"起動失敗: {e}"}

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        text = (stdout + stderr).decode(errors="replace")
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS] + "\n...(出力が長いため省略)"
        return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "output": text}
    except asyncio.TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        return {"ok": False, "output": f"タイムアウト({timeout}秒)のためプロセスを終了しました"}


def resolve_path(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(DEFAULT_CWD) / p
    return p.resolve()


async def read_file(path: str) -> dict:
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"ok": False, "output": f"存在しません: {p}"}
        if p.stat().st_size > MAX_READ_FILE_BYTES:
            return {"ok": False, "output": f"ファイルが大きすぎます({MAX_READ_FILE_BYTES}バイト上限): {p}"}
        return {"ok": True, "output": p.read_text(errors="replace")}
    except Exception as e:
        return {"ok": False, "output": f"読み込み失敗: {e}"}


async def write_file(path: str, content: str) -> dict:
    try:
        p = resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content)
        return {"ok": True, "output": f"{'上書き' if existed else '新規作成'}しました: {p} ({len(content)} bytes)"}
    except Exception as e:
        return {"ok": False, "output": f"書き込み失敗: {e}"}


async def list_dir(path: str) -> dict:
    try:
        p = resolve_path(path)
        if not p.is_dir():
            return {"ok": False, "output": f"ディレクトリではありません: {p}"}
        entries = []
        for child in sorted(p.iterdir()):
            kind = "d" if child.is_dir() else "f"
            size = child.stat().st_size if child.is_file() else 0
            entries.append(f"{kind} {size:>10} {child.name}")
        return {"ok": True, "output": "\n".join(entries) or "(空)"}
    except Exception as e:
        return {"ok": False, "output": f"一覧取得失敗: {e}"}


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        line = await reader.readline()
        if not line:
            return
        req = json.loads(line.decode())
        op = req.get("op")
        log.info("request op=%s args=%s", op, {k: v for k, v in req.items() if k != "content"})

        if op == "run_shell":
            result = await run_shell(req.get("command", ""), req.get("cwd"), int(req.get("timeout") or 60))
        elif op == "read_file":
            result = await read_file(req.get("path", ""))
        elif op == "write_file":
            result = await write_file(req.get("path", ""), req.get("content", ""))
        elif op == "list_dir":
            result = await list_dir(req.get("path", ""))
        else:
            result = {"ok": False, "output": f"未知のop: {op}"}
    except Exception as e:
        log.exception("request handling failed")
        result = {"ok": False, "output": f"executor内部エラー: {e}"}

    try:
        writer.write((json.dumps(result, ensure_ascii=False) + "\n").encode())
        await writer.drain()
    finally:
        writer.close()


async def main() -> None:
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    server = await asyncio.start_unix_server(handle_client, path=str(SOCKET_PATH))
    os.chmod(SOCKET_PATH, 0o666)  # butler-botコンテナはroot(コンテナ内)で接続してくるため
    log.info("butler-agent executor listening on %s (cwd default: %s)", SOCKET_PATH, DEFAULT_CWD)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
