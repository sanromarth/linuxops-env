#!/usr/bin/env python3
"""
baseline agent for linuxops-env.

oracle mode: hardcoded correct answers, proves tasks are solvable.
"""

import argparse
import json
import os
import sys
from typing import Any

from environment.linux_env import LinuxOpsEnvironment
from environment.grader import grade_environment
from environment.tasks import TASKS

ORACLE_SOLUTIONS: dict[str, list[dict[str, Any]]] = {
    "security_audit": [
        {"command": "chmod", "args": {"path": "/home/sanro/.ssh/authorized_keys", "mode": "600"}},
        {"command": "chmod", "args": {"path": "/etc/shadow", "mode": "640"}},
        {"command": "chmod", "args": {"path": "/etc/sudoers", "mode": "440"}},
    ],
    "provisioning_repair": [
        {"command": "chmod", "args": {"path": "/etc/ssh/sshd_config", "mode": "600"}},
        {"command": "chown", "args": {"path": "/etc/ssh/sshd_config", "owner": "root"}},
        {"command": "chmod", "args": {"path": "/var/log/auth.log", "mode": "640"}},
        {"command": "chown", "args": {"path": "/var/log/auth.log", "owner": "syslog"}},
        {"command": "chmod", "args": {"path": "/etc/crontab", "mode": "644"}},
        {"command": "chown", "args": {"path": "/etc/crontab", "owner": "root"}},
    ],
    "incident_response": [
        {"command": "chmod",           "args": {"path": "/etc/shadow",          "mode": "640"}},
        {"command": "chown",           "args": {"path": "/etc/shadow",          "owner": "root"}},
        {"command": "chmod",           "args": {"path": "/etc/gshadow",         "mode": "640"}},
        {"command": "chown",           "args": {"path": "/etc/gshadow",         "owner": "root"}},
        {"command": "chmod",           "args": {"path": "/etc/ssh/sshd_config", "mode": "600"}},
        {"command": "chown",           "args": {"path": "/etc/ssh/sshd_config", "owner": "root"}},
        {"command": "chmod",           "args": {"path": "/root/.bashrc",        "mode": "644"}},
        {"command": "chown",           "args": {"path": "/root/.bashrc",        "owner": "root"}},
        {"command": "disable_service", "args": {"name": "telnet"}},
    ],
}


def run_oracle_single(task_id, env=None):
    if env is None:
        env = LinuxOpsEnvironment()
    obs = env.reset(task_id)
    cfg = env.task_config
    print(f"  [{cfg['difficulty'].upper()}] {task_id}")
    for action in ORACLE_SOLUTIONS.get(task_id, []):
        obs, reward, done, info = env.step(action)
        cmd = action["command"]
        args_str = " ".join(f"{k}={v}" for k, v in action["args"].items())
        ok = "ok" if info["result"]["success"] else "FAIL"
        print(f"    {ok}: {cmd} {args_str}  (reward={reward:.3f})")
        if done:
            break
    result = grade_environment(env)
    tag = "PASSED" if result.passed else "FAILED"
    print(f"  Grade: {result.score} [{tag}] ({result.steps_used}/{result.max_steps} steps)\n")
    return {"task_id": task_id, "score": result.score, "passed": result.passed,
            "steps_used": result.steps_used, "max_steps": result.max_steps}


def run_oracle_all_tasks():
    results = []
    env = LinuxOpsEnvironment()
    for task_id in TASKS:
        r = run_oracle_single(task_id, env)
        results.append(r)
    avg = sum(r["score"] for r in results) / len(results)
    return {"mode": "oracle", "tasks": results, "average_score": round(avg, 3),
            "all_passed": all(r["passed"] for r in results)}


if __name__ == "__main__":
    print("LinuxOps-Env Baseline Agent\n" + "=" * 40 + "\n")
    results = []
    for tid in TASKS:
        r = run_oracle_single(tid)
        results.append(r)
    print("=" * 40)
    for r in results:
        s = "PASS" if r.get("passed") else "FAIL"
        print(f"  {r['task_id']}: {r['score']:.3f} [{s}]")
    avg = sum(r["score"] for r in results) / len(results)
    print(f"  Average: {avg:.3f}\n" + "=" * 40)
    sys.exit(0 if all(r.get("passed") for r in results) else 1)
