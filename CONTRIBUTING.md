# Contributing to NutriMentor

Thanks for helping improve NutriMentor. This project is an AI-assisted nutrition
education tool, so changes should be careful about evidence quality, privacy, and
clear user expectations.

## Development Setup

```bash
git clone https://github.com/GOOD-123-CPU/nutrimentor.git
cd nutrimentor
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

Do not commit your real `.env` file, API keys, vector stores, downloaded models,
or private datasets.

## Quality Checks

Run these before opening a pull request:

```bash
python -m ruff check src tests
python -m pytest tests -q
```

The unit tests are designed to run offline without downloading models or calling
LLM APIs.

## Pull Requests

- Keep changes focused and explain the user-facing behavior they affect.
- Add or update tests when changing retrieval, prompts, API routes, or session
  behavior.
- Use sample or synthetic data only.
- Document any new environment variables in `.env.example` and `README.md`.
- Avoid claims that the system provides medical advice.

## Security and Safety

Report vulnerabilities through the process in `SECURITY.md`. Public issues are
fine for bugs and feature requests, but not for credentials, data exposure, or
security-sensitive reports.
