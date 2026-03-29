"""
tests for linuxops-env.

covers: reset, oracle, penalties, no-ops, traps, invalid input.
"""

import pytest
from environment.linux_env import LinuxOpsEnvironment
from environment.grader import grade_environment
from environment.tasks import TASKS


# --- setup ---

@pytest.fixture
def env():
    return LinuxOpsEnvironment()


# --- test reset works for all tasks ---

@pytest.mark.parametrize("task_id", list(TASKS.keys()))
def test_reset_all_tasks(env, task_id):
    result = env.reset(task_id)
    assert result["task_id"] == task_id
    assert "episode_id" in result
    assert "observation" in result
    assert result["observation"]["task_id"] == task_id
    assert env.done is False
    assert env.episode_steps == 0


# --- test oracle solves all tasks ---

ORACLE_SOLUTIONS = {
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
    "log_audit": [
        {"command": "chmod", "args": {"path": "/var/log/syslog", "mode": "640"}},
        {"command": "chown", "args": {"path": "/var/log/syslog", "owner": "syslog"}},
        {"command": "chmod", "args": {"path": "/var/log/auth.log", "mode": "640"}},
        {"command": "chown", "args": {"path": "/var/log/auth.log", "owner": "syslog"}},
        {"command": "chmod", "args": {"path": "/etc/rsyslog.conf", "mode": "644"}},
        {"command": "chown", "args": {"path": "/etc/rsyslog.conf", "owner": "root"}},
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
    "certificate_exposure": [
        {"command": "chmod",           "args": {"path": "/etc/ssl/private/server.key",  "mode": "600"}},
        {"command": "chown",           "args": {"path": "/etc/ssl/private/server.key",  "owner": "root"}},
        {"command": "chmod",           "args": {"path": "/etc/ssl/certs/ca-bundle.crt", "mode": "644"}},
        {"command": "chown",           "args": {"path": "/etc/ssl/certs/ca-bundle.crt", "owner": "root"}},
        {"command": "chmod",           "args": {"path": "/etc/nginx/nginx.conf",        "mode": "644"}},
        {"command": "chown",           "args": {"path": "/etc/nginx/nginx.conf",        "owner": "root"}},
        {"command": "chmod",           "args": {"path": "/var/log/nginx/error.log",     "mode": "640"}},
        {"command": "chown",           "args": {"path": "/var/log/nginx/error.log",     "owner": "www-data"}},
        {"command": "disable_service", "args": {"name": "ftp"}},
    ],
}


@pytest.mark.parametrize("task_id", list(TASKS.keys()))
def test_oracle_solves_all_tasks(env, task_id):
    env.reset(task_id)
    for action in ORACLE_SOLUTIONS[task_id]:
        obs, reward, done, info = env.step(action)
        assert info["result"]["success"], f"failed: {action} -> {info['result']}"

    grade = grade_environment(env)
    assert grade.score == 1.0, f"{task_id}: expected 1.0, got {grade.score}"
    assert grade.passed is True


# --- test penalties trigger ---

def test_chmod_777_penalty(env):
    env.reset("incident_response")
    obs, reward, done, info = env.step(
        {"command": "chmod", "args": {"path": "/etc/shadow", "mode": "777"}}
    )
    # chmod 777 should give negative reward (penalty = -0.3)
    assert reward < 0, f"chmod 777 should have negative reward, got {reward}"


def test_disable_sshd_penalty(env):
    env.reset("incident_response")
    obs, reward, done, info = env.step(
        {"command": "disable_service", "args": {"name": "sshd"}}
    )
    # disabling sshd should give negative reward (penalty = -0.5)
    assert reward < 0, f"disable sshd should have negative reward, got {reward}"


# --- test no-op actions don't reward ---

def test_noop_gives_no_positive_reward(env):
    env.reset("provisioning_repair")
    # first: do a real fix
    env.step({"command": "chmod", "args": {"path": "/etc/ssh/sshd_config", "mode": "600"}})
    # repeat the same fix — should NOT get positive reward
    obs, reward, done, info = env.step(
        {"command": "chmod", "args": {"path": "/etc/ssh/sshd_config", "mode": "600"}}
    )
    assert reward <= 0, f"repeating same chmod should not reward, got {reward}"


def test_repeated_noop_stays_negative(env):
    env.reset("security_audit")
    # fix one file
    env.step({"command": "chmod", "args": {"path": "/etc/shadow", "mode": "640"}})
    # repeat it 3 times
    for _ in range(3):
        obs, reward, done, info = env.step(
            {"command": "chmod", "args": {"path": "/etc/shadow", "mode": "640"}}
        )
        assert reward <= 0, f"noop should not give positive reward, got {reward}"


# --- test trap services block perfect score ---

def test_disabling_sshd_blocks_perfect_score(env):
    """disabling sshd should prevent score 1.0 even if everything else is correct."""
    env.reset("incident_response")
    # disable sshd first (trap)
    env.step({"command": "disable_service", "args": {"name": "sshd"}})
    # then do all correct oracle steps
    for action in ORACLE_SOLUTIONS["incident_response"]:
        env.step(action)
    grade = grade_environment(env)
    assert grade.score < 1.0, f"disabling sshd should prevent perfect score, got {grade.score}"


def test_disabling_nginx_blocks_perfect_score(env):
    """disabling nginx should prevent score 1.0 in certificate_exposure."""
    env.reset("certificate_exposure")
    env.step({"command": "disable_service", "args": {"name": "nginx"}})
    for action in ORACLE_SOLUTIONS["certificate_exposure"]:
        env.step(action)
    grade = grade_environment(env)
    assert grade.score < 1.0, f"disabling nginx should prevent perfect score, got {grade.score}"


# --- test invalid input fails cleanly ---

def test_invalid_task_id(env):
    with pytest.raises(ValueError):
        env.reset("nonexistent_task")


def test_invalid_command(env):
    env.reset("security_audit")
    obs, reward, done, info = env.step(
        {"command": "rm", "args": {"path": "/etc/shadow"}}
    )
    assert info["result"]["success"] is False
    assert "not available" in info["result"]["error"]


def test_invalid_file_path(env):
    env.reset("security_audit")
    obs, reward, done, info = env.step(
        {"command": "chmod", "args": {"path": "/nonexistent", "mode": "644"}}
    )
    assert info["result"]["success"] is False


def test_invalid_chmod_mode(env):
    env.reset("security_audit")
    obs, reward, done, info = env.step(
        {"command": "chmod", "args": {"path": "/etc/shadow", "mode": "999"}}
    )
    assert info["result"]["success"] is False


# --- test episode lifecycle ---

def test_episode_done_after_max_steps(env):
    env.reset("security_audit")
    # burn through all 10 steps with ls
    for _ in range(10):
        env.step({"command": "ls", "args": {"path": "/etc/shadow"}})
    assert env.done is True


def test_step_after_done_returns_zero_reward(env):
    env.reset("security_audit")
    for _ in range(10):
        env.step({"command": "ls", "args": {"path": "/etc/shadow"}})
    obs, reward, done, info = env.step(
        {"command": "ls", "args": {"path": "/etc/shadow"}}
    )
    assert reward == 0.0
    assert done is True
