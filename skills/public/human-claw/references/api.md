# Human Claw API (backend state machine)

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
- `/root/.openclaw/workspace/scripts/human-claw.py`

### init
`human-claw.py init`

### register
`human-claw.py register --phone +31... --role worker|requester|both`

### create task
`human-claw.py create-task --requester +31... --title "..." --budget 20 --instructions "..." [--category general]`

### list open tasks
`human-claw.py open-tasks`

### propose
`human-claw.py propose --task T000001 --worker +31... --price 25 --eta "2h" --note "..."`

### accept
`human-claw.py accept --task T000001 --worker +31...`

### award
`human-claw.py award --task T000001 --requester +31... --worker +31...`

### update (private status update by awarded worker)
`human-claw.py update --task T000001 --worker +31... --message "50% done" --eta "30m"`

### submit
`human-claw.py submit --task T000001 --worker +31... --result "..."`

### approve
`human-claw.py approve --task T000001 --requester +31...`

## Notes
- Natural-language parsing and message routing happens in OpenClaw (not in the backend).
- Payments are intentionally out of scope for v1.
