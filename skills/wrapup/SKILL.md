---
name: wrapup
description: When the user is ending a session, says goodbye, or asks to wrap up — run this to document the session's work, promote lessons, and persist state to engram memory.
---

Provider-agnostic. Any agent (Claude Code, Grok Build, Codex) runs this to close a session.

End-of-session wrapup. Follow these steps in order — memory is persisted before code is
committed, so a failed commit never costs you the session record.

## 1. Store Session Summary
`memory_store` scope=project, project_dir=<this project folder>
- Key: `session/YYYY-MM-DD-brief-desc` — use the ABSOLUTE date, never "today" or "yesterday"
- Include: what was accomplished, decisions made, current state, any surprises
- Reference file paths created or modified, and any handoff docs consumed

## 2. Promote Generalizable Lessons to `scope=shared`
If you learned something that would help a **different** project, or any agent anywhere:
- `memory_store` scope=shared, key=`lesson/topic` or `fix/what-was-fixed`
- Especially cross-machine gotchas, service behaviours, workarounds, research findings
- Don't duplicate — if you already stored it at shared during the session, skip it

## 3. Record Machine-Specific Details to `scope=machine`
Any work can surface host-specific detail. If new ones appeared this session:
- `memory_store` scope=machine, key=`service/name`, `path/what`, or `infra/subject`
- Examples: a new service port, daemon name, file path, env variable, permission quirk
- These are invisible to other machines on purpose — keep them scoped correctly

## 4. Close Out the Inbox
Messages left unacked wake the next session as if they were new, and an unanswered question
blocks whoever asked it.
- `memory_inbox` — anything still open?
- Reply to anything that asked you something (`memory_reply` — it acks the parent too)
- `memory_ack` anything purely informational you have absorbed
- `memory_resolve` threads whose loop is genuinely closed

## 5. Clean Up WIP
`memory_forget` key=`wip/current` scope=project — **only** if it exists and the work it tracked
is now resolved or fully captured in the session summary.

If work is still in progress and you are stopping mid-task, **UPDATE `wip/current` instead of
deleting it**, so the next session knows to resume rather than rediscover.

## 6. Commit (only if git is initialized)
- Stage specific files — never `git add .` or `git add -A`
- Write a meaningful commit message
- Don't push unprompted — but push when the user asks, or hand off to `/push`
- If git is not initialized, skip this step

## 7. Store Startup Message for Next Session
`memory_store` scope=project, project_dir=<this project folder>, key=`startup/next`

This is the FIRST thing the next session reads in `/startup`, so make it actionable:
- Current state of work (done / in-flight / blocked)
- Services running and where (host, port, daemon name)
- Pending tasks in priority order, and known blockers
- Specific memory keys worth reviewing (`session/...`, `decision/...`)
- An explicit "next step" — what the next session should do first

## 8. Brief Recap to User
Two or three sentences. What was done, what's next. Nothing more.
