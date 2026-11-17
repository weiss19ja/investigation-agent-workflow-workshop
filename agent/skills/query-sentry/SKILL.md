---
name: query-sentry
description: How to investigate an error in Sentry — find the issue, read one representative event, and capture the exception, the responsible frames and the release. Load it before calling any Sentry connector tool.
---

# Query Sentry

Use this skill whenever the question is about an error, an exception, or a Sentry event. Every tool it names is read-only.

1. Start with `find_organizations`, then `find_projects`, to learn the organization and project slugs you are searching.
2. Call `search_issues` with the exception text or symptom from the question to find the matching issue. Capture the issue ID, its title, and its permalink.
3. Call `search_events` on that issue, most recent first, and read one representative event. From the event capture:
   - the exception: its type and message exactly as the tracker shows them;
   - the responsible frames: the file path, the function symbol, and the line number of the top in-app frame;
   - the release recorded on the event.
4. If the issue or a frame points at one specific event, confirm it with `get_sentry_resource` before you cite the exception, the frames, or the release.
5. Cite Sentry evidence in the report as source `sentry`, with the issue or event permalink as the reference, and state in `proves` exactly what the event shows — exception, responsible frame, release.

Read-only rule: call only the tools named above. Sentry write tools and the generic dispatchers are denied by the permission policy — never try them.
