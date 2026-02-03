# Human Claw (human-claw)

Human Claw is a **human-in-the-loop chore marketplace for OpenClaw**.

- **No public UI**: everything happens via OpenClaw chat on both sides.
- **Central market**: a single VPS hosts the task state machine + API.
- **Workers opt-in** with natural language (e.g. “I’m free”, “I need a job”).
- **Privacy after award**: once a task is awarded, only the requester ↔ awarded worker can exchange updates/results.

> Status: MVP (no built-in payments). Payment is arranged directly between requester and worker. See [TERMS.md](./TERMS.md).

---

## What you can do with it

Examples of chores that work well:
- Web research with citations
- Verify something in a browser and report back (screenshots)
- Data cleanup / spreadsheet edits
- Quick “check something locally” tasks (only if a worker is physically there)

Not allowed / not supported:
- Impersonation or ToS-bypass tasks (e.g. “create accounts for me”, undisclosed paid posting)

---

## Architecture

- **Skill**: `skills/public/human-claw/`
- **Central API (FastAPI)**: `services/clawmarket_api.py`
- **State machine (JSON storage)**: `scripts/clawmarket.py` → `state/clawmarket.json`
- **Installer (npx)**: `bin/human-claw-install.js`

Central API default:
- Public: `http://<VPS_IP>:8090`
- Local upstream: `127.0.0.1:8091` (proxied by nginx)

---

## Install the skill (for a friend)

From your OpenClaw workspace directory:

```bash
npx github:lucasmontano/human-claw-human#main -- --workdir .
```

This creates:

- `./skills/human-claw/SKILL.md`
- `./skills/human-claw/references/api.md`

Then restart OpenClaw / start a new session so skills reload.

---

## Run the central API (on the VPS)

This repo is intended to run on a central VPS.

### 1) Start the service

The VPS uses a user-level systemd service:

```bash
systemctl --user status clawmarket-api.service
systemctl --user restart clawmarket-api.service
```

### 2) Check it’s up

```bash
curl http://127.0.0.1:8090/status
# or public
curl http://<VPS_IP>:8090/status
```

---

## Core workflow (natural language)

### Worker

- Opt-in: “I’m free”, “I need a job”, “available”, or equivalents in other languages.
- Opt-out: “I’m busy”, “offline”, “stop sending” (stops **new offers** only).

When a worker becomes AVAILABLE, their agent should show **up to 3 open chores**.

### Requester

Say: “I need a human to … (budget €X)”

Workers can:
- accept at budget (“I’ll take it”)
- propose (“I can do it for €X, ETA Y”)

### Status + updates

- Worker: “update on T000123: 50% done, ETA 30m”
- Requester: “status T000123?” / “ping the worker”

Automation:
- If a task is awarded and there is no update for **30 minutes**, the system sends a **one-time** private nudge to the awarded worker.

---

## API quick reference

These are the central endpoints used by OpenClaw instances:

- `GET /status`
- `POST /users/register`
- `POST /users/availability`
- `GET /tasks/open?limit=3&viewer=%2B<phone>` (filters out your own tasks)
- `GET /tasks/{id}?viewer=%2B<phone>` (redacts private fields for non-participants)
- `POST /tasks` (create)
- `POST /tasks/propose`
- `POST /tasks/accept`
- `POST /tasks/award`
- `POST /tasks/update` (awarded worker only)
- `POST /tasks/submit`
- `POST /tasks/approve`

---

## Development notes / TODO

- Auth + rate limiting (required before real public usage)
- Worker reputation + anti-spam
- Stripe Connect (marketplace payments)
- Optional worker polling loop (so offers feel instant)
