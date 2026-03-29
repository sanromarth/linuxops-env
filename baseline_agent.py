#!/usr/bin/env python3
"""
baseline agent for linuxops-env.

oracle mode: hardcoded correct answers, proves tasks are solvable.
api mode: uses LLM to solve tasks (needs API_BASE_URL + HF_TOKEN).

usage:
    python baseline_agent.py              # oracle, all tasks
    python baseline_agent.py --api        # llm mode
    python baseline_agent.py --task security_audit
"""

import argparse
import json
import os
import sys
from typing import Any

from environment.linux_env import LinuxOpsEnvironment
from environment.grader import grade_environment
from environment.tasks import TASKS


# hardcoded correct solutions for each task
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


def run_oracle_single(task_id, env=None):
    if env is None:
        env = LinuxOpsEnvironment()

    obs = env.reset(task_id)
    cfg = env.task_config

    print(f"  [{cfg['difficulty'].upper()}] {task_id}")
    print(f"  Ticket: {cfg['ticket'][:80]}...")

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
    print(f"  Grade: {result.score} [{tag}] ({result.steps_used}/{result.max_steps} steps)")
    print()

    return {
        "task_id": task_id,
        "score": result.score,
        "passed": result.passed,
        "steps_used": result.steps_used,
        "max_steps": result.max_steps,
    }


def run_oracle_all_tasks():
    results = []
    env = LinuxOpsEnvironment()
    for task_id in TASKS:
        r = run_oracle_single(task_id, env)
        results.append(r)

    avg = sum(r["score"] for r in results) / len(results)
    all_passed = all(r["passed"] for r in results)
    return {
        "mode": "oracle",
        "tasks": results,
        "average_score": round(avg, 3),
        "all_passed": all_passed,
    }


# llm-based baseline
LLM_PROMPT = """\
You are a Linux sysadmin agent fixing a broken system.

Available commands (respond with JSON only, no markdown):
- chmod: {"command":"chmod","args":{"path":"/etc/shadow","mode":"640"}}
- chown: {"command":"chown","args":{"path":"/etc/shadow","owner":"root"}}
- ls: {"command":"ls","args":{"path":"/etc/shadow"}}
- stat: {"command":"stat","args":{"path":"/etc/shadow"}}
- disable_service: {"command":"disable_service","args":{"name":"telnet"}}

Rules: never chmod 777, never disable sshd, fix critical stuff first.
Read log entries for clues. Respond with ONLY a JSON object."""


def run_llm_single(task_id, model=None):
    try:
        from openai import OpenAI
    except ImportError:
        print("  openai not installed, using oracle instead")
        return run_oracle_single(task_id)

    api_base = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
    api_key = os.environ.get("HF_TOKEN") or os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY")
    model_name = model or os.environ.get("MODEL_NAME", "gpt-4o-mini")

    if not api_key:
        print("  no api key found, using oracle")
        return run_oracle_single(task_id)

    client = OpenAI(base_url=api_base, api_key=api_key)
    env = LinuxOpsEnvironment()
    obs = env.reset(task_id)
    cfg = env.task_config

    print(f"  [{cfg['difficulty'].upper()}] {task_id} (model: {model_name})")

    messages = [
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": (
            f"Task: {cfg['ticket']}\n\n"
            f"State:\n{json.dumps(obs['observation'], indent=2)}\n\n"
            f"Actions: {cfg['available_actions']}\n"
            f"Steps left: {cfg['max_steps']}\n"
            "First action?"
        )},
    ]

    for _ in range(cfg["max_steps"]):
        try:
            resp = client.chat.completions.create(
                model=model_name, messages=messages,
                temperature=0.0, max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()

            # strip markdown wrapping if present
            cleaned = raw
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            action = json.loads(cleaned)
            obs_dict, reward, done, info = env.step(action)

            cmd = action.get("command", "?")
            args_str = " ".join(f"{k}={v}" for k, v in action.get("args", {}).items())
            ok = "ok" if info["result"]["success"] else "FAIL"
            print(f"    {ok}: {cmd} {args_str}  (reward={reward:.3f})")

            if done:
                break

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": (
                f"Result: {json.dumps(info['result'])}\n"
                f"State:\n{json.dumps(obs_dict, indent=2)}\n"
                f"Steps left: {obs_dict.get('steps_remaining', '?')}\nNext?"
            )})
        except (json.JSONDecodeError, KeyError) as e:
            print(f"    parse error: {e}")
            break
        except Exception as e:
            print(f"    api error: {e}")
            break

    result = grade_environment(env)
    tag = "PASSED" if result.passed else "FAILED"
    print(f"  Grade: {result.score} [{tag}]")
    print()
    return {"task_id": task_id, "score": result.score, "passed": result.passed,
            "steps_used": result.steps_used}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinuxOps-Env baseline")
    parser.add_argument("--api", action="store_true", help="use LLM api")
    parser.add_argument("--model", default=None, help="model name")
    parser.add_argument("--task", default=None, help="run single task")
    args = parser.parse_args()

    print("LinuxOps-Env Baseline Agent")
    print("=" * 40)
    print()

    task_ids = [args.task] if args.task else list(TASKS.keys())

    results = []
    for tid in task_ids:
        if args.api:
            r = run_llm_single(tid, model=args.model)
        else:
            r = run_oracle_single(tid)
        results.append(r)

    print("=" * 40)
    print("Summary:")
    for r in results:
        s = "PASS" if r.get("passed") else "FAIL"
        print(f"  {r['task_id']}: {r['score']:.3f} [{s}]")
    avg = sum(r["score"] for r in results) / len(results)
    print(f"  Average: {avg:.3f}")
    print("=" * 40)

    sys.exit(0 if all(r.get("passed") for r in results) else 1)
