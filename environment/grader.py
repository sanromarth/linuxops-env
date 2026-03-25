"""
Grader for LinuxOps-Env.

returns per-file and per-service grade breakdown.
used by /grader endpoint and by baseline script.
"""

from .linux_env import LinuxOpsEnvironment
from .models import FileGradeDetail, GradeResult, ServiceGradeDetail


def grade_environment(env: LinuxOpsEnvironment) -> GradeResult:
    score = env.grade()
    expected = env.task_config.get("expected_state", {})

    file_details = []
    for path, expect in expected.get("files", {}).items():
        actual = env.fs.files.get(path, {}) if env.fs else {}
        exp_perm = expect.get("permissions", "")
        act_perm = actual.get("permissions", "???")
        exp_owner = expect.get("owner")
        act_owner = actual.get("owner", "???")
        file_details.append(FileGradeDetail(
            path=path,
            expected_perm=exp_perm, actual_perm=act_perm,
            perm_correct=(act_perm == exp_perm) if exp_perm else True,
            expected_owner=exp_owner, actual_owner=act_owner,
            owner_correct=(act_owner == exp_owner) if exp_owner else True,
        ))

    svc_details = []
    for svc, exp_state in expected.get("services", {}).items():
        act_state = env.fs.services.get(svc, "???") if env.fs else "???"
        svc_details.append(ServiceGradeDetail(
            name=svc, expected_state=exp_state,
            actual_state=act_state, correct=(act_state == exp_state),
        ))

    return GradeResult(
        task_id=env.current_task or "",
        score=score, passed=(score >= 1.0),
        steps_used=env.episode_steps, max_steps=env.max_steps,
        file_details=file_details, service_details=svc_details,
    )
