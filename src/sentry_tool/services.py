"""Business logic for Sentry API interactions."""

from typing import Any

from sentry_tool.utils import api


def resolve_issue_to_numeric(config: dict[str, Any], issue_id: str) -> tuple[str, str]:
    issue = api(
        f"/organizations/{config['org']}/issues/{issue_id}/",
        token=config["auth_token"],
        base_url=config["url"],
    )
    numeric_id = issue.get("id", issue_id)
    short_id = issue.get("shortId", issue_id)
    return str(numeric_id), short_id
