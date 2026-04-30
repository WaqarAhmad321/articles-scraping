# Documentation index

All project documentation in one place:

| file | purpose |
|---|---|
| **[`/CLAUDE.md`](../CLAUDE.md)** | High-level context. Auto-loaded by Claude Code in every session. Read first. |
| **[`/HANDOFF.md`](../HANDOFF.md)** | Full project deep-dive — architecture, decisions, file map, resume checklist, source-by-source notes. |
| **[`/VPS_DEPLOY.md`](../VPS_DEPLOY.md)** | Operate the VPS Docker deployment — push, build, logs, pull-down, stop. |
| [`./RESUME.md`](RESUME.md) | Cookbook for picking up the project on a fresh machine. |
| [`./INDEX.md`](INDEX.md) | This file. |
| [`/README.md`](../README.md) | User-facing project README (setup, schema, basic usage). |

## When to read what

- **Starting a fresh session in Claude Code** → CLAUDE.md is auto-loaded; ask Claude to also read HANDOFF.md.
- **Setting up the project on a new machine** → `docs/RESUME.md`.
- **Deploying / debugging the VPS** → `VPS_DEPLOY.md`.
- **Trying to understand why a particular design choice exists** → `HANDOFF.md` § 9 (Decisions & rationale).
- **Trying to understand what a single source spider does** → spider class docstring + `config/sources.yaml` entry.
