"""
Task registry for LinuxOps-Env.

each task = a sysadmin incident with broken files/services
that the agent has to fix.
"""

from __future__ import annotations
from typing import Any

TASKS: dict[str, dict[str, Any]] = {

    # task 1: easy - just fix permissions
    "security_audit": {
        "difficulty": "easy",
        "description": "Fix broken file permissions on authentication-related files.",
        "ticket": (
            "Security audit found overly permissive file modes on "
            "authentication-related files on jumpbox-01. Repair immediately."
        ),
        "host": "jumpbox-01",
        "incident": "security_audit_failed",
        "available_actions": ["chmod", "ls", "stat"],
        "max_steps": 10,
        "initial_files": {
            "/home/sanro/.ssh/authorized_keys": {"permissions": "777", "owner": "sanro"},
            "/etc/shadow":                      {"permissions": "777", "owner": "root"},
            "/etc/sudoers":                     {"permissions": "666", "owner": "root"},
            "/etc/passwd":                      {"permissions": "644", "owner": "root"},
        },
        "expected_state": {
            "files": {
                "/home/sanro/.ssh/authorized_keys": {"permissions": "600"},
                "/etc/shadow":                      {"permissions": "640"},
                "/etc/sudoers":                     {"permissions": "440"},
            },
        },
        "penalties": {},
        "log_context": [],
    },

    # task 2: medium - perms + ownership
    "provisioning_repair": {
        "difficulty": "medium",
        "description": "Fix mixed permission and ownership issues caused by a broken deployment script.",
        "ticket": (
            "Deployment script bug created mixed ownership and permission "
            "issues on app-server-03 after user provisioning. Multiple files "
            "need both chmod and chown repairs."
        ),
        "host": "app-server-03",
        "incident": "provisioning_failure",
        "available_actions": ["chmod", "chown", "ls", "stat"],
        "max_steps": 8,
        "initial_files": {
            "/etc/ssh/sshd_config": {"permissions": "777", "owner": "nobody"},
            "/var/log/auth.log":    {"permissions": "777", "owner": "nobody"},
            "/etc/crontab":         {"permissions": "666", "owner": "sanro"},
            "/etc/hostname":        {"permissions": "644", "owner": "root"},
        },
        "expected_state": {
            "files": {
                "/etc/ssh/sshd_config": {"permissions": "600", "owner": "root"},
                "/var/log/auth.log":    {"permissions": "640", "owner": "syslog"},
                "/etc/crontab":         {"permissions": "644", "owner": "root"},
            },
        },
        "penalties": {},
        "log_context": [],
    },

    # task 3: hard - files + services + traps
    "incident_response": {
        "difficulty": "hard",
        "description": "Recover a Linux host after a bad config rollout with multiple security risks.",
        "ticket": (
            "On-call alert: compliance scan failed on db-server-07 after "
            "bad config rollout. Multiple sensitive files have wrong "
            "permissions and ownership. Telnet is running. "
            "Fix without breaking SSH access."
        ),
        "host": "db-server-07",
        "incident": "compliance_scan_failed",
        "available_actions": ["chmod", "chown", "disable_service", "ls", "stat"],
        "max_steps": 10,
        "initial_files": {
            "/etc/shadow":          {"permissions": "644", "owner": "nobody"},
            "/etc/gshadow":         {"permissions": "644", "owner": "nobody"},
            "/etc/ssh/sshd_config": {"permissions": "777", "owner": "sanro"},
            "/root/.bashrc":        {"permissions": "666", "owner": "nobody"},
        },
        "initial_services": {
            "telnet": "enabled",
            "sshd":   "enabled",
        },
        "expected_state": {
            "files": {
                "/etc/shadow":          {"permissions": "640", "owner": "root"},
                "/etc/gshadow":         {"permissions": "640", "owner": "root"},
                "/etc/ssh/sshd_config": {"permissions": "600", "owner": "root"},
                "/root/.bashrc":        {"permissions": "644", "owner": "root"},
            },
            "services": {
                "telnet": "disabled",
            },
        },
        "penalties": {
            "chmod_777":    -0.3,
            "disable_sshd": -0.5,
        },
        "log_context": [],
    },
}


def get_task(task_id: str) -> dict[str, Any]:
    if task_id not in TASKS:
        valid = ", ".join(TASKS.keys())
        raise ValueError(f"Unknown task '{task_id}'. valid ones: {valid}")
    return TASKS[task_id]


def list_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_id": tid,
            "difficulty": t["difficulty"],
            "description": t["description"],
            "ticket": t["ticket"],
            "available_actions": t["available_actions"],
            "max_steps": t["max_steps"],
        }
        for tid, t in TASKS.items()
    ]
