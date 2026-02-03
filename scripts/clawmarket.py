#!/usr/bin/env python3
"""ClawMarket: minimal OpenClaw-mediated human-task marketplace (no UI, no payments).

Storage: JSON file in workspace/state/clawmarket.json
Identity: WhatsApp phone number (string) as provided by OpenClaw inbound metadata.

This script is intentionally dumb: it is a state machine + CRUD.
The OpenClaw agent (junior) is the chat/UI layer.

Usage examples:
  clawmarket.py init
  clawmarket.py register --phone +316...
  clawmarket.py create-task --requester +316... --title "Do X" --budget 20 --instructions "..."
  clawmarket.py open-tasks
  clawmarket.py propose --task T123 --worker +31... --price 25 --eta "2h" --note "..."
  clawmarket.py accept --task T123 --worker +31...
  clawmarket.py award --task T123 --requester +31... --worker +31...
  clawmarket.py submit --task T123 --worker +31... --result "..."
  clawmarket.py approve --task T123 --requester +31...

All commands print JSON to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "clawmarket.json")


def _now() -> int:
    return int(time.time())


def _load() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": 1, "createdAt": _now(), "users": {}, "tasks": {}, "seq": 0}


def _save(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def _norm_phone(p: str) -> str:
    p = p.strip()
    # very light normalization; keep leading +.
    if not p.startswith("+"):
        # allow raw digits
        p = "+" + re.sub(r"\D+", "", p)
    return p


def _new_task_id(state: Dict[str, Any]) -> str:
    state["seq"] = int(state.get("seq") or 0) + 1
    return f"T{state['seq']:06d}"


def init_cmd(_: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    _save(st)
    return {"ok": True, "statePath": STATE_PATH}


def register_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    phone = _norm_phone(args.phone)
    u = st["users"].get(phone) or {}
    u.update(
        {
            "phone": phone,
            "role": args.role,
            "createdAt": u.get("createdAt") or _now(),
            "updatedAt": _now(),
            "reputation": u.get("reputation")
            or {"approved": 0, "rejected": 0, "onTime": 0, "late": 0},
        }
    )
    st["users"][phone] = u
    _save(st)
    return {"ok": True, "user": u}


def create_task_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    requester = _norm_phone(args.requester)

    if requester not in st["users"]:
        st["users"][requester] = {
            "phone": requester,
            "role": "requester",
            "createdAt": _now(),
            "updatedAt": _now(),
            "reputation": {"approved": 0, "rejected": 0, "onTime": 0, "late": 0},
        }

    tid = _new_task_id(st)
    task = {
        "id": tid,
        "status": "open",  # open -> awarded -> submitted -> approved | rejected
        "requester": requester,
        "title": args.title.strip(),
        "instructions": args.instructions.strip(),
        "budget": float(args.budget),
        "category": args.category,
        "deadline": args.deadline,
        "createdAt": _now(),
        "updatedAt": _now(),
        "proposals": [],
        "acceptedBy": [],
        "awardedTo": None,
        "submission": None,
        "updates": [],
        "lastUpdateAt": None,
        "lastNudgedAt": None,
        "history": [{"at": _now(), "event": "created", "by": requester}],
    }
    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task}


def open_tasks_cmd(_: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tasks = [t for t in st["tasks"].values() if t.get("status") == "open"]
    tasks.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
    return {"ok": True, "tasks": tasks}


def propose_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tid = args.task
    worker = _norm_phone(args.worker)
    if tid not in st["tasks"]:
        return {"ok": False, "error": "task_not_found"}
    task = st["tasks"][tid]
    if task["status"] != "open":
        return {"ok": False, "error": "task_not_open", "status": task["status"]}

    if worker not in st["users"]:
        st["users"][worker] = {
            "phone": worker,
            "role": "worker",
            "createdAt": _now(),
            "updatedAt": _now(),
            "reputation": {"approved": 0, "rejected": 0, "onTime": 0, "late": 0},
        }

    prop = {
        "worker": worker,
        "price": float(args.price),
        "eta": args.eta,
        "note": args.note,
        "at": _now(),
    }
    task["proposals"].append(prop)
    task["updatedAt"] = _now()
    task["history"].append({"at": _now(), "event": "proposal", "by": worker, "data": prop})
    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task, "proposal": prop}


def accept_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tid = args.task
    worker = _norm_phone(args.worker)
    if tid not in st["tasks"]:
        return {"ok": False, "error": "task_not_found"}
    task = st["tasks"][tid]
    if task["status"] != "open":
        return {"ok": False, "error": "task_not_open", "status": task["status"]}

    if worker not in st["users"]:
        st["users"][worker] = {
            "phone": worker,
            "role": "worker",
            "createdAt": _now(),
            "updatedAt": _now(),
            "reputation": {"approved": 0, "rejected": 0, "onTime": 0, "late": 0},
        }

    if worker not in task["acceptedBy"]:
        task["acceptedBy"].append(worker)
    task["updatedAt"] = _now()
    task["history"].append({"at": _now(), "event": "accept", "by": worker})
    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task}


def award_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tid = args.task
    requester = _norm_phone(args.requester)
    worker = _norm_phone(args.worker)
    if tid not in st["tasks"]:
        return {"ok": False, "error": "task_not_found"}
    task = st["tasks"][tid]
    if task["requester"] != requester:
        return {"ok": False, "error": "not_requester"}
    if task["status"] != "open":
        return {"ok": False, "error": "task_not_open", "status": task["status"]}

    task["status"] = "awarded"
    task["awardedTo"] = worker
    task["updatedAt"] = _now()
    task["lastUpdateAt"] = _now()  # start the clock
    task["history"].append({"at": _now(), "event": "award", "by": requester, "to": worker})
    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task}


def update_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tid = args.task
    worker = _norm_phone(args.worker)
    if tid not in st["tasks"]:
        return {"ok": False, "error": "task_not_found"}
    task = st["tasks"][tid]

    # Privacy: only awarded worker can post updates, and only after award.
    if task.get("awardedTo") != worker:
        return {"ok": False, "error": "not_awarded_worker"}
    if task["status"] not in ("awarded", "submitted"):
        return {"ok": False, "error": "task_not_in_progress", "status": task["status"]}

    upd = {
        "by": worker,
        "message": args.message,
        "eta": args.eta,
        "at": _now(),
    }
    task.setdefault("updates", []).append(upd)
    task["lastUpdateAt"] = upd["at"]
    task["updatedAt"] = _now()
    task["history"].append({"at": _now(), "event": "update", "by": worker, "data": upd})
    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task, "update": upd}


def submit_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tid = args.task
    worker = _norm_phone(args.worker)
    if tid not in st["tasks"]:
        return {"ok": False, "error": "task_not_found"}
    task = st["tasks"][tid]
    if task["status"] != "awarded":
        return {"ok": False, "error": "task_not_awarded", "status": task["status"]}
    if task.get("awardedTo") != worker:
        return {"ok": False, "error": "not_awarded_worker"}

    sub = {"worker": worker, "result": args.result, "at": _now()}
    task["status"] = "submitted"
    task["submission"] = sub
    task["updatedAt"] = _now()
    task["history"].append({"at": _now(), "event": "submit", "by": worker})
    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task}


def approve_cmd(args: argparse.Namespace) -> Dict[str, Any]:
    st = _load()
    tid = args.task
    requester = _norm_phone(args.requester)
    if tid not in st["tasks"]:
        return {"ok": False, "error": "task_not_found"}
    task = st["tasks"][tid]
    if task["requester"] != requester:
        return {"ok": False, "error": "not_requester"}
    if task["status"] != "submitted":
        return {"ok": False, "error": "task_not_submitted", "status": task["status"]}

    task["status"] = "approved"
    task["updatedAt"] = _now()
    task["history"].append({"at": _now(), "event": "approve", "by": requester})

    worker = task.get("awardedTo")
    if worker and worker in st["users"]:
        st["users"][worker]["reputation"]["approved"] += 1

    st["tasks"][tid] = task
    _save(st)
    return {"ok": True, "task": task}


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    r = sub.add_parser("register")
    r.add_argument("--phone", required=True)
    r.add_argument("--role", choices=["worker", "requester", "both"], default="both")

    c = sub.add_parser("create-task")
    c.add_argument("--requester", required=True)
    c.add_argument("--title", required=True)
    c.add_argument("--instructions", required=True)
    c.add_argument("--budget", required=True, type=float)
    c.add_argument("--category", default="general")
    c.add_argument("--deadline", default=None)

    sub.add_parser("open-tasks")

    pr = sub.add_parser("propose")
    pr.add_argument("--task", required=True)
    pr.add_argument("--worker", required=True)
    pr.add_argument("--price", required=True, type=float)
    pr.add_argument("--eta", default=None)
    pr.add_argument("--note", default=None)

    ac = sub.add_parser("accept")
    ac.add_argument("--task", required=True)
    ac.add_argument("--worker", required=True)

    aw = sub.add_parser("award")
    aw.add_argument("--task", required=True)
    aw.add_argument("--requester", required=True)
    aw.add_argument("--worker", required=True)

    up = sub.add_parser("update")
    up.add_argument("--task", required=True)
    up.add_argument("--worker", required=True)
    up.add_argument("--message", required=True)
    up.add_argument("--eta", default=None)

    sb = sub.add_parser("submit")
    sb.add_argument("--task", required=True)
    sb.add_argument("--worker", required=True)
    sb.add_argument("--result", required=True)

    ap = sub.add_parser("approve")
    ap.add_argument("--task", required=True)
    ap.add_argument("--requester", required=True)

    args = p.parse_args()

    if args.cmd == "init":
        out = init_cmd(args)
    elif args.cmd == "register":
        out = register_cmd(args)
    elif args.cmd == "create-task":
        out = create_task_cmd(args)
    elif args.cmd == "open-tasks":
        out = open_tasks_cmd(args)
    elif args.cmd == "propose":
        out = propose_cmd(args)
    elif args.cmd == "accept":
        out = accept_cmd(args)
    elif args.cmd == "award":
        out = award_cmd(args)
    elif args.cmd == "update":
        out = update_cmd(args)
    elif args.cmd == "submit":
        out = submit_cmd(args)
    elif args.cmd == "approve":
        out = approve_cmd(args)
    else:
        out = {"ok": False, "error": "unknown_cmd"}

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
