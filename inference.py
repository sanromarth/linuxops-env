#!/usr/bin/env python3
"""
inference script for linuxops-env

runs an LLM agent against all tasks and produces scores.
uses API_BASE_URL, MODEL_NAME, HF_TOKEN from env.
falls back to oracle mode if no api key is set.
"""

import os
import json
import sys

from openai import OpenAI

from environment.linux_env import LinuxOpsEnvironment
from environment.grader import grade_environment
from environment.tasks import TASKS


# read env vars (required by hackathon spec)
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

MAX_TOKENS = 200
TEMPERATURE = 0.0


SYSTEM_PROMPT = """\
You are a Linux sysadmin agent. Your job is to fix a broken Linux system.

You get the current system state with files (permissions, owners, status)
and optionally services. You also get log entries showing what went wrong.

Fix all critical and insecure items using available commands.

Available commands (respond with JSON only, no markdown):
- chmod: {"command":"chmod","args":{"path":"/etc/shadow","mode":"640"}}
- chown: {"command":"chown","args":{"path":"/etc/shadow","owner":"root"}}
- ls: {"command":"ls","args":{"path":"/etc/shadow"}}
- stat: {"command":"stat","args":{"path":"/etc/shadow"}}
- disable_service: {"command":"disable_service","args":{"name":"telnet"}}

Rules:
- Never chmod 777 (penalized)
- Never disable sshd (penalized heavily)
- Some tasks have other trap services too, read the logs
- Fix critical stuff first
- Files with status "ok" dont need fixing
- Respond with ONLY a JSON object"""


def run_inference(task_id, client, env):
    """run llm on one task"""
    obs = env.reset(task_id)
    cfg = env.task_config

    print(f"\n  [{cfg['difficulty'].upper()}] {task_id}")
    print(f"  Desc: {cfg['description']}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Incident ticket: {cfg['ticket']}\n\n"
            f"System state:\n{json.dumps(obs['observation'], indent=2)}\n\n"
            f"Available actions: {cfg['available_actions']}\n"
            f"Steps remaining: {cfg['max_steps']}\n"
            "Analyze and give your first repair action."
        )},
    ]

    for step_num in range(cfg["max_steps"]):
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            raw = resp.choices[0].message.content.strip()

            # some models wrap json in markdown blocks, handle that
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
            print(f"    Step {step_num + 1}: {ok}: {cmd} {args_str}  (reward={reward:.3f})")

            if done:
                break

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": (
                f"Result: {json.dumps(info['result'])}\n"
                f"Updated state:\n{json.dumps(obs_dict, indent=2)}\n"
                f"Steps remaining: {obs_dict.get('steps_remaining', '?')}\n"
                "Next action?"
            )})

        except json.JSONDecodeError as e:
            print(f"    Step {step_num + 1}: parse error: {e}")
            print(f"    Raw: {raw[:100]}")
            break
        except Exception as e:
            print(f"    Step {step_num + 1}: error: {e}")
            break

    result = grade_environment(env)
    tag = "PASSED" if result.passed else "FAILED"
    print(f"  Grade: {result.score:.3f} [{tag}] ({result.steps_used}/{result.max_steps} steps)")

    return {
        "task_id": task_id,
        "score": result.score,
        "passed": result.passed,
        "steps_used": result.steps_used,
        "max_steps": result.max_steps,
    }


def run_oracle(task_id, env):
    """fallback when no api key - uses hardcoded correct answers"""
    from baseline_agent import ORACLE_SOLUTIONS

    obs = env.reset(task_id)
    cfg = env.task_config
    print(f"\n  [{cfg['difficulty'].upper()}] {task_id} (oracle fallback)")

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
    print(f"  Grade: {result.score:.3f} [{tag}] ({result.steps_used}/{result.max_steps} steps)")

    return {
        "task_id": task_id,
        "score": result.score,
        "passed": result.passed,
        "steps_used": result.steps_used,
        "max_steps": result.max_steps,
    }


def main():
    print("=" * 50)
    print("  LinuxOps-Env  |  Inference Script")
    print("=" * 50)
    print(f"  API_BASE_URL : {API_BASE_URL}")
    print(f"  MODEL_NAME   : {MODEL_NAME}")
    print(f"  HF_TOKEN     : {'[set]' if API_KEY else '[NOT SET]'}")
    print()

    env = LinuxOpsEnvironment()
    results = []

    if API_KEY and API_BASE_URL:
        print("  Mode: LLM inference")
        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
        for task_id in TASKS:
            r = run_inference(task_id, client, env)
            results.append(r)
    else:
        print("  Mode: Oracle (no api key)")
        print("  Set API_BASE_URL + MODEL_NAME + HF_TOKEN for LLM mode")
        for task_id in TASKS:
            r = run_oracle(task_id, env)
            results.append(r)

    # print summary
    print()
    print("=" * 50)
    print("  RESULTS")
    print("=" * 50)
    for r in results:
        tag = "PASS" if r["passed"] else "FAIL"
        print(f"  {r['task_id']:30s} {r['score']:.3f} [{tag}]")

    avg = sum(r["score"] for r in results) / len(results) if results else 0
    all_pass = all(r["passed"] for r in results)
    print(f"  {'Average':30s} {avg:.3f} [{'ALL PASS' if all_pass else 'SOME FAILED'}]")
    print("=" * 50)

    # json output for automated grading
    output = {
        "mode": "llm" if (API_KEY and API_BASE_URL) else "oracle",
        "model": MODEL_NAME if (API_KEY and API_BASE_URL) else "oracle",
        "tasks": results,
        "average_score": round(avg, 3),
        "all_passed": all_pass,
    }
    print("\n--- JSON OUTPUT ---")
    print(json.dumps(output, indent=2))

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
