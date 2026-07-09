"""
GitHub Projects V2クライアント + モックフォールバック。

GraphQL部分はtask-agent/src/github_client.pyと同じ手法(Projects V2はRESTに
対応していないためGraphQLのみ)。環境変数はtask-agent/.envと共用の
GITHUB_TOKEN / GITHUB_PROJECT_OWNER / GITHUB_PROJECT_OWNER_TYPE /
GITHUB_PROJECT_NUMBER / GITHUB_STATUS_FIELD_NAME を読む。

GITHUB_TOKEN未設定ならモックモード: /app/dataのJSONを同じ形で読み書きする。
朝PATを設定して再起動すれば、コード変更なしで本物に切り替わる。
"""
import logging
import os
import threading
import time

import requests

import store

log = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
CACHE_TTL_SEC = 60  # /api/state毎にGraphQLを叩かないための読み取りキャッシュ

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PROJECT_OWNER = os.environ.get("GITHUB_PROJECT_OWNER", "")
PROJECT_OWNER_TYPE = os.environ.get("GITHUB_PROJECT_OWNER_TYPE", "organization")
PROJECT_NUMBER = int(os.environ.get("GITHUB_PROJECT_NUMBER", "0") or "0")
STATUS_FIELD_NAME = os.environ.get("GITHUB_STATUS_FIELD_NAME", "Status")

MOCK_MODE = not (GITHUB_TOKEN and PROJECT_OWNER and PROJECT_NUMBER)
MOCK_STATUSES = ["Todo", "In Progress", "Done"]

_ITEMS_QUERY = """
query($login: String!, $number: Int!, $after: String) {
  %(owner_field)s(login: $login) {
    projectV2(number: $number) {
      id
      fields(first: 30) {
        nodes {
          ... on ProjectV2SingleSelectField { id name options { id name } }
        }
      }
      items(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
          content {
            ... on Issue {
              number title url state
              labels(first: 20) { nodes { name } }
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
"""

_UPDATE_STATUS_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item { id }
  }
}
"""


class TaskSource:
    """GitHub Projects V2またはモックJSONを同一インターフェースで扱う。"""

    def __init__(self):
        self.mock = MOCK_MODE
        self._lock = threading.Lock()
        self._cache: list[dict] | None = None
        self._cache_at = 0.0
        self._project_id = None
        self._status_field_id = None
        self._status_options: dict[str, str] = {}
        if not self.mock:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
            })

    # ---- 読み取り ----

    def list_tasks(self, force_refresh: bool = False) -> list[dict]:
        if self.mock:
            return store.load_mock_tasks()
        with self._lock:
            if (
                not force_refresh
                and self._cache is not None
                and time.time() - self._cache_at < CACHE_TTL_SEC
            ):
                return self._cache
            self._cache = self._fetch_items()
            self._cache_at = time.time()
            return self._cache

    def status_names(self) -> list[str]:
        if self.mock:
            return MOCK_STATUSES
        if not self._status_options:
            self.list_tasks()
        return list(self._status_options)

    # ---- 更新 ----

    def update_status(self, item_id: str, status_name: str) -> dict:
        """Statusを更新し {ok, old_status, new_status, task} を返す。"""
        tasks = self.list_tasks()
        task = next((t for t in tasks if t["item_id"] == item_id), None)
        if task is None:
            return {"ok": False, "error": f"item_id '{item_id}' が見つかりません"}
        old_status = task.get("status")

        if self.mock:
            matched = self._match_status(status_name, MOCK_STATUSES)
            if matched is None:
                return {"ok": False,
                        "error": f"'{status_name}' はStatusの選択肢にありません({MOCK_STATUSES})"}
            task["status"] = matched
            store.save_mock_tasks(tasks)
        else:
            matched = self._match_status(status_name, list(self._status_options))
            if matched is None:
                return {"ok": False,
                        "error": f"'{status_name}' はStatusの選択肢にありません"
                                 f"({list(self._status_options)})"}
            self._graphql(_UPDATE_STATUS_MUTATION, {
                "projectId": self._project_id,
                "itemId": item_id,
                "fieldId": self._status_field_id,
                "optionId": self._status_options[matched],
            })
            with self._lock:
                self._cache_at = 0.0  # 次回読み取りで再取得
            task = dict(task, status=matched)

        return {"ok": True, "old_status": old_status, "new_status": matched, "task": task}

    # ---- 内部 ----

    @staticmethod
    def _match_status(name: str, options: list[str]) -> str | None:
        # LLM経由の指定は空白・大文字小文字が揺れるため寛容に照合する
        normalized = name.strip().casefold()
        for opt in options:
            if opt.strip().casefold() == normalized:
                return opt
        aliases = {"todo": "Todo", "doing": "In Progress", "in progress": "In Progress",
                   "inprogress": "In Progress", "done": "Done", "完了": "Done",
                   "着手": "In Progress", "進行中": "In Progress", "未着手": "Todo"}
        alias = aliases.get(normalized)
        if alias and alias in options:
            return alias
        return None

    def _graphql(self, query: str, variables: dict) -> dict:
        resp = self._session.post(
            GITHUB_GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"GitHub GraphQLエラー: {payload['errors']}")
        return payload["data"]

    def _fetch_items(self) -> list[dict]:
        owner_field = "user" if PROJECT_OWNER_TYPE == "user" else "organization"
        query = _ITEMS_QUERY % {"owner_field": owner_field}

        items: list[dict] = []
        after = None
        while True:
            data = self._graphql(query, {
                "login": PROJECT_OWNER, "number": PROJECT_NUMBER, "after": after,
            })
            project = data[owner_field]["projectV2"]
            if project is None:
                raise RuntimeError(
                    f"Project #{PROJECT_NUMBER} が {PROJECT_OWNER} 配下に見つかりません")
            self._project_id = project["id"]
            for field in project["fields"]["nodes"]:
                if field and field.get("name") == STATUS_FIELD_NAME:
                    self._status_field_id = field["id"]
                    self._status_options = {o["name"]: o["id"] for o in field["options"]}

            for node in project["items"]["nodes"]:
                content = node.get("content")
                if not content or content.get("state") != "OPEN":
                    continue
                status_name = None
                for fv in node["fieldValues"]["nodes"]:
                    if fv and fv.get("field", {}).get("name") == STATUS_FIELD_NAME:
                        status_name = fv["name"]
                items.append({
                    "item_id": node["id"],
                    "number": content["number"],
                    "title": content["title"],
                    "url": content["url"],
                    "repo": content["repository"]["nameWithOwner"],
                    "labels": [l["name"] for l in content["labels"]["nodes"]],
                    "status": status_name or "Todo",
                })

            page_info = project["items"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            after = page_info["endCursor"]

        log.info("GitHub Projectから%d件のopen issueを取得", len(items))
        return items
