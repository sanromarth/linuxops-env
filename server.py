"""FastAPI server for LinuxOps-Env."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from environment.linux_env import LinuxOpsEnvironment
from environment.grader import grade_environment
from environment.tasks import list_tasks, TASKS

app = FastAPI(
    title="LinuxOps-Env",
    description="Linux ops remediation env for AI agent training",
    version="2.2.0",
)

# per-episode session store (not one global env)
sessions: dict[str, LinuxOpsEnvironment] = {}
MAX_SESSIONS = 100


def _get_env(episode_id: str) -> LinuxOpsEnvironment:
    """look up an episode by id, raise 400 if not found."""
    if episode_id not in sessions:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown episode_id: '{episode_id}'. Call /reset first.",
        )
    return sessions[episode_id]


def _cleanup_old_sessions():
    """drop oldest sessions if we're over the limit."""
    if len(sessions) > MAX_SESSIONS:
        oldest = list(sessions.keys())[: len(sessions) - MAX_SESSIONS]
        for k in oldest:
            del sessions[k]


class ResetRequest(BaseModel):
    task_id: str = Field(
        default="security_audit",
        description="one of: security_audit, provisioning_repair, log_audit, incident_response, certificate_exposure",
    )

class StepRequest(BaseModel):
    episode_id: str = Field(description="episode id from /reset")
    command: str = Field(description="chmod | chown | ls | stat | disable_service")
    args: dict = Field(default_factory=dict)

class EpisodeRequest(BaseModel):
    episode_id: str = Field(description="episode id from /reset")


@app.get("/", tags=["Info"])
def root():
    return {
        "project": "LinuxOps-Env",
        "version": "2.2.0",
        "tasks": list(TASKS.keys()),
        "endpoints": ["/tasks", "/reset", "/step", "/state", "/grader", "/baseline", "/docs"],
    }


@app.get("/tasks", tags=["Tasks"])
def tasks():
    return {"tasks": list_tasks()}


@app.post("/reset", tags=["Environment"])
def reset(req: Optional[ResetRequest] = None):
    task_id = req.task_id if req else "security_audit"
    if task_id not in TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id: '{task_id}'. Valid: {list(TASKS.keys())}",
        )
    env = LinuxOpsEnvironment()
    result = env.reset(task_id)
    sessions[env.episode_id] = env
    _cleanup_old_sessions()
    return result


@app.post("/step", tags=["Environment"])
def step(req: StepRequest):
    env = _get_env(req.episode_id)
    action = {"command": req.command, "args": req.args}
    obs, reward, done, info = env.step(action)
    return {"observation": obs, "reward": reward, "done": done, "info": info}


@app.post("/state", tags=["Environment"])
def state(req: EpisodeRequest):
    env = _get_env(req.episode_id)
    return env.state()


@app.post("/grader", tags=["Grading"])
def grader(req: EpisodeRequest):
    env = _get_env(req.episode_id)
    return grade_environment(env).model_dump()


@app.post("/history", tags=["Grading"])
def history(req: EpisodeRequest):
    env = _get_env(req.episode_id)
    return {"steps": len(env.history), "history": env.history}


@app.post("/baseline", tags=["Baseline"])
def baseline():
    """runs oracle baseline on all tasks, returns scores"""
    from baseline_agent import run_oracle_all_tasks
    return run_oracle_all_tasks()
