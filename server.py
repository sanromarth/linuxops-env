"""FastAPI server for LinuxOps-Env."""

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional

from environment.linux_env import LinuxOpsEnvironment
from environment.grader import grade_environment
from environment.tasks import list_tasks, TASKS

app = FastAPI(
    title="LinuxOps-Env",
    description="Linux ops remediation env for AI agent training",
    version="2.1.0",
)

env = LinuxOpsEnvironment()


class ResetRequest(BaseModel):
    task_id: str = Field(
        default="security_audit",
        description="one of: security_audit, provisioning_repair, log_audit, incident_response, certificate_exposure",
    )

class StepRequest(BaseModel):
    command: str = Field(description="chmod | chown | ls | stat | disable_service")
    args: dict = Field(default_factory=dict)


@app.get("/", tags=["Info"])
def root():
    return {
        "project": "LinuxOps-Env",
        "version": "2.1.0",
        "tasks": list(TASKS.keys()),
        "endpoints": ["/tasks", "/reset", "/step", "/state", "/grader", "/baseline", "/docs"],
    }


@app.get("/tasks", tags=["Tasks"])
def tasks():
    return {"tasks": list_tasks()}


@app.post("/reset", tags=["Environment"])
def reset(req: Optional[ResetRequest] = None):
    task_id = req.task_id if req else "security_audit"
    return env.reset(task_id)


@app.post("/step", tags=["Environment"])
def step(req: StepRequest):
    action = {"command": req.command, "args": req.args}
    obs, reward, done, info = env.step(action)
    return {"observation": obs, "reward": reward, "done": done, "info": info}


@app.get("/state", tags=["Environment"])
def state():
    return env.state()


@app.get("/grader", tags=["Grading"])
def grader():
    return grade_environment(env).model_dump()


@app.get("/history", tags=["Grading"])
def history():
    return {"steps": len(env.history), "history": env.history}


@app.post("/baseline", tags=["Baseline"])
def baseline():
    """runs oracle baseline on all tasks, returns scores"""
    from baseline_agent import run_oracle_all_tasks
    return run_oracle_all_tasks()
