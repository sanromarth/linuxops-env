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

Linux operations remediation environment for training AI agents on security-sensitive config tasks.

## Tasks

3 tasks (easy/medium/hard) where agents fix broken file permissions, ownership, and services.

## Quick Start

```bash
pip install -r requirements.txt
python3 baseline_agent.py
uvicorn server:app --host 0.0.0.0 --port 7860
```

## API

- GET /tasks
- POST /reset
- POST /step
- GET /state
- GET /grader
- POST /baseline

## License

MIT
