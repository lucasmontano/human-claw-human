---
name: clawmarket
description: "OpenClaw-integrated human-in-the-loop chore marketplace with no public UI. Use when you need to route a task from one OpenClaw user/agent to another human worker (availability keywords: I'm free / I'm busy), collect accepts or proposals, award work, and return results via chat."
---

# Clawmarket

## Overview

Clawmarket is a central, OpenClaw-mediated task marketplace: requesters create chores via chat, available workers receive offers via chat, and results come back via chat.

The marketplace backend is a simple task state machine + persistence; OpenClaw is the UI on both ends.

## Workflow (natural language)

### 1) Worker declares availability

When a user says **“I’m free”**, mark them AVAILABLE.
When they say **“I’m busy”**, mark them UNAVAILABLE.

When a worker becomes AVAILABLE, immediately show the **top 3 open chores**.

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

### 4) Award + delivery loop

- If multiple proposals exist, ask requester to pick a worker.
- After award, only the awarded worker can submit.
- Requester can approve or request revision.

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
