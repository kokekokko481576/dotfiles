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

def _env(name: str, default: str = "") -> str:
    # docker composeのenv_fileは行内コメントを値に含めてしまうため、防御的に除去する
    # (過去に「GITHUB_PROJECT_NUMBER=  # コメント」で起動ループになった)
    return os.environ.get(name, default).split("#")[0].strip()


def _int_env(name: str) -> int:
    raw = _env(name)
    try:
        return int(raw or "0")
    except ValueError:
        log.warning("環境変数 %s が数値でないため無視します: %r", name, raw)
        return 0


GITHUB_TOKEN = _env("GITHUB_TOKEN")
PROJECT_OWNER = _env("GITHUB_PROJECT_OWNER")
PROJECT_OWNER_TYPE = _env("GITHUB_PROJECT_OWNER_TYPE", "organization")
PROJECT_NUMBER = _int_env("GITHUB_PROJECT_NUMBER")
STATUS_FIELD_NAME = _env("GITHUB_STATUS_FIELD_NAME") or "Status"

MOCK_MODE = not (GITHUB_TOKEN and PROJECT_OWNER and PROJECT_NUMBER)
# ユーザーの実Projectと同じ並び(guide/13参照)。実モードではGitHubから取得した選択肢が使われる
MOCK_STATUSES = ["waiting", "Todo", "In Progress", "Review", "Done", "wish list"]

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
              ... on ProjectV2ItemFieldDateValue {
                date
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
          content {
            ... on Issue {
              number title url state
              labels(first: 20) { nodes { name } }
              repository { nameWithOwner }
            }
            ... on DraftIssue {
              draftTitle: title
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

# Draft item(リポジトリに属さないメモ的タスク)としてProjectに直接追加する。
# issue作成と違いリポジトリ指定が不要なので、UI/Discordからの気軽な追加に向く
_ADD_DRAFT_MUTATION = """
mutation($projectId: ID!, $title: String!) {
  addProjectV2DraftIssue(input: { projectId: $projectId, title: $title }) {
    projectItem { id }
  }
}
"""

# Project内の手動並び順を変更する(afterId=nullで先頭へ)。
# 冒険モードの敵の隊列 = Projectの並び順で、GitHub側のボードにも反映される
_MOVE_ITEM_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $afterId: ID) {
  updateProjectV2ItemPosition(input: {
    projectId: $projectId, itemId: $itemId, afterId: $afterId
  }) {
    items(first: 1) { totalCount }
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

    def move_item(self, item_id: str, after_id: str | None) -> dict:
        """itemをafter_idの直後(Noneなら先頭)へ移動する。"""
        tasks = self.list_tasks()
        if not any(t["item_id"] == item_id for t in tasks):
            return {"ok": False, "error": f"item_id '{item_id}' が見つかりません"}
        if after_id is not None and not any(t["item_id"] == after_id for t in tasks):
            return {"ok": False, "error": f"after_id '{after_id}' が見つかりません"}

        if self.mock:
            moving = next(t for t in tasks if t["item_id"] == item_id)
            rest = [t for t in tasks if t["item_id"] != item_id]
            if after_id is None:
                rest.insert(0, moving)
            else:
                idx = next(i for i, t in enumerate(rest) if t["item_id"] == after_id)
                rest.insert(idx + 1, moving)
            store.save_mock_tasks(rest)
        else:
            self._graphql(_MOVE_ITEM_MUTATION, {
                "projectId": self._project_id,
                "itemId": item_id,
                "afterId": after_id,
            })
            with self._lock:
                self._cache_at = 0.0
        return {"ok": True}

    def create_task(self, title: str) -> dict:
        """Draft itemとしてタスクを追加し、作成されたtaskを返す。"""
        title = title.strip()
        if not title:
            return {"ok": False, "error": "タイトルが空です"}
        if len(title) > 200:
            return {"ok": False, "error": "タイトルが長すぎます(200文字まで)"}

        if self.mock:
            tasks = store.load_mock_tasks()
            item_id = f"mock-{max((int(t['item_id'].split('-')[1]) for t in tasks if t['item_id'].startswith('mock-')), default=0) + 1}"
            task = {"item_id": item_id, "number": None, "title": title, "url": "",
                    "repo": "", "labels": [], "status": "Todo", "draft": True}
            tasks.append(task)
            store.save_mock_tasks(tasks)
            return {"ok": True, "task": task}

        self.list_tasks()  # project_id / statusフィールド情報を確保
        data = self._graphql(_ADD_DRAFT_MUTATION,
                             {"projectId": self._project_id, "title": title})
        item_id = data["addProjectV2DraftIssue"]["projectItem"]["id"]
        # 新規DraftはStatus未設定なので明示的にTodoへ(選択肢に無ければ未設定のまま)
        todo = self._match_status("Todo", list(self._status_options))
        if todo:
            self._graphql(_UPDATE_STATUS_MUTATION, {
                "projectId": self._project_id,
                "itemId": item_id,
                "fieldId": self._status_field_id,
                "optionId": self._status_options[todo],
            })
        with self._lock:
            self._cache_at = 0.0
        task = {"item_id": item_id, "number": None, "title": title, "url": "",
                "repo": "", "labels": [], "status": todo or "Todo", "draft": True}
        return {"ok": True, "task": task}

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
                   "着手": "In Progress", "進行中": "In Progress", "未着手": "Todo",
                   "レビュー": "Review", "確認": "Review",
                   "待ち": "waiting", "待機": "waiting", "保留": "waiting",
                   "後回し": "wish list", "あとで": "wish list", "いつか": "wish list",
                   "wishlist": "wish list", "wish": "wish list"}
        alias = aliases.get(normalized)
        if alias:
            # エイリアス先も実際の選択肢名と大文字小文字を無視して照合する
            for opt in options:
                if opt.strip().casefold() == alias.casefold():
                    return opt
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
                content = node.get("content") or {}
                is_draft = "draftTitle" in content
                # issueはOPENのみ。Draft item(リポジトリに属さないメモ的タスク)はそのまま扱う
                if not is_draft and content.get("state") != "OPEN":
                    continue
                status_name = None
                due = None
                for fv in node["fieldValues"]["nodes"]:
                    if not fv:
                        continue
                    if fv.get("field", {}).get("name") == STATUS_FIELD_NAME:
                        status_name = fv.get("name")
                    elif "date" in fv:
                        # Projectの日付フィールド(名前は問わず最初の1つ)を期限として扱う
                        due = due or fv.get("date")
                items.append({
                    "item_id": node["id"],
                    "number": content.get("number"),  # Draftはnull
                    "title": content.get("draftTitle") or content.get("title") or "(無題)",
                    "url": content.get("url", ""),
                    "repo": (content.get("repository") or {}).get("nameWithOwner", ""),
                    "labels": [l["name"] for l in (content.get("labels") or {}).get("nodes", [])],
                    "status": status_name or "Todo",
                    "draft": is_draft,
                    "due": due,
                })

            page_info = project["items"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            after = page_info["endCursor"]

        log.info("GitHub Projectから%d件のopen issueを取得", len(items))
        return items
