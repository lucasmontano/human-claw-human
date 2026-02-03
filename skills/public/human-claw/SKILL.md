---
name: human-claw
description: "OpenClaw-integrated human-in-the-loop chore marketplace with no public UI. Use when you need to route a task from one OpenClaw user/agent to another human worker (availability keywords: I'm free / I'm busy), collect accepts or proposals, award work, and return results via chat."
---

# Human Claw
## Overview

Clawmarket is a central, OpenClaw-mediated task marketplace: requesters create chores via chat, available workers receive offers via chat, and results come back via chat.

The marketplace backend is a simple task state machine + persistence; OpenClaw is the UI on both ends.

## Workflow (natural language)

### 1) Worker declares availability

Treat availability as an *intent*, not an exact command.

Mark a worker AVAILABLE when they say anything like:
- “I’m free”, “I’m free to get some work”, “I need a job”, “available”, “got work?”
- Non-English equivalents (pt-BR/spa/fr/etc.) that clearly mean they’re available

Mark a worker UNAVAILABLE when they say anything like:
- “I’m busy”, “not available”, “stop sending”, “offline”
- Non-English equivalents

UNAVAILABLE affects **new offers only** (it does not cancel an already-awarded task).

Policy: **Always** mark AVAILABLE when the intent appears (even if context is ambiguous).

When a worker becomes AVAILABLE, immediately show **up to 3** open chores (most recent first).

### 2) Requester creates a chore

When a requester says something like:
- “I need a human to …”
- “Can someone … for €20?”

Create a task with:
- title (short)
- instructions (full)
- budget (number; can be “unknown” if missing)

Then broadcast the new task only to AVAILABLE workers.

### 3) Worker responds

Workers can respond naturally:
- Accept: “I’ll take it” / “accepted”
- Propose: “I can do it for €X, ETA Y”
- Deliver: “Here’s the result: …” (include links/screenshots/files)

### 4) Award + private delivery loop

- If multiple proposals exist, ask requester to pick a worker.
- After award, only the awarded worker can submit **and post status updates**.
- Privacy: after award, communication is **requester ↔ awarded worker only**.
- Requester can approve or request revision.

### Status + updates (natural language)

Worker:
- “update on T000123: started / blocked / 50% done / ETA 30m”
- “status on T000123: …”

Requester:
- “status T000123?”
- “ping the worker”

Automation:
- If a task is awarded and there is **no update for 30 minutes**, send a one-time private nudge to the awarded worker asking for status.

## Safety guardrails

Do not facilitate ToS bypass or impersonation.

Examples:
- If someone asks “create a Reddit/X account for me”, reframe into: **guide the requester through signup** rather than having a worker impersonate them or use temp emails.
- Allow “human assistance” tasks that are about guidance, verification, research, QA, and manual steps that the requester owns.

## Backend interface

The reference spec lives in `references/api.md`.

Minimal operations:
- create task
- list open tasks
- accept / propose
- award
- submit
- approve

## Operator defaults

- Identity = WhatsApp phone number.
- Broadcast only to AVAILABLE workers.
- Keep task messages short (WhatsApp-friendly).
