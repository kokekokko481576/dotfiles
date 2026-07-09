"""
GitHub Projects V2 (GraphQL) クライアント。
- issue一覧の取得（Statusフィールドの値付き）
- Statusフィールドの更新（進捗報告の反映）

Projects V2はREST APIに対応していないため、GraphQL APIのみを使う。
"""
import logging

import requests

import config

log = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

_ITEMS_QUERY = """
query($login: String!, $number: Int!, $after: String) {
  %(owner_field)s(login: $login) {
    projectV2(number: $number) {
      id
      fields(first: 30) {
        nodes {
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
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
              id
              number
              title
              url
              state
              body
              labels(first: 20) { nodes { name } }
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
""" % {"owner_field": "organization"}

_ITEMS_QUERY_USER = _ITEMS_QUERY.replace("organization(login:", "user(login:")

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


class GithubProjectClient:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {config.GITHUB_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
            }
        )
        self.project_id = None
        self.status_field_id = None
        self.status_options = {}  # name -> option id

    def _graphql(self, query: str, variables: dict) -> dict:
        resp = self._session.post(
            GITHUB_GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"GitHub GraphQLエラー: {payload['errors']}")
        return payload["data"]

    def fetch_open_items(self) -> list[dict]:
        """Project V2上の全item(未クローズのIssueのみ)を取得する。"""
        query = (
            _ITEMS_QUERY_USER
            if config.GITHUB_PROJECT_OWNER_TYPE == "user"
            else _ITEMS_QUERY
        )
        owner_key = "user" if config.GITHUB_PROJECT_OWNER_TYPE == "user" else "organization"

        items: list[dict] = []
        after = None
        while True:
            data = self._graphql(
                query,
                {
                    "login": config.GITHUB_PROJECT_OWNER,
                    "number": config.GITHUB_PROJECT_NUMBER,
                    "after": after,
                },
            )
            project = data[owner_key]["projectV2"]
            if project is None:
                raise RuntimeError(
                    f"Project #{config.GITHUB_PROJECT_NUMBER} が "
                    f"{config.GITHUB_PROJECT_OWNER} 配下に見つかりません"
                )
            self.project_id = project["id"]

            for field in project["fields"]["nodes"]:
                if field and field.get("name") == config.GITHUB_STATUS_FIELD_NAME:
                    self.status_field_id = field["id"]
                    self.status_options = {opt["name"]: opt["id"] for opt in field["options"]}

            for node in project["items"]["nodes"]:
                content = node.get("content")
                if not content:
                    continue  # Draft issue等（本システムでは使わない想定）
                if content.get("state") != "OPEN":
                    continue

                status_name = None
                for fv in node["fieldValues"]["nodes"]:
                    if fv and fv.get("field", {}).get("name") == config.GITHUB_STATUS_FIELD_NAME:
                        status_name = fv["name"]

                labels = [l["name"] for l in content["labels"]["nodes"]]
                if config.TASK_LABELS and not any(l in config.TASK_LABELS for l in labels):
                    continue

                items.append(
                    {
                        "item_id": node["id"],
                        "issue_id": content["id"],
                        "number": content["number"],
                        "title": content["title"],
                        "url": content["url"],
                        "repo": content["repository"]["nameWithOwner"],
                        "labels": labels,
                        "status": status_name,
                        "body": (content.get("body") or "")[:500],
                    }
                )

            page_info = project["items"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            after = page_info["endCursor"]

        log.info("GitHub Projectから%d件のopen issueを取得", len(items))
        return items

    def update_status(self, item_id: str, status_name: str) -> bool:
        """指定itemのStatusフィールドを更新する。選択肢に存在しない名前ならFalseを返す。"""
        if self.project_id is None or self.status_field_id is None:
            raise RuntimeError("fetch_open_items()を先に呼んでproject/field情報を取得してください")

        option_id = self.status_options.get(status_name)
        if option_id is None:
            # Ollamaの出力は前後の空白・大文字小文字が完全一致しないことがあるため、
            # 揺れを許容したフォールバック照合を試す。
            normalized = status_name.strip().casefold()
            for name, oid in self.status_options.items():
                if name.strip().casefold() == normalized:
                    option_id = oid
                    break
        if option_id is None:
            log.warning(
                "Statusの選択肢に存在しない値 '%s' が指定されました（選択肢: %s）",
                status_name,
                list(self.status_options),
            )
            return False

        self._graphql(
            _UPDATE_STATUS_MUTATION,
            {
                "projectId": self.project_id,
                "itemId": item_id,
                "fieldId": self.status_field_id,
                "optionId": option_id,
            },
        )
        log.info("item %s のStatusを '%s' に更新", item_id, status_name)
        return True
