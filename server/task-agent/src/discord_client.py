"""
Discord REST APIクライアント。

task-agent専用のBot（butler-botとは別）を使う。同じBot名でGemini(butler-bot)とOllama
(task-agent)の発言が混在すると「どのAIが喋っているか」が分かりにくくなるため、見た目上も
Botを分けている。
Job A/Bはどちらも一度実行して終了するバッチなので、discord.pyのGateway接続は使わず、
REST APIを直接叩く（ボットのオンライン表示・常時接続は不要）。
"""
import logging

import requests

import config

log = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordClient:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bot {config.DISCORD_TOKEN}",
                "Content-Type": "application/json",
            }
        )
        self._bot_user_id = None

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._session.request(method, f"{DISCORD_API_BASE}{path}", timeout=30, **kwargs)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def bot_user_id(self) -> str:
        if self._bot_user_id is None:
            self._bot_user_id = self._request("GET", "/users/@me")["id"]
        return self._bot_user_id

    def post_message(self, channel_id: str, content: str) -> dict:
        """1件のメッセージを投稿する（Discordの2000字上限は呼び出し側でsplit_chunksすること）。
        channel_idにはスレッドIDも渡せる（DiscordのAPI上、スレッドは通常チャンネルと同じ
        エンドポイントで投稿できる）。"""
        return self._request(
            "POST", f"/channels/{channel_id}/messages", json={"content": content}
        )

    @staticmethod
    def split_chunks(content: str, size: int = 1900) -> list[str]:
        return [content[i : i + size] for i in range(0, len(content), size)] or [""]

    def start_thread(self, channel_id: str, message_id: str, name: str) -> str:
        thread = self._request(
            "POST",
            f"/channels/{channel_id}/messages/{message_id}/threads",
            json={"name": name[:100], "auto_archive_duration": 1440},
        )
        return thread["id"]

    def fetch_replies(self, thread_id: str) -> list[dict]:
        """スレッド内のメッセージをBot自身の投稿を除いて古い順で返す。"""
        bot_id = self.bot_user_id()
        messages: list[dict] = []
        before = None
        while True:
            params = {"limit": "100"}
            if before:
                params["before"] = before
            page = self._request("GET", f"/channels/{thread_id}/messages", params=params)
            if not page:
                break
            messages.extend(page)
            if len(page) < 100:
                break
            before = page[-1]["id"]

        messages.reverse()  # Discordは新しい順で返すので古い順に直す
        return [
            {"author": m["author"]["username"], "content": m["content"], "timestamp": m["timestamp"]}
            for m in messages
            if m["author"]["id"] != bot_id and m["content"].strip()
        ]
