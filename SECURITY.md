# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a vulnerability

Please do **NOT** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting
(Security tab → Report a vulnerability) or contact the maintainers directly.
We aim to respond within 72 hours.

## Security expectations for contributors

- Never commit API keys, tokens, or credentials. All secrets belong in a
  local `.env` file (git-ignored).
- Dependencies are pinned to ranges in `pyproject.toml`; run
  `pip install -e ".[dev]"` from a fresh virtualenv and review transitive changes.
- The web server binds to `127.0.0.1` by default. If you expose it publicly,
  put it behind a reverse proxy with TLS and add authentication — the app
  ships **without** built-in auth by design.
