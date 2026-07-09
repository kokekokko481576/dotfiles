"""
Web閲覧ツール(検索・URL取得)。

run_shell/read_file等と違い、ホスト実行エージェント(Unixソケット)は経由しない。
外部インターネットへのHTTPリクエストであり、ホスト側のシェル・ファイルアクセスとは
異なる権限を必要としないため、Botコンテナ自身が直接行う。

検索はVertex AI Geminiの「Grounding with Google Search」を使う。既存のLiteLLM経由で
`tools=[{"googleSearch": {}}]`を渡すだけで動き、追加のAPIキーは不要。
変遷: DuckDuckGoスクレイピング(サーバーIPがbot対策で常時ブロック) → Google Custom
Search JSON API(キー・API有効化・billing全て設定済みでも403が解消せず断念) → 現方式。
検索専用の別リクエストとしてgroundingを使うため、エージェント本体のfunction calling
(googleSearchとfunctionDeclarationsは同一リクエストで併用不可)とは干渉しない。
"""
import os
import logging
from html.parser import HTMLParser

import aiohttp
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; ButlerBot/1.0)"
_TIMEOUT = aiohttp.ClientTimeout(total=15)

_LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://litellm:4000/v1")
_LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
_SEARCH_MODEL = os.environ.get("WEB_SEARCH_MODEL", "gemini-2.5-flash-vertex")

_llm = AsyncOpenAI(base_url=_LITELLM_BASE_URL, api_key=_LITELLM_MASTER_KEY)


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
    """Gemini(Google Search grounding)で検索し、要約テキスト+ソースURLを返す。"""
    try:
        response = await _llm.chat.completions.create(
            model=_SEARCH_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    "次のクエリについてGoogle検索し、分かったことを日本語で簡潔に"
                    f"まとめてください。\nクエリ: {query}"
                ),
            }],
            tools=[{"googleSearch": {}}],
        )
    except Exception as e:
        log.error(f"web_search error: {e}")
        return f"（検索に失敗しました: {e}）"

    answer = response.choices[0].message.content or "（検索結果を要約できませんでした）"

    # groundingメタデータからソースを取り出す。URIはvertexaisearchのリダイレクトURLだが、
    # そのままfetch_urlに渡せば実ページへ辿れる。
    sources = []
    for meta in (response.model_extra or {}).get("vertex_ai_grounding_metadata", []):
        for chunk in meta.get("groundingChunks", []):
            web = chunk.get("web", {})
            if web.get("uri"):
                sources.append(f"- {web.get('title', '(不明)')}: {web['uri']}")

    if sources:
        answer += "\n\n参照元(fetch_urlで詳細を読める):\n" + "\n".join(sources[:num_results])
    return answer


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
