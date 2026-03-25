"""
Reward function for LinuxOps-Env.

scores based on how many checks pass (perms, ownership, services)
with penalties for dumb moves and a small step cost.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .linux_env import VirtualFileSystem


def compute_reward(
    fs: "VirtualFileSystem",
    expected: dict,
    action_succeeded: bool,
    is_readonly: bool = False,
    penalty: float = 0.0,
    step_number: int = 1,
) -> float:
    if not action_succeeded:
        return -0.1

    # ls/stat are cheap, just a tiny cost
    if is_readonly:
        return -0.01

    # count passing checks
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

    if total == 0:
        return 0.0

    progress = passed / total
    step_cost = -0.01

    return round(progress + step_cost + penalty, 3)
