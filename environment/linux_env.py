"""
Core environment for LinuxOps-Env.

simulates a broken linux system where an agent fixes
permissions, ownership, and services to pass compliance.
"""

from __future__ import annotations

import uuid
from typing import Any, Tuple

from .models import FileInfo, Observation, ServiceInfo
from .tasks import get_task


class VirtualFileSystem:
    """fake filesystem that tracks permissions, owners, services."""

    def __init__(self, files: dict, services: dict | None = None):
        self.files = {p: dict(info) for p, info in files.items()}
        self.services = dict(services) if services else {}

    def chmod(self, path: str, mode: str) -> dict:
        if path not in self.files:
            return {"success": False, "error": f"File not found: {path}"}
        if not mode.isdigit() or len(mode) not in (3, 4):
            return {"success": False, "error": f"Invalid mode: {mode}"}
        if any(c not in "01234567" for c in mode):
            return {"success": False, "error": f"Invalid mode: {mode}"}
        old = self.files[path]["permissions"]
        self.files[path]["permissions"] = mode
        return {"success": True, "command": f"chmod {mode} {path}",
                "old": old, "new": mode, "path": path}

    def chown(self, path: str, owner: str) -> dict:
        if path not in self.files:
            return {"success": False, "error": f"File not found: {path}"}
        if not owner or not owner.replace("_", "").replace("-", "").isalnum():
            return {"success": False, "error": f"Invalid owner: {owner}"}
        old = self.files[path]["owner"]
        self.files[path]["owner"] = owner
        return {"success": True, "command": f"chown {owner} {path}",
                "old": old, "new": owner, "path": path}

    def ls(self, path: str) -> dict:
        if path not in self.files:
            return {"success": False, "error": f"File not found: {path}"}
        f = self.files[path]
        return {"success": True, "command": f"ls -l {path}",
                "path": path, "permissions": f["permissions"], "owner": f["owner"]}

    def stat(self, path: str) -> dict:
        if path not in self.files:
            return {"success": False, "error": f"File not found: {path}"}
        f = self.files[path]
        return {"success": True, "command": f"stat {path}",
                "path": path, "permissions": f["permissions"],
                "owner": f["owner"], "type": "regular file"}

    def disable_service(self, name: str) -> dict:
        if name not in self.services:
            return {"success": False, "error": f"Unknown service: {name}"}
        old = self.services[name]
        self.services[name] = "disabled"
        return {"success": True, "command": f"systemctl disable {name}",
                "old": old, "new": "disabled", "service": name}

    def get_file_state(self) -> dict:
        return {p: dict(info) for p, info in self.files.items()}

    def get_service_state(self) -> dict:
        return dict(self.services)


class LinuxOpsEnvironment:
    """main env class. implements reset/step/state for the openenv spec."""

    def __init__(self):
        self.fs: VirtualFileSystem | None = None
        self.task_config: dict[str, Any] = {}
        self.current_task: str | None = None
        self.episode_id: str | None = None
        self.episode_steps = 0
        self.max_steps = 10
        self.done = False
        self.history: list[dict] = []
        self.cumulative_penalty = 0.0

    def reset(self, task_id: str = "security_audit") -> dict:
        cfg = get_task(task_id)
        self.task_config = cfg
        self.current_task = task_id
        self.episode_id = str(uuid.uuid4())
        self.episode_steps = 0
        self.max_steps = cfg["max_steps"]
        self.done = False
        self.history = []
        self.cumulative_penalty = 0.0

        self.fs = VirtualFileSystem(
            files=cfg["initial_files"],
            services=cfg.get("initial_services"),
        )

        return {
            "task_id": task_id,
            "episode_id": self.episode_id,
            "description": cfg["description"],
            "ticket": cfg["ticket"],
            "observation": self._build_obs().model_dump(),
            "available_actions": cfg["available_actions"],
            "max_steps": self.max_steps,
        }

    def step(self, action: dict) -> Tuple[dict, float, bool, dict]:
        if self.done:
            obs = self._build_obs()
            return obs.model_dump(), 0.0, True, {"error": "episode already done"}

        self.episode_steps += 1
        command = action.get("command", "")
        args = action.get("args", {})

        result = self._dispatch(command, args)
        penalty = self._check_penalties(command, args, result)
        self.cumulative_penalty += penalty

        from .reward import compute_reward
        reward = compute_reward(
            fs=self.fs,
            expected=self.task_config["expected_state"],
            action_succeeded=result.get("success", False),
            is_readonly=(command in ("ls", "stat")),
            penalty=penalty,
            step_number=self.episode_steps,
        )

        self.done = self._is_complete()
        if self.episode_steps >= self.max_steps and not self.done:
            self.done = True

        self.history.append({
            "step": self.episode_steps,
            "action": action,
            "result": result,
            "reward": reward,
            "penalty": penalty,
            "done": self.done,
        })

        obs = self._build_obs()
        return (obs.model_dump(), reward, self.done,
                {"result": result, "step": self.episode_steps})

    def state(self) -> dict:
        return {
            "task_id": self.current_task,
            "episode_id": self.episode_id,
            "step_count": self.episode_steps,
            "max_steps": self.max_steps,
            "done": self.done,
            "observation": self._build_obs().model_dump() if self.fs else None,
        }

    def grade(self) -> float:
        if not self.fs:
            return 0.0
        expected = self.task_config.get("expected_state", {})
        passed = 0
        total = 0

        for path, expect in expected.get("files", {}).items():
            actual = self.fs.files.get(path, {})
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
            if self.fs.services.get(svc) == exp_state:
                passed += 1

        if total == 0:
            return 1.0
        raw = passed / total
        return round(max(0.0, raw + self.cumulative_penalty), 3)

    # --- internal stuff ---

    def _dispatch(self, command: str, args: dict) -> dict:
        allowed = self.task_config.get("available_actions", [])
        if command not in allowed:
            return {"success": False,
                    "error": f"'{command}' not available. allowed: {allowed}"}

        if command == "chmod":
            return self.fs.chmod(args.get("path", ""), args.get("mode", ""))
        elif command == "chown":
            return self.fs.chown(args.get("path", ""), args.get("owner", ""))
        elif command == "ls":
            return self.fs.ls(args.get("path", ""))
        elif command == "stat":
            return self.fs.stat(args.get("path", ""))
        elif command == "disable_service":
            return self.fs.disable_service(args.get("name", ""))
        return {"success": False, "error": f"unknown command: {command}"}

    def _check_penalties(self, command: str, args: dict, result: dict) -> float:
        penalties = self.task_config.get("penalties", {})
        if not penalties or not result.get("success"):
            return 0.0

        total = 0.0
        # chmod 777 is always bad
        if command == "chmod" and args.get("mode") == "777":
            total += penalties.get("chmod_777", 0.0)
        # disabling certain services can be penalized per-task
        if command == "disable_service":
            svc = args.get("name", "")
            total += penalties.get(f"disable_{svc}", 0.0)
        return total

    def _is_complete(self) -> bool:
        expected = self.task_config.get("expected_state", {})

        for path, expect in expected.get("files", {}).items():
            actual = self.fs.files.get(path, {})
            if "permissions" in expect and actual.get("permissions") != expect["permissions"]:
                return False
            if "owner" in expect and actual.get("owner") != expect["owner"]:
                return False

        for svc, exp_state in expected.get("services", {}).items():
            if self.fs.services.get(svc) != exp_state:
                return False

        return True

    def _build_obs(self) -> Observation:
        cfg = self.task_config
        expected_files = cfg.get("expected_state", {}).get("files", {})

        file_infos = []
        for path, info in self.fs.files.items():
            # figure out status based on whether this file needs fixing
            if path in expected_files:
                exp = expected_files[path]
                perm_ok = exp.get("permissions", info["permissions"]) == info["permissions"]
                owner_ok = exp.get("owner", info["owner"]) == info["owner"]
                if perm_ok and owner_ok:
                    status = "ok"
                elif info["permissions"] in ("777", "666"):
                    status = "critical"
                else:
                    status = "insecure"
            else:
                status = "ok"  # decoy file, leave it alone

            file_infos.append(FileInfo(
                path=path, permissions=info["permissions"],
                owner=info["owner"], status=status,
            ))

        svc_infos = [
            ServiceInfo(name=n, state=s)
            for n, s in self.fs.services.items()
        ]

        return Observation(
            host=cfg.get("host", "unknown"),
            incident=cfg.get("incident", ""),
            task_id=self.current_task or "",
            description=cfg.get("description", ""),
            files=file_infos,
            services=svc_infos,
            logs=cfg.get("log_context", []),
            steps_remaining=self.max_steps - self.episode_steps,
            step_count=self.episode_steps,
            done=self.done,
            message=cfg.get("ticket", "Fix the system."),
        )