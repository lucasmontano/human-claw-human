# Clawmarket API (backend state machine)

This is the minimal backend contract used by OpenClaw to coordinate chores.

## Entities

### User
- `phone`: string (E.164-ish, e.g. +316...)
- `role`: worker | requester | both
- `available`: boolean (derived by OpenClaw chat intent: “I’m free” / “I’m busy”)

### Task
- `id`: T000001
- `status`: open | awarded | submitted | approved | rejected
- `requester`: phone
- `title`: string
- `instructions`: string
- `budget`: number
- `proposals`: [{ worker, price, eta, note, at }]
- `acceptedBy`: [phone]
- `awardedTo`: phone|null
- `submission`: { worker, result, at }|null

## Operations (CLI-backed for now)

Currently implemented as a local CLI script on the central VPS:
- `/root/.openclaw/workspace/scripts/clawmarket.py`

### init
`clawmarket.py init`

### register
`clawmarket.py register --phone +31... --role worker|requester|both`

### create task
`clawmarket.py create-task --requester +31... --title "..." --budget 20 --instructions "..." [--category general]`

### list open tasks
`clawmarket.py open-tasks`

### propose
`clawmarket.py propose --task T000001 --worker +31... --price 25 --eta "2h" --note "..."`

### accept
`clawmarket.py accept --task T000001 --worker +31...`

### award
`clawmarket.py award --task T000001 --requester +31... --worker +31...`

### submit
`clawmarket.py submit --task T000001 --worker +31... --result "..."`

### approve
`clawmarket.py approve --task T000001 --requester +31...`

## Notes
- Natural-language parsing and message routing happens in OpenClaw (not in the backend).
- Payments are intentionally out of scope for v1.
