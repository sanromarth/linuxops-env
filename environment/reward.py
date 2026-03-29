"""
Reward function for LinuxOps-Env.

rewards based on delta progress (improvement from last step),
not absolute state. no-op actions get penalized slightly.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .linux_env import VirtualFileSystem


def compute_progress(fs: "VirtualFileSystem", expected: dict) -> float:
    """calculate what fraction of checks currently pass."""
    passed = 0
    total = 0

    for path, expect in expected.get("files", {}).items():
        actual = fs.files.get(path, {})
        if "permissions" in expect:
            total += 1
            if actual.get("permissions") == expect["permissions"]:
                passed += 1
        if "owner" in expect:
            total += 1
            if actual.get("owner") == expect["owner"]:
                passed += 1

    for svc, exp_state in expected.get("services", {}).items():
        total += 1
        if fs.services.get(svc) == exp_state:
            passed += 1

    return passed / total if total > 0 else 1.0


def compute_reward(
    fs: "VirtualFileSystem",
    expected: dict,
    action_succeeded: bool,
    is_readonly: bool = False,
    penalty: float = 0.0,
    step_number: int = 1,
    prev_progress: float = 0.0,
) -> float:
    if not action_succeeded:
        return -0.1

    # ls/stat are cheap, just a tiny cost
    if is_readonly:
        return -0.01

    current = compute_progress(fs, expected)
    delta = current - prev_progress
    step_cost = -0.01

    if delta <= 0:
        # action changed nothing useful — slight penalty
        return round(-0.02 + penalty, 3)

    return round(delta + step_cost + penalty, 3)
