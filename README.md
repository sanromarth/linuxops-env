---
title: LinuxOps-Env
emoji: 🐧
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# LinuxOps-Env 🐧🔧

A Linux operations environment for training and evaluating AI agents on realistic sysadmin tasks.

[![Live Demo](https://img.shields.io/badge/🤗_Live_Demo-HuggingFace-FFD21E)](https://huggingface.co/spaces/sanromarth/linuxops-env)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

5 tasks · 5 action types · log context · penalty traps · [OpenEnv](https://github.com/open-env) spec compliant

---

## Why This Matters

Modern infrastructure runs heavily on Linux. Cloud servers, CI/CD runners, containers, internal tools, and many production services depend on Linux systems being configured, monitored, and repaired correctly. In the real world, system administrators and DevOps engineers often work under uncertainty: they inspect logs, check service status, validate files, restart components, and diagnose misconfigurations step by step.

However, many existing AI evaluation tasks do not capture this style of work well. They are often static, purely text-based, or too small to represent operational reasoning. LinuxOps-Env was created to address that gap.

**LinuxOps-Env turns real operational workflows into a training environment for AI agents.** Instead of toy puzzles, agents face the exact same decisions a junior sysadmin faces:

- "This file has 777 permissions — what should it actually be?"
- "This config file is owned by `nobody` — who should own it?"
- "Telnet is running on a production server — should I disable it? What about SSH?"
- "The TLS private key is world-readable after a cert renewal — how do I secure it?"
- "I only have N steps before the maintenance window closes — what do I fix first?"

These are judgment calls, not just command recall. An agent that scores well here demonstrates genuine operational reasoning.

---

## Motivation

This project is motivated by three ideas:

1. **AI agents should be tested on operational reasoning, not just question answering.**
   A capable infrastructure agent should be able to inspect a system, choose safe actions, and make progress toward recovery or task completion.

2. **Linux administration is a strong real-world domain for agent evaluation.**
   Linux tasks are structured, measurable, reproducible, and important in real infrastructure work. They provide a practical testbed for environment-agent interaction.

3. **Beginner-to-real-world progression matters.**
   As someone deeply focused on Linux, RHCSA-style system administration, and junior DevOps learning, I wanted to build an environment that reflects how real Linux work feels: observe, verify, act, re-check, troubleshoot, and only then declare success.

LinuxOps-Env is therefore both a benchmark and a training ground: a way to evaluate how well an AI system can behave like a careful Linux operator rather than a text-only assistant.

---

## Environment Description

LinuxOps-Env provides a containerized Linux operations environment where an AI agent receives a task, observes the current system state, and executes actions through a constrained interface. The environment is designed to simulate practical command-line administration scenarios while keeping execution reproducible and safe.

Each episode contains:

- an initial Linux system state (broken files, wrong owners, insecure services)
- a task objective framed as a realistic incident ticket
- a set of allowed actions
- structured observations with file states, service states, and log entries
- a scoring mechanism based on correctness, completion, and efficiency

The design emphasizes:
- **Reproducibility** — deterministic resets, same broken state every time
- **Safety** — sandboxed virtual filesystem, no real system changes
- **Measurable outcomes** — graders produce 0.0–1.0 scores with per-file breakdown
- **Realistic interaction** — log context, trap files, penalty mechanics
- **Progressive difficulty** — easy → medium → hard with meaningful skill gaps

---

## Tasks

5 progressively harder scenarios, each framed as a real incident ticket:

| # | Task ID | Difficulty | Scenario | Max Steps |
|---|---------|------------|----------|-----------:|
| 1 | `security_audit` | 🟢 Easy | Overly permissive file modes on auth files | 10 |
| 2 | `provisioning_repair` | 🟡 Medium | Broken deployment script corrupted ownership + permissions | 8 |
| 3 | `log_audit` | 🟡 Medium | Rsyslog migration failure — log files and config corrupted | 10 |
| 4 | `incident_response` | 🔴 Hard | Compliance scan failed — wrong perms, wrong owners, insecure services, traps | 10 |
| 5 | `certificate_exposure` | 🔴 Hard | TLS private keys exposed after botched cert renewal + trap services | 12 |

<details>
<summary><b>Task Details (click to expand)</b></summary>

### Task 1 — Security Audit (Easy)
- 3 broken files + 1 decoy (looks fine, don't touch it)
- Actions: `chmod`, `ls`, `stat`
- Oracle solves in 3 steps
- Tests: basic permission knowledge

### Task 2 — Provisioning Repair (Medium)
- 3 files with wrong permissions AND wrong ownership + 1 decoy
- Actions: `chmod`, `chown`, `ls`, `stat`
- Oracle solves in 6 steps
- Tests: understanding that both perms and ownership matter

### Task 3 — Log Audit (Medium)
- 3 log/config files corrupted during migration + 1 unaffected file (decoy)
- Actions: `chmod`, `chown`, `ls`, `stat`
- Oracle solves in 6 steps
- Tests: log-guided diagnosis, knowing correct log file ownership (syslog user)

### Task 4 — Incident Response (Hard)
- 4 broken files + 2 services (1 is a trap — disabling `sshd` is penalized)
- Actions: `chmod`, `chown`, `disable_service`, `ls`, `stat`
- Penalty traps: `chmod 777` → -0.3, `disable sshd` → -0.5
- Oracle solves in 9 steps
- Tests: multi-domain reasoning, service awareness, avoiding traps

### Task 5 — Certificate Exposure (Hard)
- 4 broken files + 1 decoy + 3 services (2 are traps — disabling `nginx` or `sshd` is penalized)
- Actions: `chmod`, `chown`, `disable_service`, `ls`, `stat`
- Penalty traps: `chmod 777` → -0.3, `disable nginx` → -0.4, `disable sshd` → -0.5
- Oracle solves in 9 steps
- Tests: TLS security knowledge, web infrastructure awareness, multi-trap avoidance

</details>

### Expected Difficulty

The benchmark is intentionally designed with progressive difficulty:

- **Easy tasks** test command-line literacy and direct inspection.
- **Medium tasks** test diagnosis from logs and combined permission + ownership reasoning.
- **Hard tasks** test multi-step operational reasoning with penalty traps under partial information.

A weak agent may issue many irrelevant commands or fall into traps. A stronger agent should behave more like a junior Linux operator: inspect carefully, act intentionally, and confirm success.

---

## Action & Observation Space

### Actions

| Command | Args | Type |
|---------|------|------|
| `chmod` | `{"path": "...", "mode": "640"}` | Modify |
| `chown` | `{"path": "...", "owner": "root"}` | Modify |
| `ls` | `{"path": "..."}` | Read-only |
| `stat` | `{"path": "..."}` | Read-only |
| `disable_service` | `{"name": "telnet"}` | Modify |

### Observation (returned every step)

```json
{
  "host": "jumpbox-01",
  "incident": "security_audit_failed",
  "task_id": "security_audit",
  "description": "Fix broken file permissions on authentication-related files.",
  "files": [
    {"path": "/etc/shadow", "permissions": "777", "owner": "root", "status": "critical"}
  ],
  "services": [],
  "logs": [
    "[AUDIT] CRIT: /etc/shadow is world-readable (mode 777) — credential exposure risk",
    "[AUDIT] OK: /etc/passwd mode 644 — compliant, no action needed"
  ],
  "steps_remaining": 9,
  "step_count": 1,
  "done": false,
  "message": "Security audit found overly permissive file modes..."
}
```

The `logs` field gives the agent clues about what went wrong and what's safe to touch. Real Linux troubleshooting depends on reading logs, so we include them in every observation.

---

## Reward Design

| Signal | Value | Purpose |
|--------|-------|---------|
| Progress | `passed_checks / total_checks` | Guides toward full repair |
| Step cost | `-0.01` | Encourages efficiency |
| Failed action | `-0.1` | Penalizes invalid commands |
| Read-only (ls/stat) | `-0.01` | Cheap inspection |
| `chmod 777` | **-0.3** | Penalizes making things worse |
| `disable_service nginx` | **-0.4** | Penalizes breaking web service |
| `disable_service sshd` | **-0.5** | Penalizes locking yourself out |

Partial credit is supported — fixing 2 out of 3 files yields a proportional reward. This enables meaningful gradient signal for RL training.

---

## Quick Start

```bash
# install dependencies
pip install -r requirements.txt

# run oracle baseline (proves all 5 tasks are solvable)
python3 baseline_agent.py

# start the API server
uvicorn server:app --host 0.0.0.0 --port 7860

# run inference with LLM (uses hackathon env vars)
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=gpt-4o-mini
export HF_TOKEN=your-token-here
python3 inference.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check + project info |
| `GET` | `/tasks` | List all 5 tasks with metadata |
| `POST` | `/reset` | Reset environment to broken state |
| `POST` | `/step` | Execute an action |
| `GET` | `/state` | Current state (OpenEnv spec) |
| `GET` | `/grader` | Grading result with per-file breakdown |
| `POST` | `/baseline` | Run oracle baseline, return scores |
| `GET` | `/history` | Full episode action log |
| `GET` | `/docs` | Interactive Swagger UI |

<details>
<summary><b>Example: Solve via curl</b></summary>

```bash
# reset to medium task
curl -X POST http://localhost:7860/reset \
  -H 'Content-Type: application/json' \
  -d '{"task_id": "provisioning_repair"}'

# fix a file
curl -X POST http://localhost:7860/step \
  -H 'Content-Type: application/json' \
  -d '{"command": "chmod", "args": {"path": "/etc/ssh/sshd_config", "mode": "600"}}'

# check grade
curl http://localhost:7860/grader
```

</details>

---

## Baseline Results

Oracle baseline — hardcoded correct answers proving each task is solvable:

| Task | Score | Steps Used | Status |
|------|-------|------------|--------|
| `security_audit` | **1.000** | 3/10 | ✅ PASS |
| `provisioning_repair` | **1.000** | 6/8 | ✅ PASS |
| `log_audit` | **1.000** | 6/10 | ✅ PASS |
| `incident_response` | **1.000** | 9/10 | ✅ PASS |
| `certificate_exposure` | **1.000** | 9/12 | ✅ PASS |
| **Average** | **1.000** | — | ✅ |

Also supports **LLM inference mode** (`inference.py` or `baseline_agent.py --api`) where a model reads observations and logs, then decides actions autonomously.

---

## How It Works

1. Agent calls `POST /reset` → gets broken system state + incident ticket
2. Agent reads files, services, logs → decides what to fix first
3. Agent calls `POST /step` with a repair action → gets updated state + reward
4. Repeat until done or out of steps
5. `GET /grader` returns final score (0.0 to 1.0) with per-file breakdown

---

## Inference Script

The `inference.py` script is the main entry point for running an LLM agent against all tasks. It reads:

| Variable | Purpose |
|----------|---------|
| `API_BASE_URL` | The API endpoint for the LLM |
| `MODEL_NAME` | The model identifier for inference |
| `HF_TOKEN` | Your Hugging Face / API key |

It uses the **OpenAI Client** for all LLM calls and falls back to oracle mode when no API key is set.

```bash
# LLM mode
API_BASE_URL=https://router.huggingface.co/v1 \
MODEL_NAME=meta-llama/Llama-3-8B-Instruct \
HF_TOKEN=hf_... \
python3 inference.py

# Oracle mode (no API key needed)
python3 inference.py
```

---

## Safety

- Runs in Docker, no host access
- Virtual filesystem — no real files are touched
- Deterministic resets, same broken state every time
- Dangerous actions (chmod 777, disable sshd) are penalized
- No network calls or privileged operations

---

## Deploy

```bash
# build container
docker build -t linuxops-env .

# run locally
docker run -p 7860:7860 linuxops-env
```

Live deployment: [huggingface.co/spaces/sanromarth/linuxops-env](https://huggingface.co/spaces/sanromarth/linuxops-env)

---

## Project Structure

```
linuxops-env/
├── environment/
│   ├── __init__.py        # package exports
│   ├── models.py          # typed Pydantic models (OpenEnv spec)
│   ├── tasks.py           # 5-task registry with incident tickets + log context
│   ├── linux_env.py       # core environment engine
│   ├── grader.py          # grader with per-file breakdown
│   └── reward.py          # reward function with penalties
├── server.py              # FastAPI server (all endpoints)
├── inference.py           # hackathon inference script (API_BASE_URL + MODEL_NAME + HF_TOKEN)
├── baseline_agent.py      # oracle + LLM baseline agent
├── openenv.yaml           # OpenEnv manifest
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## License

MIT
