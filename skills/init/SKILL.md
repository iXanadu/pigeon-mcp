---
name: init
description: When initializing a new generic Python project from this template for the first time — run this to bootstrap project name, virtualenv, env files, and initial memory state. It does NOT create databases (that's a deliberate manual step).
---

This is a NEW PROJECT initialization. Run it ONCE, after `startup` has determined the
project is still template-shaped. Follow these steps in order.

## 1. Gather Project Information

Ask the user for:
- **Project name** (lowercase, no spaces, e.g., `myapp`)
- **One-line description** — what this project is. This fills `AGENTS.md` later.
- **Domain** (e.g., `myapp.trustworthyagents.com`) — only if the project is web-facing.

## 2. Read Project Specs

Read any files in `docs/specs/` (especially `prd.md`) to understand what this project should
do. Do this BEFORE any scaffolding decisions.

If `docs/specs/` is empty or missing, say so and ask the user whether they have a PRD to drop
in. Don't invent requirements.

## 3. Set Up Python Environment

Hard rule (see `AGENTS.md`): **pyenv + pyenv-virtualenv — NEVER `python -m venv`.**

```bash
pyenv virtualenv 3.13 {projectname}-3.13
pyenv local {projectname}-3.13
```

`pyenv local` writes `.python-version`, pinning every later command to the virtualenv.
The template ships `.python-version.example` as a reference; `pyenv local` supersedes it.

## 4. Set Up Environment Files

The examples ship in-repo — there is no external source to copy from:

```bash
cp examples/.env.example .env
cp examples/.keys.example .keys
chmod 600 .keys
```

Then use the Edit tool to replace `PROJECTNAME` in `.env` with the actual project name.

The template already ships a root `.gitignore` — leave it alone.

Skip this step entirely if the project needs neither config nor secrets.

## 5. Database — MANUAL, NOT done by `/init`

`/init` never touches a database. Provisioning the Postgres role + dev/prod DBs mutates the
shared cluster, so it's a deliberate step **you run yourself**, and only if the project needs one:

```bash
./scripts/provision-db.sh <projectname>
```

That script sources the shared password from `.keys` (never hardcoded) and uses `db_admin`
creds from `~/.pgpass`. No database needed? Skip this entirely.

## 6. Requirements

Create `requirements.txt` if it does not exist. If the specs from step 2 make the
dependencies clear, add them now and install:

```bash
touch requirements.txt
pip install -r requirements.txt   # once it has content
```

## 7. Update AGENTS.md

Edit `AGENTS.md` — the real file, never the `CLAUDE.md` symlink — to replace the template
placeholders with actual detail:
- Project name and the one-line description from step 1
- Project structure as actually created
- Commands specific to this project
- Any conventions from the specs

## 8. Update README.md

The shipped `README.md` is template-shaped. Replace it with a short description of THIS
project: what it is, how to run it, where the specs live.

## 9. Git Init and Project Identity

```bash
git init
git add -A
git commit -m "Initialize <projectname> from proj template"
```

Write `.engram.cfg` at the repo root:

```
project = <projectname>
```

This is the canonical memory identity — `startup` reads it every session, and without it
`scope=project` memory and the inbox resolve inconsistently. Stage and commit it.

Ask the user whether they want to push to GitHub. Don't push unprompted.

## 10. Store Initial State in Memory

Use `memory_store` with `scope=project` and an explicit `project_dir` (this repo root):
- Key: `session/YYYY-MM-DD-project-init` — use the ABSOLUTE date, not "today"
- Include: project name, description, domain, database info, what the specs say the project
  should do, setup steps completed

Also store `startup/next` so the next session starts oriented rather than re-deriving state.

## 11. Summary

When complete, summarize:
- What was set up
- What the PRD says the project should do
- Suggested next steps based on the PRD
- Ask what the user wants to work on first
