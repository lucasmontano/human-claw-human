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
def open_tasks(limit: int = 50):
    out = cm.open_tasks_cmd(None)  # type: ignore
    tasks = out.get("tasks", [])
    return {"ok": True, "tasks": tasks[:limit]}


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    st = _state()
    t = st.get("tasks", {}).get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="task_not_found")
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
