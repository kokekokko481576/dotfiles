"""
Web閲覧ツール(検索・URL取得)。APIキー不要でDuckDuckGoのHTML版を使う。

run_shell/read_file等と違い、ホスト実行エージェント(Unixソケット)は経由しない。
外部インターネットへのHTTPリクエストであり、ホスト側のシェル・ファイルアクセスとは
異なる権限を必要としないため、Botコンテナ自身が直接行う。
"""
import re
import logging
from html.parser import HTMLParser

import aiohttp

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; ButlerBot/1.0)"
_TIMEOUT = aiohttp.ClientTimeout(total=15)


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


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


async def web_search(query: str, num_results: int = 5) -> str:
    """DuckDuckGoのHTML版(APIキー不要)から検索結果を取得する。

    注意: このサーバーのIPからのアクセスはDuckDuckGo側のbot対策(画像認証)に
    引っかかり、常に失敗する状態を2026-07-08時点で確認済み。根本的に解決するには
    Google Custom Search API / Bing Search API等の(要サインアップ・APIキー)有償/無償
    APIへの切り替えが必要（詳細: guide/11またはproject_homeserverメモリ参照）。
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": _UA},
                timeout=_TIMEOUT,
            ) as resp:
                status = resp.status
                html = await resp.text()
    except Exception as e:
        log.error(f"web_search error: {e}")
        return f"（検索に失敗しました: {e}）"

    if "anomaly-modal" in html or "bots use DuckDuckGo too" in html:
        return (
            "（検索エンジン側のbot対策(画像認証)によりブロックされました。"
            "このツールは現状使えません。持ち主にAPIキー方式の検索API導入を依頼してください。）"
        )
    if status != 200:
        return f"（検索に失敗しました: HTTP {status}）"

    # DuckDuckGo HTML版の検索結果マークアップ: <a class="result__a" href="URL">タイトル</a>
    titles_urls = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    snippets = re.findall(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )

    if not titles_urls:
        return "検索結果が見つかりませんでした。"

    lines = []
    for i, (url, title) in enumerate(titles_urls[:num_results]):
        snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
        lines.append(f"{i + 1}. {_strip_tags(title)}\n   {url}\n   {snippet}")
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
