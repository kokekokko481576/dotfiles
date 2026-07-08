"""
Web閲覧ツール(検索・URL取得)。

run_shell/read_file等と違い、ホスト実行エージェント(Unixソケット)は経由しない。
外部インターネットへのHTTPリクエストであり、ホスト側のシェル・ファイルアクセスとは
異なる権限を必要としないため、Botコンテナ自身が直接行う。

検索はGoogle Custom Search JSON APIを使う(要.envのGOOGLE_CSE_API_KEY/GOOGLE_CSE_ID)。
以前はAPIキー不要のDuckDuckGo HTML版スクレイピングだったが、このサーバーのIPからの
アクセスがDuckDuckGo側のbot対策(画像認証)で常にブロックされることを確認したため撤退した
(詳細: project_homeserverメモリ)。
"""
import os
import logging
from html.parser import HTMLParser

import aiohttp

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; ButlerBot/1.0)"
_TIMEOUT = aiohttp.ClientTimeout(total=15)

_GOOGLE_CSE_API_KEY = os.environ.get("GOOGLE_CSE_API_KEY", "")
_GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")


class _TextExtractor(HTMLParser):
    """<script>/<style>を除いた本文テキストだけを抽出する。"""

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.chunks.append(text)

    def get_text(self) -> str:
        return "\n".join(self.chunks)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.get_text()


async def web_search(query: str, num_results: int = 5) -> str:
    """Google Custom Search JSON APIで検索する。"""
    if not _GOOGLE_CSE_API_KEY or not _GOOGLE_CSE_ID:
        return "（Web検索は未設定です。持ち主に.envのGOOGLE_CSE_API_KEY/GOOGLE_CSE_ID設定を依頼してください。）"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": _GOOGLE_CSE_API_KEY,
                    "cx": _GOOGLE_CSE_ID,
                    "q": query,
                    "num": max(1, min(num_results, 10)),
                },
                timeout=_TIMEOUT,
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    err = data.get("error", {}).get("message", f"HTTP {resp.status}")
                    log.error(f"web_search error: {err}")
                    return f"（検索に失敗しました: {err}）"
    except Exception as e:
        log.error(f"web_search error: {e}")
        return f"（検索に失敗しました: {e}）"

    items = data.get("items", [])
    if not items:
        return "検索結果が見つかりませんでした。"

    lines = []
    for i, item in enumerate(items[:num_results], 1):
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "").replace("\n", " ")
        lines.append(f"{i}. {title}\n   {link}\n   {snippet}")
    return "\n".join(lines)


async def fetch_url(url: str, max_chars: int = 4000) -> str:
    """指定したURLの内容を取得し、HTMLタグを除いたテキストを返す。"""
    if not url.startswith(("http://", "https://")):
        return "http(s)から始まるURLを指定してください。"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"User-Agent": _UA},
                timeout=_TIMEOUT,
                max_redirects=5,
            ) as resp:
                if resp.status != 200:
                    return f"（取得に失敗しました: HTTP {resp.status}）"
                content_type = resp.headers.get("Content-Type", "")
                if "text" not in content_type and "html" not in content_type:
                    return f"（テキスト系コンテンツではありません: {content_type}）"
                raw = await resp.text(errors="ignore")
    except Exception as e:
        log.error(f"fetch_url error: {e}")
        return f"（取得に失敗しました: {e}）"

    text = _html_to_text(raw)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…（以下省略）"
    return text
