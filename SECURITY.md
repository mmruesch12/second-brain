# Security Policy

## Reporting a vulnerability

If you discover a security issue in this project (egress bypass, DataZone leak, secret scanner failure, credential exposure in logs), please report it responsibly.

**Do not** include real personal note content, API keys, or reproduction corpora in your report.

### How to report

1. Open a [GitHub Security Advisory](https://github.com/mmruesch12/second-brain/security/advisories/new) (preferred), or
2. Open a private GitHub issue and ask the maintainer to mark it sensitive.

Include:

- Description of the issue and affected component
- Steps to reproduce using **synthetic `demo/` data only**
- Impact assessment (what data could leak, under what conditions)

## Scope

In scope:

- Unintended cloud egress when air-gap is expected
- Cross-zone retrieval (`PERSONAL` / `WORK_ADJACENT` / `PUBLIC_DEMO`)
- Secret scanner bypasses
- Sensitive data written to logs, traces, or git-tracked files

Out of scope:

- Vulnerabilities in third-party models (Ollama, LiteLLM providers)
- Compromise of the user's local machine outside this application

## Response

The maintainer will acknowledge reports within a reasonable timeframe and coordinate fixes on the `master` branch.