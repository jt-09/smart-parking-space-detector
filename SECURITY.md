# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.x / 1.x | Security fixes while the repository is actively maintained |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Email the repository owner through the contact listed on the GitHub profile for `jt-09`, or use GitHub's private vulnerability reporting if enabled for this repository.

Include:

- a description of the issue;
- steps to reproduce;
- impact assessment;
- any suggested remediation.

You should receive an acknowledgement when practical. Fixes are prioritized by severity and whether a public exploit exists.

## Application secrets

This application does not require cloud API keys for the default synthetic demo. If you configure RTSP sources:

- keep credentials in local `.env` (gitignored);
- never commit passwords, tokens, or private footage;
- confirm logs redact credentials (frame-source helpers strip userinfo from URIs).

Sample env keys live in `.env.example` with empty placeholders only.

## Secret scanning

Repository maintainers should enable GitHub **secret scanning** and **push protection** when the hosting plan supports them (Settings → Code security and analysis). Contributors must never bypass push protection to force-commit credentials.

If a secret is leaked:

1. rotate the credential immediately;
2. purge it from git history if it was committed;
3. notify the owner via the private reporting channel above.

## Supply chain

- Prefer locked dependencies via `uv.lock` (`uv sync --locked`).
- Dependabot opens weekly PRs for `uv` and GitHub Actions ecosystems (`.github/dependabot.yml`).
- CodeQL scans Python on `main` pushes/PRs and on a weekly schedule (`.github/workflows/codeql.yml`).
- Pin third-party Actions to stable major tags (or commit SHAs for sensitive workflows).
- Do not commit model weights, untrusted binaries, generated videos, or SQLite databases.
- Review agent skills and automation sources before granting repository write access.
