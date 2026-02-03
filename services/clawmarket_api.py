#!/usr/bin/env python3
"""ClawMarket HTTP API (MVP, no auth, no payments).

Runs on a central VPS. OpenClaw instances call this API.
Identity: phone number string.
Storage: workspace/state/clawmarket.json (same as scripts/clawmarket.py).

This is intentionally minimal. Add auth/rate limits before going truly public.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Reuse the CLI state machine implementation.
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

import clawmarket as cm  # type: ignore

app = FastAPI(title="ClawMarket API", version="0.1.0")


class RegisterIn(BaseModel):
    phone: str
    role: str = Field(default="both", pattern="^(worker|requester|both)$")


class AvailabilityIn(BaseModel):
    phone: str
    available: bool


class CreateTaskIn(BaseModel):
    requester: str
    title: str
    instructions: str
    budget: float
    category: str = "general"
    deadline: Optional[str] = None


class ProposeIn(BaseModel):
    task: str
    worker: str
    price: float
    eta: Optional[str] = None
    note: Optional[str] = None


class AcceptIn(BaseModel):
    task: str
    worker: str


class AwardIn(BaseModel):
    task: str
    requester: str
    worker: str


class UpdateIn(BaseModel):
    task: str
    worker: str
    message: str
    eta: Optional[str] = None


class SubmitIn(BaseModel):
    task: str
    worker: str
    result: str


class ApproveIn(BaseModel):
    task: str
    requester: str


def _state() -> Dict[str, Any]:
    return cm._load()  # noqa: SLF001 (MVP)


def _save(st: Dict[str, Any]) -> None:
    cm._save(st)  # noqa: SLF001


@app.get("/status")
def status():
    st = _state()
    users = st.get("users", {})
    tasks = st.get("tasks", {})
    open_tasks = sum(1 for t in tasks.values() if t.get("status") == "open")
    return {
        "ok": True,
        "time": int(time.time()),
        "counts": {
            "users": len(users),
            "tasks": len(tasks),
            "open_tasks": open_tasks,
        },
    }


@app.post("/users/register")
def register(inp: RegisterIn):
    class A:  # argparse-like
        phone = inp.phone
        role = inp.role

    return cm.register_cmd(A())


@app.post("/users/availability")
def set_availability(inp: AvailabilityIn):
    st = _state()
    phone = cm._norm_phone(inp.phone)  # noqa

    u = st.get("users", {}).get(phone)
    if not u:
        # auto-register
        st.setdefault("users", {})[phone] = {
            "phone": phone,
            "role": "both",
            "createdAt": int(time.time()),
            "updatedAt": int(time.time()),
            "reputation": {"approved": 0, "rejected": 0, "onTime": 0, "late": 0},
        }
        u = st["users"][phone]

    u["available"] = bool(inp.available)
    u["updatedAt"] = int(time.time())
    st["users"][phone] = u
    _save(st)
    return {"ok": True, "user": u}


@app.get("/tasks/open")
def open_tasks(limit: int = 50, viewer: Optional[str] = None):
    out = cm.open_tasks_cmd(None)  # type: ignore
    tasks = out.get("tasks", [])

    if viewer:
        v = cm._norm_phone(viewer)  # noqa
        # Do not show the viewer their own requested tasks when browsing as a worker.
        tasks = [t for t in tasks if t.get("requester") != v]

    return {"ok": True, "tasks": tasks[:limit]}


@app.get("/tasks/{task_id}")
def get_task(task_id: str, viewer: Optional[str] = None):
    """Return a task.

    Privacy: if `viewer` is provided and is not the requester or the awarded worker,
    redact private fields once the task is awarded.
    """
    st = _state()
    t = st.get("tasks", {}).get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="task_not_found")

    if viewer:
        v = cm._norm_phone(viewer)  # noqa
        is_requester = v == t.get("requester")
        is_awarded = v == t.get("awardedTo")
        if t.get("status") in ("awarded", "submitted", "approved") and not (is_requester or is_awarded):
            redacted = dict(t)
            for k in ("requester", "awardedTo", "submission", "updates", "proposals", "acceptedBy"):
                redacted.pop(k, None)
            return {"ok": True, "task": redacted, "redacted": True}

    return {"ok": True, "task": t}


@app.post("/tasks")
def create_task(inp: CreateTaskIn):
    class A:
        requester = inp.requester
        title = inp.title
        instructions = inp.instructions
        budget = inp.budget
        category = inp.category
        deadline = inp.deadline

    return cm.create_task_cmd(A())


@app.post("/tasks/propose")
def propose(inp: ProposeIn):
    class A:
        task = inp.task
        worker = inp.worker
        price = inp.price
        eta = inp.eta
        note = inp.note

    return cm.propose_cmd(A())


@app.post("/tasks/accept")
def accept(inp: AcceptIn):
    class A:
        task = inp.task
        worker = inp.worker

    return cm.accept_cmd(A())


@app.post("/tasks/award")
def award(inp: AwardIn):
    class A:
        task = inp.task
        requester = inp.requester
        worker = inp.worker

    return cm.award_cmd(A())


@app.post("/tasks/update")
def update(inp: UpdateIn):
    class A:
        task = inp.task
        worker = inp.worker
        message = inp.message
        eta = inp.eta

    return cm.update_cmd(A())


@app.post("/tasks/submit")
def submit(inp: SubmitIn):
    class A:
        task = inp.task
        worker = inp.worker
        result = inp.result

    return cm.submit_cmd(A())


@app.post("/tasks/approve")
def approve(inp: ApproveIn):
    class A:
        task = inp.task
        requester = inp.requester

    return cm.approve_cmd(A())


@app.get("/admin/needs-nudge")
def needs_nudge(silenceSeconds: int = 1800, limit: int = 50):
    """Return awarded tasks with no update for >silenceSeconds and not yet nudged."""
    st = _state()
    now = int(time.time())
    out = []
    for t in st.get("tasks", {}).values():
        if t.get("status") != "awarded":
            continue
        last = t.get("lastUpdateAt") or t.get("updatedAt") or t.get("createdAt")
        if not last:
            continue
        if now - int(last) <= int(silenceSeconds):
            continue
        if t.get("lastNudgedAt"):
            # one-time auto nudge
            continue
        worker = t.get("awardedTo")
        requester = t.get("requester")
        if not worker or not requester:
            continue
        out.append({"task": t.get("id"), "worker": worker, "requester": requester})
    return {"ok": True, "tasks": out[:limit]}


class MarkNudgedIn(BaseModel):
    task: str


@app.post("/admin/mark-nudged")
def mark_nudged(inp: MarkNudgedIn):
    st = _state()
    t = st.get("tasks", {}).get(inp.task)
    if not t:
        raise HTTPException(status_code=404, detail="task_not_found")
    t["lastNudgedAt"] = int(time.time())
    t["updatedAt"] = int(time.time())
    st["tasks"][inp.task] = t
    _save(st)
    return {"ok": True, "task": inp.task, "lastNudgedAt": t["lastNudgedAt"]}
