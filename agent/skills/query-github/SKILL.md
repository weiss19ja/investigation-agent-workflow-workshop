---
name: query-github
description: How to read the responsible code on GitHub — find the repository, resolve the release to a commit, and open files at that commit. Load it before calling any GitHub connector tool.
---

# Query GitHub

Use this skill to open the code behind a Sentry finding. Every tool it names is read-only.

1. Call `search_repositories` with the repository name from the question to find the repo; capture its full name (owner and repo).
2. Resolve the release recorded on the Sentry event to a commit:
   - call `get_latest_release`, or `list_releases` to pick the matching one, to get the release tag;
   - call `get_release_by_tag` (or `get_tag`) with that tag to get the commit SHA the release points at.
3. Open the responsible file at that commit with `get_file_contents`, passing the repository, the file path from the Sentry frame, and the release's commit SHA — never the default branch, so the code you read is the code that shipped in the release.
4. Read the responsible symbol and quote the exact line that breaks. If a frame points into another file, follow it the same way. Use `search_code` to locate a symbol or string, and `get_commit` or `list_commits` to see what changed at the release.
5. For regression context, `issue_read`, `list_issues`, `pull_request_read`, `list_pull_requests`, `search_pull_requests`, and `search_commits` are also available — all read-only.
6. Cite GitHub evidence in the report as source `github`, with the file URL at the release commit as the reference, and state in `proves` what the quoted line proves.

Read-only rule: call only the tools named above. Creating, updating, commenting, merging, or pushing anything is denied by the permission policy — never try it.
