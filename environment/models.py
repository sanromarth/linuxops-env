"""Pydantic models for LinuxOps-Env."""

from typing import Optional
from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    path: str
    permissions: str
    owner: str
    status: str = Field(description="insecure | critical | ok")


class ServiceInfo(BaseModel):
    name: str
    state: str = Field(description="enabled | disabled")


class Observation(BaseModel):
    host: str
    incident: str
    task_id: str
    description: str
    files: list[FileInfo]
    services: list[ServiceInfo] = []
    logs: list[str] = Field(default_factory=list, description="log/audit entries for context")
    steps_remaining: int
    step_count: int
    done: bool
    message: str


class Action(BaseModel):
    command: str = Field(description="chmod | chown | ls | stat | disable_service")
    args: dict = Field(default_factory=dict)


class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: dict


class EnvState(BaseModel):
    task_id: Optional[str] = None
    episode_id: Optional[str] = None
    step_count: int = 0
    max_steps: int = 0
    done: bool = False
    observation: Optional[Observation] = None


class FileGradeDetail(BaseModel):
    path: str
    expected_perm: str
    actual_perm: str
    perm_correct: bool
    expected_owner: Optional[str] = None
    actual_owner: Optional[str] = None
    owner_correct: bool = True


class ServiceGradeDetail(BaseModel):
    name: str
    expected_state: str
    actual_state: str
    correct: bool


class GradeResult(BaseModel):
    task_id: str
    score: float
    passed: bool
    steps_used: int
    max_steps: int
    file_details: list[FileGradeDetail] = []
    service_details: list[ServiceGradeDetail] = []


class TaskInfo(BaseModel):
    task_id: str
    difficulty: str
    description: str
    ticket: str
    available_actions: list[str]
    max_steps: int
