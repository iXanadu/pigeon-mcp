---
name: startup
description: When a new session begins in this project, run this to orient on project state, memory, and recent work before doing anything else.
---

Provider-agnostic. Any agent (Claude Code, Grok Build, Codex) runs this to orient at the
start of a session, before any substantive work.

## 0. Orientation Prelude

Do both of these before any `scope=project` memory calls or substantive work.

**0a. Refresh global directives.** Re-read `~/.agents/AGENTS.md` — the provider-neutral canonical holding your global operating rules (communication style, memory scope resolution, git safety, Python convention). It's loaded at session start but fades when buried in a long system prompt; re-reading pulls it into active attention.

**0b. Confirm project identity.** Check `.engram.cfg` at the repo root.

- If present: parse `project = <name>`. This is the canonical id for all `scope=project` memory and inbox addressing. Proceed.
- If absent:
  1. **Only** auto-suggest a name when CWD matches `~/projects/<name>/` (one level directly under `projects/`, at the repo root) AND `<name>` is NOT a generic deploy label (`prod`, `dev`, `staging`, `main`, `trunk`, `current`, `release`, `live`). In that case, suggest `<name>` and ask the user to confirm.
  2. Otherwise (nested layouts like `~/projects/site/sub/`, domain-style `~/projects/site.com/dev/`, server paths like `/var/www/site/prod`, or anything that doesn't match the clean `~/projects/<name>/` shape), do NOT guess — ask the user directly. Do not infer from git remotes or path segments in ambiguous cases; the user decides.
  3. Once the user confirms: write `.engram.cfg` at the repo root containing `project = <name>`. Stage it. Commit (`Add .engram.cfg — canonical project identifier`).

  `/init` also writes `.engram.cfg` during scaffolding. If both run, the user's confirmed name takes precedence.

## 1. Check the Project Is Initialized

This template is scaffolding until `/init` has run. It is still uninitialized if `AGENTS.md`
still contains the `[Project Name]` placeholder.

If uninitialized, tell the user:
> "This looks like a fresh project from the template. Run `/init` to bootstrap it."

Then **STOP** — do not run the rest of startup. There is no state to recover yet, and the
memory sweep below would query an identity that has not been established.

## 2. Read Handoff Note

`memory_get` key=`startup/next` scope=project — the handoff from the last session. If it
references other memory keys, fetch those too.

Note the date it was written. If it's more than a day or two old, treat it as a starting
point rather than a complete picture — the sweep in Step 4 may surface newer state.

## 3. Check for Interrupted Work

`memory_search` query="wip" scope=project limit=3 — if `wip/current` exists, the last session
stopped mid-task. Read it, orient, and plan to continue.

## 4. Thorough Memory Recovery

The handoff captures one moment. To orient fully, sweep memory with several targeted queries
(run them in parallel where possible):

### Project scope
1. `memory_search` query="session" scope=project limit=10 — recent session summaries
2. `memory_search` query="decision architecture" scope=project limit=10 — design and direction decisions
3. `memory_search` query="strategy direction goals" scope=project limit=5 — strategic direction
4. `memory_search` query="wip current working" scope=project limit=5 — active work

### Shared + machine
5. `memory_search` scope=shared limit=5 — cross-project lessons (cross-project Python lessons)
6. `memory_search` scope=machine limit=3 — local env, paths, services, ports

### Reconcile
Compare dates across results. If the most recent memories are newer than `startup/next`, the
handoff is incomplete — note the gap and lead with the newer state.

Watch for gaps like: the handoff says something is pending but recent memories discuss work
that came after it, or the handoff predates a decision that changed direction.

## 5. Check Inbox

`memory_inbox` — messages from other agent sessions. Read and reply to anything actionable.

## 6. Read Project Identity

Read `AGENTS.md` — project purpose, folder layout, conventions.

## 7. Check Current State

```bash
git status
git log --oneline -10
```

## 8. Summarize and Ask

- Lead with the most recent state (from the memory sweep), not just the handoff
- If the handoff was incomplete, say so and explain what you reconstructed
- Summarize current status
- Identify pending tasks, blockers, technical debt
- Reference the specific memory keys and files you drew context from, so the user can verify
- Note any inbox messages needing attention
- Ask what we're working on today

Be brief. The user does not need a recap of everything surveyed — just the load-bearing context.
