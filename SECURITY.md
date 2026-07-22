# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.x / 1.x | Security fixes while the project is actively maintained |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Email the repository owner through the contact listed on the GitHub profile for `jt-09`, or use GitHub's private vulnerability reporting if enabled for this repository.

Include:

- a description of the issue;
- steps to reproduce;
- impact assessment;
- any suggested remediation.

## Application secrets

This application does not require cloud API keys for the default synthetic demo. If you configure RTSP sources:

- keep credentials in local `.env` (gitignored);
- never commit passwords or tokens;
- confirm logs redact credentials.

## Supply chain

- Prefer locked dependencies via `uv.lock`.
- Review Dependabot and Actions updates carefully.
- Do not commit model weights or untrusted binaries.
