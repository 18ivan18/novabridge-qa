# AI conversation logs

Full, unedited exports of every AI-assistant conversation used on this project, as the brief requires.

| Log | Tool | Covered |
|---|---|---|
| [2026-11-06-claude-app-planning.md](2026-11-06-claude-app-planning.md) ([JSON](2026-11-06-claude-app-planning.json)) | Claude app | Planning: the handoff and the UI designs |
| [2026-11-07-claude-code-M0-M11.jsonl](2026-11-07-claude-code-M0-M11.jsonl) | Claude Code | The implementation, M0 to M11 and the improvements list. The complete raw session transcript, including everything before the context was compacted |
| [2026-11-08-005011-read-docshandoffmd-and-do-m0.txt](2026-11-08-005011-read-docshandoffmd-and-do-m0.txt) | Claude Code | The same session from `/export`, easier to read. It starts after the compaction, so it covers M7 onwards only |
| [2026-11-09-004316-docsimprovementsmd-lets-start-implementing-1.txt](2026-11-09-004316-docsimprovementsmd-lets-start-implementing-1.txt) | Claude Code | The improvements session from `/export`: task 1 (HTML loader), task 2 (answer evaluation), recall before fusion, task 4 (re-ranker) and task 11 written up. It starts at the session's first message |

The `.jsonl` is Claude Code's own transcript format: one JSON object per line, holding messages,
tool calls and their results.
