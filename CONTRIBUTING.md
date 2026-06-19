# Contributing

This is a public repository for a **personal** knowledge system. Privacy mistakes are irreversible once pushed.

## Before you start

1. Read [AGENTS.md](./AGENTS.md) in full — especially §3 (Security & Privacy) and §4 (Pre-Commit Checklist).
2. Use only the `demo/` synthetic corpus in tests, screenshots, examples, and PR descriptions.
3. Respect PRD phase gates in [personal-agentic-second-brain-prd-v2.md](./personal-agentic-second-brain-prd-v2.md) — do not skip ahead to LangGraph, cloud defaults, or UI polish.

## Making changes

1. Run the pre-commit checklist in AGENTS.md §4 before every commit.
2. Install optional hooks: `pip install pre-commit && pre-commit install`
3. Open an issue before large architectural changes or new dependencies.
4. PRs must not include personal notes, real golden queries, `.env` files, vector indexes, or home-directory paths.

## Pull requests

- Target branch: `master`
- Keep PRs focused; one logical change per PR when possible
- Maintainers will reject PRs that add binary DB/index files or credential-like content

## Questions

Open a [GitHub issue](https://github.com/mmruesch12/second-brain/issues).