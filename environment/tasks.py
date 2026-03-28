"""
Task registry for LinuxOps-Env.

each task = a sysadmin incident with broken files/services
that the agent has to fix. 5 tasks total, easy to hard.
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
            "/etc/passwd":                      {"permissions": "644", "owner": "root"},  # decoy
        },
        "expected_state": {
            "files": {
                "/home/sanro/.ssh/authorized_keys": {"permissions": "600"},
                "/etc/shadow":                      {"permissions": "640"},
                "/etc/sudoers":                     {"permissions": "440"},
            },
        },
        "penalties": {},
        "log_context": [
            "[AUDIT] WARN: /home/sanro/.ssh/authorized_keys has mode 777 — should be 600",
            "[AUDIT] CRIT: /etc/shadow is world-readable (mode 777) — credential exposure risk",
            "[AUDIT] WARN: /etc/sudoers has mode 666 — should be 440 (read-only root+group)",
            "[AUDIT] OK: /etc/passwd mode 644 — compliant, no action needed",
        ],
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
            "/etc/hostname":        {"permissions": "644", "owner": "root"},  # decoy
        },
        "expected_state": {
            "files": {
                "/etc/ssh/sshd_config": {"permissions": "600", "owner": "root"},
                "/var/log/auth.log":    {"permissions": "640", "owner": "syslog"},
                "/etc/crontab":         {"permissions": "644", "owner": "root"},
            },
        },
        "penalties": {},
        "log_context": [
            "[DEPLOY] ERROR: provision_users.sh ran chown nobody:nobody on /etc/ssh/sshd_config",
            "[DEPLOY] ERROR: log rotation script set /var/log/auth.log to 777",
            "[DEPLOY] WARN: crontab owner changed from root to sanro during provisioning",
            "[DEPLOY] OK: /etc/hostname unaffected by provisioning script",
        ],
    },

    # task 3: medium - log server migration went wrong
    "log_audit": {
        "difficulty": "medium",
        "description": "Fix logging infrastructure after a failed rsyslog migration.",
        "ticket": (
            "Central logging migration on logging-server-02 failed midway. "
            "Log files and rsyslog config have wrong permissions and ownership. "
            "Restore proper access controls so log collection resumes. "
            "Note: audit.log was on a separate mount and was not affected."
        ),
        "host": "logging-server-02",
        "incident": "log_migration_failure",
        "available_actions": ["chmod", "chown", "ls", "stat"],
        "max_steps": 10,
        "initial_files": {
            "/var/log/syslog":          {"permissions": "777", "owner": "nobody"},
            "/var/log/auth.log":        {"permissions": "666", "owner": "nobody"},
            "/etc/rsyslog.conf":        {"permissions": "777", "owner": "sanro"},
            "/var/log/audit/audit.log": {"permissions": "640", "owner": "root"},  # decoy
        },
        "expected_state": {
            "files": {
                "/var/log/syslog":   {"permissions": "640", "owner": "syslog"},
                "/var/log/auth.log": {"permissions": "640", "owner": "syslog"},
                "/etc/rsyslog.conf": {"permissions": "644", "owner": "root"},
            },
        },
        "penalties": {},
        "log_context": [
            "[MIGRATION] ERROR: rsyslog.conf permissions set to 777 during config copy",
            "[MIGRATION] ERROR: /var/log/syslog ownership lost — now owned by nobody",
            "[MIGRATION] WARN: /var/log/auth.log set to world-writable (mode 666)",
            "[MIGRATION] OK: /var/log/audit/audit.log on separate mount — not affected",
            "[SYSLOG] rsyslog stopped — cannot write to log files with current permissions",
        ],
    },

    # task 4: hard - files + services + traps
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
            "sshd":   "enabled",   # trap! don't disable this
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
        "log_context": [
            "[COMPLIANCE] CRITICAL: /etc/shadow readable by non-root (mode 644, owner nobody)",
            "[COMPLIANCE] CRITICAL: /etc/gshadow readable by non-root (mode 644, owner nobody)",
            "[COMPLIANCE] HIGH: sshd_config owned by unprivileged user 'sanro' with mode 777",
            "[COMPLIANCE] MEDIUM: /root/.bashrc has mode 666 and is owned by nobody",
            "[COMPLIANCE] HIGH: telnet service is active on production database host",
            "[COMPLIANCE] INFO: sshd is running — do NOT disable (required for remote access)",
        ],
    },

    # task 5: hard - tls cert renewal gone bad + multiple trap services
    "certificate_exposure": {
        "difficulty": "hard",
        "description": "Secure exposed TLS private keys and configs after a botched certificate renewal.",
        "ticket": (
            "URGENT: Certificate renewal script on web-proxy-01 ran with "
            "wrong umask. TLS private keys are now world-readable. "
            "Nginx config ownership was also corrupted. FTP is running "
            "on this web proxy and must be disabled. "
            "Do NOT disable nginx (HTTPS termination) or sshd (remote access)."
        ),
        "host": "web-proxy-01",
        "incident": "certificate_exposure",
        "available_actions": ["chmod", "chown", "disable_service", "ls", "stat"],
        "max_steps": 12,
        "initial_files": {
            "/etc/ssl/private/server.key":     {"permissions": "644", "owner": "www-data"},
            "/etc/ssl/certs/ca-bundle.crt":    {"permissions": "777", "owner": "nobody"},
            "/etc/nginx/nginx.conf":           {"permissions": "666", "owner": "nobody"},
            "/etc/nginx/sites-enabled/default": {"permissions": "644", "owner": "root"},  # decoy
            "/var/log/nginx/error.log":        {"permissions": "777", "owner": "nobody"},
        },
        "initial_services": {
            "ftp":   "enabled",    # insecure, disable this
            "nginx": "enabled",    # trap! don't disable
            "sshd":  "enabled",    # trap! don't disable
        },
        "expected_state": {
            "files": {
                "/etc/ssl/private/server.key":  {"permissions": "600", "owner": "root"},
                "/etc/ssl/certs/ca-bundle.crt": {"permissions": "644", "owner": "root"},
                "/etc/nginx/nginx.conf":        {"permissions": "644", "owner": "root"},
                "/var/log/nginx/error.log":     {"permissions": "640", "owner": "www-data"},
            },
            "services": {
                "ftp": "disabled",
            },
        },
        "penalties": {
            "chmod_777":     -0.3,
            "disable_nginx": -0.4,
            "disable_sshd":  -0.5,
        },
        "log_context": [
            "[CERT-RENEW] CRITICAL: /etc/ssl/private/server.key is world-readable (mode 644)",
            "[CERT-RENEW] ERROR: CA bundle /etc/ssl/certs/ca-bundle.crt set to mode 777",
            "[CERT-RENEW] WARN: nginx.conf ownership changed to nobody with mode 666",
            "[CERT-RENEW] OK: /etc/nginx/sites-enabled/default unchanged — no action needed",
            "[CERT-RENEW] WARN: nginx error log permissions corrupted (mode 777, owner nobody)",
            "[SECURITY] ALERT: FTP service running on production web proxy — must be disabled",
            "[SECURITY] INFO: nginx must stay running for HTTPS termination",
            "[SECURITY] INFO: sshd must stay running for remote management access",
        ],
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
