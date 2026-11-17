"""Connectors and the permission policy: names from the environment, reviewed read-only tools only.

Studio names connectors uniquely per workspace, so the names never live in code — they come from the environment.
The policy is deny-by-default: only the tools listed below, plus the skill loader, may ever run.
"""

import os
import re

import mistralai.agents as agents

SENTRY_READ_TOOLS = frozenset(
    {
        "find_organizations",
        "find_projects",
        "get_sentry_resource",
        "search_events",
        "search_issues",
    }
)

GITHUB_READ_TOOLS = frozenset(
    {
        "get_commit",
        "get_file_contents",
        "get_latest_release",
        "get_release_by_tag",
        "get_tag",
        "issue_read",
        "list_branches",
        "list_commits",
        "list_issues",
        "list_pull_requests",
        "list_releases",
        "list_tags",
        "pull_request_read",
        "search_code",
        "search_commits",
        "search_pull_requests",
        "search_repositories",
    }
)


def connector_name(env_var: str) -> str:
    """Read a connector name from the environment; raise a clear error when it is unset."""
    name = os.environ.get(env_var)
    if not name:
        raise RuntimeError(f"{env_var} is not set: connector names come from the environment, never from code.")
    return name


def connector_namespace(name: str) -> str:
    """The namespace the SDK puts a connector's tools under: `connector_<name>`, non-alphanumerics as `_`."""
    return f"connector_{re.sub(r'[^a-zA-Z0-9]', '_', name).strip('_')}"


def tool_ids(name: str, tools: frozenset[str]) -> list[str]:
    """The sorted stable tool IDs `<namespace>.<tool>` of one connector's tools."""
    namespace = connector_namespace(name)
    return sorted(f"{namespace}.{tool}" for tool in tools)


def read_only_tool_ids(sentry: str, github: str) -> list[str]:
    """The sorted tool IDs of every reviewed read-only tool on both connectors."""
    return sorted(tool_ids(sentry, SENTRY_READ_TOOLS) + tool_ids(github, GITHUB_READ_TOOLS))


def permission_policy(sentry: str, github: str) -> agents.PermissionPolicy:
    """Deny by default; allow only the reviewed read-only connector tools and the skill loader."""
    return agents.PermissionPolicy(
        default="deny",
        rules=(
            agents.PermissionRule(tools=tuple(read_only_tool_ids(sentry, github)), decision="allow"),
            agents.PermissionRule(tools=("skill.*",), decision="allow"),
        ),
    )


SENTRY_CONNECTOR_NAME = connector_name("SENTRY_CONNECTOR_NAME")
GITHUB_CONNECTOR_NAME = connector_name("GITHUB_CONNECTOR_NAME")
